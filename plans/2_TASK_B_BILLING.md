# Phase 2 — Task B: Monthly billing run

> **Status:** Not started
> **Depends on:** Phase 0 (Celery for async email + Beat for scheduling), Phase 1 (perms for endpoint gating + scoping)
> **Feeds:** Phase 3 (Task C builds on the invoices this run creates)
> **Part of:** the Task B + Task C "lift" — see [README](./README.md)

## Why / what

Finance generates monthly invoices from approved hours. The Billing page is **fully wired** to three endpoints that currently return hardcoded stubs:

- `POST /api/billing/runs/` — body `{month: "YYYY-MM"}` → `{run_id, invoices_generated, status}`
- `GET /api/invoices/?month=YYYY-MM` — list
- `GET /api/invoices/<id>/` — detail

We implement real behaviour: for each **company × freelancer**, build an invoice from that freelancer's **approved, not-yet-billed** timesheet entries, email it to the company `billing_email` and the freelancer, and record what was billed. The frontend is loosely coupled — the list only reads `inv.id`, the run only reads `data.invoices_generated`, and `InvoiceDetail.tsx` renders the detail as raw `JSON.stringify` — so the response shapes are ours to design (a clean line-items-and-totals detail displays as-is).

## Scope — lean by design

This task is "generate monthly invoices from approved hours and email them," **not** an accounts-receivable subsystem. So we build the generation path and email handling, and we **defer the invoice lifecycle** (drafts, issue/void, corrections, audit) to documented TODOs — see *Deliberately deferred*.

The one invariant we **cannot** defer is **no approved hours left behind**: every approved hour must eventually get billed, exactly once. That falls out of *selection*, not lifecycle (see §3), so the lean version still gets it right.

## Decisions

### 1. Cost convention — `amount = hours × (daily_rate ÷ 8)`  ⚠️ ASSUMPTION (documented)
`daily_rate` is a *daily* rate; entries log *hours*. To bill hours we need an hourly rate = `daily_rate ÷ WORKING_DAY_HOURS`, with `WORKING_DAY_HOURS = 8`. The seed corroborates it: entries log 7.5–8.0 hours/day, and `8.0 × (600 ÷ 8) = 600` recovers exactly one daily rate for a full day. The 8h day is a business assumption (not derivable from code), so it stays centralized and documented.

Task A (approval inbox, built later) shows a running cost total and **must use the same formula**, so the calc lives on the **`TimesheetEntry` model itself** as a `cost` property — an entry's cost is a *contracts* concern both A and B consume, and `TimesheetEntry` is a contracts model, so A's approvals never depend on the `billing` app for it:

```python
# contracts/models.py — on TimesheetEntry
WORKING_DAY_HOURS = 8                 # business assumption (documented): 8-hour working day

@property
def cost(self):                       # For use by Task A (approval cost total) AND Task B (invoice lines)
    return (self.hours * self.contract.daily_rate / self.WORKING_DAY_HOURS).quantize(Decimal('0.01'))
```

- **Build now (B):** the property + B's invoice lines which read `entry.cost`. Exposing `cost` on the `TimesheetEntry` serializer is **Task A's** job (noted, not built).
- **Rejected:** hours-as-fractional-days (× daily directly) over-bills ~8×; Task A's literal "hours × contract rate" wording is one of the repo's deliberate inconsistencies.
- **Rejected (placement):** a standalone `contracts/pricing.py::line_amount(entry)` module helper — fine and equally decoupled, but fat-model says behaviour that *can* sit on the model should: `entry.cost` reads better at call sites and keeps the assumption next to the data it describes.

### 2. Data model (`billing/models.py`) — three models, one run → many invoices

