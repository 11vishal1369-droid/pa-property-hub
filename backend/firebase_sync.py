import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import APIRouter, Depends
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from core import db, require, now_iso, encrypt, mask_aadhaar, fee_category, audit, gst_split, GST_RATE_DEFAULT as GST_RATE

router = APIRouter(prefix="/api")
log = logging.getLogger("firebase_sync")
SOURCES = ["users", "properties", "units", "rental_accounts", "agreements", "payments", "fee_orders", "subscriptions",
           "coupons", "complaints", "leaving_requests", "banners", "notifications"]
WRITEBACK = {"banners": "banners", "coupons": "coupons", "notifications": "notifications"}
SAMPLE_COLLS = ["owners", "tenants", "properties", "agreements", "payments", "subscriptions", "coupons", "complaints", "leaving",
                "banners", "notifications"]
SAMPLE_ONLY = ["tenancies", "coupon_usages", "refunds", "notification_campaigns"]
FAR = "2099-12-31"
SYSTEM = {"id": "system", "email": "firestore-sync", "name": "Firestore Sync", "ip": ""}
_client = None
cache = {c: {} for c in SOURCES}
state = {"running": False, "ready": [], "initial_load_done": False, "last_event_at": None, "events": 0, "errors": [], "cutover_at": None}
_queue = None
_loop = None


def client():
    global _client
    if _client is None:
        info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
        app = firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": os.environ["FIREBASE_PROJECT_ID"],
                                                                            "storageBucket": os.environ["FIREBASE_STORAGE_BUCKET"]}, name="pa-admin")
        _client = firestore.client(app)
    return _client


def iso(v):
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    return v


def day(v, default=None):
    v = iso(v)
    return v[:10] if isinstance(v, str) and v else default


def to_dt(d):
    if not d or d == FAR:
        return None
    return datetime.fromisoformat(d if "T" in d else d + "T00:00:00+00:00")


def norm(x):
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return iso(x)


def latest(items, key="created_at"):
    items = list(items)
    return max(items, key=lambda d: str(d.get(key) or "")) if items else None


_memo = {}


def by(coll, field, value):
    key = (coll, field)
    if key not in _memo:
        idx = {}
        for d in cache[coll].values():
            idx.setdefault(d.get(field), []).append(d)
        _memo[key] = idx
    return _memo[key].get(value, [])


def gender(g):
    return (g or "").strip().capitalize() or None


# ---------- Firestore -> panel mappers ----------

def owner_ids():
    if "owners" not in _memo:
        _memo["owners"] = _owner_ids()
    return _memo["owners"]


def tenant_ids():
    if "tenants" not in _memo:
        _memo["tenants"] = _tenant_ids()
    return _memo["tenants"]


def _owner_ids():
    return {i for i, u in cache["users"].items() if u.get("role") == "owner"} | {p.get("owner_id") for p in cache["properties"].values()} - {None}


def _tenant_ids():
    return {i for i, u in cache["users"].items() if u.get("role") == "tenant"} | {r.get("tenant_id") for r in cache["rental_accounts"].values()} - {None}


def map_owner(u):
    today = day(now_iso())
    subs = [s for s in by("subscriptions", "owner_id", u["id"]) if s.get("status") == "active"]
    m = {"name": (u.get("full_name") or "").strip(), "gender": gender(u.get("gender")), "dob": (u.get("profile") or {}).get("date_of_birth"),
         "mobile": u.get("mobile"), "email": u.get("email"), "address": u.get("address"), "city": None, "owner_code": u.get("owner_code"),
         "created_at": iso(u.get("created_at")), "app_status": "active", "status": "active",
         "subscription_status": "none", "subscription_start": None, "subscription_expiry": None}
    if subs:
        exp = max(day(s.get("expires_at")) or "" for s in subs)
        current = [s for s in subs if (day(s.get("starts_at")) or "") <= today <= (day(s.get("expires_at")) or "")]
        start = day((current[0] if current else min(subs, key=lambda s: str(s.get("starts_at")))).get("starts_at"))
        m.update(subscription_status="active" if exp >= today else "expired", subscription_start=start, subscription_expiry=exp)
    return m


def aadhaar_for(tid):
    for a in sorted(by("agreements", "tenant_id", tid), key=lambda d: str(d.get("created_at") or ""), reverse=True):
        n = re.sub(r"\D", "", str((a.get("tenant_details") or {}).get("aadhaar_number") or ""))
        if len(n) == 12:
            return n
    return None


