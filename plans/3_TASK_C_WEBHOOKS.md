# Phase 3 — Task C: Outbound webhooks (fullstack)

> **Status:** Not started
> **Depends on:** Phase 0 (Celery for async delivery + retries), Phase 1 (perms), Phase 2 (the `invoice.created` event, emitted on `Invoice.issue()`)
> **Part of:** the Task B + Task C "lift" — see [README](./README.md)

## Why / what

Let a company admin configure webhook destinations and receive system events. The Developer Settings page is stubbed (`POST /api/webhook-endpoints/` returns a hardcoded row; list/delete are stubs). We build:

- A webhook endpoint config model.
- Config UI: create, edit, delete, **send test event**.
- A **delivery log** in the UI: what fired, when, response code, attempt number.
- **Async delivery for one system event**, signed, with retries.
- A **versioned** payload schema.

A `webhook-receiver` service runs at `localhost:8027` to catch deliveries.

The domain here is simple (no lifecycle/immutability concerns like Task B) — the difficulty the brief actually grades is the **failure handling**: retries, receiver idempotency, signing, "destination down for hours." That's where the decisions below concentrate.

## Decisions

### 1. Event delivered: `invoice.created`  (decided; fallback `timesheet.approved`)
Fires when an invoice is **issued** (`Invoice.issue()`, Phase 2) — a draft is internal-only, so the external event is the finalised document.

**Reasoning:** it ties directly to Task B (same submission), giving a clean end-to-end demo — *run billing → invoice issued → webhook fires → lands in the receiver UI* — and it's a meaningful business event an external accounting/ERP system would consume. The brief's menu allows "another you can justify"; the B↔C synergy and the "fits with later work" framing justify it.

- **Fallback:** `timesheet.approved` — standalone, also meaningful, if the Phase-2 emit seam isn't ready.
- **Tradeoff:** couples C's demo to B existing — acceptable, both are in scope.

### 2. Data model (`webhooks/models.py`) — **two** models

- **`WebhookEndpoint`** — `company` FK, `url`, `secret` (auto-generated, for signing), `is_active`, `created_at`, optional `description`. One row per destination a company configures.
- **`WebhookDelivery`** — one row per **(event, endpoint)**. It *is* the delivery log **and** carries its own copy of the event:
  - `endpoint` FK
  - `event_id` (`UUIDField`, `default=uuid.uuid4`, set once at row creation) — stable across all retries of this row; the receiver-idempotency key
  - `event_type` (e.g. `invoice.created`)
  - `payload` (`JSONField`) — the immutable envelope snapshot that was sent
  - `status` (`pending | success | failed | exhausted`)
  - `attempt_count`, `last_response_code`, `last_error`, `last_attempt_at`, `created_at`

**Reasoning — why two, not three.** Delivery state (status, response code, retry timing) is inherently **per-endpoint**, and the README lets a company configure **multiple** destinations. So one logical event fans out to **N rows — one per endpoint** — each with its own `status`, `event_id`, and retry counter. That makes the natural grain per-(event, endpoint): a *delivery*. The `payload` duplicates across the N rows for a single event — cheap, and it's the exact immutable record of what each endpoint received, which is what a delivery log wants.

**Alternative rejected:** the earlier three-table split (`Endpoint` / `WebhookEvent` / `WebhookDelivery`). The separate event table only pays off if one event needs *shared identity across endpoints*, which we don't — and it's over-normalized for a single event type. Collapsing it puts the log in one table that reads directly. (Same "don't add a table that doesn't pay for itself" call as Task B.)

### 3. Trigger: explicit `emit()`, async via Celery — **not** a `post_save` signal

When `Invoice.issue()` finalises an invoice, inside its `transaction.on_commit` it calls `emit('invoice.created', invoice)`. The seam lives in its own importable module so it isn't trapped inside billing/webhooks internals:

```python
# webhooks/events.py — the one emission seam
def emit(event_type, obj):          # For use by Task A too: emit('timesheet.approved', entry) on bulk approve
    """Fan an event out to the company's ACTIVE endpoints: create a WebhookDelivery per
    endpoint and enqueue deliver_webhook for each. Call from inside transaction.on_commit."""
    ...
```

