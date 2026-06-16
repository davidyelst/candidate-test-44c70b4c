from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser, User

from accounts.permissions import CompanyScopedMixin, IsCompanyAdmin, company_for
from contracts.models import Contract


# --- company_for ---


@pytest.mark.django_db
def test_company_for_returns_company_for_admin(admin_user, northstar):
    assert company_for(admin_user) == northstar


@pytest.mark.django_db
def test_company_for_returns_none_for_freelancer(freelancer_user):
    assert company_for(freelancer_user) is None


@pytest.mark.django_db
def test_company_for_returns_none_for_plain_user():
    user = User.objects.create_user(username='nobody@test.test', email='nobody@test.test', password='x')
    assert company_for(user) is None


# --- IsCompanyAdmin: the gate (runs first; covers reads and creates alike) ---


@pytest.mark.django_db
def test_gate_allows_admin(admin_user):
    assert IsCompanyAdmin().has_permission(SimpleNamespace(user=admin_user), view=None) is True


@pytest.mark.django_db
def test_gate_denies_freelancer(freelancer_user):
    assert IsCompanyAdmin().has_permission(SimpleNamespace(user=freelancer_user), view=None) is False


def test_gate_denies_anonymous():
    assert IsCompanyAdmin().has_permission(SimpleNamespace(user=AnonymousUser()), view=None) is False


# --- test doubles for the mixin: a fake serializer + a minimal view host ---


class _FakeSerializer:
    """Records what save() was called with; stands in for a DRF serializer."""

    def __init__(self):
        self.saved = None

    def save(self, **kwargs):
        self.saved = kwargs
        return kwargs


class _ScopedView(CompanyScopedMixin):
    queryset = Contract.objects.all()
    company_lookup = 'company'

    def __init__(self, user):
        self.request = SimpleNamespace(user=user)


# --- CompanyScopedMixin.get_queryset: scopes reads to the caller's company ---


@pytest.mark.django_db
def test_reads_scope_admin_to_own_company(admin_user, active_contract, other_contract):
    ids = set(_ScopedView(admin_user).get_queryset().values_list('id', flat=True))
    assert active_contract.id in ids       # own company (northstar)
    assert other_contract.id not in ids    # other company (meridian) — not visible, no existence leak


@pytest.mark.django_db
def test_reads_empty_for_company_less_user(freelancer_user, active_contract):
    # Defensive fallback: at a real endpoint IsCompanyAdmin returns 403 first.
    assert list(_ScopedView(freelancer_user).get_queryset()) == []


# --- CompanyScopedMixin.perform_create: stamps the company server-side ---


@pytest.mark.django_db
def test_create_stamps_company_for_admin(admin_user, northstar):
    serializer = _FakeSerializer()
    _ScopedView(admin_user).perform_create(serializer)
    assert serializer.saved == {'company': northstar}