def map_tenant(u):
    accts = by("rental_accounts", "tenant_id", u["id"])
    ra = latest([r for r in accts if r.get("status") == "active"]) or latest(accts) or {}
    agr = latest([a for a in by("agreements", "tenant_id", u["id"]) if a.get("rental_account_id") == ra.get("id")] or by("agreements", "tenant_id", u["id"]))
    det = (agr or {}).get("tenant_details") or {}
    m = {"name": (u.get("full_name") or "").strip(), "gender": gender(u.get("gender")), "dob": det.get("date_of_birth"), "mobile": u.get("mobile"),
         "email": u.get("email"), "tenant_code": u.get("tenant_code"), "occupation": u.get("occupation") or det.get("occupation"),
         "father_name": det.get("father_name"), "mother_name": det.get("mother_name"), "permanent_address": det.get("permanent_address"),
         "current_address": det.get("current_address") or u.get("address"), "emergency_contact_phone": u.get("emergency_contact") or det.get("emergency_contact"),
         "owner_id": ra.get("owner_id"), "property_id": ra.get("property_id"), "room": ra.get("unit_name"), "rental_code": ra.get("rental_code"),
         "join_date": ra.get("rent_start_date"), "leave_date": None if not ra or ra.get("status") == "active" else ra.get("agreement_end_date"),
         "rent": ra.get("monthly_rent"), "deposit": ra.get("security_deposit"), "agreement_status": AGR_STATUS.get((agr or {}).get("status"), (agr or {}).get("status")),
         "aadhaar_status": "verified" if str(ra.get("identity_status", "")).startswith("verified") else "pending",
         "created_at": iso(u.get("created_at")), "app_status": "active", "status": "active"}
    n = aadhaar_for(u["id"])
    if n:
        m.update(aadhaar_enc=encrypt(n), aadhaar_last4=n[-4:], aadhaar_masked=mask_aadhaar(n[-4:]))
    elif u.get("id_number_masked") or det.get("id_number_masked"):
        last4 = re.sub(r"\D", "", u.get("id_number_masked") or det.get("id_number_masked"))[-4:]
        m.update(aadhaar_last4=last4, aadhaar_masked=mask_aadhaar(last4))
    return m


RESIDENTIAL = {"Flat", "Apartment", "Independent House", "Chawl", "Bungalow", "Row House", "Room", "House"}


def map_property(p):
    units = by("units", "property_id", p["id"])
    parents = {u.get("parent_unit_id") for u in units}
    leaves = [u for u in units if u["id"] not in parents] or units
    rents = [u.get("monthly_rent") for u in leaves if u.get("monthly_rent")]
    deps = [u.get("security_deposit") for u in leaves if u.get("security_deposit")]
    cat = p.get("category") or ""
    if cat.startswith("PG"):
        category, typ = "PG", "PG"
    elif cat in ("Flat/Apartment", "Residential") or cat in RESIDENTIAL:
        category, typ = "Residential", {"Flat/Apartment": "Flat", "Residential": "Independent House"}.get(cat, cat)
    else:
        category, typ = "Commercial", cat or "Other"
    occupied = any(r.get("status") == "active" for r in by("rental_accounts", "property_id", p["id"]))
    status = p.get("status") or "active"
    m = {"owner_id": p.get("owner_id"), "name": p.get("name"), "property_code": p.get("property_code"), "category": category, "type": typ,
         "app_category": cat, "pg_gender": p.get("pg_gender"), "address": p.get("address"), "city": p.get("city"), "state": p.get("state"),
         "pincode": p.get("pincode"), "description": p.get("description"), "facilities": p.get("facilities") or [], "photos": p.get("photos") or [],
         "total_units": len(leaves), "unit_label": "Beds" if category == "PG" else "Units",
         "units": [{"label": u.get("name"), "rent": u.get("monthly_rent"), "status": u.get("status")} for u in leaves],
         "rent": min(rents) if rents else None, "deposit": min(deps) if deps else None, "rental_availability": p.get("rental_availability"), "occupancy_state": "occupied" if occupied else "vacant",
         "created_at": iso(p.get("created_at")), "app_status": status, "status": status}
    m["fee_category"] = fee_category(m)
    return m


