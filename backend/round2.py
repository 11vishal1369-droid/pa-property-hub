import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from core import (db, clean, audit, require, require_app, now_iso, require_reason, decrypt, fee_category, gst_split,
                  FEE_CATEGORIES, SYSTEM_ACTOR, GST_RATE_DEFAULT)
from data import enrich
from exports import pdf_bytes
import firebase_sync
from ops_routes import (must, agreement_full, agreement_lines, evaluate_coupon, leaving_transition, leaving_field)

router = APIRouter(prefix="/api")
app = APIRouter(prefix="/api/app", dependencies=[Depends(require_app)])
PARTIES = ("owner", "tenant")


async def bulk_ids(prefix, n):
    doc = await db.counters.find_one_and_update({"_id": prefix}, {"$inc": {"seq": n}}, upsert=True, return_document=True)
    return [f"{prefix}-{10000 + doc['seq'] - n + i + 1}" for i in range(n)]


async def settings():
    return await db.settings.find_one({"key": "global"}, {"_id": 0})


async def app_actor(request, user_type, user_id):
    if user_type not in PARTIES or not user_id:
        raise HTTPException(400, "user_type must be owner or tenant, and user_id is required")
    u = await db[f"{user_type}s"].find_one({"id": user_id}, {"_id": 0, "id": 1, "name": 1, "status": 1})
    if not u:
        raise HTTPException(404, f"{user_type.title()} not found")
    if u["status"] != "active":
        raise HTTPException(403, f"{user_type.title()} account is {u['status']}")
    return {"id": user_id, "email": f"{user_type}:{user_id}", "name": u["name"], "type": user_type,
            "ip": request.client.host if request.client else ""}


# ---------- e-Sign ----------
async def esign_initiate(aid, party, actor):
    if party not in PARTIES:
        raise HTTPException(400, "party must be owner or tenant")
    a = await must("agreements", aid)
    if a["status"] != "pending_signature":
        raise HTTPException(400, f"Agreement is {a['status']}; e-Sign is only possible while Pending Signature")
    if not a.get("fee_paid"):
        raise HTTPException(400, "Agreement fee must be paid before e-Sign")
    if (a.get("esign") or {}).get(party, {}).get("status") == "signed":
        raise HTTPException(400, f"{party.title()} has already signed")
    s = await db.settings.find_one({"key": "global"})
    cfg = s.get("esign") or {}
    if not (cfg.get("enabled") and cfg.get("api_base_url") and cfg.get("api_key_set") and cfg.get("webhook_secret_set")):
        raise HTTPException(400, "No e-Sign provider is configured. A Super Admin must set provider URL, API key and webhook secret in Settings → e-Sign.")
    full = await agreement_full(aid)
    signer = full["owner"] if party == "owner" else full["tenant"]
    reference = f"{aid}:{party}:{uuid.uuid4().hex[:10]}"
    payload = {"reference": reference, "auth_mode": "aadhaar_otp", "client_id": cfg.get("client_id"),
               "signer": {"name": signer.get("name"), "mobile": signer.get("mobile"), "email": signer.get("email"), "role": party},
               "document": {"name": f"{aid}_v{a['current_version']}.pdf",
                            "content_base64": base64.b64encode(pdf_bytes(f"PA Rental Agreement — {aid}", agreement_lines(full, a["current_version"]))).decode()},
               "callback_url": f"{os.environ['PUBLIC_BASE_URL']}/api/esign/webhook"}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{cfg['api_base_url'].rstrip('/')}/sign-requests", json=payload,
                             headers={"Authorization": f"Bearer {decrypt(s['esign_api_key_enc'])}"})
    except httpx.HTTPError as e:
        raise HTTPException(502, f"e-Sign provider unreachable: {e.__class__.__name__}")
    if r.status_code >= 300:
        raise HTTPException(502, f"e-Sign provider rejected the request ({r.status_code}): {r.text[:200]}")
    data = r.json()
    if not data.get("request_id"):
        raise HTTPException(502, "e-Sign provider response missing request_id")
    prev = (a.get("esign") or {}).get(party) or {}
    rec = {"status": "initiated", "provider": cfg.get("provider_name"), "request_id": data["request_id"], "reference": reference,
           "sign_url": data.get("sign_url"), "initiated_at": now_iso(), "initiated_by": actor["email"], "attempts": prev.get("attempts", 0) + 1}
    await audit(actor, "esign_initiate", "agreements", aid, {"status": prev.get("status", "pending")}, {"party": party, "request_id": data["request_id"]}, f"e-Sign request sent to {party}")
    await db.agreements.update_one({"id": aid}, {"$set": {f"esign.{party}": rec}, "$push": {"esign_history": {**rec, "party": party, "at": now_iso()}}})
    return {"party": party, "status": "initiated", "request_id": data["request_id"], "sign_url": data.get("sign_url")}