A scheduled run bills **every** company, so one execution fans out into many invoices. That gives the natural grain: **`BillingRun` 1 ──< `Invoice` (one per contract) 1 ──< `InvoiceLineItem`**, where `InvoiceLineItem` is the **M2M through** joining an invoice to the timesheet entries it bills. The run loops over **contracts** — a contract already pins exactly one (company, freelancer) pair, so it is the natural unit and avoids a two-level grouping key — and each contract's billable entries become one invoice. The `Invoice` still carries `company` + `freelancer` (read off the contract) as the parties it is *to* and *for*. **Grain note:** a freelancer with two distinct contracts at the same company gets one invoice *per contract*, not a merged one — the agreement is the unit.

> **Decision (BillingRun retained):** the scheduled all-companies run is a **confirmed requirement** (see §6), so this one-run-fans-out-across-all-companies grain is real, not hypothetical — `BillingRun` is kept rather than collapsed into a two-model `Invoice` + `InvoiceLineItem` design. It is the parent the system-wide Beat run needs, and supplies the response `run_id`. (Considered and rejected: dropping it and returning a throwaway `run_id` — leaner, and the frontend ignores `run_id`'s value, but it loses the natural parent for the all-companies fan-out and the per-run audit grain.)

- **`BillingRun`** — one execution record: `period` (1st of month), `status`, `created_at`, and a **nullable** `company` (null = system-wide Beat run; set = a single-company run from the button). The run is audit + supplies the response `run_id`.
- **`Invoice`** — one per contract per period (carrying the contract's `company` + `freelancer`): `billing_run` FK, `company`, `freelancer`, `period`, `subtotal` (snapshot), `email_status` (`pending | sent | failed`), `created_at`. **No invoice `status` field** — an invoice existing *means* it's issued; the draft/issue/void lifecycle is deferred. `email_status` is the only lifecycle, and it exists for the brief's email-after-commit question (§5).
- **`InvoiceLineItem`** — the **M2M through**: plain FK `invoice` + plain FK `timesheet_entry`, plus the immutable snapshot `date` / `hours` / `rate` / `amount` (so a later contract-rate change never mutates a past invoice).

```python
class BillingRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    company    = models.ForeignKey(Company, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='billing_runs')   # null = system-wide (Beat)
    period     = models.DateField()                               # 1st of the billing month
    status     = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    created_at = models.DateTimeField(auto_now_add=True)


class Invoice(models.Model):
    class EmailStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    billing_run  = models.ForeignKey(BillingRun, on_delete=models.PROTECT, related_name='invoices')
    company      = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='invoices')
    freelancer   = models.ForeignKey(Freelancer, on_delete=models.PROTECT, related_name='invoices')
    period       = models.DateField()                             # billing month (= run.period)
    subtotal     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    email_status = models.CharField(max_length=10, choices=EmailStatus.choices, default=EmailStatus.PENDING)
    created_at   = models.DateTimeField(auto_now_add=True)
    entries      = models.ManyToManyField('contracts.TimesheetEntry', through='InvoiceLineItem',
                                          related_name='invoices')


class InvoiceLineItem(models.Model):
    """M2M through: the TimesheetEntries an Invoice bills, with a frozen snapshot."""
    invoice         = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='line_items')
    timesheet_entry = models.ForeignKey('contracts.TimesheetEntry', on_delete=models.PROTECT,
                                        related_name='line_items')
    date   = models.DateField()
    hours  = models.DecimalField(max_digits=5, decimal_places=2)
    rate   = models.DecimalField(max_digits=8, decimal_places=2)   # contract.daily_rate, frozen
    amount = models.DecimalField(max_digits=10, decimal_places=2)
```

`on_delete=PROTECT` throughout — nothing financial (an entry, an invoice, a run) can be deleted out from under a record.

### 3. The run — `BillingRun.generate(period, company=None)`

A classmethod on `BillingRun` is the single entry point; both triggers (§6) call it.

```python
@classmethod
def generate(cls, period, company=None):
    """Bill every approved, not-yet-billed entry dated on/before `period` end into invoices.
    company=None → all companies (Beat); company=X → just that company (the button)."""
    run = cls.objects.create(period=period, company=company)
    contracts = Contract.objects.select_related('company', 'freelancer')
    if company is not None:
        contracts = contracts.filter(company=company)

    count = 0
    for contract in contracts:                                    # the contract IS the (company, freelancer) unit
        entries = (contract.timesheet_entries
                   .filter(status='approved', line_items__isnull=True, date__lte=end_of_month(period))
                   .select_related('contract').order_by('date'))
        if not entries:
            continue
        try:
            with transaction.atomic():                            # one invoice per txn
                invoice = Invoice.objects.create(
                    billing_run=run, company=contract.company, freelancer=contract.freelancer,
                    period=period, subtotal=sum(e.cost for e in entries))
                InvoiceLineItem.objects.bulk_create([
                    InvoiceLineItem(invoice=invoice, timesheet_entry=e, date=e.date, hours=e.hours,
                                    rate=contract.daily_rate, amount=e.cost)
                    for e in entries])
                transaction.on_commit(lambda inv=invoice: send_invoice_email.delay(inv.id))
            count += 1
        except Exception:                                         # one contract's failure can't sink the batch
            logger.exception('Billing run %s: failed to bill contract %s', run.id, contract.id)
            continue
    run.status = cls.Status.COMPLETED
    run.save(update_fields=['status'])
    return run, count
```
(`logger = logging.getLogger(__name__)` at module level in `billing/models.py`.)

Each invoice commits in **its own transaction wrapped in `try/except`**, so a single company's failure is logged and skipped — it **cannot** sink the rest of the batch. This matters precisely because the Beat run is **system-wide** (§6): one company's bad data must not abort every other company's billing. The bare `atomic()` alone wouldn't give this — it rolls back the one invoice but re-raises, so the `try/except` is what actually delivers the isolation. `count` reflects only invoices that committed.

A skipped company writes **no** line items (its `atomic()` block rolled back), so its entries stay unbilled and the **next** run sweeps them up — fault-isolation and *nothing-left-behind* (§3 selection) compose cleanly, no entry is stranded by a transient failure. `on_commit` fires per invoice. (`logger` is module-level.)

#### Selection — what guarantees "nothing left behind"

The run bills **all approved, unbilled** entries dated on or before the period end — **not** entries whose date falls *in* the run's month. The monthly run is just a *trigger*; each run sweeps everything still outstanding, so a May entry approved on June 3rd is caught by the next run instead of being stranded. The period is a **billing cutoff**, not a narrow month filter.

```python
# Per contract, inside generate()'s loop — no grouping needed, the contract IS the unit:
contract.timesheet_entries.filter(
    status='approved', line_items__isnull=True, date__lte=end_of_month(period),
)
```

We loop contracts and pull each one's billable entries directly (one query per contract). At this scale that's plainly clearer than one big ordered query chunked with `itertools.groupby` — the grouping machinery only earns its keep when the per-contract query count actually matters, which it doesn't here.

`line_items__isnull=True` = the entry has no line item yet = unbilled. That single predicate gives us **both** "billed at most once" (an entry with a line item is excluded) **and** "nothing left behind" (no date-equality filter to drop late approvals).

(`end_of_month(period)` here and `first_of_this_month()` in §6 are trivial date helpers — house them in `billing/dates.py`.)

### 4. Idempotency

Comes for free from the selection: a re-run finds no newly-unbilled entries → **0 invoices**. Billed-once is the same predicate (`line_items__isnull=True`).

⚠️ **Concurrency is a deferred TODO.** With a plain-FK through (no DB uniqueness on `timesheet_entry`), two runs racing the *same* entries could each bill them before either commits → double-bill. The unbilled-selection covers the normal single-run case; the hardening (a `unique` constraint on the link, or `select_for_update` on the entries) is named, not built — see *Deliberately deferred*.

### 5. Transaction boundaries + email — the brief's explicit question
> *"what happens if the email send fails after the invoice row is committed?"*

The invoice is the source of truth and must commit independently of notification. **Email fires after commit, via Celery, never inside the transaction:**

```python
transaction.on_commit(lambda inv=invoice: send_invoice_email.delay(inv.id))
```

If email were inside the transaction and the commit later failed, we'd have emailed a non-existent invoice; if a synchronous send raised *after* commit we'd either (impossibly) roll back a committed invoice or silently lose the mail. Correct design: **commit the invoice, then fire email as a separate retryable side-effect.** `email_status` tracks delivery (`pending → sent`, or `failed` + Celery retry/backoff; a manual resend is possible).

**Tradeoff accepted:** an invoice can exist with `email_status = failed`. That's correct — the financial record doesn't depend on the notification. Recipients: `company.billing_email` and `freelancer.user.email`. Email content is plaintext line-items + total (the brief's stand-in for a PDF/e-invoice).

### 6. Trigger — Celery Beat (1st of month) + the wired button

Both call the same `generate()`:

- **Scheduled (Beat):** a `billing.tasks.run_monthly_billing` task, registered on `celery beat` for `day_of_month=1`, calls `generate(first_of_this_month(), company=None)` → one system-wide run, invoices fanned out across **all** companies.
- **Button (`POST /api/billing/runs/`):** a company admin runs their own company — the view calls `generate(period, company=company_for(request.user))` **synchronously**, so the wired frontend gets its real `invoices_generated` count in the response. Still one run, many invoices (one per the company's freelancers).

```python
# billing/tasks.py
import logging
from celery import shared_task

from .dates import first_of_this_month
from .models import BillingRun

logger = logging.getLogger(__name__)


@shared_task
def run_monthly_billing():
    run, count = BillingRun.generate(first_of_this_month(), company=None)
    logger.info('Monthly billing run %s generated %s invoice(s)', run.id, count)
```

#### Beat infrastructure — **this plan sets it up** (decision: a scheduled monthly run is a confirmed requirement, not optional)

The stack today has the Celery **worker** + Redis (Phase 0) but **no beat scheduler**. Task B wires it, staying with Celery's **built-in** scheduler — deliberately **no `django-celery-beat`**: a DB-backed scheduler is more moving parts than a single monthly job needs, and a take-home doesn't warrant it. Three concrete pieces:

1. **Schedule (settings).** Register the periodic task with a crontab in `config/settings.py`, in the existing `CELERY` namespace:
   ```python
   from celery.schedules import crontab

   CELERY_BEAT_SCHEDULE = {
       'run-monthly-billing': {
           'task': 'billing.tasks.run_monthly_billing',
           'schedule': crontab(minute=0, hour=0, day_of_month=1),   # 00:00 on the 1st; TIME_ZONE='UTC'
       },
   }
   ```
   (`billing` is already in `INSTALLED_APPS` and `config/celery.py` calls `autodiscover_tasks()`, so the task name resolves with no extra wiring.)

2. **Process (Taskfile).** Beat is a **separate process** from the worker — it only *enqueues* `run_monthly_billing` on schedule; the worker executes it. Add a `backend:beat` task mirroring the existing `backend:worker`:
   ```yaml
   backend:beat:
     desc: Start the Celery Beat scheduler (monthly billing run).
     dir: backend
     cmds:
       - uv run celery -A config beat -l info
   ```
   Runs on the host like the worker — **no docker-compose change** (Redis is already there). Keep it **out** of the default `task backend` aggregate so ordinary dev runs stay quiet; start it explicitly (or document a manual `run_monthly_billing.delay()` / `generate()` call) when exercising the schedule. Document `backend:beat` in the README next to `backend:worker`.

3. **Scheduler state (.gitignore).** The default `PersistentScheduler` writes a `celerybeat-schedule` file (and `celerybeat.pid`) in `backend/`; add both to `.gitignore` (not currently ignored).

> **Cross-phase note (resolved):** Phase 0 listed Beat as *optional/deferred*; that is now **superseded** — Task B owns the Beat setup above and makes it required. Phase 0's "Celery Beat / scheduled billing — not built" deferral should be updated to point here.

### 7. Endpoints (DRF generics + Phase-1 perms)
Phase 1 landed the perms layer **consolidated into one module** — `IsCompanyAdmin`, `CompanyScopedMixin`, and `company_for` all import from `accounts.permissions` (the planned split into `roles.py`/`mixins.py` was dropped; the mixin was renamed from `CompanyScopedQuerysetMixin` → `CompanyScopedMixin`).

- `POST /api/billing/runs/` — `IsCompanyAdmin`; parse `{month}` → `period` (400 on a missing/malformed `month`); `run, count = BillingRun.generate(period, company=company_for(request.user))`; return `{run_id: run.id, invoices_generated: count, status: run.status}`.
- `GET /api/invoices/?month=YYYY-MM` — `IsCompanyAdmin` + `CompanyScopedMixin` (`company_lookup='company'`); the company's invoices for the period (id, freelancer name, subtotal, email_status).
- `GET /api/invoices/<id>/` — `IsCompanyAdmin` + scoped detail with line items + totals (free shape — `InvoiceDetail.tsx` renders raw JSON).

No `void` endpoint — there is no void in the lean model.

## Testing — a single demonstrative test (the rest deferred → CANDIDATE_NOTES.md)

Given the time-box, `billing/tests/test_billing.py` is **one representative test, not a suite**: it runs `generate()` end-to-end and asserts the invoice, its frozen snapshot line items, and the total — enough to demonstrate the approach. The rest of the behaviour is implemented; its tests are deferred.

**Deferred to the "more time" pile** (named in CANDIDATE_NOTES.md): the other run guarantees (idempotency, nothing-left-behind, per-contract fault isolation, email-after-commit), the API-contract + permissions matrix (401/403/404 scoping, bad-month parsing), the selection matrix (which statuses bill), and the all-companies fan-out + per-contract grain. (`end_of_month` leap-year and `cost` rounding are handled by design — `calendar.monthrange` and `Decimal.quantize` — so they're not gaps.)

## Deliberately deferred (→ CANDIDATE_NOTES.md) — the "more time" pile

- **Invoice lifecycle** — `draft → issued → void`, modifiable drafts, and a finance **review gate** (build a draft, review, then issue). The model takes a `status` field and the run a stop-at-draft option; not built.
- **Corrections via credit notes** — the *real* AR instrument (a partial credit note adjusts an issued invoice without mutating it). We don't model corrections at all in lean; void+reissue would be a fake of this and is also skipped. **Named, not built.**
- **Concurrency guard** — a `unique` constraint on the through link (or `select_for_update` on the entries) to make double-billing impossible under racing runs (§4). Query-based idempotency covers the normal case.
- **Audit trail** — who triggered a run, line-level history.
- **Payment tracking, PDF/e-invoice document, invoice numbering, tax, multi-currency** — out of scope; named.

## Done when

- [ ] `BillingRun.generate(period, company=None)` bills all approved + unbilled entries (≤ period end) into per-(company, freelancer) invoices with snapshot line items.
- [ ] The three wired endpoints return real, company-scoped data; the button shows `invoices_generated`.
- [ ] A re-run bills nothing new; a late-approved entry is picked up on the next run (nothing left behind).
- [ ] Invoice emails land in Mailpit for both recipients after commit; `email_status` reflects the outcome.
- [ ] Celery Beat triggers a monthly, all-companies run via `generate(..., company=None)`, with the infra wired: `CELERY_BEAT_SCHEDULE` (crontab, 1st of month) in settings, a `backend:beat` Taskfile task + README note, and `celerybeat-schedule`/`celerybeat.pid` git-ignored.
- [ ] `TimesheetEntry.cost` is the one canonical cost calc (a property on the contracts model, shared with Task A); invoice lines read `entry.cost`.
- [ ] A single demonstrative test is green (a run produces an invoice with snapshot lines and the right total); broader coverage is deferred to CANDIDATE_NOTES.md.