AGR_STATUS = {"finalized": "completed", "sent": "pending_signature", "draft": "draft", "cancelled": "cancelled", "expired": "expired"}
TEMPLATES = {"pg_girls": "Girls PG Terms & Conditions", "pg_boys": "Boys PG Terms & Conditions", "flat": "Flat Rent Agreement",
             "house": "Independent House Rent Agreement", "commercial": "Commercial Rent Agreement"}


def map_agreement(a):
    terms, snap = a.get("terms") or {}, a.get("snapshot") or {}
    fee = cache["fee_orders"].get(a.get("fee_order_id")) or {}
    det = {k: v for k, v in (a.get("tenant_details") or {}).items() if k != "aadhaar_number"}
    st = AGR_STATUS.get(a.get("status"), a.get("status") or "draft")
    prop = cache["properties"].get(a.get("property_id")) or {}
    m = {"owner_id": a.get("owner_id"), "tenant_id": a.get("tenant_id"), "property_id": a.get("property_id"), "agreement_number": a.get("agreement_number"),
         "category": TEMPLATES.get(a.get("template_key"), (a.get("template_key") or "Agreement").replace("_", " ").title()),
         "fee": fee.get("original"), "discount": fee.get("discount") or 0, "coupon_code": fee.get("coupon_code"), "fee_paid": bool(a.get("fee_paid")),
         "payment_id": a.get("fee_order_id"), "rent": terms.get("monthly_rent") or snap.get("monthly_rent"),
         "deposit": terms.get("security_deposit") or snap.get("security_deposit"), "start_date": terms.get("start_date"), "end_date": terms.get("end_date"),
         "terms": norm(terms), "snapshot": norm(snap), "owner_details": norm(a.get("owner_details") or {}), "tenant_details": norm(det),
         "pdf_path": a.get("pdf_path"), "rental_account_id": a.get("rental_account_id"), "fee_category": fee_category(map_property(prop)) if prop else None,
         "owner_accepted_at": iso(a.get("owner_confirmed_at")), "tenant_accepted_at": iso(a.get("tenant_accepted_at")),
         "created_at": iso(a.get("created_at")), "app_status": st, "status": st}
    for party, at in (("owner", a.get("owner_confirmed_at")), ("tenant", a.get("tenant_accepted_at"))):
        if at:
            m[f"esign.{party}.status"] = "signed"
            m[f"esign.{party}.signed_at"] = iso(at)
    return m


def agreement_defaults(a):
    text = a.get("text") or "Agreement created in the PA mobile app. Terms: " + json.dumps(norm(a.get("terms") or {}), default=str)
    return {"versions": [{"version": 1, "content": text, "created_at": iso(a.get("created_at")), "created_by": "app"}], "current_version": 1,
            "esign": {"owner": {"status": "pending"}, "tenant": {"status": "pending"}}}


PAY_STATUS = {"verified": "approved", "pending": "pending", "rejected": "rejected"}
FEE_STATUS = {"paid": "success", "awaiting_gateway": "pending", "failed": "failed", "cancelled": "failed"}


def map_payment(p):
    st = PAY_STATUS.get(p.get("status"), p.get("status"))
    return {"txn_ref": p.get("transaction_id") or p["id"], "purpose": p.get("kind") or "rent", "owner_id": p.get("owner_id"), "tenant_id": p.get("tenant_id"),
            "property_id": p.get("property_id"), "amount": round(float(p.get("amount") or 0), 2), "discount": 0, "coupon_code": None,
            "method": p.get("payment_method"), "receipt_no": p.get("receipt_number"), "for_month": p.get("for_month"), "sender_name": p.get("sender_name"),
            "proof_url": p.get("proof_url"), "failure_reason": p.get("reject_reason"), "created_at": iso(p.get("created_at")), "app_status": st, "status": st}


def map_fee(f):
    st = FEE_STATUS.get(f.get("status"), f.get("status"))
    return {"txn_ref": f.get("transaction_id") or f.get("order_code") or f["id"], "purpose": "platform_fee" if f.get("service") == "platform" else "agreement_fee",
            "owner_id": f.get("owner_id"), "agreement_id": f.get("agreement_id"), "amount": round(float(f.get("final") or 0), 2),
            "discount": round(float(f.get("discount") or 0), 2), "coupon_code": f.get("coupon_code"), "method": f.get("paid_via") or "online",
            "receipt_no": f.get("receipt_number"), "order_code": f.get("order_code"), "created_at": iso(f.get("created_at")), "app_status": st, "status": st}


