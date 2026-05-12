import datetime
from decimal import Decimal

import pytest

from accounts.models import Freelancer
from contracts.models import Contract
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_contract_list_requires_auth(api_client):
    resp = api_client.get('/api/contracts/')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_admin_sees_own_company_contracts(admin_client, active_contract, other_contract):
    resp = admin_client.get('/api/contracts/')
    assert resp.status_code == 200
    ids = [b['id'] for b in resp.data]
    assert active_contract.id in ids
    assert other_contract.id not in ids


@pytest.mark.django_db
def test_freelancer_sees_own_contracts(freelancer_client, active_contract, other_contract):
    resp = freelancer_client.get('/api/contracts/')
    assert resp.status_code == 200
    ids = [b['id'] for b in resp.data]
    assert active_contract.id in ids
    assert other_contract.id in ids  # freelancer has both contracts


@pytest.mark.django_db
def test_admin_contract_detail(admin_client, active_contract):
    resp = admin_client.get(f'/api/contracts/{active_contract.id}/')
    assert resp.status_code == 200
    assert resp.data['id'] == active_contract.id
    assert 'company' in resp.data
    assert 'freelancer' in resp.data


@pytest.mark.django_db
def test_admin_cannot_see_other_company_contract(admin_client, other_contract):
    resp = admin_client.get(f'/api/contracts/{other_contract.id}/')
    assert resp.status_code == 404


@pytest.mark.django_db
def test_freelancer_contract_detail(freelancer_client, active_contract):
    resp = freelancer_client.get(f'/api/contracts/{active_contract.id}/')
    assert resp.status_code == 200
    assert resp.data['id'] == active_contract.id


@pytest.mark.django_db
def test_contract_detail_requires_auth(api_client, active_contract):
    resp = api_client.get(f'/api/contracts/{active_contract.id}/')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_contract_response_shape(admin_client, active_contract):
    resp = admin_client.get(f'/api/contracts/{active_contract.id}/')
    assert resp.status_code == 200
    data = resp.data
    assert set(data.keys()) >= {'id', 'company', 'freelancer', 'daily_rate', 'start_date', 'end_date', 'status'}
    assert isinstance(data['company'], dict)
    assert {'id', 'name', 'billing_email'} <= set(data['company'].keys())
    assert isinstance(data['freelancer'], dict)
    assert {'id', 'name'} <= set(data['freelancer'].keys())


@pytest.mark.django_db
def test_freelancer_cannot_see_another_freelancers_contract(freelancer_client, northstar):
    other_user = User.objects.create_user(username='other@test.test', email='other@test.test', password='x')
    other_freelancer = Freelancer.objects.create(user=other_user, name='Other Person')
    unrelated = Contract.objects.create(
        company=northstar,
        freelancer=other_freelancer,
        daily_rate=Decimal('500.00'),
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        status='active',
    )
    resp = freelancer_client.get(f'/api/contracts/{unrelated.id}/')
    assert resp.status_code == 404
