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

---
# Round 4: Deployment package (user's words)
"Prepare this app for deployment on an external Ubuntu 22.04 VPS (Hostinger). Create a deployment package with: a Dockerfile, a docker-compose.yml, an Nginx config to serve the admin panel at propertysavailable.com/admin and the backend API at propertysavailable.com/api, and a deploy.sh script that installs Docker, pulls the image, and starts the container. Do not change any app logic or Firebase config. Do not deploy anywhere."
Note: Round 3 (Firestore mapping + live sync) is paused waiting on user decisions; do not change it in this round.

---
# Round 3 resumed: user decisions
- Firestore data: "Show it as-is, real registrations will add to it" (treat current Firestore records as the app's data, no test labels).
- Banners, coupons, notifications: admin panel manages "The app's Firebase ones, so changes show in the app directly" (read/write the app's Firestore collections banners, coupons, notifications).
- Mobile backend: no answer; default = read Firestore directly, no dependency on propertysavailable.com/api.
- Deployment: "Yes, the panel's backend should use /api" (keep Nginx /api -> admin backend).
Build the Firestore mapping and real-time sync, remove sample data once real data loads, keep audit/archive/no-hard-delete/Aadhaar masking. Retest.

---
# Round 5: Public website + web content editor (user's words)
"Only do this task. Do not continue any pending work. Stop and report when done.
Add a public website with five pages served from the same app: homepage at /, terms and conditions at /terms-conditions, privacy policy at /privacy-policy, refund policy at /refund-policy, and contact us at /contact-us. Each page content should come from the Word documents I have uploaded -- use them as the exact content for each respective page. Add a private web content editor at /webcontent with its own login (separate from the admin panel login) where the owner can edit the text content of all five pages including links and contact details, and save changes that reflect on the public pages instantly. The editor should not touch any admin panel data or the /api backend. Update the Nginx config and deployment package to include these new routes."
Uploaded documents:
- Homepage: https://customer-assets-m6fa6gv7.emergentagent.net/job_pa-property-hub--6bckfbno/artifacts/c38c60b04ac2e4c4_Homepage.docx
- Terms and Conditions (.doc, old Word format): https://customer-assets-m6fa6gv7.emergentagent.net/job_pa-property-hub--6bckfbno/artifacts/79df929778c46a4f_Terms%20and%20Conditions.doc
- Privacy Policy: https://customer-assets-m6fa6gv7.emergentagent.net/job_pa-property-hub--6bckfbno/artifacts/0c0df2362c59556c_Privacy%20Policy.docx
- Refund and Cancellation Policy: https://customer-assets-m6fa6gv7.emergentagent.net/job_pa-property-hub--6bckfbno/artifacts/4dbe64c2f86859df_REFUND%20AND%20CANCELLATION%20POLICY.docx
Note: no separate Contact Us document was uploaded; use contact details found in the uploaded documents, editable in /webcontent.

---
# Round 6: Public pages colour theme (user's words)
"Only do this task. Do not continue any pending work. Stop and report when done.
Change the home, terms conditions, privacy policy, refund policy pages colour theme to match the attached reference image, using dark navy, royal blue, white and orange accents. Keep the existing layout and functionality unchanged."
Note: no reference image was actually received; use dark navy, royal blue, white and orange accents. Do not continue the pending Round 5 items (deployment package, tests).

---
# Round 7: Logo + premium look (user's words)
"Only do this task. Do not continue any pending work. Stop and report when done.
Use this logo.
make colour look premium and attractive for home, terms conditions, privacy policy,refund policy pages..
Change style make big and use symbol for below things:
LOGIN OR REGISTER AS A TENANT
LOGIN OR REGISTER AS A PROPERTY OWNER"
Logo (image is inside this Word document; extract it): https://customer-assets-m6fa6gv7.emergentagent.net/job_pa-property-hub--6bckfbno/artifacts/5e559532079024aa_Logo.docx

---
# Round 8: Duration-based agreement fees (user's words)
"Only do this task. Do not continue any pending work. Stop and report when done.
From /Admin remove "Fees" from setting. of /admin
and add option "Agreement Fees" to change fees for agreement based on duration. example: 30 days price will be diffrent, 90 days will be diffrent. and it will reflect in mobile apk."
Notes: the old Fees tab also held the owner platform subscription fee (₹99/365 days) and tenant fees; those must stay editable somewhere, not be lost. Past agreement fees and payments must not change. "Reflect in mobile apk": the app reads Firestore, so the duration fees must be available to the mobile app without an APK update (and via the existing /api/app fee endpoints).

---
# Round 9: Deployment routing (user's words)
"Only do this task. Do not continue any pending work. Stop and report when done.
Make sure frontend/yarn.lock exists and is not ignored by .gitignore. If it is missing, run yarn install inside the frontend folder to generate it.
Set up Nginx configuration so that:
propertysavailable.com and www.propertysavailable.com serve the main website (frontend)
admin.propertysavailable.com serves the admin panel. Both domains point to the same VPS IP 201.18.206.131. Both should run from the same project and Docker deployment.
Update docker-compose.yml and all deploy scripts so a single docker compose up -d --build from the /opt/propertysavailable/deploy folder starts everything — backend API, main website frontend, admin panel, and MongoDB — with the Nginx routing above.
Save everything to GitHub after all changes are made.
Do not make any changes to features, data, or existing functionality. Only fix deployment, yarn.lock, and Nginx routing."
Notes: yarn.lock already exists and is not ignored (checked). Include the web content service (/webcontent editor and its API) in the deployment so the website and editor work. Saving to GitHub is done by the user via the "Save to GitHub" button; the builder cannot push.
