# YunoJuno Fullstack Engineer Take-Home

Welcome to the YunoJuno Fullstack Engineer take-home test. We appreciate the time you're putting into this, as such we've done our best to a starting point which represents a reasonable project.

This document should explain everything, read it end-to-end before you get started. If you have any issues or questions, don't be afraid to reach out to your main recruitment contact.

This code base is a small, deliberately incomplete slice of a product like YunoJuno, using similar tech to what we use day to day. The goal of the application is to let companies book freelancers, freelancers can log hours, hours can be approved, and hours then roll up into bills. The project is built to look and feel like an existing product codebase, most of it is clean but there are a few rough edges.

Below we outline 3 possible tasks, you should select two of them to complete.

---

## Technology stack

- **Backend:** Python 3.11 / Django + Django REST Framework
- **Frontend:** React 18 + TypeScript + Vite, Tailwind for styling
- **Database:** Postgres 18
- **Email capture:** Mailpit on `localhost:8025` — anything sent via Django's email backend shows up in its web UI
- **Webhook capture:** a small local receiver on `localhost:8027` that logs inbound requests with headers and body to its own web UI

Everything runs locally via docker-compose, there are no external dependencies or accounts to setup.

---

## Getting started

We provide a nix flake to set up a developer environment quickly with the right tool versions. If you're not familiar with nix or prefer to use another tool, here are the main tools and versions you'll need.

- Python 3.11
- uv 0.11
- Node.js 24
- pnpm 10.33
- Task 3
- Docker and Docker Compose (any modern version)

Once those tools are installed you can use the following tasks provided by the [Taskfile](./Taskfile.dist.yml) to get going.

```bash
task up        # boot the supporting stack
task seed      # load seed data (run once after task up)
task test      # run backend tests
task backend   # run backend dev server
task frontend  # run frontend dev server
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api/`
- Django admin: `http://localhost:8000/admin/`
- Mailpit: `http://localhost:8025`
- Webhook receiver: `http://localhost:8027`

Seed credentials are in `seed_users.md`. There's one company admin and one freelancer pre-loaded with realistic data — a handful of contracts, ~40 timesheet entries in mixed states across submitted, approved, and rejected.

---

## The domain

The product models a tiny version of YunoJuno's contracts world:

- A **Company** hires **Freelancers** via a **Contract** — a fixed daily rate, a start and end date, a status.
- Freelancers log a **TimesheetEntry** per day worked. Entries move through `draft` → `submitted` → `approved` or `rejected`.
- Approved entries are eventually billed.

**What works today:**
- Login as either user
- Freelancer view: see your contracts, see your timesheets on each, submit hours
- Company admin view: see your contracts, see timesheets on each as a table, create a new contract
- Standard auth, basic CRUD endpoints, a few filters

**What's deliberately rough or missing:**
- The approval workflow is just a status field with no UI worth using
- The billing page exists but every endpoint behind it is stubbed — clicks return 200, nothing happens
- The developer/integrations page exists but everything on it is a stub
- A few small inconsistencies in the existing code, left as-is

You shouldn't need to fix rough edges outside your chosen tasks. If something blocks you, fix it and mention it in your notes.

---

## Your task

Pick **two** of the three tasks below, implement them, and explain your work.

Choose the two tasks you think make the best submission. In your notes, explain what you picked, what you left out, and why.

You can assume the other task gets built later by someone else, so think about what will fit with later work.

---

### Task A — Frontend: Approval Inbox

A "Pending Approvals" page for company admins.

Right now, an admin has to click into each contract to see what's waiting on them. Build a single screen that surfaces every `submitted` timesheet entry across all their contracts, with the ability to action them in bulk.

**The backend is ready.** `GET /api/timesheets/?status=submitted` returns flat, unaggregated data. `PATCH /api/timesheets/<id>/` accepts `{"status": "approved"}` or `{"status": "rejected", "rejection_reason": "..."}`. There's no bulk endpoint — that's part of the decision space.

**What you build:**
- The page itself, using the component primitives that fit the existing frontend
- Bulk approve / bulk reject, with a reason required on rejection
- A running total of the cost being approved (hours × contract rate)
- Filters that matter: by contract, by freelancer, by date range
- Clear empty, loading, and error states

**What we're looking for:** how you compose UI, how you handle state, how aggressive you are with optimistic updates, what you choose to test on the frontend, and small product decisions such as the empty state, rejection flow, and partial failures during bulk approval.

---

### Task B — Backend: Monthly billing run

A way for finance to generate monthly invoices from approved hours.

