from datetime import timedelta, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel
from core import db, clean, audit, audited, require, current_admin, now_iso, require_reason, next_id, decrypt, fee_category, gst_split
import re
from data import enrich, validate_coupon as validate_coupon_fields, validate_coupon_targets, ELIGIBILITY
from exports import simple_pdf
import firebase_sync

router = APIRouter(prefix="/api")


async def activity(rid):
    return [clean(d) async for d in db.audit_logs.find({"record_id": rid}).sort("seq", -1).limit(100)]


async def find_all(coll, q, limit=500):
    return await enrich(coll, [clean(d) async for d in db[coll].find(q).sort("created_at", -1).limit(limit)])


async def must(coll, rid):
    d = await db[coll].find_one({"id": rid}, {"_id": 0})
    if not d:
        raise HTTPException(404, f"{coll[:-1].title()} not found")
    return d


class ReasonIn(BaseModel):
    reason: str


@router.get("/owners/{oid}/profile")
async def owner_profile(oid: str, admin=Depends(require("owners", "view"))):
    owner = (await enrich("owners", [clean(await must("owners", oid))]))[0]
    payments = await find_all("payments", {"owner_id": oid})
    return {"owner": owner, "properties": await enrich("properties", await find_all("properties", {"owner_id": oid})),
            "tenants": await find_all("tenants", {"owner_id": oid}), "agreements": await find_all("agreements", {"owner_id": oid}),
            "payments": payments, "subscriptions": await find_all("subscriptions", {"owner_id": oid}),
            "coupon_usage": [clean(d) async for d in db.coupon_usages.find({"owner_id": oid})],
            "activity": await activity(oid)}


@router.get("/tenants/{tid}/profile")
async def tenant_profile(tid: str, admin=Depends(require("tenants", "view"))):
    t = (await enrich("tenants", [clean(await must("tenants", tid))]))[0]
    tenancies = await find_all("tenancies", {"tenant_id": tid})
    return {"tenant": t, "tenancies": tenancies, "agreements": await find_all("agreements", {"tenant_id": tid}),
            "payments": await find_all("payments", {"tenant_id": tid}), "complaints": await find_all("complaints", {"tenant_id": tid}),
            "leaving": await find_all("leaving", {"tenant_id": tid}), "activity": await activity(tid)}


@router.post("/tenants/{tid}/aadhaar/reveal")
async def reveal_aadhaar(tid: str, body: ReasonIn, admin=Depends(require("aadhaar", "view"))):
    reason = require_reason(body.reason)
    t = await must("tenants", tid)
    if not t.get("aadhaar_enc"):
        raise HTTPException(404, "No Aadhaar on file")
    full = decrypt(t["aadhaar_enc"])
    await audit(admin, "aadhaar_view", "tenants", tid, None, {"field": "aadhaar"}, reason)
    return {"aadhaar": f"{full[:4]}-{full[4:8]}-{full[8:]}"}


@router.get("/properties/{pid}/profile")
async def property_profile(pid: str, admin=Depends(require("properties", "view"))):
    p = (await enrich("properties", [clean(await must("properties", pid))]))[0]
    tenancies = await find_all("tenancies", {"property_id": pid})
    return {"property": p, "current_tenants": [x for x in tenancies if x.get("active")],
            "previous_tenants": [x for x in tenancies if not x.get("active")],
            "agreements": await find_all("agreements", {"property_id": pid}), "payments": await find_all("payments", {"property_id": pid}),
            "complaints": await find_all("complaints", {"property_id": pid}), "leaving": await find_all("leaving", {"property_id": pid}),
            "activity": await activity(pid)}


class PhotoIn(BaseModel):
    url: str
    reason: str


@router.post("/properties/{pid}/photos")
async def add_photo(pid: str, body: PhotoIn, admin=Depends(require("properties", "edit"))):
    reason = require_reason(body.reason)
    await must("properties", pid)
    await audit(admin, "add_photo", "properties", pid, None, {"url": body.url}, reason)
    await db.properties.update_one({"id": pid}, {"$push": {"photos": body.url}})
    return {"ok": True}


@router.post("/properties/{pid}/photos/remove")
async def remove_photo(pid: str, body: PhotoIn, admin=Depends(require("properties", "edit"))):
    reason = require_reason(body.reason)
    await must("properties", pid)
    await audit(admin, "remove_photo", "properties", pid, {"url": body.url}, None, reason)
    await db.properties.update_one({"id": pid}, {"$pull": {"photos": body.url}, "$push": {"removed_photos": {"url": body.url, "at": now_iso(), "by": admin["email"], "reason": reason}}})
    return {"ok": True}