`emit` looks up the company's **active** endpoints, creates one `WebhookDelivery` per endpoint, and enqueues one Celery `deliver_webhook` task each.

**Hand-off to Task A** *(noted, not built here)*: when A builds bulk approve, it fires its event the same way — `emit('timesheet.approved', entry)` from the approval **code path**, *not* a `post_save` signal (`bulk_update`/`.update()` bypass signals — see below). `emit` is per-object today; a bulk variant (accept an iterable / `emit_many`) is a trivial extension when A needs it.

**Why explicit emit, not `post_save`:**
- We know the exact point an invoice becomes real (`issue()`); emitting there is direct. A signal would have to *re-derive* "did status just become issued?" after the fact (track the old value / inspect `update_fields`) — more work, more fragile.
- `post_save` fires *before* commit — you'd risk delivering for an invoice that then rolls back. The emit is already inside `on_commit`.
- Coherence + the bulk rule (same decision as Task B): `post_save` is bypassed by `bulk_create`/`bulk_update`, and a signal here would be a *second*, competing trigger alongside the explicit emit. One mechanism, from the code that makes the change.

**Why async (Celery, Phase 0):** delivery POSTs to an arbitrary, possibly slow/down external URL — it must never block or fail the billing run, and retries/backoff require a queue.
- **Rejected:** synchronous in-request delivery — blocks the trigger, no retries, a down endpoint would break billing.

### 4. Delivery + retry: Celery `self.retry()` → `exhausted`

One `deliver_webhook(delivery_id)` task per delivery row. **The task is the state machine; Celery drives the retries — it does not poll the DB.** The `WebhookDelivery` row is *our* log; Celery never reads it to decide anything. Retries are driven entirely by whether the function returns (stop) or calls `self.retry()` (go again), with the attempt counter carried in the task *message*, not a table.

Outbound HTTP uses `requests` (add it to `backend/pyproject.toml`): synchronous calls are correct inside a Celery worker, and `requests.RequestException` is the clean transient-failure surface the retry path keys on. (`httpx` would also work but adds nothing for a blocking worker task; stdlib `urllib` saves the dependency at the cost of clumsier timeout and error handling.)

```python
@shared_task(bind=True, max_retries=5)
def deliver_webhook(self, delivery_id):
    d = WebhookDelivery.objects.select_related('endpoint').get(pk=delivery_id)
    d.attempt_count = self.request.retries + 1
    d.last_attempt_at = timezone.now()
    body = canonical_json(d.payload)                     # exact bytes we send
    ts = str(int(timezone.now().timestamp()))            # delivery timestamp (replay window)
    signed = f'{ts}.'.encode() + body                    # sign timestamp + body (Stripe-style)
    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Id': str(d.event_id),                 # stable across retries → receiver dedupes
        'X-Webhook-Timestamp': ts,
        'X-Webhook-Signature': hmac_sha256(d.endpoint.secret, signed),
        'X-Webhook-Version': 'v1',
    }
    try:
        resp = requests.post(d.endpoint.url, data=body, headers=headers, timeout=10)
        d.last_response_code = resp.status_code
        if 200 <= resp.status_code < 300:                # 2xx ONLY (not resp.ok, which allows 3xx)
            d.status = 'success'; d.save(); return       # return == stop; nothing re-queued
        d.last_error = f'HTTP {resp.status_code}'
    except requests.RequestException as exc:             # timeout / conn refused / DNS
        d.last_error = str(exc)
    d.status = 'failed'; d.save()                        # this attempt failed
    try:
        raise self.retry(countdown=min(10 * 2 ** self.request.retries, 600))  # exp backoff (+ jitter)
    except self.MaxRetriesExceededError:
        d.status = 'exhausted'; d.save()                 # gave up — visible in the log, resendable
```

**State machine:** `pending → success` (2xx, done) `| failed` (attempt failed, retry scheduled) `→ exhausted` (cap hit). `max_retries=5` → 1 initial + 5 retries = **6 attempts**. Success short-circuits at *any* attempt — the function just `return`s; the cap is only a ceiling on the failure path, never a target.

