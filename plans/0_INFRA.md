# Phase 0 — Async infrastructure (Celery + Redis)

> **Status:** Not started
> **Depends on:** nothing (this is the foundation)
> **Consumed by:** Phase 2 (async invoice email), Phase 3 (async webhook delivery)
> **Part of:** the shared foundation for Task B + Task C

## Why this exists

Both chosen tasks need to do work *outside* the HTTP request/response cycle:

- **Task B** sends an invoice email after the invoice row is committed. That send hits SMTP (Mailpit) and can fail independently of the invoice.
- **Task C** delivers webhooks by POSTing to arbitrary, externally-controlled URLs that may be slow or down, and must be retried with backoff.

Doing either synchronously inside the request is wrong:

- It blocks the user's request on external I/O (SMTP / an unknown webhook host).
- It makes retries/backoff impossible.
- It couples the success of the user's action (e.g. "run billing") to the success of a side-effect that is *allowed* to fail and be retried later.

There is no queue pre-configured — the brief confirms this and explicitly leaves the choice of whether to add one, and which, open. So Phase 0 stands up a task queue that Phases 2 and 3 both build on. Doing it first means the business-logic phases never have to stop and bootstrap infrastructure.

## Decision: Celery + Redis

### Why a queue at all (vs synchronous)
Rejected synchronous side-effects because they cannot satisfy Task B's "email fails after commit" requirement or Task C's "retry policy / destination down for hours" requirement. Both tasks center on failure handling, which *requires* asynchronous, retryable execution.

### Why Celery (vs alternatives)
- **Celery (chosen).** The standard async task framework for a Django shop; first-class retry/backoff (`autoretry_for`, `retry_backoff`, `retry_jitter`), and `celery beat` is available if monthly billing later becomes scheduled. It is the conventional choice in this stack.
- **RQ / django-rq (rejected, mildly).** Lighter and Redis-native; would work fine. Rejected because Celery's retry ergonomics and scheduling are a better fit for *both* tasks and it is the more conventional choice for the stack. **Tradeoff acknowledged:** Celery is heavier than RQ for what Phase 0 strictly needs today.
- **Django-Q2 / dramatiq / DB-backed queue (rejected).** Less standard here; no advantage that pays for the unfamiliarity.

### Why Redis as broker (vs RabbitMQ)
Redis is a one-line docker service, needs no AMQP setup, and doubles as the result backend. RabbitMQ would be heavier with no benefit at this scale. **Tradeoff:** Redis as a broker has weaker delivery guarantees than RabbitMQ; irrelevant at this volume and criticality.

## Where things run (coherence with the existing setup)

The repo's convention is already clear and must be preserved:

- `docker-compose.yml` holds **supporting infrastructure** (Postgres, Mailpit).
- Application processes run **on the host via `task`** (`task backend`, `task frontend`).

So:

- **Redis → `docker-compose.yml`** (it is infrastructure, like the DB), brought up by `task up`.
- **Celery worker → a host process run by `task`**, like the dev server — *not* docker-compose. Adding the worker to compose would split the convention.

The worker is the other half of "the backend," so **`task backend` launches both the Django dev server and the Celery worker together**: one command brings up everything an engineer needs to exercise billing emails and webhook delivery locally — there is no separate "did you remember to start the worker?" step to forget. Mechanically `task backend` runs two subtasks in parallel (`backend:server`, `backend:worker`), each of which stays individually runnable for debugging.

This keeps the mental model intact: *compose = infra; `task` = host processes*. We are only deciding that `task backend` means "the whole backend (server + worker)," not just the web server.

**Tradeoffs (acknowledged):**

- Server and worker logs interleave in one terminal. Fine for local dev; run `task backend:worker` alone when you want clean worker logs.
- `runserver` auto-reloads on code changes; the Celery worker does **not**. After editing task code you must restart the worker (Ctrl-C `task backend` and re-run, or restart just `task backend:worker` in its own terminal). An optional `watchmedo auto-restart` wrapper could auto-reload the worker, but it pulls in a `watchdog` dependency and is deferred.

**Alternative considered — a standalone `task worker` in its own terminal (rejected).** It gives cleaner log separation and simpler signal handling, but reintroduces the "forgot to start the worker" footgun a reviewer cloning the repo will hit. Bundling both under `task backend` favours the one-command dev experience; the separately-runnable `backend:worker` subtask preserves the standalone option when you want it.

## Implementation steps

1. **`docker-compose.yml`** — add a `redis` service:
   - image `redis:7-alpine`, port `6379:6379`. No volume needed (broker state is ephemeral).