# Agreements
PARTY_FIELDS = {"_id": 0, "id": 1, "name": 1, "mobile": 1, "email": 1, "gender": 1, "address": 1, "city": 1, "status": 1, "permanent_address": 1, "room": 1}


async def agreement_full(aid):
    a = (await enrich("agreements", [clean(await must("agreements", aid))]))[0]
    prop = await db.properties.find_one({"id": a["property_id"]}, {"_id": 0, "id": 1, "name": 1, "category": 1, "type": 1, "pg_gender": 1, "address": 1, "city": 1})
    pay = await db.payments.find_one({"id": a.get("payment_id")}, {"_id": 0}) if a.get("payment_id") else None
    pay = pay or await db.payments.find_one({"agreement_id": aid, "purpose": "agreement_fee"}, {"_id": 0}, sort=[("created_at", -1)])
    if pay:
        pay = (await enrich("payments", [clean(pay)]))[0]
    a["owner"] = await db.owners.find_one({"id": a["owner_id"]}, PARTY_FIELDS)
    a["tenant"] = await db.tenants.find_one({"id": a["tenant_id"]}, PARTY_FIELDS)
    a["property"] = {**(prop or {}), "fee_category": a.get("fee_category") or (fee_category(prop) if prop else None)}
    a["payment"] = pay
    return a


@router.get("/agreements/{aid}/detail")
async def agreement_detail(aid: str, admin=Depends(require("agreements", "view"))):
    a = await agreement_full(aid)
    return {"agreement": a, "payments": await find_all("payments", {"agreement_id": aid}), "activity": await activity(aid)}


def agreement_lines(a, v):
    ver = next((x for x in a["versions"] if x["version"] == v), None)
    if not ver:
        raise HTTPException(404, "Version not found")
    o, t, p, pay = a.get("owner") or {}, a.get("tenant") or {}, a.get("property") or {}, a.get("payment")
    es = a.get("esign") or {}

    def sign(party):
        e = es.get(party) or {}
        return (f"{party.title()} e-Sign: {e.get('status', 'pending').upper()}"
                + (f" | Signed {e.get('signed_at')} | Provider {e.get('provider')} ref {e.get('provider_ref')} | Verification {e.get('verification_result')}" if e.get("status") == "signed" else ""))
    lines = [("h", a["category"]), ("p", f"Agreement No: {a['id']} | Version {v} | Created {ver['created_at'][:10]}"),
             ("p", f"Owner (Licensor): {o.get('name')} ({a['owner_id']}) | {o.get('mobile')} | {o.get('email')}"),
             ("p", f"Tenant (Licensee): {t.get('name')} ({a['tenant_id']}) | {t.get('mobile')} | {t.get('email')}"),
             ("p", f"Property: {p.get('name')} ({a['property_id']}) | Category: {p.get('fee_category')} | {p.get('address')}, {p.get('city')}"),
             ("p", f"Term: {a.get('start_date')} to {a.get('end_date')} | Rent: Rs. {a.get('rent')} | Deposit: Rs. {a.get('deposit')}"),
             ("h", "Terms & Conditions"), ("p", ver["content"]), ("h", "Agreement fee")]
    if pay:
        lines += [("p", f"Fee Rs. {a.get('fee')} | Coupon {a.get('coupon_code') or '—'} discount Rs. {a.get('discount') or 0} | Final paid Rs. {pay['total_received']} "
                        f"(Base Rs. {pay['base_amount']} + GST {pay['gst_rate']}% Rs. {pay['gst_amount']}) | {pay['method']} | Txn {pay['txn_ref']} | {pay['status']}")]
    else:
        lines += [("p", f"Fee Rs. {a.get('fee')} — not paid")]
    lines += [("h", "Aadhaar e-Sign"), ("p", sign("owner")), ("p", sign("tenant")),
              ("p", "Note: Stamp duty / registration charges are government levies and are separate from PA service fees.")]
    return lines


@router.get("/agreements/{aid}/pdf")
async def agreement_pdf(aid: str, version: Optional[int] = None, admin=Depends(require("agreements", "view"))):
    a = await agreement_full(aid)
    v = version or a["current_version"]
    return simple_pdf(f"PA Rental Agreement — {a['id']}", agreement_lines(a, v), f"{a['id']}_v{v}.pdf")


class VersionIn(BaseModel):
    content: str
    reason: str