- **2xx only is success.** A 3xx/1xx on a delivery POST is not "received," so the explicit range beats `resp.ok` / `raise_for_status` (which treat 3xx as fine). Optional refinement worth a line: give up immediately on a `4xx` (permanent — malformed/wrong URL) except `408`/`429`; retry `5xx` + network/timeout (transient).
- **"Destination down for hours"** → backoff spreads attempts over a widening window; after the cap → `exhausted`, surfaced in the log; "send test" / manual **resend** re-enqueues `deliver_webhook`.

⚠️ **Long-backoff caveat (documented, not worked around):** with Redis as broker, a `countdown` task is held in the *worker's memory* until due — fine for seconds→minutes. For genuinely hours-long retries that's fragile (a worker restart can drop an in-flight ETA task). The production pattern is to persist `next_retry_at` and run a periodic **Celery beat** sweep over due deliveries. For this exercise, bounded backoff (cap ~minutes, `max_retries=5`) sidesteps it; the beat-sweep is the named scale-up.

### 5. Signing: HMAC-SHA256
Sign `"{timestamp}.{body}"` — the `X-Webhook-Timestamp` value, a dot, then the exact `canonical_json(payload)` bytes we send — with the endpoint's `secret`; send the digest as `X-Webhook-Signature` alongside `X-Webhook-Timestamp`. Binding the timestamp *into* the signed content (Stripe-style) is what makes it a genuine replay guard: the consumer recomputes the HMAC over `timestamp.body` and rejects deliveries whose timestamp falls outside its tolerance window. Signing the body alone would let an attacker replay a captured request indefinitely.

- **Rejected:** no signing (spoofable); signing the body only (no replay protection); mTLS / asymmetric (overkill here).
- Document the verification recipe for consumers: recompute `HMAC_SHA256(secret, f"{X-Webhook-Timestamp}.{raw_body}")`, constant-time compare against `X-Webhook-Signature`, and reject stale timestamps.

### 6. Receiver-side idempotency
`event_id` (UUID) travels in the payload **and** as `X-Webhook-Id`, **identical across every retry** of a given (event × endpoint). Because retries make delivery **at-least-once** (a lost 2xx is retried, so a consumer can receive the same event twice), the consumer dedupes on `event_id`. We document this contract; the local receiver just logs.

### 7. Versioned payload schema
Envelope:
```json
{ "id": "<uuid>", "type": "invoice.created", "api_version": "v1",
  "created_at": "<iso8601>", "data": { /* invoice summary */ } }
```
Plus `X-Webhook-Version: v1`. Version lives in the envelope so consumers can branch; bump on breaking changes. Document the `invoice.created` `data` shape. The stored `WebhookDelivery.payload` is this exact envelope.

### 8. Endpoints (generics + Phase-1 perms; all `IsCompanyAdmin` + company-scoped)
- `GET/POST /api/webhook-endpoints/` — list/create (`perform_create` stamps the company + generates the `secret`).
- `GET/PATCH/DELETE /api/webhook-endpoints/<id>/` — retrieve / edit (toggle `is_active`) / delete. *(The current stub only has create + delete; add retrieve + update.)*
- `POST /api/webhook-endpoints/<id>/test/` — send a synthetic `invoice.created` sample through the **real** delivery path (creates a `WebhookDelivery`, enqueues `deliver_webhook`).
- `GET /api/webhook-endpoints/<id>/deliveries/` — the delivery log, scoped via `company_lookup='endpoint__company'`.

