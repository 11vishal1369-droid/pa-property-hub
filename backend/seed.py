import os
import random
from datetime import datetime, timezone, timedelta, date
from core import db, hash_password, encrypt, MODULES, now_iso

R = random.Random(42)
FIRST_M = ["Rahul", "Amit", "Suresh", "Vikram", "Sanjay", "Prakash", "Rohan", "Nitin", "Ajay", "Mahesh", "Ganesh", "Sachin", "Deepak", "Kiran", "Omkar", "Tushar", "Yash", "Aniket"]
FIRST_F = ["Priya", "Sneha", "Pooja", "Anjali", "Kavita", "Neha", "Swati", "Rutuja", "Shruti", "Meera", "Aarti", "Komal", "Sayali", "Manasi"]
LAST = ["Patil", "Deshmukh", "Kulkarni", "Joshi", "Pawar", "Jadhav", "Shinde", "More", "Gaikwad", "Chavan", "Bhosale", "Sharma", "Mehta", "Naik", "Kale", "Sawant"]
CITIES = ["Pune", "Mumbai", "Nashik", "Nagpur", "Thane", "Aurangabad", "Kolhapur"]
AREAS = ["Kothrud", "Baner", "Hinjewadi", "Wakad", "Viman Nagar", "Andheri East", "Dadar", "College Road", "Dharampeth", "Ghodbunder Road", "Shivaji Nagar", "Aundh"]
PHOTOS = ["https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800&q=70",
          "https://images.unsplash.com/photo-1624204386084-dd8c05e32226?w=800&q=70",
          "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=800&q=70"]
TYPES = {"PG": ["PG"], "Residential": ["Flat", "Apartment", "Independent House", "Chawl"],
         "Commercial": ["Office", "Shop", "Godown", "Shed", "Warehouse", "Open Space", "Other"]}
AGR_CATS = ["Flat Rent Agreement (Marathi)", "Independent House Rent Agreement (English)", "Boys PG Terms & Conditions (Marathi)",
            "Girls PG Terms & Conditions (Marathi)", "Commercial Rent Agreement"]
ALL_EDIT = {m: "edit" for m in MODULES}


def role_perms():
    v = lambda *ms: {m: "view" for m in ms}
    e = lambda *ms: {m: "edit" for m in ms}
    base = lambda d: {m: d.get(m, "none") for m in MODULES}
    return [
        ("Super Admin", "Full system access", ALL_EDIT, True),
        ("Finance Admin", "Payments, subscriptions, coupons, finance reports",
         base({**v("dashboard", "owners", "tenants", "properties", "agreements", "reports", "archive", "notifications"), **e("finance", "subscriptions", "coupons")}), False),
        ("Owner Support Admin", "Owner accounts and owner complaints",
         base({**v("dashboard", "properties", "agreements", "finance", "subscriptions", "reports", "notifications", "archive"), **e("owners", "complaints")}), False),
        ("Tenant Support Admin", "Tenant accounts, complaints, leaving requests",
         base({**v("dashboard", "properties", "agreements", "owners", "reports", "notifications"), **e("tenants", "complaints", "leaving")}), False),
        ("Property Management Admin", "Properties, occupancy and archival",
         base({**v("dashboard", "owners", "tenants", "complaints", "leaving", "reports", "archive"), **e("properties", "banners")}), False),
        ("Agreement Verification Admin", "Agreement verification queue",
         base({**v("dashboard", "owners", "tenants", "properties", "reports"), **e("agreements")}), False),
        ("Read-Only Admin", "View-only access", base(v(*[m for m in MODULES if m not in ("admins", "aadhaar")])), False),
    ]


def ts(days_ago, hour=None):
    d = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=R.randint(0, 12), minutes=R.randint(0, 59))
    return d.isoformat()


def person(gender=None):
    g = gender or R.choice(["Male", "Female"])
    first = R.choice(FIRST_M if g == "Male" else FIRST_F)
    return g, f"{first} {R.choice(LAST)}"


def phone():
    return f"9{R.randint(100000000, 999999999)}"


async def ensure_indexes():
    await db.admins.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    for c in ["owners", "tenants", "properties", "agreements", "payments", "subscriptions", "coupons", "complaints", "leaving", "banners", "notifications", "admins", "refunds", "tenancies"]:
        await db[c].create_index("id", unique=True)
    await db.payments.create_index("txn_ref", unique=True)
    await db.coupons.create_index("code", unique=True)
    await db.audit_logs.create_index("seq", unique=True)
    await db.audit_logs.create_index("record_id")