@router.post("/agreements/{aid}/versions")
async def new_version(aid: str, body: VersionIn, admin=Depends(require("agreements", "edit"))):
    reason = require_reason(body.reason)
    a = await must("agreements", aid)
    if a["status"] == "completed" or any((a.get("esign") or {}).get(p, {}).get("status") == "signed" for p in ("owner", "tenant")):
        raise HTTPException(400, "Agreement already has e-signatures; a signed document cannot be changed")
    v = a["current_version"] + 1
    ver = {"version": v, "content": body.content, "created_at": now_iso(), "created_by": admin["email"], "reason": reason}
    await audit(admin, "new_version", "agreements", aid, {"version": v - 1}, {"version": v}, reason)
    await db.agreements.update_one({"id": aid}, {"$push": {"versions": ver}, "$set": {"current_version": v}})
    return ver


# Finance
@router.get("/finance/summary")
async def finance_summary(frm: Optional[str] = None, to: Optional[str] = None, admin=Depends(require("finance", "view"))):
    dq = {}
    if frm:
        dq.setdefault("created_at", {})["$gte"] = frm
    if to:
        dq.setdefault("created_at", {})["$lte"] = to + "T23:59:59.999999"
    rows = [x async for x in db.payments.aggregate([{"$match": dq}, {"$group": {"_id": {"p": "$purpose", "s": "$status", "m": "$method"}, "n": {"$sum": 1}, "amt": {"$sum": "$amount"}}}])]
    by_status, by_purpose, by_method = {}, {}, {}
    for r in rows:
        s, p, m = r["_id"]["s"], r["_id"]["p"], r["_id"]["m"]
        by_status.setdefault(s, {"count": 0, "amount": 0})
        by_status[s]["count"] += r["n"]
        by_status[s]["amount"] += r["amt"]
        if s in ("success", "approved", "refunded", "partially_refunded"):
            by_purpose[p] = by_purpose.get(p, 0) + r["amt"]
            by_method[m] = by_method.get(m, 0) + r["amt"]
    ref = [x async for x in db.refunds.aggregate([{"$match": dq}, {"$group": {"_id": None, "t": {"$sum": "$amount"}, "n": {"$sum": 1}}}])]
    return {"by_status": by_status, "by_purpose": by_purpose, "by_method": by_method,
            "refunds": {"amount": ref[0]["t"], "count": ref[0]["n"]} if ref else {"amount": 0, "count": 0}}


async def pay_transition(pid, admin, reason, new_status, allowed):
    p = await must("payments", pid)
    if p["status"] not in allowed or (new_status in ("approved", "rejected") and p["method"] != "manual"):
        raise HTTPException(400, f"Cannot change payment from {p['status']} to {new_status}")
    upd = {"status": new_status}
    if new_status == "approved":
        upd["receipt_no"] = p.get("receipt_no") or await next_id("RCPT")
    entry = {"at": now_iso(), "by": admin["email"], "old": p["status"], "new": new_status, "reason": reason}
    async def write():
        r = await db.payments.update_one({"id": pid, "status": p["status"]}, {"$set": upd, "$push": {"history": entry}})
        if not r.modified_count:
            raise HTTPException(409, "Payment was modified concurrently")

    async def undo():
        await db.payments.update_one({"id": pid, "status": new_status}, {"$set": {"status": p["status"], "receipt_no": p.get("receipt_no")}, "$pull": {"history": entry}})
    await audited(admin, f"payment_{new_status}", "finance", pid, {"status": p["status"]}, upd, reason, write, undo)
    if new_status == "approved":
        await apply_payment_effects(p, admin)
    return {"ok": True, **upd}


async def apply_payment_effects(p, admin):
    if p.get("purpose") == "agreement_fee" and p.get("agreement_id"):
        await db.agreements.update_one({"id": p["agreement_id"]}, {"$set": {"fee_paid": True}})
    if p.get("purpose") == "platform_fee" and p.get("owner_id"):
        s = await db.settings.find_one({"key": "global"})
        start = date.today()
        exp = start + timedelta(days=s["platform_validity_days"])
        sid = await next_id("SUB")
        await db.subscriptions.insert_one({"id": sid, "owner_id": p["owner_id"], "plan": f"Platform {s['platform_validity_days']} days",
                                           "amount": p["amount"], "start_date": start.isoformat(), "expiry_date": exp.isoformat(),
                                           "status": "active", "payment_id": p["id"], "created_at": now_iso(), "history": []})
        await db.owners.update_one({"id": p["owner_id"]}, {"$set": {"subscription_status": "active", "subscription_start": start.isoformat(), "subscription_expiry": exp.isoformat()}})