def map_subscription(s):
    exp = day(s.get("expires_at"))
    st = "expired" if s.get("status") == "active" and exp and exp < day(now_iso()) else s.get("status")
    return {"owner_id": s.get("owner_id"), "plan": "Platform 365 days", "amount": s.get("amount"), "start_date": day(s.get("starts_at")), "expiry_date": exp,
            "payment_id": s.get("order_id"), "created_at": iso(s.get("paid_at") or s.get("starts_at")), "app_status": st, "status": st}


def map_coupon(c):
    sv = set(c.get("services") or ["agreement", "platform"])
    st = "active" if c.get("active", True) else "inactive"
    m = {"code": (c.get("code") or "").upper(), "description": c.get("description") or "", "discount_type": "percent" if c.get("discount_type") == "percent" else "fixed",
         "app_discount_type": c.get("discount_type"), "value": c.get("value"), "max_discount": c.get("max_discount"), "min_amount": c.get("min_amount") or 0,
         "start_date": day(c.get("starts_at")) or day(c.get("created_at")), "end_date": day(c.get("expires_at"), FAR),
         "max_usage": c.get("usage_limit") or 100000, "used_count": c.get("used") or 0,
         "applies_to": "both" if {"agreement", "platform"} <= sv else ("platform_fee" if "platform" in sv else "agreement_fee"),
         "created_at": iso(c.get("created_at")), "app_status": st, "status": st}
    for k in ("per_owner_limit", "eligibility", "eligible_ids"):
        if k in c:
            m[k] = c[k]
    return m


CMP_STATUS = {"submitted": "open", "pending_owner_review": "open", "accepted": "in_progress", "in_progress": "in_progress",
              "resolved": "resolved", "closed": "closed", "rejected": "closed"}


def map_complaint(c):
    st = CMP_STATUS.get(c.get("status"), c.get("status") or "open")
    return {"subject": c.get("title"), "description": c.get("description"), "category": c.get("category"), "priority": c.get("priority") or "medium",
            "raised_by": "tenant", "raised_by_id": c.get("tenant_id"), "tenant_id": c.get("tenant_id"), "owner_id": c.get("owner_id"),
            "property_id": c.get("property_id"), "complaint_code": c.get("complaint_code"), "unit_name": c.get("unit_name"), "app_raw_status": c.get("status"),
            "resolution": c.get("resolution_remarks"), "attachments": c.get("photos") or [],
            "timeline": [{"at": iso(h.get("at")), "by": h.get("by", "app"), "action": h.get("status"), "reason": h.get("note") or h.get("remarks")} for h in (c.get("history") or [])],
            "created_at": iso(c.get("created_at")), "app_status": st, "status": st}


def complaint_defaults(c):
    return {"assigned_to": None, "escalation_level": 0, "reopen_count": 0, "messages": [
        {"id": c["id"][:10], "sender_type": "tenant", "sender_id": c.get("tenant_id"), "sender_name": c.get("tenant_name"), "text": c.get("description") or "",
         "attachments": c.get("photos") or [], "at": iso(c.get("created_at"))}]}


def map_leaving(lr):
    ra = cache["rental_accounts"].get(lr.get("rental_account_id")) or {}
    st = lr.get("status") or "pending"
    return {"tenant_id": lr.get("tenant_id"), "owner_id": lr.get("owner_id"), "property_id": lr.get("property_id"), "request_code": lr.get("request_code"),
            "requested_leave_date": lr.get("leaving_date"), "reason_text": lr.get("reason"), "info": lr.get("info"), "notice_days": lr.get("notice_days"),
            "deposit": ra.get("security_deposit"), "deposit_received": lr.get("deposit_received"), "requested_by": "tenant",
            "created_at": iso(lr.get("created_at")), "app_status": st, "status": st}


LEAVING_DEFAULTS = {"move_out_status": "not_started", "settlement_status": "pending", "settlement": None, "settlement_history": [], "timeline": [], "refund_amount": None}


