# Seed Users

Two accounts are pre-loaded with realistic data. Use these to explore the application.

## Company Admin

| Field    | Value                     |
|----------|---------------------------|
| Email    | `admin@northstar.test`    |
| Password | `testpass123`             |
| Role     | Company admin — NorthStar Consulting |

The admin account sees all contracts and timesheet entries for NorthStar Consulting. Use `/billing` and `/developers` to explore the stubbed pages.

## Freelancer

| Field    | Value                     |
|----------|---------------------------|
| Email    | `alex@freelance.test`     |
| Password | `testpass123`             |
| Role     | Freelancer — Alex Rivera  |

Alex has active contracts at **both** companies (NorthStar and Meridian Digital), so the contract list shows work across multiple clients. Use `/contracts/:id/submit` to log new hours against an active contract.