@router.post("/payments/{pid}/approve")
async def approve_payment(pid: str, body: ReasonIn, admin=Depends(require("finance", "edit"))):
    return await pay_transition(pid, admin, require_reason(body.reason), "approved", ["pending"])


@router.post("/payments/{pid}/reject")
async def reject_payment(pid: str, body: ReasonIn, admin=Depends(require("finance", "edit"))):
    return await pay_transition(pid, admin, require_reason(body.reason), "rejected", ["pending"])


class RefundIn(BaseModel):
    amount: float
    reason: str


@router.post("/payments/{pid}/refund")
async def refund_payment(pid: str, body: RefundIn, admin=Depends(require("finance", "edit"))):
    reason = require_reason(body.reason)
    p = await must("payments", pid)
    if p["status"] not in ("success", "approved", "partially_refunded"):
        raise HTTPException(400, "Only successful/approved payments can be refunded")
    remaining = p["amount"] - p.get("refunded_amount", 0)
    if body.amount <= 0 or body.amount > remaining:
        raise HTTPException(400, f"Refund amount must be between 1 and {remaining}")
    old_ref = p.get("refunded_amount", 0)
    new_ref = round(old_ref + body.amount, 2)
    status = "refunded" if new_ref >= p["amount"] else "partially_refunded"
    rid = await next_id("RFD")
    entry = {"at": now_iso(), "by": admin["email"], "old": p["status"], "new": status, "reason": reason, "refund_id": rid}

    async def write():
        r = await db.payments.update_one({"id": pid, "status": p["status"], "refunded_amount": old_ref},
                                         {"$set": {"refunded_amount": new_ref, "status": status}, "$push": {"history": entry}})
        if not r.modified_count:
            raise HTTPException(409, "Payment was modified by another refund — reload and try again")

    async def undo():
        await db.payments.update_one({"id": pid, "refunded_amount": new_ref}, {"$set": {"refunded_amount": old_ref, "status": p["status"]}, "$pull": {"history": entry}})
    await audited(admin, "refund", "finance", pid, {"status": p["status"], "refunded_amount": old_ref}, {"status": status, "refunded_amount": new_ref, "refund_id": rid}, reason, write, undo)
    await db.refunds.insert_one({"id": rid, "payment_id": pid, "amount": body.amount, "reason": reason, "by": admin["email"], "created_at": now_iso()})
    return {"ok": True, "refund_id": rid, "status": status}


class ManualIn(BaseModel):
    owner_id: str
    tenant_id: Optional[str] = None
    agreement_id: Optional[str] = None
    purpose: str
    amount: float
    txn_ref: str
    reason: str


@router.post("/payments/manual")
async def record_manual(body: ManualIn, admin=Depends(require("finance", "edit"))):
    reason = require_reason(body.reason)
    if body.purpose not in ("platform_fee", "agreement_fee", "rent"):
        raise HTTPException(400, "Invalid purpose")
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    await must("owners", body.owner_id)
    doc = {"id": await next_id("PAY"), "txn_ref": body.txn_ref.strip(), "purpose": body.purpose, "owner_id": body.owner_id,
           "tenant_id": body.tenant_id, "agreement_id": body.agreement_id, "property_id": None, "amount": body.amount, "discount": 0,
           "coupon_code": None, "refunded_amount": 0, "gst_rate": (await db.settings.find_one({"key": "global"}))["tax"].get("gst_percent", 18), "method": "manual", "gateway": None, "status": "pending", "receipt_no": None,
           "created_at": now_iso(), "recorded_by": admin["email"], "history": [{"at": now_iso(), "by": admin["email"], "new": "pending", "reason": reason}]}
    async def write():
        try:
            await db.payments.insert_one(doc)
        except DuplicateKeyError:
            raise HTTPException(409, "Duplicate transaction reference — this payment already exists")

    async def undo():
        await db.payments.delete_one({"id": doc["id"]})
    await audited(admin, "record_manual_payment", "finance", doc["id"], None, {"amount": body.amount, "txn_ref": doc["txn_ref"]}, reason, write, undo)
    return clean(doc)