def map_banner(b):
    st = "removed" if b.get("removed") else ("active" if b.get("active", True) else "inactive")
    return {"title": b.get("title"), "description": b.get("description"), "image_url": b.get("image_url"), "button_text": b.get("button_text") or "",
            "destination": b.get("button_link") or "", "order": b.get("order") or 0, "audience": b.get("audience") or "owner",
            "start_date": day(b.get("starts_at")) or day(b.get("created_at")), "end_date": day(b.get("ends_at"), FAR),
            "created_at": iso(b.get("created_at")), "app_status": st, "status": st}


def map_notification(n):
    uid = n.get("user_id")
    u = cache["users"].get(uid) or {}
    st = "read" if n.get("read") else "delivered"
    return {"recipient_id": uid, "recipient_name": (u.get("full_name") or "").strip() or None, "recipient_type": "owner" if uid in owner_ids() and u.get("role") != "tenant" else "tenant",
            "type": n.get("type"), "title": n.get("title"), "message": n.get("body"), "channel": "in_app", "ref_id": n.get("ref_id"),
            "campaign_id": n.get("campaign_id"), "scheduled_at": None, "created_at": iso(n.get("created_at")), "app_status": st, "status": st}


# target coll -> (source coll, mapper, insert defaults)
TARGETS = {
    "owners": ("users", map_owner, lambda d: {"remarks": [], "status_history": [], "history": []}),
    "tenants": ("users", map_tenant, lambda d: {"remarks": [], "status_history": [], "history": [], "documents": []}),
    "properties": ("properties", map_property, lambda d: {"remarks": [], "status_history": [], "history": [], "removed_photos": []}),
    "tenancies": ("rental_accounts", lambda r: {"tenant_id": r.get("tenant_id"), "property_id": r.get("property_id"), "owner_id": r.get("owner_id"),
                                                 "room": r.get("unit_name"), "rent": r.get("monthly_rent"), "deposit": r.get("security_deposit"),
                                                 "join_date": r.get("rent_start_date"), "leave_date": None if r.get("status") == "active" else r.get("agreement_end_date"),
                                                 "active": r.get("status") == "active", "created_at": iso(r.get("created_at")), "app_status": r.get("status")}, lambda d: {}),
    "agreements": ("agreements", map_agreement, agreement_defaults),
    "payments": (None, None, lambda d: {"refunded_amount": 0, "history": []}),
    "subscriptions": ("subscriptions", map_subscription, lambda d: {"history": []}),
    "coupons": ("coupons", map_coupon, lambda d: {"history": [], "per_owner_limit": 1000, "eligibility": "both", "eligible_ids": []}),
    "complaints": ("complaints", map_complaint, complaint_defaults),
    "leaving": ("leaving_requests", map_leaving, lambda d: dict(LEAVING_DEFAULTS)),
    "banners": ("banners", map_banner, lambda d: {"history": []}),
    "notifications": ("notifications", map_notification, lambda d: {}),
}
ARCHIVABLE = {"owners", "tenants", "properties", "agreements"}


def source_doc(target, rid):
    if target == "payments":
        return cache["payments"].get(rid) or cache["fee_orders"].get(rid)
    if target == "owners" and rid not in owner_ids():
        return None
    if target == "tenants" and rid not in tenant_ids():
        return None
    return cache[TARGETS[target][0]].get(rid)


CODE_FIELDS = {"owners": ["owner_code"], "tenants": ["tenant_code"], "properties": ["property_code"], "agreements": ["agreement_number"],
               "payments": ["receipt_number", "order_code", "transaction_id"], "complaints": ["complaint_code"], "leaving": ["request_code"],
               "tenancies": ["rental_code"]}


def build(target, raw):
    if target == "payments":
        m = map_payment(raw) if raw["id"] in cache["payments"] else map_fee(raw)
    else:
        m = TARGETS[target][1](raw)
    code = next((raw.get(f) for f in CODE_FIELDS.get(target, []) if raw.get(f)), None)
    if code:
        m["code"] = code
    return m


def removal(target, ex):
    upd = {"app_status": "deleted", "deleted_in_app_at": now_iso()}
    if target in ARCHIVABLE and ex.get("status") != "archived":
        upd.update(status="archived", archived_at=now_iso(), archived_by="mobile app", archive_reason="Deleted in mobile app",
                   archived_source="app", status_before_archive=ex.get("status"))
    elif target == "banners":
        upd["status"] = "removed"
    elif target == "coupons":
        upd["status"] = "inactive"
    return upd


