# Requirements: PA Super Admin Panel

## Core Value
Admin panel for the PA Property Management Platform: a complete central view and control of owners, tenants, properties, agreements, payments, and historical records. Build as a separate web admin panel on its own backend and database (existing Owner/Tenant apps are not in this workspace; build with its own database and realistic sample data so every screen can be tested; design so it can connect to the existing backend later). Payment gateway: keep generic. Login: email and password with individual admin accounts; Settings must include an option to change admin password.

## Personas & Roles
I am the business owner and authorized administrator of PA. I need complete Super Admin access. Roles: Super Admin, Finance Admin, Owner Support Admin, Tenant Support Admin, Property Management Admin, Agreement Verification Admin, Read-Only Admin; permissions configurable.

## Features
The full specification (sections 1-20) the user gave is saved verbatim in /app/memory/product/spec_full.md. Implement all of it: dashboard with date ranges, owners, properties, tenants, agreements (with versions), payments & finance, subscriptions, coupons, complaints, leaving requests & settlements, banners, notifications, reports (Excel/CSV/PDF), archived records, admin users & permissions, audit logs (tamper-resistant), settings (fees: ₹99 owner platform fee for 365 days, ₹99 agreement fee, tenant fees ₹0, all editable), central historical search. No hard delete; soft delete/archival only. Aadhaar masked by default, restricted permission, access logged, encrypted.

## UI/UX Rules
Modern professional responsive dashboard (desktop/laptop/tablet), blue and orange PA brand colours, left sidebar with the 17 listed sections. All buttons, filters, tables, edits, downloads must be functional against the real backend and database.

## Integrations
Generic payment gateway settings (no specific provider).

## Seed Data
Yes, include realistic sample data (owners, tenants, properties, agreements, payments, complaints, etc.) so every screen can be tested.

---
# Round 2: Required Updates Only (user's words, verbatim intent)
Update the existing Admin Panel. Do not rebuild the panel or change existing working features. Implement only the following changes. Reuse existing tables/APIs; minimal changes; minimum unnecessary credit consumption. Owner/Tenant Apps are not in this workspace: expose/extend the backend APIs they will consume (fees, banners, notifications, coupons, complaint replies, move-out status) so changes sync automatically.

1. GST on all payments (GST inclusive, 18%): Base = Total Received ÷ 1.18; GST = Total − Base; Total = Base + GST. Show Total Received, Base Amount, GST Amount, Total in payment details, reports and receipts, for agreement fees, platform subscriptions, and every other applicable payment.
2. Property-wise agreement fees: editable Agreement Fee Management in Settings for categories PG – Boys, PG – Girls, PG – Co-living/Mixed, Flat/Apartment, Independent House, Office, Shop, Chawl, Godown, Shed, Warehouse, Open Space/Land, Other. Property category automatically determines the fee; exposed to Owner App/payment flow. Do not overwrite historical agreement fees or completed payments when prices change.
3. Aadhaar e-Sign approval: remove the manual Approve Agreement button and manual approval workflow. Completion depends on successful Aadhaar e-sign by both owner and tenant via an authorized e-sign provider; when both succeed, status auto-updates to Signed/Completed; otherwise stays Pending Signature. Show each party's verification and signing status separately, with signing date, time, provider reference, verification result; preserve provider evidence. No manual admin substitute. Provider: not yet chosen/no account — build provider-configurable integration (settings for provider credentials, webhook/callback endpoint that updates status only from verified provider responses). Do NOT fake signatures.
4. Agreement detail shows: Agreement Number, Owner Details, Tenant Details, Property ID and Category, Agreement Fee, GST Breakdown, Coupon Discount, Final Amount Paid, Payment Date, Method, Transaction ID, Payment Status, Owner e-Sign Status, Tenant e-Sign Status, complete Agreement PDF, Download Agreement option.
5. Complaints split into tabs Owner Complaints / Tenant Complaints. Detail: Complaint ID, Raised By, Owner/Tenant info, Property info, Description, Photos/Videos, Responses and Conversation History, Status, Resolution. Owner and tenant exchange replies within the complaint (API for apps); admin views/monitors conversation and updates status.
6. Leaving Requests show: ID, Requested By, Tenant, Owner, Property and Bed/Room/Seat, Requested Leaving Date, Approval Status, Approved By, Approval Date, Rejection Reason, Outstanding Rent, Security Deposit, Deductions, Refund Amount, Final Settlement, Move-Out Status. Admin controls to update move-out and final settlement status; owner can update from Owner App (API), synced. Clearly identify who requested, who accepted, owner vs admin approval. Preserve all status and settlement history.
7. Banners split into Owner App Banners / Tenant App Banners, managed separately (add, edit, activate, deactivate, remove from display, reorder); each reflects only in its app.
8. Notifications split into Notifications to Owners / Notifications to Tenants. Super Admin can send to all owners, all tenants, selected/multiple recipients, title and message, schedule, view history and delivery status. Never cross audiences.
9. Coupon recipient eligibility: All Owners, Selected Owner, Multiple Selected Owners, All Tenants, Selected Tenant, Multiple Selected Tenants, Both Owners and Tenants. Search/select users by name, mobile, Owner ID, Tenant ID. Also configure applies-to Agreement Fee / Platform Subscription Fee, fixed or percentage, min amount, max discount, usage limit, start/expiry, active. Backend validates eligibility and discount.
Test each updated workflow with actual backend data. No dummy buttons.

---
# Round 3: Firebase connection (user's words)
"Connect this admin panel to Firebase project new-accounting-b2d50 using the credentials in Secrets (FIREBASE_PROJECT_ID, FIREBASE_STORAGE_BUCKET, FIREBASE_CLIENT_EMAIL, FIREBASE_SERVICE_ACCOUNT_JSON). Read owner registrations, tenant registrations, properties, agreements, payments and complaints from Firestore collections: users, properties, units, rental_accounts, agreements, payments, complaints, leaving_requests, notifications. When a new owner or tenant registers in the mobile app (backend at FIREBASE_MOBILE_APP_URL), their data must automatically appear in this admin panel via Firestore in real time. Do not use dummy or static data."
Notes: keys are saved in backend Secrets (also FIREBASE_MOBILE_APP_URL). Inspect the real Firestore schema before mapping. Sample/seed data must not be mixed with real data; real Firestore data replaces it. Keep audit/archive/no-hard-delete guarantees. Also first: read /app/test_reports/iteration_2.json and fix anything it found from Round 2.