@router.get("/payments/{pid}/receipt")
async def receipt(pid: str, admin=Depends(require("finance", "view"))):
    p = (await enrich("payments", [clean(await must("payments", pid))]))[0]
    if p["status"] not in ("success", "approved", "refunded", "partially_refunded"):
        raise HTTPException(400, "Receipt is only available for successful payments")
    lines = [("p", f"Receipt No: {p.get('receipt_no')}"), ("p", f"Payment ID: {p['id']} | Txn Ref: {p['txn_ref']}"),
             ("p", f"Date: {p['created_at'][:19].replace('T', ' ')}"), ("p", f"Paid by: {p.get('owner_name') or p.get('tenant_name')}"),
             ("p", f"Purpose: {p['purpose'].replace('_', ' ').title()} | Method: {p['method'].title()}"),
             ("p", f"Gross: Rs. {p['amount'] + (p.get('discount') or 0)} | Discount: Rs. {p.get('discount') or 0} ({p.get('coupon_code') or 'no coupon'})"),
             ("h", "GST breakdown (GST inclusive)"),
             ("p", f"Total Received: Rs. {p['total_received']:.2f}<br/>Base Amount: Rs. {p['base_amount']:.2f}<br/>GST @ {p['gst_rate']}%: Rs. {p['gst_amount']:.2f}<br/>Total: Rs. {p['total']:.2f}"),
             ("h", f"Amount Paid: Rs. {p['amount']:.2f}"), ("p", f"Refunded: Rs. {p.get('refunded_amount', 0)} | Status: {p['status']}")]
    return simple_pdf("PA Property Management — Payment Receipt", lines, f"receipt_{p['id']}.pdf")


@router.get("/payments/{pid}/history")
async def payment_history(pid: str, admin=Depends(require("finance", "view"))):
    p = await must("payments", pid)
    return {"history": p.get("history", []), "refunds": [clean(r) async for r in db.refunds.find({"payment_id": pid})]}


# Subscriptions
class ExtendIn(BaseModel):
    days: int
    reason: str


@router.post("/subscriptions/{sid}/extend")
async def extend_sub(sid: str, body: ExtendIn, admin=Depends(require("subscriptions", "edit"))):
    reason = require_reason(body.reason)
    if body.days < 1 or body.days > 730:
        raise HTTPException(400, "Days must be 1-730")
    s = await must("subscriptions", sid)
    base = max(date.fromisoformat(s["expiry_date"]), date.today())
    new_exp = (base + timedelta(days=body.days)).isoformat()
    entry = {"at": now_iso(), "by": admin["email"], "action": "extend", "old": s["expiry_date"], "new": new_exp, "reason": reason}
    await audit(admin, "extend_subscription", "subscriptions", sid, {"expiry_date": s["expiry_date"]}, {"expiry_date": new_exp}, reason)
    await db.subscriptions.update_one({"id": sid}, {"$set": {"expiry_date": new_exp, "status": "active"}, "$push": {"history": entry}})
    await db.owners.update_one({"id": s["owner_id"]}, {"$set": {"subscription_expiry": new_exp, "subscription_status": "active"}})
    return {"ok": True, "expiry_date": new_exp}


# Coupons
class CouponIn(BaseModel):
    code: str
    description: Optional[str] = ""
    discount_type: str
    value: float
    max_discount: Optional[float] = None
    min_amount: float = 0
    start_date: str
    end_date: str
    max_usage: int = 100
    per_owner_limit: int = 1
    applies_to: str = "both"
    eligibility: str = "all_owners"
    eligible_ids: List[str] = []
    reason: str


@router.post("/coupons")
async def create_coupon(body: CouponIn, admin=Depends(require("coupons", "edit"))):
    reason = require_reason(body.reason)
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(400, "Coupon code is required")
    validate_coupon_fields(body.model_dump())
    await validate_coupon_targets(body.model_dump())
    if await db.coupons.find_one({"code": code}):
        raise HTTPException(409, "Coupon code already exists")
    doc = {**body.model_dump(exclude={"reason"}), "code": code, "id": await next_id("CPN"), "status": "active", "used_count": 0,
           "created_at": now_iso(), "created_by": admin["email"], "history": []}
    await audit(admin, "create", "coupons", doc["id"], None, {"code": code, "value": body.value}, reason)
    await db.coupons.insert_one(doc)
    await firebase_sync.push("coupons", [doc["id"]])
    return clean(doc)


class ValidateIn(BaseModel):
    code: str
    amount: float
    fee_type: str
    user_type: Optional[str] = None
    user_id: Optional[str] = None
    owner_id: Optional[str] = None