class InitiateIn(BaseModel):
    party: str


@router.post("/agreements/{aid}/esign/initiate")
async def admin_esign_initiate(aid: str, body: InitiateIn, admin=Depends(require("agreements", "edit"))):
    return await esign_initiate(aid, body.party, admin)


@router.get("/agreements/{aid}/esign/evidence")
async def esign_evidence(aid: str, admin=Depends(require("agreements", "view"))):
    return [clean(d) async for d in db.esign_evidence.find({"agreement_id": aid}).sort("received_at", -1)]


@router.post("/esign/webhook")
async def esign_webhook(request: Request):
    raw = await request.body()
    s = await db.settings.find_one({"key": "global"})
    if not s.get("esign_webhook_secret_enc"):
        raise HTTPException(503, "e-Sign webhook secret not configured")
    expected = hmac.new(decrypt(s["esign_webhook_secret_enc"]).encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Esign-Signature", "")):
        raise HTTPException(401, "Invalid provider signature")
    try:
        p = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Invalid JSON")
    rid, status = p.get("request_id"), p.get("status")
    if status not in ("signed", "failed"):
        raise HTTPException(400, "status must be signed or failed")
    a = await db.agreements.find_one({"$or": [{"esign.owner.request_id": rid}, {"esign.tenant.request_id": rid}]}, {"_id": 0})
    if not rid or not a:
        raise HTTPException(404, "Unknown e-Sign request")
    party = "owner" if a["esign"]["owner"].get("request_id") == rid else "tenant"
    cur = a["esign"][party]
    if cur.get("status") == "signed":
        return {"ok": True, "duplicate": True}
    ev_id = f"EVD-{uuid.uuid4().hex[:12]}"
    await db.esign_evidence.insert_one({"id": ev_id, "agreement_id": a["id"], "party": party, "request_id": rid, "status": status,
                                        "payload_raw": raw.decode("utf-8", "replace"), "payload_sha256": hashlib.sha256(raw).hexdigest(),
                                        "signature_header": request.headers.get("X-Esign-Signature"), "received_at": now_iso(),
                                        "ip": request.client.host if request.client else ""})
    rec = {**cur, "status": status, "signed_at": p.get("signed_at") if status == "signed" else None, "provider_ref": p.get("provider_ref"),
           "verification_result": p.get("verification_result"), "signer_name": p.get("signer_name"),
           "aadhaar_last4": str(p.get("aadhaar_last4") or "")[-4:] or None, "failure_reason": p.get("failure_reason"),
           "evidence_id": ev_id, "updated_at": now_iso()}
    other = a["esign"]["owner" if party == "tenant" else "tenant"]
    upd = {f"esign.{party}": rec}
    hist = {"at": now_iso(), "by": "esign-provider", "action": f"esign_{party}_{status}", "old": a["status"], "new": a["status"], "reason": f"Provider ref {p.get('provider_ref')}"}
    if status == "signed" and other.get("status") == "signed":
        upd.update(status="completed", completed_at=now_iso())
        hist["new"] = "completed"
    actor = {**SYSTEM_ACTOR, "ip": request.client.host if request.client else ""}
    await audit(actor, f"esign_{status}", "agreements", a["id"], {"party": party, "status": cur.get("status")},
                {"party": party, "status": status, "agreement_status": upd.get("status", a["status"]), "evidence_id": ev_id}, f"Verified provider callback {rid}")
    await db.agreements.update_one({"id": a["id"]}, {"$set": upd, "$push": {"status_history": hist}})
    return {"ok": True, "agreement_status": upd.get("status", a["status"])}


# ---------- Notifications ----------
class SendIn(BaseModel):
    audience: str
    target: str
    recipient_ids: List[str] = []
    title: str
    message: str
    scheduled_at: Optional[str] = None
    reason: str


@router.post("/notifications/send")
async def send_notifications(body: SendIn, admin=Depends(require("notifications", "edit"))):
    reason = require_reason(body.reason)
    if body.audience not in PARTIES:
        raise HTTPException(400, "audience must be owner or tenant")
    if body.target not in ("all", "selected"):
        raise HTTPException(400, "target must be all or selected")
    if not body.title.strip() or not body.message.strip():
        raise HTTPException(400, "Title and message are required")
    sched = None
    if body.scheduled_at:
        try:
            sched = datetime.fromisoformat(body.scheduled_at)
        except ValueError:
            raise HTTPException(400, "Invalid schedule date/time")
        sched = (sched if sched.tzinfo else sched.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        if sched <= datetime.now(timezone.utc):
            raise HTTPException(400, "Scheduled time must be in the future")
    coll = f"{body.audience}s"
    q = {"status": {"$ne": "archived"}}
    if body.target == "selected":
        ids = list(dict.fromkeys(body.recipient_ids))
        if not ids:
            raise HTTPException(400, "Select at least one recipient")
        q = {"id": {"$in": ids}}
    users = [u async for u in db[coll].find(q, {"_id": 0, "id": 1, "name": 1})]
    if body.target == "selected" and len(users) != len(ids):
        raise HTTPException(400, f"All recipients must be {body.audience}s")
    if not users:
        raise HTTPException(400, "No recipients found")
    cid = (await bulk_ids("NTC", 1))[0]
    status = "scheduled" if sched else "queued"
    camp = {"id": cid, "audience": body.audience, "target": body.target, "recipient_count": len(users), "title": body.title.strip(),
            "message": body.message.strip(), "scheduled_at": sched.isoformat() if sched else None, "created_by": admin["email"], "created_at": now_iso(), "reason": reason}
    await audit(admin, "send_notification", "notifications", cid, None, {"audience": body.audience, "target": body.target, "count": len(users), "title": camp["title"]}, reason)
    await db.notification_campaigns.insert_one(camp)
    ids = await bulk_ids("NTF", len(users))
    await db.notifications.insert_many([{"id": nid, "campaign_id": cid, "recipient_id": u["id"], "recipient_name": u["name"], "recipient_type": body.audience,
                                         "type": "announcement", "channel": "in_app", "title": camp["title"], "message": camp["message"],
                                         "scheduled_at": camp["scheduled_at"], "status": status, "created_at": now_iso()} for nid, u in zip(ids, users)])
    await firebase_sync.push("notifications", ids)
    return clean(camp)


@router.get("/notifications/campaigns")
async def campaigns(audience: str, admin=Depends(require("notifications", "view"))):
    out = [clean(c) async for c in db.notification_campaigns.find({"audience": audience}).sort("created_at", -1).limit(100)]
    for c in out:
        c["delivery"] = {g["_id"]: g["n"] async for g in db.notifications.aggregate([{"$match": {"campaign_id": c["id"]}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    return out


# ---------- App API (Owner / Tenant apps, X-App-Key) ----------
@app.get("/fees")
async def app_fees(property_id: Optional[str] = None):
    s = await settings()
    rate = s["tax"].get("gst_percent", GST_RATE_DEFAULT)
    out = {"gst_inclusive": True, "gst_rate": rate, "platform_fee": s["owner_platform_fee"], "platform_validity_days": s["platform_validity_days"],
           "platform_fee_gst": gst_split(s["owner_platform_fee"], rate), "tenant_fees": s["tenant_fees"],
           "agreement_fees": [{"category": k, "fee": s["agreement_fees"][k], "gst": gst_split(s["agreement_fees"][k], rate)} for k in FEE_CATEGORIES]}
    if property_id:
        p = await must("properties", property_id)
        cat = fee_category(p)
        out["property"] = {"id": p["id"], "fee_category": cat, "agreement_fee": s["agreement_fees"][cat], "gst": gst_split(s["agreement_fees"][cat], rate)}
    return out


class QuoteIn(BaseModel):
    fee_type: str
    property_id: Optional[str] = None
    user_type: str
    user_id: str
    coupon_code: Optional[str] = None


@app.post("/fees/quote")
async def app_quote(body: QuoteIn, request: Request):
    await app_actor(request, body.user_type, body.user_id)
    s = await settings()
    rate = s["tax"].get("gst_percent", GST_RATE_DEFAULT)
    if body.fee_type == "platform_fee":
        amount, cat = s["owner_platform_fee"], None
    elif body.fee_type == "agreement_fee":
        if not body.property_id:
            raise HTTPException(400, "property_id is required for agreement fee")
        cat = fee_category(await must("properties", body.property_id))
        amount = s["agreement_fees"][cat]
    else:
        raise HTTPException(400, "fee_type must be agreement_fee or platform_fee")
    out = {"fee_type": body.fee_type, "fee_category": cat, "amount": amount, "discount": 0, "final_amount": amount, "coupon": None}
    if body.coupon_code:
        if not s["coupon_applicability"].get(body.fee_type, True):
            raise HTTPException(400, f"Coupons are disabled for {body.fee_type}")
        res = await evaluate_coupon(body.coupon_code, amount, body.fee_type, body.user_type, body.user_id)
        out["coupon"] = res
        if res["valid"]:
            out.update(discount=res["discount"], final_amount=res["final_amount"])
    out["gst"] = gst_split(out["final_amount"], rate)
    return out


class AppCouponIn(BaseModel):
    code: str
    amount: float
    fee_type: str
    user_type: str
    user_id: str


@app.post("/coupons/validate")
async def app_coupon(body: AppCouponIn, request: Request):
    await app_actor(request, body.user_type, body.user_id)
    return await evaluate_coupon(body.code, body.amount, body.fee_type, body.user_type, body.user_id)


@app.get("/notifications")
async def app_notifications(user_type: str, user_id: str, request: Request):
    await app_actor(request, user_type, user_id)
    now = now_iso()
    base = {"recipient_type": user_type, "recipient_id": user_id}
    await db.notifications.update_many({**base, "status": {"$in": ["queued", "sent"]}, "scheduled_at": None}, {"$set": {"status": "delivered", "delivered_at": now}})
    await db.notifications.update_many({**base, "status": "scheduled", "scheduled_at": {"$lte": now}}, {"$set": {"status": "delivered", "delivered_at": now}})
    q = {**base, "status": {"$in": ["delivered", "read"]}}
    return [clean(n) async for n in db.notifications.find(q).sort("created_at", -1).limit(100)]


class AckIn(BaseModel):
    user_type: str
    user_id: str


@app.post("/notifications/{nid}/read")
async def app_read(nid: str, body: AckIn):
    r = await db.notifications.update_one({"id": nid, "recipient_type": body.user_type, "recipient_id": body.user_id, "status": "delivered"},
                                          {"$set": {"status": "read", "read_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(404, "Notification not found for this user")
    return {"ok": True}


def party_filter(user_type, user_id):
    return {f"{user_type}_id": user_id}


class AppComplaintIn(BaseModel):
    user_type: str
    user_id: str
    property_id: str
    tenant_id: Optional[str] = None
    subject: str
    description: str
    category: str = "Maintenance"
    priority: str = "medium"
    attachments: List[str] = []


@app.post("/complaints")
async def app_create_complaint(body: AppComplaintIn, request: Request):
    actor = await app_actor(request, body.user_type, body.user_id)
    prop = await must("properties", body.property_id)
    if body.user_type == "owner":
        if prop["owner_id"] != body.user_id:
            raise HTTPException(403, "Property does not belong to this owner")
        tenant_id = body.tenant_id
    else:
        t = await must("tenants", body.user_id)
        if t["property_id"] != body.property_id:
            raise HTTPException(403, "Tenant is not linked to this property")
        tenant_id = body.user_id
    if tenant_id:
        tt = await must("tenants", tenant_id)
        if tt["property_id"] != body.property_id:
            raise HTTPException(400, "Tenant is not linked to this property")
    if not body.subject.strip() or not body.description.strip():
        raise HTTPException(400, "Subject and description are required")
    cid = (await bulk_ids("CMP", 1))[0]
    msg = {"id": uuid.uuid4().hex[:10], "sender_type": body.user_type, "sender_id": body.user_id, "sender_name": actor["name"],
           "text": body.description.strip(), "attachments": body.attachments, "at": now_iso()}
    doc = {"id": cid, "subject": body.subject.strip(), "description": body.description.strip(), "category": body.category, "priority": body.priority,
           "raised_by": body.user_type, "raised_by_id": body.user_id, "tenant_id": tenant_id, "owner_id": prop["owner_id"], "property_id": prop["id"],
           "assigned_to": None, "status": "open", "attachments": body.attachments, "messages": [msg], "escalation_level": 0, "reopen_count": 0,
           "timeline": [{"at": now_iso(), "by": actor["email"], "action": "created", "reason": "Raised from app"}], "created_at": now_iso()}
    await audit(actor, "create", "complaints", cid, None, {"subject": doc["subject"]}, "Raised from app")
    await db.complaints.insert_one(doc)
    return clean(doc)


@app.get("/complaints")
async def app_list_complaints(user_type: str, user_id: str, request: Request):
    await app_actor(request, user_type, user_id)
    return await enrich("complaints", [clean(c) async for c in db.complaints.find(party_filter(user_type, user_id)).sort("created_at", -1).limit(200)])


async def complaint_for(cid, user_type, user_id):
    c = await must("complaints", cid)
    if c.get(f"{user_type}_id") != user_id:
        raise HTTPException(403, "Not a party to this complaint")
    return c


@app.get("/complaints/{cid}")
async def app_get_complaint(cid: str, user_type: str, user_id: str, request: Request):
    await app_actor(request, user_type, user_id)
    return (await enrich("complaints", [clean(await complaint_for(cid, user_type, user_id))]))[0]


class MessageIn(BaseModel):
    user_type: str
    user_id: str
    text: str
    attachments: List[str] = []


@app.post("/complaints/{cid}/messages")
async def app_reply(cid: str, body: MessageIn, request: Request):
    actor = await app_actor(request, body.user_type, body.user_id)
    c = await complaint_for(cid, body.user_type, body.user_id)
    if c["status"] == "closed":
        raise HTTPException(400, "Complaint is closed")
    if not body.text.strip():
        raise HTTPException(400, "Message text is required")
    msg = {"id": uuid.uuid4().hex[:10], "sender_type": body.user_type, "sender_id": body.user_id, "sender_name": actor["name"],
           "text": body.text.strip(), "attachments": body.attachments, "at": now_iso()}
    await audit(actor, "complaint_reply", "complaints", cid, None, {"message_id": msg["id"]}, "App reply")
    await db.complaints.update_one({"id": cid}, {"$push": {"messages": msg}})
    return msg


class AppLeaveIn(BaseModel):
    user_type: str
    user_id: str
    tenant_id: str
    requested_leave_date: str
    reason_text: str


@app.post("/leaving")
async def app_create_leaving(body: AppLeaveIn, request: Request):
    actor = await app_actor(request, body.user_type, body.user_id)
    t = await must("tenants", body.tenant_id)
    if (body.user_type == "tenant" and body.user_id != t["id"]) or (body.user_type == "owner" and t["owner_id"] != body.user_id):
        raise HTTPException(403, "Not allowed to raise a leaving request for this tenant")
    if await db.leaving.find_one({"tenant_id": t["id"], "status": {"$in": ["pending", "approved"]}}):
        raise HTTPException(409, "An open leaving request already exists for this tenant")
    lid = (await bulk_ids("LVR", 1))[0]
    doc = {"id": lid, "tenant_id": t["id"], "owner_id": t["owner_id"], "property_id": t["property_id"], "requested_by": body.user_type,
           "requested_by_id": body.user_id, "requested_by_name": actor["name"], "requested_leave_date": body.requested_leave_date,
           "reason_text": body.reason_text, "deposit": t.get("deposit"), "refund_amount": None, "settlement": None, "settlement_history": [],
           "status": "pending", "move_out_status": "not_started", "settlement_status": "pending",
           "timeline": [{"at": now_iso(), "by": actor["email"], "actor_type": body.user_type, "action": "created", "new": "pending", "reason": body.reason_text}],
           "created_at": now_iso()}
    await audit(actor, "create", "leaving", lid, None, {"tenant_id": t["id"], "requested_by": body.user_type}, body.reason_text)
    await db.leaving.insert_one(doc)
    return clean(doc)


@app.get("/leaving")
async def app_list_leaving(user_type: str, user_id: str, request: Request):
    await app_actor(request, user_type, user_id)
    return await enrich("leaving", [clean(d) async for d in db.leaving.find(party_filter(user_type, user_id)).sort("created_at", -1)])


class OwnerLeaveActionIn(BaseModel):
    owner_id: str
    action: str
    reason: str


@app.post("/leaving/{lid}/action")
async def app_leaving_action(lid: str, body: OwnerLeaveActionIn, request: Request):
    actor = await app_actor(request, "owner", body.owner_id)
    if body.action == "complete":
        raise HTTPException(400, "Move-out completion is done by updating move-out status after settlement")
    return await leaving_transition(lid, body.action, actor, "owner", require_reason(body.reason), owner_id=body.owner_id)


class OwnerLeaveFieldIn(BaseModel):
    owner_id: str
    field: str
    value: str
    reason: str


@app.post("/leaving/{lid}/status")
async def app_leaving_status(lid: str, body: OwnerLeaveFieldIn, request: Request):
    actor = await app_actor(request, "owner", body.owner_id)
    if body.field not in ("move_out_status", "settlement_status"):
        raise HTTPException(400, "Invalid field")
    return await leaving_field(lid, body.field, body.value, actor, "owner", require_reason(body.reason), owner_id=body.owner_id)


class AppSignIn(BaseModel):
    user_type: str
    user_id: str


@app.post("/agreements/{aid}/esign/initiate")
async def app_esign(aid: str, body: AppSignIn, request: Request):
    actor = await app_actor(request, body.user_type, body.user_id)
    a = await must("agreements", aid)
    if a.get(f"{body.user_type}_id") != body.user_id:
        raise HTTPException(403, "Not a party to this agreement")
    return await esign_initiate(aid, body.user_type, actor)


@app.get("/agreements/{aid}/esign")
async def app_esign_status(aid: str, user_type: str, user_id: str, request: Request):
    await app_actor(request, user_type, user_id)
    a = await must("agreements", aid)
    if a.get(f"{user_type}_id") != user_id:
        raise HTTPException(403, "Not a party to this agreement")
    strip = lambda e: {k: e.get(k) for k in ("status", "signed_at", "provider", "provider_ref", "verification_result", "sign_url")}
    return {"agreement_status": a["status"], "owner": strip(a["esign"]["owner"]), "tenant": strip(a["esign"]["tenant"])}


# ---------- Migration ----------
async def migrate_round2():
    if await db.migrations.find_one({"_id": "round2"}):
        return
    s = await settings()
    old = s.get("agreement_fees", {})
    await db.settings.update_one({"key": "global"}, {"$set": {
        "agreement_fees": {k: old.get(k, s.get("agreement_fee_default", 99)) for k in FEE_CATEGORIES},
        "tax": {**s.get("tax", {}), "gst_enabled": True, "gst_inclusive": True, "gst_percent": 18},
        "esign": s.get("esign") or {"provider_name": "", "mode": "test", "api_base_url": "", "client_id": "", "enabled": False,
                                    "api_key_set": False, "api_key_last4": "", "webhook_secret_set": False, "webhook_secret_last4": ""}}})
    props = {p["id"]: p async for p in db.properties.find({}, {"_id": 0})}
    async for a in db.agreements.find({"esign": {"$exists": False}}, {"_id": 0}):
        new = a["status"] if a["status"] in ("draft", "archived") else "pending_signature"
        upd = {"esign": {"owner": {"status": "pending"}, "tenant": {"status": "pending"}}, "status": new, "legacy_status": a["status"],
               "legacy_verification": a.get("verification"), "fee_category": fee_category(props.get(a["property_id"], {}))}
        if a["status"] == "archived":
            upd["status_before_archive"] = "pending_signature"
        await db.agreements.update_one({"id": a["id"]}, {"$set": upd, "$unset": {"verification": ""}, "$push": {"status_history": {
            "at": now_iso(), "by": "system", "action": "migration", "old": a["status"], "new": new,
            "reason": "Manual approval removed; completion requires Aadhaar e-Sign by owner and tenant"}}})
    async for c in db.complaints.find({"messages": {"$exists": False}}, {"_id": 0}):
        sender = c.get("raised_by", "tenant")
        sid = c.get(f"{sender}_id")
        coll = f"{sender}s"
        u = await db[coll].find_one({"id": sid}, {"name": 1}) if sid else None
        await db.complaints.update_one({"id": c["id"]}, {"$set": {"raised_by_id": sid, "attachments": c.get("attachments", []), "messages": [
            {"id": uuid.uuid4().hex[:10], "sender_type": sender, "sender_id": sid, "sender_name": (u or {}).get("name"), "text": c.get("description", ""),
             "attachments": [], "at": c["created_at"]}]}})
    await db.leaving.update_many({"requested_by": {"$exists": False}}, {"$set": {"requested_by": "tenant", "move_out_status": "not_started", "settlement_status": "pending"}})
    await db.leaving.update_many({"status": "completed", "move_out_status": "not_started"}, {"$set": {"move_out_status": "completed", "settlement_status": "calculated"}})
    async for b in db.banners.find({"audience": "both"}, {"_id": 0}):
        await db.banners.update_one({"id": b["id"]}, {"$set": {"audience": "owner"}})
        await db.banners.insert_one({**b, "id": (await bulk_ids("BNR", 1))[0], "audience": "tenant", "copied_from": b["id"]})
    for aud in PARTIES:
        i = 0
        async for b in db.banners.find({"audience": aud}).sort("order", 1):
            i += 1
            await db.banners.update_one({"_id": b["_id"]}, {"$set": {"order": i}})
    await db.coupons.update_many({"eligibility": {"$exists": False}}, {"$set": {"eligibility": "all_owners", "eligible_ids": []}})
    async for n in db.notifications.find({"message": {"$exists": False}}, {"_id": 0, "id": 1, "title": 1}):
        await db.notifications.update_one({"id": n["id"]}, {"$set": {"message": n["title"], "scheduled_at": None}})
    await db.migrations.insert_one({"_id": "round2", "at": now_iso()})
