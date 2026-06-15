# Phase 2 — Task B: Monthly billing run

> **Status:** Not started
> **Depends on:** Phase 0 (Celery for async email + Beat for scheduling), Phase 1 (perms for endpoint gating + scoping)
> **Feeds:** Phase 3 (emits the `invoice.created` event that Task C delivers)
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

Task A (approval inbox, built later) shows a running cost total and **must use the same formula**, so the calc lives in **one canonical helper** in `contracts/` (an entry's cost is a *contracts* concern both A and B consume — A's approvals must not have to depend on the `billing` app for it):

```python
# contracts/pricing.py
WORKING_DAY_HOURS = 8

def line_amount(entry):              # For use by Task A (approval cost total) AND Task B (invoice lines)
    return (entry.hours * entry.contract.daily_rate / WORKING_DAY_HOURS).quantize(Decimal('0.01'))
```

- **Build now (B):** the helper + B's invoice lines which call it. Exposing `amount` on the `TimesheetEntry` serializer is **Task A's** job (noted, not built).
- **Rejected:** hours-as-fractional-days (× daily directly) over-bills ~8×; Task A's literal "hours × contract rate" wording is one of the repo's deliberate inconsistencies.

### 2. Data model (`billing/models.py`) — three models, one run → many invoices

A scheduled run bills **every** company, so one execution fans out into many invoices. That gives the natural grain: **`BillingRun` 1 ──< `Invoice` (per company × freelancer) 1 ──< `InvoiceLineItem`**, where `InvoiceLineItem` is the **M2M through** joining an invoice to the timesheet entries it bills.

- **`BillingRun`** — one execution record: `period` (1st of month), `status`, `created_at`, and a **nullable** `company` (null = system-wide Beat run; set = a single-company run from the button). The run is audit + supplies the response `run_id`.
- **`Invoice`** — per company × freelancer: `billing_run` FK, `company`, `freelancer`, `period`, `subtotal` (snapshot), `email_status` (`pending | sent | failed`), `created_at`. **No invoice `status` field** — an invoice existing *means* it's issued; the draft/issue/void lifecycle is deferred. `email_status` is the only lifecycle, and it exists for the brief's email-after-commit question (§5).
- **`InvoiceLineItem`** — the **M2M through**: plain FK `invoice` + plain FK `timesheet_entry`, plus the immutable snapshot `date` / `hours` / `rate` / `amount` (so a later contract-rate change never mutates a past invoice).

```python
class BillingRun(models.Model):
    STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED = 'running', 'completed', 'failed'
    STATUS_CHOICES = [(STATUS_RUNNING, 'Running'), (STATUS_COMPLETED, 'Completed'), (STATUS_FAILED, 'Failed')]

    company    = models.ForeignKey(Company, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='billing_runs')   # null = system-wide (Beat)
    period     = models.DateField()                               # 1st of the billing month
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    created_at = models.DateTimeField(auto_now_add=True)


class Invoice(models.Model):
    EMAIL_PENDING, EMAIL_SENT, EMAIL_FAILED = 'pending', 'sent', 'failed'
    EMAIL_CHOICES = [(EMAIL_PENDING, 'Pending'), (EMAIL_SENT, 'Sent'), (EMAIL_FAILED, 'Failed')]

    billing_run  = models.ForeignKey(BillingRun, on_delete=models.PROTECT, related_name='invoices')
    company      = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='invoices')
    freelancer   = models.ForeignKey(Freelancer, on_delete=models.PROTECT, related_name='invoices')
    period       = models.DateField()                             # billing month (= run.period)
    subtotal     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    email_status = models.CharField(max_length=10, choices=EMAIL_CHOICES, default=EMAIL_PENDING)
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
    count = 0
    for (co, freelancer), entries in _group_billable(period, company):
        with transaction.atomic():                                # one invoice per txn
            invoice = Invoice.objects.create(billing_run=run, company=co,
                                             freelancer=freelancer, period=period)
            lines = [InvoiceLineItem(invoice=invoice, timesheet_entry=e, date=e.date, hours=e.hours,
                                     rate=e.contract.daily_rate, amount=pricing.line_amount(e))
                     for e in entries]
            InvoiceLineItem.objects.bulk_create(lines)
            invoice.subtotal = sum(li.amount for li in lines)
            invoice.save(update_fields=['subtotal'])
            transaction.on_commit(lambda inv=invoice: send_invoice_email.delay(inv.id))
            transaction.on_commit(lambda inv=invoice: emit('invoice.created', inv))   # Task C seam
        count += 1
    run.status = cls.STATUS_COMPLETED
    run.save(update_fields=['status'])
    return run, count
```

Each invoice commits in **its own transaction**, so one bad invoice can't sink the batch (important for the all-companies Beat run), and `on_commit` fires per invoice. (`emit` is imported locally inside the method to avoid a billing→webhooks import cycle.)