def upsert_op(target, rid, raw, ex):
    m = build(target, raw)
    if ex and ex.get("app_status") == m.get("app_status"):
        m.pop("status", None)
    m.update(id=rid, source="firestore", synced_at=now_iso())
    on_insert = {k: v for k, v in TARGETS[target][2](raw).items() if k not in m}
    if any("." in k for k in m):
        on_insert.pop("esign", None)
        for p in ("owner", "tenant"):
            if f"esign.{p}.status" not in m and not ex:
                on_insert[f"esign.{p}.status"] = "pending"
    return m, on_insert


async def apply(target, ids):
    ids = list(dict.fromkeys(ids))
    existing = {d["id"]: d async for d in db[target].find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "app_status": 1, "status": 1, "source": 1})}
    ops = []
    for rid in ids:
        raw, ex = source_doc(target, rid), existing.get(rid)
        if raw is None:
            if ex and ex.get("source") == "firestore" and ex.get("app_status") != "deleted":
                ops.append(UpdateOne({"id": rid}, {"$set": removal(target, ex)}))
            continue
        m, ins = upsert_op(target, rid, raw, ex)
        ops.append(UpdateOne({"id": rid}, {"$set": m, "$setOnInsert": ins}, upsert=True))
    for i in range(0, len(ops), 500):
        try:
            await db[target].bulk_write(ops[i:i + 500], ordered=False)
        except BulkWriteError as e:
            for err in e.details.get("writeErrors", []):
                op = ops[i + err["index"]]
                if target == "payments" and err.get("code") == 11000 and "txn_ref" in err.get("errmsg", ""):
                    doc = op._doc
                    doc["$set"]["txn_ref"] = f"{doc['$set']['txn_ref']}-{doc['$set']['id'][:6]}"
                    await db[target].update_one(op._filter, doc, upsert=True)
                else:
                    raise


async def upsert(target, rid):
    await apply(target, [rid])


def affected(coll, d):
    rid = d["id"]
    out = set()
    if coll == "users":
        out |= {("owners", rid), ("tenants", rid)}
        out |= {("notifications", n["id"]) for n in by("notifications", "user_id", rid)}
    elif coll == "properties":
        out |= {("properties", rid), ("owners", d.get("owner_id"))}
    elif coll == "units":
        out.add(("properties", d.get("property_id")))
    elif coll == "rental_accounts":
        out |= {("tenancies", rid), ("tenants", d.get("tenant_id")), ("properties", d.get("property_id"))}
        out |= {("leaving", lr["id"]) for lr in by("leaving_requests", "rental_account_id", rid)}
    elif coll == "agreements":
        out |= {("agreements", rid), ("tenants", d.get("tenant_id"))}
    elif coll in ("payments", "fee_orders"):
        out.add(("payments", rid))
        if coll == "fee_orders" and d.get("agreement_id"):
            out.add(("agreements", d["agreement_id"]))
    elif coll == "subscriptions":
        out |= {("subscriptions", rid), ("owners", d.get("owner_id"))}
    else:
        out.add(({"leaving_requests": "leaving"}.get(coll, coll), rid))
    return {(t, i) for t, i in out if i}


def all_targets():
    out = set()
    for coll in SOURCES:
        for d in cache[coll].values():
            out |= affected(coll, d)
    return out


async def cutover():
    if await db.migrations.find_one({"_id": "firestore_cutover"}):
        return
    removed = {}
    for c in SAMPLE_COLLS:
        removed[c] = (await db[c].delete_many({"source": {"$ne": "firestore"}})).deleted_count
    for c in SAMPLE_ONLY:
        removed[c] = (await db[c].delete_many({})).deleted_count
    state["cutover_at"] = now_iso()
    await db.migrations.insert_one({"_id": "firestore_cutover", "at": state["cutover_at"], "removed": removed})
    await audit(SYSTEM, "sample_data_removed", "settings", "firestore_cutover", None, removed, "Real Firestore data loaded; sample data removed")
    log.info("Firestore cutover done: %s", removed)


