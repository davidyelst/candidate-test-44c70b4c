# Phase 1 — Tenant-scoping + capability gate ("perms")

> **Status:** Not started
> **Depends on:** nothing (pure code; can land alongside Phase 0)
> **Consumed by:** Phase 2 (billing endpoints), Phase 3 (webhook endpoints)
> **Part of:** the Task B + Task C "lift" — see [README](./README.md)

## Why this exists

Both tasks add endpoints that must enforce **multi-tenant isolation** (a company user only ever touches *their own* company's data) and a **capability gate** (only company users can run billing / configure webhooks; freelancers cannot).

The existing code already does this, but ad-hoc: every view hand-writes `hasattr(user, 'company_admin')` / `hasattr(user, 'freelancer')` branches, and they are subtly inconsistent (some return `.none()`, some raise 404, some 403). The repo flags this itself — `contracts/views.py` carries `TODO: extract permission checking into a reusable mixin or policy object`.

Tasks B and C add ~6–8 new endpoints that all need the *same* logic. A small shared layer is therefore justified: it DRYs the new code, stops propagating the inconsistency, and is the exact refactor the codebase asked for.

## The model reality (context for a no-prior-knowledge reader)

A `User` relates to a company **only** via `CompanyAdmin` (a `OneToOneField` from user to a `company` FK). There is:

- **No role field** and **no `CompanyMember` tier.** `CompanyAdmin` is simply "this user belongs to this company." The name overstates it — functionally it is *company membership*, not an elevated role.
- **No `(b)`-style "which role within the company" question** — there are no roles to choose between.

So authorization here is **membership / tenancy-based, not RBAC.** Every check reduces to two questions:

- **(a) capability:** are you a company user at all? (vs a freelancer / nobody)
- **(c) scope:** is *this row* your company's?

There is no `(b)` (role-within-company) because the model has none.

## Decisions

### Hand-rolled mixin + permission class — not a tenancy package
Alternatives: `django-organizations`, `django-tenants`, `drf-guardian`. **Rejected** — ~30 lines covers a two-type model, and a dependency drags in concepts we don't need (org hierarchies, schema-per-tenant, per-object ACLs). Pulling one in would be over-engineering. **Tradeoff:** we hand-maintain the scoping, but it is trivial, explicit, and greppable.

### Queryset scoping (not `has_object_permission`) as the primary mechanism
**Reasoning:**
- Scoping `get_queryset()` covers *both* list endpoints and object lookups in one place.
- On a generic view, `get_object()` runs `get_object_or_404` against the *scoped* queryset, so another company's object returns **404, not 403** — no existence leak. (`has_object_permission` only fires at the object level, skips lists, and tends to 403, which leaks existence.)

**Tradeoff:** none meaningful for this shape; queryset scoping is strictly the better tool.

### Capability gate kept separate from scoping
They are orthogonal and cover different holes:
- The **permission class** (`IsCompanyAdmin`) guards *who can touch the endpoint at all* — applied to **every** new billing/webhook endpoint, read and write, so a non-company user (freelancer / nobody) gets **403**. It is also the only thing that can guard a write (`POST /billing/runs/`), which has no queryset to scope.
- The **mixin** guards *which rows* a company user sees — so Admin A requesting Admin B's object gets **404** (no existence leak).

Both consume **one resolver** (`company_for`) so there is a single source of truth.

**Decision — reads are gated too, not just scoped.** Every company-only endpoint carries `IsCompanyAdmin`, so a freelancer gets `403` on reads *and* writes. The alternative was to gate only writes and let the mixin scope reads (a freelancer would then get an empty `200` list). We chose `403`-everywhere: a freelancer has no business with billing or webhooks at all, so a flat 403 is more honest than a silent empty list, and it keeps Task B and Task C consistent (Task C was already all-`IsCompanyAdmin`). The mixin's empty-queryset branch then matters only as a defensive fallback (unit-tested directly), never as a user-facing outcome.

### Do not rename `CompanyAdmin`
Renaming to `CompanyUser` / `CompanyMembership` would touch migrations, the `seed` command, and every existing view — working-code churn for cosmetics. **Keep the name; document the semantic** in the permission docstring. The model is also the natural seam for future roles (a `role` field on `CompanyAdmin`): because checks live behind `company_for()` + `IsCompanyAdmin`, that future split changes *one helper*, not N call sites. That dual payoff (DRY now, seam later) is why the thin abstraction is worth it even though today's check is one line — while *building* a role system now would be the over-engineering we avoid.

## Implementation (the kit — ~30 lines, all in `accounts/`)

`accounts/` owns `Company` / `CompanyAdmin` / `Freelancer`, so the membership/permission logic belongs there.

**One file (reviewed):** the kit is ~30 lines about a single concern — access control for company-only endpoints — so it lives in one module, `accounts/permissions.py`, holding the resolver, the gate, and the scope mixin together. An earlier draft split it across three files (resolver / permission / mixin); that fragmented one small concept (and `IsCompanyAdmin` is a four-line wrapper over `company_for` — keeping them apart bought nothing but extra imports). It's named `permissions.py` — the conventional Django home for access control, and the umbrella the DRF docs use for both `permission_classes` and queryset scoping — *not* `roles.py`, since there are no roles here.

**`accounts/permissions.py`** — resolver + gate + scope, together:
```python
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
    company_lookup = 'company'   # override per view: 'endpoint__company', etc.

    def get_queryset(self):
        company = company_for(self.request.user)
        if company is None:
            return self.queryset.none()
        return self.queryset.filter(**{self.company_lookup: company})

    def perform_create(self, serializer):
        serializer.save(company=company_for(self.request.user))  # stamp tenant, never from body
```

**Why both a permission and a mixin, not one.** The DRF permissions docs are explicit: permission checks "are always run at the very start of the view, before any other code", and for a *create* the queryset offers no control while `permission_classes` apply globally. So `IsCompanyAdmin` is what denies a freelancer a clean 403 on every verb (list and POST included), before any body validation; `get_queryset` then scopes *which* rows a company user sees (cross-company → 404); `perform_create` stamps the owning company. A queryset alone can't gate a POST; a permission alone can't scope rows. The docs say to use both — so we do.

### Consumption pattern (used by Phases 2 & 3)
```python
class SomeView(CompanyScopedMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    serializer_class = SomeSerializer
    queryset = SomeModel.objects.all()
    company_lookup = 'company'           # or 'endpoint__company', etc.
```
The view adds **nothing extra**: `get_queryset` (scoping) and `perform_create` (tenant stamp) come from the mixin, and detail / update / delete isolation falls out of the scoped queryset.

### Optional, contained backport
Refactor **only the timesheet views** in `contracts/` to the new perms (approvals are adjacent to billing) — proves the migration is real, not theoretical, at low blast radius. **Mark optional**; skip under time pressure. Do **not** touch `contracts`/`accounts` further, and do not rewrite the working `APIView`s into generics wholesale.

## Testing

- `company_for` returns the right company for an admin, `None` for a freelancer.
- Freelancer → **403** on any new billing/webhook endpoint (reads *and* writes are `IsCompanyAdmin`-gated).
- The mixin in isolation → **empty queryset** for a company-less user (unit-test it directly; at the endpoint level the gate returns 403 first).
- Admin A cannot retrieve Admin B's object → **404** (no existence leak).

## Deliberately deferred (→ CANDIDATE_NOTES.md)

- **Real roles** (finance vs admin vs viewer) — *named, not built*. The model has no role field and neither task needs one; the layer is structured so roles slot in via one helper later.

## Done when

- [ ] `accounts/permissions.py` exists with `company_for` + `IsCompanyAdmin` + `CompanyScopedMixin`.
- [ ] Unit tests cover admin/freelancer/cross-company cases.
- [ ] Phases 2 and 3 can `import` and consume the kit.
