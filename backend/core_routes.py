import re
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from core import (db, clean, audit, require, current_admin, now_iso, require_reason, hash_password, verify_password,
                  create_token, next_id, MODULES, LEVELS, hash_entry, encrypt)

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
async def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    ident = f"account:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until", "") <= now_iso():
        await db.login_attempts.delete_one({"identifier": ident})
        att = None
    if att and att.get("count", 0) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    admin = await db.admins.find_one({"email": email})
    if not admin or not verify_password(body.password, admin["password_hash"]):
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$setOnInsert": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    if admin.get("status") != "active":
        raise HTTPException(403, "Your admin account is inactive")
    await db.login_attempts.delete_one({"identifier": ident})
    await db.admins.update_one({"id": admin["id"]}, {"$set": {"last_login": now_iso()}})
    a = {"id": admin["id"], "email": admin["email"], "name": admin["name"], "ip": ip}
    await audit(a, "login", "auth", admin["id"])
    return {"token": create_token(admin["id"], admin["email"]), "admin": clean(admin)}


@router.get("/auth/me")
async def me(admin=Depends(current_admin)):
    return admin


@router.post("/auth/logout")
async def logout(admin=Depends(current_admin)):
    await audit(admin, "logout", "auth", admin["id"])
    return {"ok": True}


class PwdIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
async def change_password(body: PwdIn, admin=Depends(current_admin)):
    doc = await db.admins.find_one({"id": admin["id"]})
    if not verify_password(body.current_password, doc["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    await audit(admin, "change_password", "auth", admin["id"], reason="Self password change")
    await db.admins.update_one({"id": admin["id"]}, {"$set": {"password_hash": hash_password(body.new_password), "password_changed_at": now_iso()}})
    return {"ok": True}


class AdminIn(BaseModel):
    name: str
    email: str
    password: str
    role: str
    mobile: Optional[str] = None
    reason: str


@router.post("/admins")
async def create_admin(body: AdminIn, admin=Depends(require("admins", "edit"))):
    reason = require_reason(body.reason)
    email = body.email.strip().lower()
    if await db.admins.find_one({"email": email}):
        raise HTTPException(409, "Admin with this email already exists")
    if not await db.roles.find_one({"name": body.role}):
        raise HTTPException(400, "Unknown role")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    doc = {"id": await next_id("ADM"), "name": body.name, "email": email, "mobile": body.mobile, "role": body.role,
           "status": "active", "password_hash": hash_password(body.password), "created_at": now_iso(), "created_by": admin["email"]}
    await audit(admin, "create", "admins", doc["id"], None, {"email": email, "role": body.role}, reason)
    await db.admins.insert_one(doc)
    return clean(doc)


class ResetIn(BaseModel):
    new_password: str
    reason: str


@router.post("/admins/{aid}/reset-password")
async def reset_admin_password(aid: str, body: ResetIn, admin=Depends(require("admins", "edit"))):
    reason = require_reason(body.reason)
    if len(body.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if not await db.admins.find_one({"id": aid}):
        raise HTTPException(404, "Admin not found")
    await audit(admin, "reset_password", "admins", aid, reason=reason)
    await db.admins.update_one({"id": aid}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}


@router.get("/roles")
async def list_roles(admin=Depends(current_admin)):
    return {"roles": [r async for r in db.roles.find({}, {"_id": 0})], "modules": MODULES, "levels": list(LEVELS)}


class RoleIn(BaseModel):
    permissions: Dict[str, str]
    reason: str


@router.put("/roles/{name}")
async def update_role(name: str, body: RoleIn, admin=Depends(require("admins", "edit"))):
    reason = require_reason(body.reason)
    role = await db.roles.find_one({"name": name}, {"_id": 0})
    if not role:
        raise HTTPException(404, "Role not found")
    if role.get("locked"):
        raise HTTPException(400, "Super Admin role permissions are locked")
    perms = {m: (body.permissions.get(m) if body.permissions.get(m) in LEVELS else "none") for m in MODULES}
    await audit(admin, "update_permissions", "admins", name, role["permissions"], perms, reason)
    await db.roles.update_one({"name": name}, {"$set": {"permissions": perms, "updated_at": now_iso()}})
    return {"name": name, "permissions": perms}


class NewRoleIn(BaseModel):
    name: str
    description: Optional[str] = ""
    reason: str


@router.post("/roles")
async def create_role(body: NewRoleIn, admin=Depends(require("admins", "edit"))):
    reason = require_reason(body.reason)
    if await db.roles.find_one({"name": body.name}):
        raise HTTPException(409, "Role exists")
    doc = {"name": body.name, "description": body.description, "permissions": {m: "none" for m in MODULES}, "locked": False}
    await audit(admin, "create_role", "admins", body.name, None, {"name": body.name}, reason)
    await db.roles.insert_one(doc)
    return clean(doc)


@router.get("/settings")
async def get_settings(admin=Depends(require("settings", "view"))):
    s = await db.settings.find_one({"key": "global"}, {"_id": 0})
    s["gateway"]["secret_masked"] = "••••••••" + s["gateway"].get("secret_last4", "") if s["gateway"].get("secret_set") else ""
    s.pop("gateway_secret_enc", None)
    return s


class SettingsIn(BaseModel):
    settings: Dict[str, Any]
    reason: str
    gateway_secret: Optional[str] = None


@router.put("/settings")
async def update_settings(body: SettingsIn, admin=Depends(require("settings", "edit"))):
    reason = require_reason(body.reason)
    old = await db.settings.find_one({"key": "global"}, {"_id": 0, "gateway_secret_enc": 0})
    new = {k: v for k, v in body.settings.items() if k in old and k not in ("key", "version", "updated_at", "updated_by")}
    if "gateway" in new:
        new["gateway"].pop("secret_masked", None)
        new["gateway"]["secret_set"] = old["gateway"].get("secret_set", False)
        new["gateway"]["secret_last4"] = old["gateway"].get("secret_last4", "")
    upd = {**new, "version": old.get("version", 1) + 1, "updated_at": now_iso(), "updated_by": admin["email"]}
    if body.gateway_secret:
        upd["gateway_secret_enc"] = encrypt(body.gateway_secret)
        upd.setdefault("gateway", dict(old["gateway"]))
        upd["gateway"]["secret_set"] = True
        upd["gateway"]["secret_last4"] = body.gateway_secret[-4:]
    changed_old = {k: old.get(k) for k in new}
    await audit(admin, "update_settings", "settings", "global", changed_old, {k: upd.get(k) for k in new if k != "gateway_secret_enc"}, reason)
    await db.settings_history.insert_one({**old, "archived_at": now_iso(), "replaced_by": admin["email"], "reason": reason})
    await db.settings.update_one({"key": "global"}, {"$set": upd})
    return await get_settings(admin)


@router.get("/settings/history")
async def settings_history(admin=Depends(require("settings", "view"))):
    return [d async for d in db.settings_history.find({}, {"_id": 0, "gateway_secret_enc": 0}).sort("archived_at", -1).limit(50)]


@router.get("/audit/verify")
async def verify_audit(admin=Depends(require("audit", "view"))):
    prev, count = "GENESIS", 0
    async for e in db.audit_logs.find({}, {"_id": 0}).sort("seq", 1):
        if e["prev_hash"] != prev or hash_entry(e) != e["hash"]:
            return {"valid": False, "broken_at": e["id"], "checked": count}
        prev, count = e["hash"], count + 1
    return {"valid": True, "checked": count}


def resolve_range(rng, frm, to):
    today = datetime.now(timezone.utc).date()
    if rng == "today":
        return today, today
    if rng == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if rng == "last7":
        return today - timedelta(days=6), today
    if rng == "last30":
        return today - timedelta(days=29), today
    if rng == "this_month":
        return today.replace(day=1), today
    if rng == "prev_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if rng == "this_year":
        return today.replace(month=1, day=1), today
    if rng == "custom" and frm and to:
        return date.fromisoformat(frm), date.fromisoformat(to)
    return None, None


@router.get("/dashboard")
async def dashboard(range: str = "all", frm: Optional[str] = None, to: Optional[str] = None, admin=Depends(require("dashboard", "view"))):
    s, e = resolve_range(range, frm, to)
    dq = {"created_at": {"$gte": s.isoformat(), "$lte": e.isoformat() + "T23:59:59.999999"}} if s else {}

    async def c(coll, extra=None):
        return await db[coll].count_documents({**dq, **(extra or {})})

    async def total(match):
        r = [x async for x in db.payments.aggregate([{"$match": {**dq, **match}}, {"$group": {"_id": None, "t": {"$sum": "$amount"}, "d": {"$sum": "$discount"}, "r": {"$sum": "$refunded_amount"}}}])]
        return r[0] if r else {"t": 0, "d": 0, "r": 0}
    ok = {"status": {"$in": ["success", "approved", "refunded", "partially_refunded"]}}
    agr_fee = await total({"purpose": "agreement_fee", **ok})
    sub_fee = await total({"purpose": "platform_fee", **ok})
    disc = await total({"coupon_code": {"$nin": [None, ""]}, **ok})
    online = await total({"method": "online", **ok})
    manual_count = await c("payments", {"method": "manual"})
    refunds = [x async for x in db.refunds.aggregate([{"$match": dq}, {"$group": {"_id": None, "t": {"$sum": "$amount"}}}])]
    settle = [x async for x in db.leaving.aggregate([{"$match": {**dq, "status": "completed"}}, {"$group": {"_id": None, "t": {"$sum": "$refund_amount"}}}])]
    cards = {
        "owners_total": await c("owners"), "owners_active": await c("owners", {"status": "active"}),
        "owners_blocked": await c("owners", {"status": "blocked"}), "owners_deactivated": await c("owners", {"status": "deactivated"}),
        "tenants_total": await c("tenants"), "tenants_active": await c("tenants", {"status": "active"}),
        "tenants_blocked": await c("tenants", {"status": "blocked"}), "tenants_deactivated": await c("tenants", {"status": "deactivated"}),
        "properties_total": await c("properties"), "properties_active": await c("properties", {"status": "active"}),
        "properties_occupied": await c("properties", {"occupancy_state": "occupied", "status": "active"}),
        "properties_vacant": await c("properties", {"occupancy_state": "vacant", "status": "active"}),
        "properties_archived": await c("properties", {"status": "archived"}),
        "pg_count": await c("properties", {"category": "PG"}), "residential_count": await c("properties", {"category": "Residential"}),
        "commercial_count": await c("properties", {"category": "Commercial"}),
        "agreements_total": await c("agreements"), "agreements_pending": await c("agreements", {"status": {"$in": ["pending_verification", "draft"]}}),
        "agreements_completed": await c("agreements", {"status": {"$in": ["verified", "completed"]}}),
        "agreement_fees": agr_fee["t"], "subscription_fees": sub_fee["t"], "coupon_discounts": disc["d"],
        "online_payments": online["t"], "manual_submissions": manual_count,
        "pending_approvals": await c("payments", {"method": "manual", "status": "pending"}),
        "complaints_total": await c("complaints"), "complaints_pending": await c("complaints", {"status": {"$in": ["open", "in_progress", "escalated", "reopened"]}}),
        "leaving_pending": await c("leaving", {"status": "pending"}),
        "refunds_settlements": (refunds[0]["t"] if refunds else 0) + (settle[0]["t"] if settle else 0),
    }
    monthly = [x async for x in db.payments.aggregate([{"$match": {**dq, **ok}}, {"$group": {"_id": {"$substr": ["$created_at", 0, 7]}, "amount": {"$sum": "$amount"}}}, {"$sort": {"_id": 1}}])]
    status_mix = [x async for x in db.payments.aggregate([{"$match": dq}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])]
    recent = [clean(x) async for x in db.audit_logs.find({}, {"_id": 0}).sort("seq", -1).limit(8)]
    return {"cards": cards, "range": {"from": s.isoformat() if s else None, "to": e.isoformat() if e else None},
            "monthly_revenue": [{"month": m["_id"], "amount": m["amount"]} for m in monthly][-12:],
            "payment_status": [{"status": x["_id"], "count": x["n"]} for x in status_mix], "recent_activity": recent}


SEARCH_SPACES = [("owners", "owners", ["id", "name", "mobile", "email"]), ("tenants", "tenants", ["id", "name", "mobile", "email"]),
                 ("properties", "properties", ["id", "name", "address", "city"]), ("agreements", "agreements", ["id", "category"]),
                 ("payments", "finance", ["id", "txn_ref", "receipt_no"]), ("complaints", "complaints", ["id", "subject"]),
                 ("leaving", "leaving", ["id"])]


@router.get("/search")
async def global_search(q: str, admin=Depends(current_admin)):
    if len(q.strip()) < 2:
        return {"results": {}}
    rx = {"$regex": re.escape(q.strip()), "$options": "i"}
    out = {}
    for coll, module, fields in SEARCH_SPACES:
        if LEVELS.get(admin["permissions"].get(module, "none"), 0) < 1:
            continue
        out[coll] = [clean(d) async for d in db[coll].find({"$or": [{f: rx} for f in fields]}).limit(10)]
    return {"results": out}


@router.get("/archive/summary")
async def archive_summary(admin=Depends(require("archive", "view"))):
    return {c: await db[c].count_documents({"status": "archived"}) for c in ["owners", "tenants", "properties", "agreements"]}


class RestoreIn(BaseModel):
    reason: str


@router.post("/archive/{entity}/{rid}/restore")
async def restore(entity: str, rid: str, body: RestoreIn, admin=Depends(require("archive", "edit"))):
    reason = require_reason(body.reason)
    if entity not in ("owners", "tenants", "properties", "agreements"):
        raise HTTPException(400, "Invalid entity")
    doc = await db[entity].find_one({"id": rid, "status": "archived"}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Archived record not found")
    new_status = doc.get("status_before_archive") or ("pending_verification" if entity == "agreements" else "active")
    if new_status == "archived":
        new_status = "active"
    entry = {"at": now_iso(), "by": admin["email"], "action": "restore", "old": "archived", "new": new_status, "reason": reason}
    await audit(admin, "restore", entity, rid, {"status": "archived"}, {"status": new_status}, reason)
    await db[entity].update_one({"id": rid}, {"$set": {"status": new_status}, "$push": {"status_history": entry}})
    return {"ok": True, "status": new_status}