async def evaluate_coupon(code, amount, fee_type, user_type=None, user_id=None):
    c = await db.coupons.find_one({"code": (code or "").strip().upper()}, {"_id": 0})
    today = date.today().isoformat()
    if not c:
        return {"valid": False, "message": "Coupon not found"}
    aud, _ = ELIGIBILITY.get(c.get("eligibility", "all_owners"), ("owner", False))
    checks = [(c["status"] == "active", "Coupon is inactive"), (c["start_date"] <= today <= c["end_date"], "Coupon is not within validity dates"),
              (c["applies_to"] in ("both", fee_type), f"Coupon does not apply to {fee_type}"),
              (amount >= (c.get("min_amount") or 0), f"Minimum amount is {c.get('min_amount')}"),
              (c["used_count"] < c["max_usage"], "Coupon usage limit reached")]
    if user_type or user_id:
        checks.append((user_type in ("owner", "tenant") and bool(user_id), "user_type (owner/tenant) and user_id are required"))
        checks.append((aud is None or aud == user_type, f"Coupon is only for {aud}s"))
        checks.append((not c.get("eligibility", "").startswith("selected") or user_id in (c.get("eligible_ids") or []), "You are not eligible for this coupon"))
    for ok, msg in checks:
        if not ok:
            return {"valid": False, "message": msg}
    if user_id:
        used = await db.coupon_usages.count_documents({"coupon_id": c["id"], "$or": [{"user_id": user_id}, {"owner_id": user_id}]})
        if used >= c["per_owner_limit"]:
            return {"valid": False, "message": "Per-user usage limit reached"}
    disc = amount * c["value"] / 100 if c["discount_type"] == "percent" else c["value"]
    if c.get("max_discount"):
        disc = min(disc, c["max_discount"])
    disc = round(min(disc, amount), 2)
    final = round(amount - disc, 2)
    return {"valid": True, "coupon_id": c["id"], "discount": disc, "final_amount": final, "gst": gst_split(final), "message": "Coupon applied"}


@router.post("/coupons/validate")
async def validate_coupon(body: ValidateIn, admin=Depends(require("coupons", "view"))):
    ut, uid = body.user_type, body.user_id
    if body.owner_id and not uid:
        ut, uid = "owner", body.owner_id
    return await evaluate_coupon(body.code, body.amount, body.fee_type, ut, uid)


@router.get("/lookup/users")
async def lookup_users(type: str, q: str = "", ids: str = "", admin=Depends(current_admin)):
    if type not in ("owner", "tenant"):
        raise HTTPException(400, "type must be owner or tenant")
    coll = "owners" if type == "owner" else "tenants"
    if ids:
        query = {"id": {"$in": ids.split(",")}}
    else:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query = {"$or": [{"id": rx}, {"name": rx}, {"mobile": rx}]} if q.strip() else {}
    return [d async for d in db[coll].find(query, {"_id": 0, "id": 1, "name": 1, "mobile": 1, "status": 1}).limit(20)]


@router.get("/coupons/{cid}/usage")
async def coupon_usage(cid: str, admin=Depends(require("coupons", "view"))):
    return await enrich("coupon_usages", [clean(d) async for d in db.coupon_usages.find({"coupon_id": cid}).sort("created_at", -1)])


# Complaints
class ComplaintActionIn(BaseModel):
    action: str
    value: Optional[str] = None
    reason: str


@router.post("/complaints/{cid}/action")
async def complaint_action(cid: str, body: ComplaintActionIn, admin=Depends(require("complaints", "edit"))):
    reason = require_reason(body.reason)
    c = await must("complaints", cid)
    upd = {}
    if body.action == "status":
        if body.value not in ("open", "in_progress", "resolved"):
            raise HTTPException(400, "Invalid status")
        upd["status"] = body.value
        if body.value == "resolved":
            upd.update(resolution=reason, resolved_at=now_iso(), resolved_by=admin["email"])
    elif body.action == "escalate":
        upd.update(status="escalated", escalation_level=c.get("escalation_level", 0) + 1)
    elif body.action == "assign":
        a = await db.admins.find_one({"id": body.value})
        if not a:
            raise HTTPException(400, "Admin not found")
        upd["assigned_to"] = body.value
    elif body.action == "reopen":
        if c["status"] not in ("resolved", "closed"):
            raise HTTPException(400, "Only resolved/closed complaints can be reopened")
        upd.update(status="reopened", reopen_count=c.get("reopen_count", 0) + 1, close_reason=None, closed_at=None, resolution=None, resolved_at=None)
    elif body.action == "close":
        upd.update(status="closed", closed_at=now_iso(), close_reason=reason, resolution=c.get("resolution") or reason)
    elif body.action != "remark":
        raise HTTPException(400, "Unknown action")
    entry = {"at": now_iso(), "by": admin["email"], "action": body.action, "value": body.value, "old_status": c["status"], "reason": reason}
    await audit(admin, f"complaint_{body.action}", "complaints", cid, {k: c.get(k) for k in upd}, upd or {"remark": reason}, reason)
    await db.complaints.update_one({"id": cid}, {"$set": upd, "$push": {"timeline": entry}})
    return clean(await db.complaints.find_one({"id": cid}))


