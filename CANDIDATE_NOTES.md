# Candidate Notes

> _Sections 1–3 are mine to complete; section 4 (Next steps) is drafted below._

## 1. What I built and why

_[To complete: which tasks I tackled and which I deliberately left, and how I made that call.]_

## 2. Key implementation notes

_[To complete: the approach to each task and the decisions worth calling out — e.g. invoice grain = the contract; the "nothing left behind" cutoff (period-end, not month-equality); per-invoice fault isolation so one company can't sink a system-wide run; email as a post-commit Celery side-effect that never blocks the financial record.]_

## 3. Workflow

_[To complete: tools and approach, including which AI tooling I used and how that experience went.]_

## 4. Next steps — with another four hours

**Test coverage.** `backend/billing/tests/test_billing.py` is a single, representative test — a deliberate demonstration of approach, not a suite: it runs `generate()` end-to-end and checks the invoice, its frozen snapshot line items, and the total. The rest of the behaviour is **implemented and was covered in an earlier cut of the suite**; I pared it right back for the time-box. The regressions I'd restore first (our-own-logic first):

- the **core run guarantees** the single test doesn't assert — idempotent re-runs, nothing-left-behind (cutoff is period-end, not month-equality), per-contract fault isolation, and the post-commit email to both recipients;
- the **API contract + permissions matrix** — auth (401), role gating (403), cross-company scoping (404, no existence leak), bad-`month` parsing (400);
- the **selection matrix** — `submitted` / `rejected` / `draft` and already-billed entries excluded;
- the **all-companies fan-out** (`company=None`) and **per-contract grain** (two contracts at one company → two invoices).

(`end_of_month` leap-year correctness is handled by design via `calendar.monthrange`, and `cost` rounding via `Decimal.quantize` — handled cases, not risks, so they're not listed as gaps.)

**Billing features deferred by design** (rationale in `plans/2_TASK_B_BILLING.md`):

- **Invoice lifecycle** — `draft → issued → void`, modifiable drafts, and a finance review gate (build draft → review → issue).
- **Corrections via credit notes** — the real accounts-receivable instrument; void-and-reissue would be a fake of it, so it's named-not-faked.
- **Concurrency guard** — a unique constraint on the through link (or `select_for_update`) to make double-billing impossible under racing runs; query-based idempotency covers the normal case today.
- **Audit trail** — who triggered a run, line-level history.
- **Payment tracking, PDF/e-invoice document, invoice numbering, tax, multi-currency** — out of scope, named not built.