async def worker():
    pending = set()
    while True:
        coll, changes = await _queue.get()
        try:
            olds = []
            for kind, d in changes:
                old = cache[coll].get(d["id"])
                if old:
                    olds.append(old)
                if kind == "REMOVED":
                    cache[coll].pop(d["id"], None)
                else:
                    cache[coll][d["id"]] = d
            _memo.clear()
            if len(state["ready"]) >= len(SOURCES) - (coll not in state["ready"]):
                for d in [d for _, d in changes] + olds:
                    pending |= affected(coll, d)
            state["events"] += len(changes)
            state["last_event_at"] = now_iso()
            if coll not in state["ready"]:
                state["ready"].append(coll)
            if len(state["ready"]) < len(SOURCES):
                continue
            if not state["initial_load_done"]:
                await cutover()
                pending |= all_targets()
            groups = {}
            for t, i in pending:
                groups.setdefault(t, []).append(i)
            t0 = datetime.now(timezone.utc)
            for t, ids in groups.items():
                try:
                    await apply(t, ids)
                except Exception as e:
                    log.exception("apply %s failed", t)
                    state["errors"] = (state["errors"] + [{"at": now_iso(), "collection": t, "error": str(e)[:300]}])[-10:]
            state["last_apply_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
            pending.clear()
            if not state["initial_load_done"]:
                state["initial_load_done"] = True
                log.info("Firestore initial load applied")
        except Exception as e:
            log.exception("sync error")
            state["errors"] = (state["errors"] + [{"at": now_iso(), "collection": coll, "error": str(e)[:300]}])[-10:]


def _listener(coll):
    def on_snapshot(_docs, changes, _read_time):
        batch = [(c.type.name, {**c.document.to_dict(), "id": c.document.id}) for c in changes]
        _loop.call_soon_threadsafe(_queue.put_nowait, (coll, batch))
    return on_snapshot


def _start_listeners():
    fs = client()
    return [fs.collection(c).on_snapshot(_listener(c)) for c in SOURCES]


async def start():
    global _queue, _loop
    if not os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or state["running"]:
        return
    _loop, _queue = asyncio.get_running_loop(), asyncio.Queue()
    asyncio.create_task(worker())
    asyncio.create_task(deliver_scheduled())
    try:
        await asyncio.to_thread(_start_listeners)
        state["running"] = True
    except Exception as e:
        state["errors"].append({"at": now_iso(), "collection": "*", "error": str(e)[:300]})
        log.exception("Could not start Firestore listeners")


# ---------- panel -> Firestore (banners, coupons, notifications) ----------

def rev_banner(b):
    return {"id": b["id"], "title": b.get("title"), "description": b.get("description"), "image_url": b.get("image_url"), "button_text": b.get("button_text") or "",
            "button_link": b.get("destination") or "", "order": b.get("order") or 0, "audience": b.get("audience"), "active": b.get("status") == "active",
            "removed": b.get("status") == "removed", "starts_at": to_dt(b.get("start_date")), "ends_at": to_dt(b.get("end_date")), "created_at": to_dt(b.get("created_at"))}


def rev_coupon(c):
    at = c.get("applies_to")
    return {"id": c["id"], "code": c.get("code"), "description": c.get("description") or "",
            "discount_type": c.get("app_discount_type") if c.get("discount_type") != "percent" and c.get("app_discount_type") else c.get("discount_type"),
            "value": float(c.get("value") or 0), "max_discount": c.get("max_discount"), "min_amount": c.get("min_amount") or 0,
            "starts_at": to_dt(c.get("start_date")), "expires_at": to_dt(c.get("end_date")), "usage_limit": c.get("max_usage"),
            "services": ["agreement", "platform"] if at == "both" else (["platform"] if at == "platform_fee" else ["agreement"]),
            "active": c.get("status") == "active", "per_owner_limit": c.get("per_owner_limit"), "eligibility": c.get("eligibility"),
            "eligible_ids": c.get("eligible_ids") or [], "created_at": to_dt(c.get("created_at"))}


def rev_notification(n):
    return {"id": n["id"], "user_id": n.get("recipient_id"), "title": n.get("title"), "body": n.get("message"), "type": n.get("type") or "announcement",
            "read": n.get("status") == "read", "ref_id": n.get("campaign_id"), "campaign_id": n.get("campaign_id"), "source": "admin_panel",
            "created_at": to_dt(n.get("created_at"))}


REVERSE = {"banners": rev_banner, "coupons": rev_coupon, "notifications": rev_notification}


def _write(coll, docs):
    fs = client()
    for i in range(0, len(docs), 400):
        batch = fs.batch()
        for d in docs[i:i + 400]:
            batch.set(fs.collection(coll).document(d["id"]), d, merge=True)
        batch.commit()


async def push(entity, ids):
    if not os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
        return
    docs = [REVERSE[entity](d) async for d in db[entity].find({"id": {"$in": list(ids)}}, {"_id": 0})]
    if entity == "notifications":
        docs = [d for d, n in zip(docs, [n async for n in db.notifications.find({"id": {"$in": list(ids)}}, {"_id": 0, "status": 1})]) if n.get("status") != "scheduled"]
    if docs:
        await asyncio.to_thread(_write, WRITEBACK[entity], docs)
        await db[entity].update_many({"id": {"$in": [d["id"] for d in docs]}}, {"$set": {"source": "firestore", "pushed_at": now_iso()}})


async def deliver_scheduled():
    while True:
        await asyncio.sleep(60)
        try:
            now = now_iso()
            ids = [n["id"] async for n in db.notifications.find({"status": "scheduled", "scheduled_at": {"$lte": now}}, {"id": 1})]
            if ids:
                await db.notifications.update_many({"id": {"$in": ids}}, {"$set": {"status": "delivered", "delivered_at": now}})
                await push("notifications", ids)
        except Exception as e:
            state["errors"] = (state["errors"] + [{"at": now_iso(), "collection": "notifications", "error": str(e)[:300]}])[-10:]


# ---------- status ----------

FEE_KEYS = ["agreement_duration_fees", "owner_platform_fee", "platform_validity_days", "tenant_fees", "tax", "coupon_applicability"]
FEES_DOC = ("app_config", "fees")


async def fee_config():
    s = await db.settings.find_one({"key": "global"}, {"_id": 0})
    rate = s["tax"].get("gst_percent", GST_RATE)
    return {"agreement_duration_fees": [{**t, "gst": gst_split(t["fee"], rate)} for t in s["agreement_duration_fees"]],
            "agreement_fee_rule": "Use the shortest duration whose days are greater than or equal to the agreement length (end date minus start date). "
                                  "If the agreement is longer than every duration, use the longest duration's fee.",
            "gst_inclusive": True, "gst_rate": rate, "platform_fee": s["owner_platform_fee"], "platform_validity_days": s["platform_validity_days"],
            "platform_fee_gst": gst_split(s["owner_platform_fee"], rate), "tenant_fees": s["tenant_fees"],
            "coupons_allowed": s.get("coupon_applicability", {}), "settings_version": s.get("version", 1), "updated_at": s.get("updated_at") or now_iso()}


async def publish_fees():
    if not os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
        return False
    cfg = await fee_config()
    try:
        await asyncio.to_thread(lambda: client().collection(FEES_DOC[0]).document(FEES_DOC[1]).set({**cfg, "published_at": firestore.SERVER_TIMESTAMP}))
        state["fees_published_at"] = now_iso()
        return True
    except Exception as e:
        state["errors"] = (state["errors"] + [{"at": now_iso(), "collection": "app_config", "error": str(e)[:300]}])[-10:]
        log.exception("publish fees failed")
        return False


def probe():
    out = {"project_id": os.environ["FIREBASE_PROJECT_ID"], "checked_at": now_iso(), "collections": {}}
    try:
        fs = client()
        for name in SOURCES:
            out["collections"][name] = fs.collection(name).count().get()[0][0].value
        out["connected"] = True
    except Exception as e:
        msg = str(e)
        out["connected"] = False
        out["error"] = ("Cloud Firestore API is disabled for this project. Enable it in Google Cloud Console → APIs & Services → Cloud Firestore API, "
                        "and make sure a Firestore database exists.") if "has not been used" in msg or "SERVICE_DISABLED" in msg else msg[:300]
    return out


@router.get("/firebase/status")
async def firebase_status(admin=Depends(require("settings", "view"))):
    out = await asyncio.to_thread(probe)
    out["sync"] = {**state, "ready": len(state["ready"]), "total_sources": len(SOURCES)}
    cut = await db.migrations.find_one({"_id": "firestore_cutover"}, {"_id": 0})
    out["sync"]["cutover"] = cut
    out["panel_counts"] = {c: await db[c].count_documents({"source": "firestore"}) for c in SAMPLE_COLLS}
    return out
