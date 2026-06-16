# Candidate Notes

## 1. What I built and why

I took **Task B (monthly billing run)** and **Task C (outbound webhooks)**, leaving **Task A (frontend approval inbox)**. B and C share backend foundations — async via Celery + Redis, and a small admin-only, company-scoped permission layer — and chain end-to-end: the billing run emits `invoice.created` and the webhook system delivers it. I built the shared seams so Task A slots in later.

## 2. Key implementation notes

**Task B — billing**
- `BillingRun` → one `Invoice` per contract → line items that **snapshot rate/hours** at run time, so a later rate change can't rewrite history.
- Cost (`hours × daily_rate ÷ 8`) is defined once on `TimesheetEntry`, shared with Task A.
- **Idempotent, nothing left behind** by selection: it bills approved, not-yet-billed entries dated ≤ period end — re-runs do nothing, late approvals are caught next run. A `unique` on the billed entry is the DB backstop against two concurrent runs double-billing it; a coordinating lock for that race is still deferred.
- **Email after commit** (Celery), one message per recipient so neither party sees the other's address: a failed send flags the invoice but never blocks or rolls it back — the brief's transaction-boundary question.

**Task C — webhooks**
- Event `invoice.created`; async delivery (Celery), one `WebhookDelivery` per (event × endpoint) = delivery log + retry state machine.
- Retries: 6 attempts, capped exponential backoff (~5 min), then `exhausted`. A destination down for hours fails fast rather than holding a worker; durable hours-long retry is deferred.
- Signed (HMAC-SHA256 over the body, per-endpoint secret), versioned envelope, stable `event_id` for at-least-once dedupe.
- Frontend: Developer Settings — endpoint CRUD, send-test, and the delivery log.

Tests cover both tasks' graded core — Task B's idempotent re-runs and email-fails-after-commit boundary, Task C's signing and retry state machine; broader CRUD/permission coverage is the next step.

## 3. Workflow

**Claude Code**, planned and staged (infra → permissions → B → C; reasoning and rejected alternatives in `plans/`).

**Experience.** AI's payoff scales with task size, and a tightly time-boxed one like this doesn't let it stretch. Design was the bottleneck, not typing — a roughly fixed cost AI doesn't compress; it earns its keep on volume, not a few hours on a small surface. The real work was scope discipline: going deep only where the brief is evaluated, deferring the rest.

## 4. Next steps — another four hours

Robustness and UX, not new features:
- **Billing:** invoice lifecycle (`draft → issued → void`, review gate, credit notes); a coordinating lock for fully concurrent runs (the per-entry `unique` already blocks a double-bill at the DB, but a lock would avoid a losing run failing noisily).
- **Webhooks:** timestamp-bound signing (replay protection); durable long-backoff (`next_retry_at` + beat sweep); reveal-once secret, per-endpoint subscriptions, auto-disable.
- **UX & tests:** real invoice detail view; filterable delivery log with re-deliver; broaden backend tests and add a frontend harness.
