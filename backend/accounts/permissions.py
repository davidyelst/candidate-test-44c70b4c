"""Multi-tenant access for company-only endpoints.

Two complementary pieces, the way DRF intends them:

* ``IsCompanyAdmin`` — the capability gate. As a permission class it runs at the
  very start of the view, before the body is touched, and it covers the verbs a
  queryset can't: it denies a non-company user (freelancer / nobody) a clean 403
  on *every* method, list and create included.
* ``CompanyScopedMixin`` — tenant scoping. ``get_queryset`` filters list and
  object lookups to the caller's company (another company's row 404s, no
  existence leak); ``perform_create`` stamps the owning company server-side so
  it can't be forged from the request body.

Authorization here is membership/tenancy-based, not RBAC — a user belongs to a
company only via ``CompanyAdmin`` (there is no role field).
"""

from rest_framework.permissions import BasePermission


def company_for(user):
    """Company this user belongs to, or None. (CompanyAdmin == company membership.)"""
    admin = getattr(user, 'company_admin', None)
    return admin.company if admin else None


class IsCompanyAdmin(BasePermission):
    """Gate company-only endpoints: the caller must belong to a company."""

    message = 'You must be a company user to do this.'

    def has_permission(self, request, view):
        return company_for(request.user) is not None


class CompanyScopedMixin:
    """Scope a generic view's queryset to the caller's company and stamp it on create.

    Override ``company_lookup`` when the company isn't a direct FK
    (e.g. ``'endpoint__company'``). Pair with ``IsCompanyAdmin`` in
    ``permission_classes`` — that gate is what denies non-company users up front,
    so the ``None`` branches below are only a defensive fallback.
    """

    company_lookup = 'company'

    def get_queryset(self):
        company = company_for(self.request.user)
        if company is None:
            return self.queryset.none()
        return self.queryset.filter(**{self.company_lookup: company})

    def perform_create(self, serializer):
        serializer.save(company=company_for(self.request.user))