# Leaving requests
class SettlementIn(BaseModel):
    outstanding_rent: float = 0
    utilities: float = 0
    other_charges: float = 0
    damage: float = 0
    notes: Optional[str] = ""
    reason: str


@router.post("/leaving/{lid}/settlement")
async def settlement(lid: str, body: SettlementIn, admin=Depends(require("leaving", "edit"))):
    reason = require_reason(body.reason)
    lr = await must("leaving", lid)
    if lr["status"] in ("completed", "rejected"):
        raise HTTPException(400, "Settlement locked for completed/rejected requests")
    vals = [body.outstanding_rent, body.utilities, body.other_charges, body.damage]
    if any(v < 0 for v in vals):
        raise HTTPException(400, "Values cannot be negative")
    tenant = await must("tenants", lr["tenant_id"])
    deposit = float(tenant.get("deposit") or 0)
    deductions = round(sum(vals), 2)
    net = round(deposit - deductions, 2)
    s = {**body.model_dump(exclude={"reason"}), "deposit": deposit, "deposit_source": f"tenant {tenant['id']} record", "total_deductions": deductions, "refund_amount": max(net, 0),
         "payable_by_tenant": max(-net, 0), "calculated_at": now_iso(), "calculated_by": admin["email"], "reason": reason,
         "version": len(lr.get("settlement_history", [])) + 1}
    await audit(admin, "settlement", "leaving", lid, lr.get("settlement"), s, reason)
    await db.leaving.update_one({"id": lid}, {"$set": {"settlement": s, "refund_amount": s["refund_amount"], "settlement_status": "calculated"}, "$push": {"settlement_history": s}})
    return s


class LeaveActionIn(BaseModel):
    action: str
    reason: str


MOVE_OUT = ["not_started", "scheduled", "in_progress", "completed"]
SETTLEMENT_STATUS = ["pending", "calculated", "approved", "paid", "disputed"]


async def leaving_transition(lid, action, actor, actor_type, reason, owner_id=None):
    lr = await must("leaving", lid)
    if owner_id and lr["owner_id"] != owner_id:
        raise HTTPException(403, "This leaving request does not belong to this owner")
    flow = {"approve": (["pending"], "approved"), "reject": (["pending", "approved"], "rejected"), "complete": (["approved"], "completed")}
    if action not in flow:
        raise HTTPException(400, "Unknown action")
    allowed, new = flow[action]
    if lr["status"] not in allowed:
        raise HTTPException(400, f"Cannot {action} a {lr['status']} request")
    if new == "completed" and not lr.get("settlement"):
        raise HTTPException(400, "Calculate settlement before completing")
    by = {"by_type": actor_type, "by_id": actor["id"], "by_name": actor.get("name"), "by_email": actor.get("email"), "at": now_iso()}
    upd = {"status": new}
    if new == "approved":
        upd["approval"] = by
    if new == "rejected":
        upd.update(rejection=by, rejection_reason=reason)
    if new == "completed":
        upd.update(move_out_status="completed", completion=by)
    entry = {"at": now_iso(), "by": actor.get("email") or actor["id"], "actor_type": actor_type, "action": action, "old": lr["status"], "new": new, "reason": reason}
    await audit(actor, f"leaving_{action}", "leaving", lid, {"status": lr["status"]}, {"status": new, "by_type": actor_type}, reason)
    if new == "completed":
        await db.tenants.update_one({"id": lr["tenant_id"]}, {"$set": {"leave_date": lr["requested_leave_date"]}})
        await db.tenancies.update_one({"tenant_id": lr["tenant_id"], "property_id": lr["property_id"], "active": True},
                                      {"$set": {"active": False, "leave_date": lr["requested_leave_date"]}})
        if not await db.tenancies.count_documents({"property_id": lr["property_id"], "active": True}):
            await db.properties.update_one({"id": lr["property_id"]}, {"$set": {"occupancy_state": "vacant"}})
    await db.leaving.update_one({"id": lid}, {"$set": upd, "$push": {"timeline": entry}})
    return {"ok": True, "status": new}