async def seed_core():
    for name, desc, perms, locked in role_perms():
        if not await db.roles.find_one({"name": name}):
            await db.roles.insert_one({"name": name, "description": desc, "permissions": perms, "locked": locked})
    email = os.environ["ADMIN_EMAIL"].lower()
    if not await db.admins.find_one({"email": email}):
        await db.admins.insert_one({"id": "ADM-10001", "name": "PA Super Admin", "email": email, "mobile": "9800000001", "role": "Super Admin",
                                    "status": "active", "password_hash": hash_password(os.environ["ADMIN_PASSWORD"]), "created_at": now_iso()})
        await db.counters.update_one({"_id": "ADM"}, {"$set": {"seq": 1}}, upsert=True)
        staff = [("Finance Admin", "finance@pa.com", "Meera Kulkarni"), ("Owner Support Admin", "ownersupport@pa.com", "Rohan Deshmukh"),
                 ("Tenant Support Admin", "tenantsupport@pa.com", "Sneha Patil"), ("Property Management Admin", "property@pa.com", "Vikram Jadhav"),
                 ("Agreement Verification Admin", "verify@pa.com", "Anjali Joshi"), ("Read-Only Admin", "readonly@pa.com", "Amit Shinde")]
        for i, (role, em, nm) in enumerate(staff):
            await db.admins.insert_one({"id": f"ADM-{10002 + i}", "name": nm, "email": em, "mobile": phone(), "role": role, "status": "active",
                                        "password_hash": hash_password("Staff@123"), "created_at": ts(200 - i * 10)})
        await db.counters.update_one({"_id": "ADM"}, {"$set": {"seq": 1 + len(staff)}}, upsert=True)
    if not await db.settings.find_one({"key": "global"}):
        await db.settings.insert_one({
            "key": "global", "version": 1, "owner_platform_fee": 99, "platform_validity_days": 365, "agreement_fee_default": 99,
            "agreement_fees": {c: 99 for c in AGR_CATS}, "tenant_fees": {"registration": 0, "agreement": 0, "monthly": 0},
            "coupon_applicability": {"agreement_fee": True, "platform_fee": True},
            "renewal": {"grace_days": 7, "reminder_days_before": 15, "auto_block_on_expiry": False},
            "gateway": {"provider_name": "Generic Gateway", "mode": "test", "key_id": "", "merchant_id": "", "webhook_url": "", "enabled": False, "secret_set": False, "secret_last4": ""},
            "tax": {"gst_enabled": False, "gst_percent": 18, "gstin": ""},
            "stamp_duty_info": "Stamp duty is a government levy as per the Maharashtra Stamp Act and is charged separately from PA service fees.",
            "registration_info": "Registration charges (if any) are payable to the Sub-Registrar office and are not part of PA platform or agreement fees.",
            "updated_at": now_iso()})