#### Selection — what guarantees "nothing left behind"

The run bills **all approved, unbilled** entries dated on or before the period end — **not** entries whose date falls *in* the run's month. The monthly run is just a *trigger*; each run sweeps everything still outstanding, so a May entry approved on June 3rd is caught by the next run instead of being stranded. The period is a **billing cutoff**, not a narrow month filter.

```python
def _billable_entries(period, company=None):
    qs = (TimesheetEntry.objects
          .filter(status='approved', line_items__isnull=True, date__lte=end_of_month(period))
          .select_related('contract', 'contract__company', 'contract__freelancer')
          .order_by('contract__company_id', 'contract__freelancer_id', 'date'))
    return qs.filter(contract__company=company) if company is not None else qs

def _group_billable(period, company=None):
    for key, group in groupby(_billable_entries(period, company),
                              key=lambda e: (e.contract.company, e.contract.freelancer)):
        yield key, list(group)
```

`line_items__isnull=True` = the entry has no line item yet = unbilled. That single predicate gives us **both** "billed at most once" (an entry with a line item is excluded) **and** "nothing left behind" (no date-equality filter to drop late approvals).

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

- **Scheduled (Beat):** a `billing.tasks.run_monthly_billing` task, registered on `celery beat` for `day_of_month=1`, calls `generate(first_of_this_month, company=None)` → one system-wide run, invoices fanned out across **all** companies.
- **Button (`POST /api/billing/runs/`):** a company admin runs their own company — the view calls `generate(period, company=company_for(request.user))` **synchronously**, so the wired frontend gets its real `invoices_generated` count in the response. Still one run, many invoices (one per the company's freelancers).

```python
# billing/tasks.py
@shared_task
def run_monthly_billing():
    BillingRun.generate(first_of_this_month(), company=None)
```

> **Cross-phase note:** Phase 0 lists Celery Beat as *optional/deferred* — this task makes it **required**. Phase 0 needs the `beat` process wired (`task beat`) and documented. Flagged, not changed here.

### 7. Endpoints (DRF generics + Phase-1 perms)
- `POST /api/billing/runs/` — `IsCompanyAdmin`; parse `{month}` → `period`; `run, count = BillingRun.generate(period, company=company_for(request.user))`; return `{run_id: run.id, invoices_generated: count, status: run.status}`.
- `GET /api/invoices/?month=YYYY-MM` — `IsCompanyAdmin` + `CompanyScopedQuerysetMixin` (`company_lookup='company'`); the company's invoices for the period (id, freelancer name, subtotal, email_status).
- `GET /api/invoices/<id>/` — `IsCompanyAdmin` + scoped detail with line items + totals (free shape — `InvoiceDetail.tsx` renders raw JSON).

No `void` endpoint — there is no void in the lean model.

### 8. Event seam (forward hook to Task C)
On invoice creation, inside the same `on_commit`, call `emit('invoice.created', invoice)`. There is no separate `issue()` step in the lean model, so **invoice creation is the emit point**. In Phase 2 `emit` can be a thin log; **Phase 3 implements delivery.**

> **Cross-phase note:** Phase 3 currently says the event fires on `Invoice.issue()`. There is no `issue()` here — update Phase 3's emit reference to "on invoice creation." Flagged, not changed here.

## Testing (the brief cares what we choose to test)

- **Idempotency:** run twice → second run reports `invoices_generated == 0`, no duplicate lines.
- **Nothing left behind:** an entry approved *after* a run is billed by the next run; an entry dated in a prior month but approved late is included (cutoff is period-end, not month-equality).
- **Selection:** only `approved` + unbilled entries are billed; `submitted` / `rejected` / `draft` and already-billed entries are excluded.
- **Totals:** `subtotal == Σ(hours × daily_rate/8)` with `Decimal` precision.
- **Email after commit:** fires to both recipients (`company.billing_email` + `freelancer.user.email`); `email_status` transitions `pending → sent`; drive the `on_commit` chain with pytest-django's `django_capture_on_commit_callbacks(execute=True)` and assert against the `mailoutbox` fixture (locmem), not Mailpit.
- **All-companies run:** `generate(period, company=None)` produces **one** `BillingRun` and invoices spanning multiple companies.
- **Perms:** freelancer → 403 on the run and invoice reads; Admin A can't see Admin B's invoices (404).

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
- [ ] Celery Beat triggers a monthly, all-companies run via `generate(..., company=None)`.
- [ ] `contracts/pricing.py::line_amount` is the one canonical cost helper (marked `For use by Task A`); invoice lines use it.
- [ ] `emit('invoice.created', invoice)` fires on invoice creation (delivery wired in Phase 3).
- [ ] Tests green (idempotency, nothing-left-behind, selection, totals, email-after-commit, all-companies, perms).