async def leaving_field(lid, field, value, actor, actor_type, reason, owner_id=None):
    options = {"move_out_status": MOVE_OUT, "settlement_status": SETTLEMENT_STATUS}[field]
    if value not in options:
        raise HTTPException(400, f"{field} must be one of {options}")
    lr = await must("leaving", lid)
    if owner_id and lr["owner_id"] != owner_id:
        raise HTTPException(403, "This leaving request does not belong to this owner")
    if lr["status"] == "rejected":
        raise HTTPException(400, "Request is rejected")
    if field == "move_out_status" and value != "not_started" and lr["status"] == "pending":
        raise HTTPException(400, "Approve the request before updating move-out")
    if field == "settlement_status" and value in ("approved", "paid") and not lr.get("settlement"):
        raise HTTPException(400, "Calculate settlement first")
    old = lr.get(field)
    entry = {"at": now_iso(), "by": actor.get("email") or actor["id"], "actor_type": actor_type, "action": field, "old": old, "new": value, "reason": reason}
    await audit(actor, f"leaving_{field}", "leaving", lid, {field: old}, {field: value, "by_type": actor_type}, reason)
    await db.leaving.update_one({"id": lid}, {"$set": {field: value}, "$push": {"timeline": entry}})
    return {"ok": True, field: value}


@router.post("/leaving/{lid}/action")
async def leaving_action(lid: str, body: LeaveActionIn, admin=Depends(require("leaving", "edit"))):
    return await leaving_transition(lid, body.action, admin, "admin", require_reason(body.reason))


class LeaveFieldIn(BaseModel):
    field: str
    value: str
    reason: str


@router.post("/leaving/{lid}/status")
async def leaving_status(lid: str, body: LeaveFieldIn, admin=Depends(require("leaving", "edit"))):
    if body.field not in ("move_out_status", "settlement_status"):
        raise HTTPException(400, "Invalid field")
    return await leaving_field(lid, body.field, body.value, admin, "admin", require_reason(body.reason))


# Banners
class BannerIn(BaseModel):
    title: str
    description: Optional[str] = ""
    image_url: str
    button_text: Optional[str] = ""
    destination: Optional[str] = ""
    start_date: str
    end_date: str
    audience: str
    reason: str


@router.post("/banners")
async def create_banner(body: BannerIn, admin=Depends(require("banners", "edit"))):
    reason = require_reason(body.reason)
    if body.audience not in ("owner", "tenant"):
        raise HTTPException(400, "Audience must be owner or tenant")
    last = await db.banners.find_one({"audience": body.audience}, sort=[("order", -1)])
    doc = {**body.model_dump(exclude={"reason"}), "id": await next_id("BNR"), "order": (last["order"] + 1) if last else 1,
           "status": "active", "created_at": now_iso(), "created_by": admin["email"], "history": []}
    await audit(admin, "create", "banners", doc["id"], None, {"title": body.title}, reason)
    await db.banners.insert_one(doc)
    await firebase_sync.push("banners", [doc["id"]])
    return clean(doc)


class ReorderIn(BaseModel):
    ids: List[str]
    reason: str


@router.post("/banners/reorder")
async def reorder_banners(body: ReorderIn, admin=Depends(require("banners", "edit"))):
    reason = require_reason(body.reason)
    auds = {b["audience"] async for b in db.banners.find({"id": {"$in": body.ids}}, {"audience": 1})}
    if len(auds) != 1:
        raise HTTPException(400, "Reorder banners of one app (owner or tenant) at a time")
    await audit(admin, "reorder", "banners", "banners", None, {"audience": auds.pop(), "order": body.ids}, reason)
    for i, bid in enumerate(body.ids):
        await db.banners.update_one({"id": bid}, {"$set": {"order": i + 1}})
    await firebase_sync.push("banners", body.ids)
    return {"ok": True}


@router.get("/public/banners")
async def public_banners(audience: str):
    if audience not in ("owner", "tenant"):
        raise HTTPException(400, "audience must be owner or tenant")
    today = date.today().isoformat()
    q = {"status": "active", "audience": audience, "start_date": {"$lte": today}, "end_date": {"$gte": today}}
    return [clean(b) async for b in db.banners.find(q, {"history": 0, "created_by": 0}).sort("order", 1)]


@router.post("/notifications/{nid}/retry")
async def retry_notification(nid: str, body: ReasonIn, admin=Depends(require("notifications", "edit"))):
    reason = require_reason(body.reason)
    n = await must("notifications", nid)
    if n["status"] != "failed":
        raise HTTPException(400, "Only failed notifications can be re-queued")
    await audit(admin, "retry", "notifications", nid, {"status": "failed"}, {"status": "queued"}, reason)
    await db.notifications.update_one({"id": nid}, {"$set": {"status": "queued", "retry_count": n.get("retry_count", 0) + 1}})
    return {"ok": True}