async def seed_data():
    if await db.owners.count_documents({}) > 0 or os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or await db.migrations.find_one({"_id": "firestore_cutover"}):
        return
    counters = {}

    def nid(p):
        counters[p] = counters.get(p, 0) + 1
        return f"{p}-{10000 + counters[p]}"
    owners, props, tenants, tenancies, agrs, pays, subs, comps, leaves, notifs, usages = [], [], [], [], [], [], [], [], [], [], []
    coupons = []
    today = date.today()
    for code, typ, val, mx, applies in [("WELCOME50", "percent", 50, 50, "both"), ("FLAT20", "fixed", 20, None, "agreement_fee"),
                                        ("PGSTART", "percent", 25, 30, "platform_fee"), ("DIWALI99", "fixed", 99, None, "both"),
                                        ("RENEW10", "percent", 10, 10, "platform_fee"), ("OLDPROMO", "fixed", 30, None, "both")]:
        coupons.append({"id": nid("CPN"), "code": code, "description": f"{code} promotional coupon", "discount_type": typ, "value": val,
                        "max_discount": mx, "min_amount": 50, "start_date": (today - timedelta(days=300)).isoformat(),
                        "end_date": (today + timedelta(days=-30 if code == "OLDPROMO" else 200)).isoformat(), "max_usage": 200,
                        "per_owner_limit": 2, "applies_to": applies, "status": "inactive" if code == "OLDPROMO" else "active", "used_count": 0,
                        "created_at": ts(300), "created_by": "admin@pa.com", "history": []})

    def make_pay(purpose, owner_id, amount, created, tenant_id=None, agreement_id=None, property_id=None, coupon=None):
        method = R.choices(["online", "manual"], [0.8, 0.2])[0]
        if method == "online":
            status = R.choices(["success", "failed", "pending"], [0.85, 0.1, 0.05])[0]
        else:
            status = R.choices(["approved", "pending", "rejected"], [0.6, 0.3, 0.1])[0]
        disc = 0
        if coupon and status in ("success", "approved"):
            disc = coupon["value"] if coupon["discount_type"] == "fixed" else amount * coupon["value"] / 100
            if coupon.get("max_discount"):
                disc = min(disc, coupon["max_discount"])
            disc = min(disc, amount)
            coupon["used_count"] += 1
            usages.append({"id": nid("CPU"), "coupon_id": coupon["id"], "code": coupon["code"], "owner_id": owner_id, "discount": disc,
                           "payment_id": None, "created_at": created})
        p = {"id": nid("PAY"), "txn_ref": f"{'GW' if method == 'online' else 'UTR'}{R.randint(10**10, 10**11)}", "purpose": purpose,
             "owner_id": owner_id, "tenant_id": tenant_id, "agreement_id": agreement_id, "property_id": property_id,
             "amount": round(amount - disc, 2), "discount": round(disc, 2), "coupon_code": coupon["code"] if disc else None,
             "refunded_amount": 0, "method": method, "gateway": "Generic Gateway" if method == "online" else None, "status": status,
             "receipt_no": nid("RCPT") if status in ("success", "approved") else None, "created_at": created,
             "failure_reason": "Bank declined" if status == "failed" else None, "history": []}
        if disc:
            usages[-1]["payment_id"] = p["id"]
        pays.append(p)
        return p

    for i in range(42):
        g, name = person()
        reg_days = R.randint(5, 420)
        status = R.choices(["active", "blocked", "suspended", "deactivated", "archived"], [0.78, 0.07, 0.05, 0.06, 0.04])[0]
        oid = nid("OWN")
        city = R.choice(CITIES)
        o = {"id": oid, "name": name, "gender": g, "dob": date(R.randint(1960, 1995), R.randint(1, 12), R.randint(1, 28)).isoformat(),
             "mobile": phone(), "email": f"{name.lower().replace(' ', '.')}{i}@gmail.com", "address": f"{R.randint(1, 99)}, {R.choice(AREAS)}, {city}",
             "city": city, "photo": None, "status": status, "created_at": ts(reg_days), "remarks": [], "status_history": [], "history": [],
             "subscription_status": "none", "subscription_start": None, "subscription_expiry": None}
        if status == "archived":
            o.update(archived_at=ts(2), archived_by="admin@pa.com", archive_reason="Owner requested account closure", archived_source="admin", status_before_archive="deactivated")
        owners.append(o)
        if R.random() < 0.85:
            start = today - timedelta(days=R.randint(0, min(reg_days, 400)))
            exp = start + timedelta(days=365)
            coupon = R.choice([c for c in coupons if c["applies_to"] in ("both", "platform_fee")]) if R.random() < 0.3 else None
            p = make_pay("platform_fee", oid, 99, datetime.combine(start, datetime.min.time(), timezone.utc).isoformat(), coupon=coupon)
            if p["status"] in ("success", "approved"):
                st = "active" if exp >= today else "expired"
                subs.append({"id": nid("SUB"), "owner_id": oid, "plan": "Platform 365 days", "amount": p["amount"], "start_date": start.isoformat(),
                             "expiry_date": exp.isoformat(), "status": st, "payment_id": p["id"], "created_at": p["created_at"], "history": []})
                o.update(subscription_status=st, subscription_start=start.isoformat(), subscription_expiry=exp.isoformat())
            else:
                o["subscription_status"] = "pending"
        for _ in range(R.randint(1, 3)):
            cat = R.choices(["PG", "Residential", "Commercial"], [0.4, 0.4, 0.2])[0]
            typ = R.choice(TYPES[cat])
            pid = nid("PRP")
            units = R.randint(4, 20) if cat == "PG" else (R.randint(1, 4) if cat == "Residential" else R.randint(1, 3))
            pstatus = "archived" if status == "archived" else R.choices(["active", "inactive", "blocked", "closed", "archived"], [0.82, 0.06, 0.03, 0.03, 0.06])[0]
            area = R.choice(AREAS)
            rent = R.choice([4500, 6000, 7500, 9000]) if cat == "PG" else (R.choice([12000, 15000, 18000, 25000]) if cat == "Residential" else R.choice([20000, 35000, 50000]))
            pr = {"id": pid, "owner_id": oid, "name": f"{area} {typ} {R.choice(['Residency', 'Heights', 'Nest', 'Plaza', 'Corner', 'Homes'])}",
                  "category": cat, "type": typ, "pg_gender": R.choice(["Boys", "Girls"]) if cat == "PG" else None,
                  "address": f"{R.randint(1, 300)}, {area}", "city": city, "photos": R.sample(PHOTOS, R.randint(1, 3)), "removed_photos": [],
                  "total_units": units, "unit_label": "Beds" if cat == "PG" else ("Rooms" if cat == "Residential" else "Seats/Units"),
                  "units": [{"label": f"{'B' if cat == 'PG' else 'U'}-{k + 1}", "rent": rent} for k in range(units)],
                  "rent": rent, "deposit": rent * 2, "status": pstatus, "occupancy_state": "vacant",
                  "created_at": ts(R.randint(1, reg_days)), "remarks": [], "status_history": [], "history": []}
            if pstatus == "archived":
                src = R.choice(["owner", "admin"])
                pr.update(archived_at=ts(R.randint(1, 30)), archived_by=o["email"] if src == "owner" else "admin@pa.com",
                          archive_reason="Removed by owner from Owner App" if src == "owner" else "Duplicate listing", archived_source=src, status_before_archive="active")
            props.append(pr)
            if pstatus in ("active", "archived"):
                for k in range(R.randint(0, min(units, 4))):
                    tg = pr["pg_gender"] and ("Male" if pr["pg_gender"] == "Boys" else "Female")
                    g2, tname = person(tg or None)
                    tid = nid("TNT")
                    join_days = R.randint(10, 380)
                    join = today - timedelta(days=join_days)
                    left = R.random() < 0.2
                    aad = f"{R.randint(2000, 9999)}{R.randint(1000, 9999)}{R.randint(1000, 9999)}"
                    tstat = "archived" if pstatus == "archived" and R.random() < 0.5 else R.choices(["active", "blocked", "suspended", "deactivated"], [0.85, 0.05, 0.04, 0.06])[0]
                    t = {"id": tid, "name": tname, "gender": g2, "dob": date(R.randint(1985, 2004), R.randint(1, 12), R.randint(1, 28)).isoformat(),
                         "mobile": phone(), "email": f"{tname.lower().replace(' ', '')}{counters['TNT']}@gmail.com", "photo": None, "selfie": None,
                         "father_name": f"{R.choice(FIRST_M)} {tname.split()[1]}", "mother_name": f"{R.choice(FIRST_F)} {tname.split()[1]}",
                         "permanent_address": f"{R.randint(1, 200)}, {R.choice(AREAS)}, {R.choice(CITIES)}", "current_address": pr["address"] + ", " + city,
                         "occupation": R.choice(["Software Engineer", "Student", "Accountant", "Sales Executive", "Teacher", "Business", "Designer"]),
                         "emergency_contact_name": f"{R.choice(FIRST_M)} {tname.split()[1]}", "emergency_contact_phone": phone(),
                         "owner_id": oid, "property_id": pid, "room": pr["units"][k]["label"], "join_date": join.isoformat(),
                         "leave_date": (join + timedelta(days=R.randint(5, join_days))).isoformat() if left else None,
                         "rent": rent, "deposit": rent * 2, "aadhaar_enc": encrypt(aad), "aadhaar_last4": aad[-4:], "aadhaar_masked": f"XXXX-XXXX-{aad[-4:]}",
                         "aadhaar_status": R.choices(["verified", "pending", "failed"], [0.8, 0.15, 0.05])[0],
                         "documents": [{"name": "Aadhaar (front)", "status": "verified"}, {"name": "Selfie", "status": "uploaded"}],
                         "status": tstat, "agreement_status": None, "created_at": datetime.combine(join, datetime.min.time(), timezone.utc).isoformat(),
                         "remarks": [], "status_history": [], "history": []}
                    if tstat == "archived":
                        t.update(archived_at=ts(3), archived_by="admin@pa.com", archive_reason="Property archived", archived_source="admin", status_before_archive="active")
                    tenants.append(t)
                    tenancies.append({"id": nid("TNY"), "tenant_id": tid, "property_id": pid, "owner_id": oid, "room": t["room"], "rent": rent,
                                      "deposit": rent * 2, "join_date": t["join_date"], "leave_date": t["leave_date"], "active": not left, "created_at": t["created_at"]})
                    if not left:
                        pr["occupancy_state"] = "occupied"
                    for m in range(min(join_days // 30, 4)):
                        rp = make_pay("rent", oid, rent, ts(max(join_days - 30 * m - 30, 0)), tenant_id=tid, property_id=pid)
                        rp["amount"] = rent
                    if R.random() < 0.8:
                        acat = (f"{pr['pg_gender']} PG Terms & Conditions (Marathi)" if cat == "PG" else
                                "Independent House Rent Agreement (English)" if typ == "Independent House" else
                                "Commercial Rent Agreement" if cat == "Commercial" else "Flat Rent Agreement (Marathi)")
                        aid = nid("AGR")
                        astat = R.choices(["pending_verification", "verified", "completed", "rejected", "draft"], [0.2, 0.4, 0.3, 0.05, 0.05])[0]
                        created = t["created_at"]
                        coupon = R.choice([c for c in coupons if c["applies_to"] in ("both", "agreement_fee")]) if R.random() < 0.25 else None
                        ap = make_pay("agreement_fee", oid, 99, created, tenant_id=tid, agreement_id=aid, property_id=pid, coupon=coupon) if astat != "draft" else None
                        content = (f"This agreement is entered into between the Licensor (Owner) and the Licensee (Tenant) for the premises described above. "
                                   f"Monthly rent Rs. {rent} payable on or before the 5th of every month. Security deposit Rs. {rent * 2} refundable "
                                   f"at the end of the term after deductions for dues and damages. Notice period: 30 days. "
                                   f"{'PG rules: visitors till 9 PM, no smoking, mess timings as notified.' if cat == 'PG' else 'Licensee shall not sub-let the premises.'}")
                        versions = [{"version": 1, "content": content, "created_at": created, "created_by": "system"}]
                        if R.random() < 0.2:
                            versions.append({"version": 2, "content": content + " Amended: Maintenance charges borne by Licensor.", "created_at": ts(5), "created_by": "admin@pa.com", "reason": "Owner requested amendment"})
                        a = {"id": aid, "category": acat, "owner_id": oid, "tenant_id": tid, "property_id": pid, "fee": 99,
                             "coupon_code": ap["coupon_code"] if ap else None, "discount": ap["discount"] if ap else 0,
                             "fee_paid": bool(ap and ap["status"] in ("success", "approved")), "payment_id": ap["id"] if ap else None,
                             "rent": rent, "deposit": rent * 2, "start_date": t["join_date"], "end_date": (join + timedelta(days=330)).isoformat(),
                             "owner_accepted_at": created if astat != "draft" else None, "tenant_accepted_at": created if astat not in ("draft",) else None,
                             "status": "archived" if tstat == "archived" else astat,
                             "verification": {"by": "verify@pa.com", "at": created, "decision": astat, "remarks": "Documents in order"} if astat in ("verified", "completed", "rejected") else None,
                             "versions": versions, "current_version": len(versions), "created_at": created, "status_history": [], "remarks": [], "history": []}
                        agrs.append(a)
                        t["agreement_status"] = a["status"]
    by_admin = ["ADM-10003", "ADM-10004", "ADM-10002", None]
    subjects = [("Water leakage in bathroom", "Maintenance"), ("Wi-Fi not working", "Amenities"), ("Deposit refund delayed", "Payment"),
                ("Owner not responding", "Behaviour"), ("Electricity bill dispute", "Payment"), ("Noise from neighbours", "Behaviour"),
                ("Agreement copy not received", "Agreement"), ("Lift not working", "Maintenance")]
    active_tenants = [t for t in tenants if t["status"] == "active"]
    for _ in range(45):
        t = R.choice(tenants)
        s, cat = R.choice(subjects)
        st = R.choices(["open", "in_progress", "escalated", "resolved", "closed", "reopened"], [0.25, 0.2, 0.1, 0.2, 0.2, 0.05])[0]
        comps.append({"id": nid("CMP"), "subject": s, "description": f"{s}. Please resolve at the earliest.", "category": cat,
                      "priority": R.choice(["low", "medium", "high", "urgent"]), "raised_by": R.choice(["tenant", "owner"]),
                      "tenant_id": t["id"], "owner_id": t["owner_id"], "property_id": t["property_id"], "assigned_to": R.choice(by_admin),
                      "status": st, "escalation_level": 1 if st == "escalated" else 0, "reopen_count": 1 if st == "reopened" else 0,
                      "timeline": [{"at": ts(R.randint(1, 60)), "by": "system", "action": "created", "reason": "Raised from app"}],
                      "created_at": ts(R.randint(0, 120))})
    for t in R.sample(active_tenants, min(22, len(active_tenants))):
        st = R.choices(["pending", "approved", "completed", "rejected"], [0.4, 0.2, 0.3, 0.1])[0]
        lr = {"id": nid("LVR"), "tenant_id": t["id"], "owner_id": t["owner_id"], "property_id": t["property_id"],
              "requested_leave_date": (today + timedelta(days=R.randint(-20, 40))).isoformat(), "reason_text": R.choice(["Job relocation", "Shifting to own house", "Completed course", "Rent too high"]),
              "deposit": t["deposit"], "refund_amount": None, "settlement": None, "settlement_history": [], "status": st,
              "timeline": [], "created_at": ts(R.randint(0, 60))}
        if st in ("approved", "completed"):
            dmg = R.choice([0, 0, 500, 1500])
            util = R.choice([0, 350, 800])
            s = {"outstanding_rent": 0, "utilities": util, "other_charges": 0, "damage": dmg, "deposit": t["deposit"], "notes": "Final inspection done",
                 "total_deductions": util + dmg, "refund_amount": t["deposit"] - util - dmg, "payable_by_tenant": 0, "calculated_at": ts(2),
                 "calculated_by": "tenantsupport@pa.com", "reason": "Move-out inspection", "version": 1}
            lr.update(settlement=s, settlement_history=[s], refund_amount=s["refund_amount"])
        leaves.append(lr)
    ntypes = [("payment_success", "Payment received"), ("subscription_expiry", "Subscription expiring soon"), ("agreement_verified", "Agreement verified"),
              ("complaint_update", "Complaint status updated"), ("rent_reminder", "Rent due reminder"), ("leaving_update", "Leaving request update")]
    for _ in range(140):
        if R.random() < 0.5:
            r = R.choice(owners)
            rt = "owner"
        else:
            r = R.choice(tenants)
            rt = "tenant"
        ty, title = R.choice(ntypes)
        notifs.append({"id": nid("NTF"), "recipient_id": r["id"], "recipient_name": r["name"], "recipient_type": rt, "type": ty, "title": title,
                       "channel": R.choice(["push", "sms", "email"]), "status": R.choices(["delivered", "sent", "failed", "queued"], [0.7, 0.15, 0.1, 0.05])[0],
                       "created_at": ts(R.randint(0, 90))})
    banners = [{"id": nid("BNR"), "title": t, "description": d, "image_url": PHOTOS[i % 3], "button_text": b, "destination": dest,
                "order": i + 1, "start_date": (today - timedelta(days=30)).isoformat(), "end_date": (today + timedelta(days=60 if i < 3 else -5)).isoformat(),
                "audience": aud, "status": "active" if i != 3 else "inactive", "created_at": ts(40 - i), "created_by": "admin@pa.com", "history": []}
               for i, (t, d, b, dest, aud) in enumerate([
                   ("List your property free for 30 days", "Owners get a free trial of PA platform.", "List Now", "/owner/properties/new", "owner"),
                   ("Digital rent agreements in minutes", "Create Marathi & English agreements online.", "Create Agreement", "/agreements/new", "both"),
                   ("Pay rent online, get instant receipts", "Secure payments for tenants.", "Pay Rent", "/tenant/pay", "tenant"),
                   ("Diwali offer: ₹99 off", "Use code DIWALI99", "Apply", "/offers", "both")])]
    # one refund sample
    paid = [p for p in pays if p["status"] in ("success", "approved") and p["purpose"] != "rent"]
    refunds = []
    for p in paid[:3]:
        p["refunded_amount"] = p["amount"]
        p["status"] = "refunded"
        refunds.append({"id": nid("RFD"), "payment_id": p["id"], "amount": p["amount"], "reason": "Duplicate charge reported by owner", "by": "finance@pa.com", "created_at": ts(3)})
    for coll, docs in [("owners", owners), ("properties", props), ("tenants", tenants), ("tenancies", tenancies), ("agreements", agrs),
                       ("payments", pays), ("subscriptions", subs), ("coupons", coupons), ("coupon_usages", usages), ("complaints", comps),
                       ("leaving", leaves), ("notifications", notifs), ("banners", banners), ("refunds", refunds)]:
        if docs:
            await db[coll].insert_many(docs)
    for p, n in counters.items():
        await db.counters.update_one({"_id": p}, {"$set": {"seq": n}}, upsert=True)


async def run_seed():
    await ensure_indexes()
    await seed_core()
    await seed_data()