2. **`backend/pyproject.toml`** — add dependencies `celery>=5.4,<6.0` and `redis>=5.0` (the Python Redis client Celery needs). `uv run` auto-syncs these on the next invocation, so `task backend` picks up Celery with no separate install step.
3. **`backend/config/celery.py`** — create the Celery app:
   - `app = Celery('yunojuno')`
   - `app.config_from_object('django.conf:settings', namespace='CELERY')`
   - `app.autodiscover_tasks()`
4. **`backend/config/__init__.py`** — `from .celery import app as celery_app` / `__all__ = ('celery_app',)` so the app loads with Django.
5. **`backend/config/settings.py`** — add, via `decouple.config`:
   - `CELERY_BROKER_URL` (default `redis://localhost:6379/0`)
   - `CELERY_RESULT_BACKEND` (default `redis://localhost:6379/1`)
   - `CELERY_TASK_SERIALIZER = 'json'`, `CELERY_ACCEPT_CONTENT = ['json']`, `CELERY_RESULT_SERIALIZER = 'json'`
   - `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True` — Celery 5.x prints a deprecation warning on worker startup without it. Setting it explicitly silences the warning *and* makes the worker retry the broker connection at boot, so starting `task backend` before Redis is fully up (or restarting Redis) recovers instead of crashing the worker.
6. **`Taskfile.dist.yml`** — make `task backend` start the dev server *and* the worker together:
   - Move today's server command into `backend:server` → `uv run python manage.py runserver` (`dir: backend`).
   - Add `backend:worker` → `uv run celery -A config worker -l info` (`dir: backend`).
   - Redefine `backend` as a thin task that runs both in parallel: `deps: [backend:server, backend:worker]` (Taskfile runs `deps` concurrently; with no `cmds` of its own, `task backend` just keeps both processes up). Each subtask remains runnable on its own.
   - **Behaviour note:** because these run as parallel `deps`, if either process exits non-zero (e.g. the worker crashes) `task backend` tears down both. In dev that is desirable — a dead worker is immediately visible rather than silently absent — but it is a deliberate change from the standalone-`task worker` model, where the server kept running independently of the worker.
   - *(Optional, not needed yet)* `backend:beat` → `uv run celery -A config beat -l info`, for if/when billing becomes scheduled.
7. **Smoke task** — `backend/core/tasks.py` with a trivial `@shared_task def ping(): return 'pong'` to prove the wiring end-to-end before any business logic depends on it. (`core` is the natural home — it is the near-empty shared app.)
8. **`README.md`** — document the new infra for colleagues in *Getting started*: note that `task up` now also boots Redis, and that `task backend` now runs the worker too. Drafted addition (apply when the infra lands):

   > **Running background jobs.** `task up` now also starts Redis (the Celery broker) alongside Postgres and Mailpit. `task backend` now starts **both** the Django dev server and the Celery worker (invoice emails + webhook delivery) — one command, no separate worker terminal. The worker runs on the host, so webhooks deliver to `http://localhost:8027/hook`.
   >
   > Need them apart — e.g. clean worker logs, or restarting the worker after editing task code? Run them individually:
   >
   > ```bash
   > task backend:server   # Django dev server only
   > task backend:worker   # Celery worker only
   > ```

## Testing strategy (decided here, used by Phases 2 & 3)

The test approach for async work is a real decision and is settled now so B and C are consistent:

- **Unit-test the task *function* directly** (call `send_invoice_email(invoice_id)` as a plain function) for the logic.
- **Assert *enqueue* at call sites** with a mock (`patch('...send_invoice_email.delay')`) to prove the trigger fires the task.
- **Prefer this over `CELERY_TASK_ALWAYS_EAGER`.** EAGER changes `transaction.on_commit` and error semantics and can hide real bugs (a task that only works because it ran inline). This repo's suite is **pytest-django function tests** (no `unittest.TestCase` anywhere — confirmed), so to test the on-commit chain use pytest-django's `django_capture_on_commit_callbacks(execute=True)` fixture, or mark the test `@pytest.mark.django_db(transaction=True)` for a real commit.
- **Document the `on_commit` gotcha now:** under the default `@pytest.mark.django_db` (each test runs in a transaction that is rolled back), `transaction.on_commit` callbacks do **not** fire unless captured. Phase 2's email test must account for this (the capture fixture above) and assert sends via pytest-django's `mailoutbox` fixture.

Manual smoke check: `task up` (boots Redis) → `task backend` (starts the server *and* the worker) → in a Django shell `from core.tasks import ping; ping.delay()` → worker logs `pong`.

## Deliberately deferred (→ CANDIDATE_NOTES.md)

- **Celery Beat / scheduled billing** — not built. The run is admin-triggered and idempotent (Phase 2), so a cron is a trivial future add, not a requirement.
- **Flower / task monitoring** — out of scope here.
- **Dead-letter queue** — replaced by the explicit `exhausted` delivery state + manual resend in Phase 3.

## Done when

