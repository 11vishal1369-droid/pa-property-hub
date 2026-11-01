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