### 9. Frontend (the fullstack half — `pages/DeveloperSettings.tsx`)
**Extend the existing hand-rolled client** (`api/client.ts` + `api/webhooks.ts`), don't introduce Axios. Add:
- Edit (toggle active) + delete (exists).
- **Reconcile the `is_active` field name across the stack.** The model field is `is_active`, but the *current* FE type (`WebhookEndpoint.active`) and JSX (`ep.active` status badge) read `active`. Pick one and make the serializer, the TS interface, and the JSX agree — otherwise the badge silently shows "Disabled" for every endpoint (an invisible, absence-shaped bug). Single source of truth for the field name, same lesson as Task B.
- **Fix the in-form hint URL.** `DeveloperSettings.tsx` hardcodes `http://webhook-receiver:8027/hook`; since the worker delivers from the host, change it to `http://localhost:8027/hook` (see "Local delivery target note").
- Show the `secret` (reveal-once / copy UX — a small product decision to make and note).
- A **"Send test event"** button.
- A **deliveries table**: event type, time, status, response code, attempt #. (Reads `WebhookDelivery` directly — one table, no event/delivery join.)
- React Query with proper query keys + invalidation (already the app's pattern).
- *Optional:* **Zod** runtime-validating the endpoint/delivery responses. *(Not currently a dependency — adds `zod` to `package.json`.)*

**Why not Axios:** there is no coherent adoption boundary in a single-task frontend — Axios-only-for-C = split-brain client; Axios-everywhere = rewriting the already-wired billing/contract pages. The existing `fetch` wrapper already gives typed verbs + auth injection + `ApiError` + 204 handling. *Documented as a deliberate skip.*

## Local delivery target note

The worker runs on the **host** (`task worker`), so it delivers to `http://localhost:8027/hook`. The `http://webhook-receiver:8027/hook` hostname in the UI hint assumes the docker network; since the receiver also runs on the host (`task receiver`), `localhost` is the working target. Document this for the reviewer.

## Testing

- **Signing:** signature matches the expected HMAC for a known body + secret; signing the canonical bytes round-trips.
- **Retry state machine:** a failed POST → `failed` + a scheduled retry with growing countdown; success → `success` + response code recorded and **no** further retry; cap reached → `exhausted`. (Unit-test `deliver_webhook` directly; assert `self.retry` is raised rather than relying on `ALWAYS_EAGER` — Phase 0's testing note.)
- **Idempotency:** `event_id` is identical across all retry attempts for one (event × endpoint).
- **Fan-out:** one event → N active endpoints → N deliveries; inactive endpoints get none.
- **Trigger wiring:** issuing an invoice (Phase 2) enqueues a delivery for each active endpoint via the explicit emit (no signal).
- **CRUD + perms:** freelancer → 403; Admin A can't see/edit Admin B's endpoints or deliveries (404).

## Deliberately deferred (→ CANDIDATE_NOTES.md)

- **Long-backoff durability** (`next_retry_at` + a Celery-beat sweep) — for hours-scale retries that outlive a worker's in-memory ETA hold. *Named, not built;* bounded backoff is used instead (§4).
- **Per-endpoint event subscriptions** (`subscribed_events` array) — for one event type, all active endpoints receive it; the array is the easy extension.
- **Circuit-breaker / auto-disable after N failures**, payload encryption, per-endpoint rate limiting — named, not built. (The `exhausted` state + manual resend is the lightweight stand-in for a dead-letter queue.)
- **Axios / Zod** — fetch kept; Zod optional.
- **Frontend test harness** — the repo ships no FE test setup (no vitest/jest/testing-library), so adding tests means standing up tooling. Cut on the brief's framing: Task C is graded on *"how you model an external integration boundary, how you reason about failure"* — its test signal is the backend (signing, retry, fan-out, idempotency), which is fully covered. *Frontend* testing is the explicit emphasis of **Task A**, which we did not pick.

## Done when

- [ ] Admin can create / edit / delete endpoints and send a test event.
- [ ] Deliveries log shows status, response code, attempt number (reads `WebhookDelivery`).
- [ ] A real `invoice.created` (on issue) fans out to active endpoints, signs, retries on failure → `exhausted`, and lands in the receiver.
- [ ] `emit()` lives in an importable module (`webhooks/events.py`), marked `For use by Task A`; `Invoice.issue()` calls it.
- [ ] Developer Settings UI surfaces config + delivery log; `is_active` agrees across the stack; the hint URL points at `localhost:8027`.
- [ ] Tests green (signing, retry state machine, idempotency, fan-out, trigger wiring, perms).