- [ ] `redis` runs via `task up`.
- [ ] Celery app boots with Django (`config/__init__.py` exposes `celery_app`).
- [ ] `task backend` starts the dev server **and** the worker, and the worker connects to Redis (`task backend:worker` also runs standalone).
- [ ] `ping.delay()` round-trips through the worker.

---

## Addendum — Logging (added after the initial infra landed)

> **Context:** added once the billing run (Phase 2) existed and needed to be observable. Logging is the same *shape* of concern as the queue itself — cross-cutting infrastructure that Phase 0 owns and every phase consumes — so it belongs here, not in a business-logic phase. The Celery angle in particular (below) is squarely Phase 0's.

### Why

The async work this phase introduced is operationally invisible by default:

- **App `INFO` logs are mute.** With no `LOGGING` setting, our app loggers (`billing.*`, `webhooks.*`) fall through to Python's last-resort handler, which only emits `WARNING`+. So every `logger.info(...)` — including the billing run's "started / completed" trail — never appears; only tracebacks (`logger.exception`) surface. The most useful operational lines are exactly the ones that vanish.
- **Celery hijacks logging in the worker.** By default the worker reconfigures the root logger itself (`worker_hijack_root_logger` defaults on), so the *same* code logs differently depending on which process runs it: a billing run kicked off by the button (web process) vs. by Beat (worker) would format and level inconsistently.
- **The billing run especially needs a trail.** It fans out across companies and one company can fail without sinking the batch (Phase 2 §3). Without a start/completion summary and per-failure tracebacks, a *partial* run is silent about what it skipped.

### Decision: one basic dictConfig, shared by Django and the worker

- **`LOGGING` in `settings.py`** — a single `dictConfig`: a console `StreamHandler`, a readable format (`{asctime} {levelname} {name}: {message}`), root at `INFO`, and explicit `billing` / `webhooks` / `django` loggers at `INFO`. `disable_existing_loggers: False` keeps Django's own loggers alive; the explicit per-app entries (`propagate: False`) keep each line single instead of double-handled via root.
- **The worker uses that *same* config via the `setup_logging` signal** (`config/celery.py`):
  ```python
  @setup_logging.connect
  def configure_logging(**kwargs):
      dictConfig(settings.LOGGING)
  ```
  Connecting `setup_logging` is the linchpin: it tells Celery **not** to configure its own logging and to use ours instead, so the worker and the web process log identically.

### Alternatives considered

- **`CELERY_WORKER_HIJACK_ROOT_LOGGER = False` (instead of the signal).** Lighter — it just stops Celery clobbering the root logger — but it leaves the worker's task-logger formatting to Celery's own defaults, so worker lines wouldn't match the Django format. The `setup_logging` signal makes both processes consistent; chosen for that consistency.
- **Structured / JSON logging (`structlog`, `python-json-logger`).** Better for log aggregation in production, but over-engineering for a take-home and a new dependency. **Deferred** — the basic config is a clean upgrade point.
- **Leave Django's defaults.** Rejected: the billing run's operational trail would stay mute (see *Why*).

### Tradeoffs (acknowledged)

- **Console only** — no file handler, rotation, JSON, or request-id correlation. Fine for local dev; the `dictConfig` is the seam to add handlers later.
- **Worker + server still share one terminal** under `task backend` (per the earlier tradeoff), so their lines interleave — now at least in a consistent format. `task backend:worker` alone still gives a clean worker stream.

### Implementation

1. **`backend/config/settings.py`** — add the `LOGGING` dictConfig described above.
2. **`backend/config/celery.py`** — add the `setup_logging` receiver that calls `dictConfig(settings.LOGGING)`.
3. **First consumer — the billing run (Phase 2).** `BillingRun.generate()` logs a **start** line and a **completion summary** (`N billed, K failed`, with the failure count now tracked); per-company failures keep `logger.exception` (full traceback) with the run id; the run view logs the **trigger + actor**. A button run now reads:
   ```
   INFO billing.views:  Billing run 7 triggered by admin@northstar.test for 2026-04
   INFO billing.models: Billing run 7 started: period=2026-04-01, scope=NorthStar Consulting
   INFO billing.models: Billing run 7 completed: 1 billed, 0 failed
   ```

### Done when

- [ ] `LOGGING` config in `settings.py`; app `INFO` logs surface on the console.
- [ ] Celery `setup_logging` receiver connected, so the worker uses Django's config (verify: a task's `INFO` log appears in `task backend:worker` output, in the same format).
- [ ] The billing run logs start, completion (with billed/failed counts), and per-failure tracebacks.

### Still deferred (→ CANDIDATE_NOTES.md)

- Structured/JSON logging, log shipping/aggregation, request-id correlation, and per-environment verbosity (e.g. a `DEBUG`-driven or env-var log level).