**The frontend is fully wired.** The "Billing" page has a month/year picker and a "Run billing" button that POSTs to `/api/billing/runs/`. Below it, a list of generated invoices reads from `GET /api/invoices/?month=YYYY-MM`. Clicking an invoice opens a detail view from `GET /api/invoices/<id>/`. All three endpoints currently exist as stubs that return hardcoded payloads. The UI is wired to these endpoints, but the backend does not yet implement the behaviour.

**What you build:**
- An `Invoice` model — one per Company × Freelancer × month, with line items per approved entry, totals, period bounds, generation timestamp
- A real implementation of `POST /api/billing/runs/` that scans all approved entries in the period and creates invoices
- Real implementations of `GET /api/invoices/` (filterable by month) and `GET /api/invoices/<id>/` (with line items)
- **Delivery via email.** When an invoice is created, an email goes to the company's `billing_email` (seeded) and to the freelancer. Mailpit catches everything — check `localhost:8025` to see what arrived. Choose an approach: HTML or plain text, one email or two, and what the email contains.

**Two things you must get right:**

1. **Idempotency.** Re-running billing for the same month must not double-create. This endpoint will get retried, scheduled, and accidentally clicked twice. Model it accordingly.
2. **Partial months.** Contracts that start or end mid-period are common. Your billing run for March needs to behave correctly when a contract ran 12 Feb – 18 Mar.

**A note on the medium.** In production, an invoice would be a PDF or an e-invoice document with a legally compliant schema. For this exercise, an email containing the invoice content is a stand-in for that delivery — we're not asking you to generate a legal invoice. Treat email as the transport, and model the invoice as if you might need to render it to PDF later.

**What we're looking for:** data modelling, idempotency thinking, transaction boundaries (what happens if the email send fails *after* the invoice row is committed?), and what you choose to test.

---

### Task C — Fullstack: Outbound webhooks

A minimal developer integration: let a company admin configure webhook destinations and receive events from the system.

**The frontend has a stubbed "Developer settings" page.** A form for adding a destination URL, a table for listing configured endpoints. The form POSTs to `/api/webhook-endpoints/`, which returns a hardcoded response and does nothing. There's a `webhook-receiver` service running in docker-compose on `localhost:8027` with its own web UI — point your webhooks at `http://webhook-receiver:8027/hook` (from inside the docker network) or `http://localhost:8027/hook` if delivering from outside, and you'll see them land.

**What you build:**
- A data model for webhook endpoints — URL, a secret, active/disabled state, anything else you think matters
- Configuration UI: create, edit, delete, and a "send test event" action
- A delivery log surfaced in the UI: what fired, when, response code, attempt number
- Delivery for **one system event of your choice** — pick one from `timesheet.submitted`, `timesheet.approved`, `contract.created`, or another you can justify. The choice is part of the exercise.
- A sensible payload schema. Version it.

**Decisions you'll need to make, and we'll ask about:**
- Sync or async delivery, and how you implement it. There's no queue pre-configured — whether you add one and what you pick is part of your answer.
- Retry policy on failure: how many attempts, what backoff, when do you give up
- How you sign the request, if at all
- Idempotency on the receiver side — how does the consumer dedupe
- What happens when the destination is down for hours

You don't need to implement every one of these — but you do need to articulate what you cut and why.

**What we're looking for:** how you model an external integration boundary, how you reason about failure, and what you defer deliberately.

---

## On AI tooling

Use it. We do, and we expect you to.

We don't grade "AI usage" as a specific axis, so we don't need to see prompt logs or screenshots. Instead we're interested in seeing a well rounded submission that displays good engineering with the aid of AI tools. We're also interested in understanding a bit about your chosen tools, workflow, and experience using AI tools for this project.

---

## What to deliver

Deliver the final project, plus a `CANDIDATE_NOTES.md` at the root covering:

1. **What you built and why.** We want to know how you made the decision of which tasks to tackle, and which one you decided not to do.
2. **Key implementation notes.** Give us some details on the approach you took to each task, and why you made particular decisions.
3. **Your workflow.** What tools and approach did you use to complete the tasks? Did you use any AI tools, if so how was that experience?
4. **Next steps.** If you had another four hours on this, what would you do.

Half a page to a page is the right length, we read it all in detail along with the rest of your submission.

---

## Time

We don't set a hard cap. Most candidates using AI tooling finish in a few hours. If you find yourself spending a full day on this, something's gone wrong — get in touch before going further.

If you have questions about the brief, anything blocking, or anything ambiguous: reach out to your primary recruitment contact.
