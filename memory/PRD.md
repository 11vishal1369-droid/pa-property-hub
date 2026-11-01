# PRD — PA Super Admin Panel

## Original problem
Build the PA Super Admin Panel described in /app/memory/product/requirements.md and spec_full.md: a separate admin web panel (own FastAPI + MongoDB backend and seed data) for the PA Property Management Platform. It covers owners, tenants, properties, agreements, payments, subscriptions, coupons, complaints, leaving requests, banners, notifications, reports, archive, admin RBAC, audit logs and settings. Nothing is ever hard-deleted, and Aadhaar is masked and encrypted.

## Architecture
- Backend: FastAPI (core.py auth/RBAC/audit, data.py generic list/export/edit/status/remarks, core_routes.py, ops_routes.py, seed.py, exports.py)
- Frontend: React + shadcn. Generic DataTable and FormDialog (with a required reason field). Pages for all 17 sections, plus /account/password and /search.
- Auth: JWT Bearer token. Login lockout is per account (5 failures → 15 min).
- Audit: hash-chained and append-only. Writes are serialised with a lock and retried. The audit entry is written before each change, or the change is rolled back if the audit write fails.

## Implemented
- 2026-10-31: MVP of all sections, with a test pass of 47/50 backend checks and all UI flows passing.
- 2026-11-01: Bug-fix round:
  - Concurrent audit writes no longer fail.
  - Change password moved to its own page, open to every admin.
  - Login lockout can no longer be dodged with a spoofed IP header.
  - A bad page number returns 400.
  - Coupon edits get the same validation as create, including end date after start date.
  - Concurrent refunds are blocked with a conditional update (409).
  - Admins can't change their own role or the Super Admin's role.
  - Settlements use the tenant's recorded deposit.
  - Amounts show 2 decimals.
  - Reopening a complaint clears the close reason.
  - The Save settings button only shows on the editable tabs.
  - The database was reset to clean seed data.

## Backlog
- P1: Integration with the existing Owner/Tenant app backend; a real payment provider; object storage for photos and documents.
- P2: Paging for global search results; Owner ID lookup in the manual-payment dialog; shadcn date pickers; broken-image placeholder on banners.
