import re
from datetime import date
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from core import db, clean, audit, current_admin, LEVELS, now_iso, require_reason, gst_split, GST_RATE_DEFAULT, fee_category
from exports import export_response

router = APIRouter(prefix="/api/data")

STD_STATUS = ["active", "blocked", "suspended", "deactivated", "archived"]

ENTITIES = {
    "owners": dict(module="owners", search=["id", "name", "mobile", "email"], filters=["status", "gender", "subscription_status", "city"],
                   archivable=True, statuses=STD_STATUS, editable=["name", "gender", "dob", "mobile", "email", "address", "city", "photo"],
                   columns=[("id", "Owner ID"), ("name", "Name"), ("gender", "Gender"), ("dob", "DOB"), ("mobile", "Mobile"),
                            ("email", "Email"), ("created_at", "Registered"), ("status", "Status"), ("property_count", "Properties"),
                            ("active_property_count", "Active Props"), ("archived_property_count", "Archived Props"),
                            ("tenant_count", "Tenants"), ("agreement_count", "Agreements"), ("subscription_status", "Subscription"),
                            ("subscription_start", "Sub Start"), ("subscription_expiry", "Sub Expiry"), ("fees_paid", "Fees Paid"),
                            ("outstanding", "Outstanding")]),
    "tenants": dict(module="tenants", search=["id", "name", "mobile", "email"], filters=["status", "gender", "aadhaar_status", "property_id", "owner_id"],
                    archivable=True, statuses=STD_STATUS,
                    editable=["name", "gender", "dob", "mobile", "email", "father_name", "mother_name", "permanent_address",
                              "current_address", "occupation", "emergency_contact_name", "emergency_contact_phone", "room", "rent", "deposit"],
                    columns=[("id", "Tenant ID"), ("name", "Name"), ("gender", "Gender"), ("dob", "DOB"), ("mobile", "Mobile"),
                             ("email", "Email"), ("property_name", "Property"), ("owner_name", "Owner"), ("room", "Room/Bed"),
                             ("join_date", "Joined"), ("leave_date", "Left"), ("rent", "Rent"), ("deposit", "Deposit"),
                             ("agreement_status", "Agreement"), ("aadhaar_masked", "Aadhaar"), ("aadhaar_status", "Aadhaar Status"),
                             ("status", "Status")]),
    "properties": dict(module="properties", search=["id", "name", "address", "city"], filters=["status", "category", "type", "owner_id", "city"],
                       archivable=True, statuses=["active", "inactive", "blocked", "deactivated", "closed", "archived"],
                       editable=["name", "category", "type", "pg_gender", "address", "city", "rent", "deposit", "total_units"],
                       columns=[("id", "Property ID"), ("name", "Name"), ("owner_name", "Owner"), ("category", "Category"),
                                ("type", "Type"), ("address", "Address"), ("city", "City"), ("total_units", "Units"),
                                ("occupied_units", "Occupied"), ("rent", "Rent"), ("deposit", "Deposit"), ("status", "Status"),
                                ("created_at", "Created")]),
    "agreements": dict(module="agreements", search=["id", "category"], filters=["status", "category", "owner_id", "tenant_id", "property_id"],
                       archivable=True, statuses=["draft", "pending_signature", "completed", "cancelled", "expired", "archived"],
                       manual_statuses=["cancelled", "expired", "archived"], editable=["start_date", "end_date", "rent", "deposit"],
                       columns=[("id", "Agreement ID"), ("category", "Category"), ("owner_name", "Owner"), ("tenant_name", "Tenant"),
                                ("property_name", "Property"), ("fee", "Fee"), ("coupon_code", "Coupon"), ("discount", "Discount"),
                                ("fee_paid", "Paid"), ("owner_esign", "Owner e-Sign"), ("tenant_esign", "Tenant e-Sign"), ("status", "Status"), ("current_version", "Version"), ("start_date", "Start"),
                                ("end_date", "End"), ("created_at", "Created")]),
    "payments": dict(module="finance", search=["id", "txn_ref", "receipt_no"], filters=["status", "method", "purpose", "owner_id", "tenant_id"],
                     archivable=False, statuses=[], editable=[],
                     columns=[("id", "Payment ID"), ("txn_ref", "Txn Ref"), ("receipt_no", "Receipt"), ("purpose", "Purpose"),
                              ("owner_name", "Owner"), ("tenant_name", "Tenant"), ("total_received", "Total Received"), ("base_amount", "Base Amount"),
                              ("gst_amount", "GST Amount"), ("total", "Total"), ("discount", "Discount"),
                              ("coupon_code", "Coupon"), ("refunded_amount", "Refunded"), ("method", "Method"), ("status", "Status"),
                              ("created_at", "Date")]),
    "subscriptions": dict(module="subscriptions", search=["id", "owner_id"], filters=["status", "owner_id"], archivable=False,
                          statuses=["active", "expired", "cancelled"], editable=[],
                          columns=[("id", "Sub ID"), ("owner_name", "Owner"), ("plan", "Plan"), ("amount", "Amount"),
                                   ("start_date", "Start"), ("expiry_date", "Expiry"), ("status", "Status"), ("created_at", "Created")]),
    "coupons": dict(module="coupons", search=["id", "code", "description"], filters=["status", "discount_type", "applies_to", "eligibility"], archivable=False,
                    statuses=["active", "inactive"],
                    editable=["description", "discount_type", "value", "max_discount", "min_amount", "start_date", "end_date",
                              "max_usage", "per_owner_limit", "applies_to", "eligibility", "eligible_ids"],
                    columns=[("id", "Coupon ID"), ("code", "Code"), ("discount_type", "Type"), ("value", "Value"),
                             ("max_discount", "Max Disc"), ("min_amount", "Min Amt"), ("applies_to", "Applies To"), ("eligibility", "Eligibility"), ("eligible_ids", "Eligible Users"),
                             ("start_date", "Start"), ("end_date", "End"), ("used_count", "Used"), ("max_usage", "Max Use"),
                             ("status", "Status")]),
    "complaints": dict(module="complaints", search=["id", "subject"], filters=["status", "priority", "category", "assigned_to", "owner_id", "tenant_id", "property_id", "raised_by"],
                       archivable=False, statuses=["open", "in_progress", "escalated", "resolved", "closed", "reopened"], editable=["subject", "priority", "category"],
                       columns=[("id", "Complaint ID"), ("subject", "Subject"), ("category", "Category"), ("priority", "Priority"),
                                ("raised_by", "Raised By"), ("tenant_name", "Tenant"), ("owner_name", "Owner"), ("property_name", "Property"),
                                ("assigned_to_name", "Assigned"), ("message_count", "Replies"), ("status", "Status"), ("resolution", "Resolution"), ("created_at", "Created")]),
    "leaving": dict(module="leaving", search=["id"], filters=["status", "owner_id", "tenant_id", "property_id", "requested_by", "move_out_status", "settlement_status"], archivable=False,
                    statuses=[], editable=["requested_leave_date"],
                    columns=[("id", "Request ID"), ("requested_by", "Requested By"), ("tenant_name", "Tenant"), ("owner_name", "Owner"),
                             ("property_name", "Property"), ("room", "Bed/Room/Seat"), ("requested_leave_date", "Leave Date"), ("status", "Approval Status"),
                             ("approved_by", "Approved By"), ("approved_by_type", "Approver Type"), ("approval_date", "Approval Date"),
                             ("rejection_reason", "Rejection Reason"), ("outstanding_rent", "Outstanding Rent"), ("deposit", "Security Deposit"),
                             ("deductions", "Deductions"), ("refund_amount", "Refund"), ("settlement_status", "Final Settlement"),
                             ("move_out_status", "Move-Out Status"), ("created_at", "Created")]),
    "banners": dict(module="banners", search=["id", "title"], filters=["audience", "status"], archivable=False, statuses=["active", "inactive", "removed"], hidden_status="removed",
                    editable=["title", "description", "image_url", "button_text", "destination", "start_date", "end_date"],
                    columns=[("id", "Banner ID"), ("title", "Title"), ("audience", "Audience"), ("order", "Order"),
                             ("start_date", "Start"), ("end_date", "End"), ("status", "Status")]),
    "notifications": dict(module="notifications", search=["id", "recipient_name", "title"], filters=["status", "type", "recipient_type", "channel", "campaign_id"],
                          archivable=False, statuses=[], editable=[],
                          columns=[("id", "ID"), ("recipient_name", "Recipient"), ("recipient_type", "Recipient Type"),
                                   ("type", "Type"), ("channel", "Channel"), ("title", "Title"), ("message", "Message"), ("scheduled_at", "Scheduled"), ("status", "Delivery"), ("created_at", "Date")]),
    "admins": dict(module="admins", search=["id", "name", "email"], filters=["status", "role"], archivable=False, statuses=["active", "inactive"],
                   editable=["name", "role", "mobile"],
                   columns=[("id", "Admin ID"), ("name", "Name"), ("email", "Email"), ("role", "Role"), ("status", "Status"),
                            ("last_login", "Last Login"), ("created_at", "Created")]),
    "audit_logs": dict(module="audit", search=["id", "record_id", "admin_email", "action"], filters=["module", "action", "admin_email"],
                       archivable=False, statuses=[], editable=[],
                       columns=[("id", "Log ID"), ("created_at", "Time"), ("admin_email", "Admin"), ("action", "Action"), ("module", "Module"),
                                ("record_id", "Record"), ("reason", "Reason"), ("ip", "IP")]),
}


def validate_coupon(c):
    def num(k):
        v = c.get(k)
        try:
            return None if v in (None, "") else float(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{k} must be a number")
    if c.get("discount_type") not in ("percent", "fixed"):
        raise HTTPException(400, "Discount type must be percent or fixed")
    if c.get("applies_to") not in ("agreement_fee", "platform_fee", "both"):
        raise HTTPException(400, "Applies to must be agreement_fee, platform_fee or both")
    value = num("value")
    if value is None or value <= 0:
        raise HTTPException(400, "Discount value must be greater than 0")
    if c["discount_type"] == "percent" and value > 100:
        raise HTTPException(400, "Percent value must be between 1 and 100")
    md = num("max_discount")
    if md is not None and md <= 0:
        raise HTTPException(400, "Max discount must be greater than 0")
    if (num("min_amount") or 0) < 0:
        raise HTTPException(400, "Min amount cannot be negative")
    if (num("max_usage") or 0) < 1 or (num("per_owner_limit") or 0) < 1:
        raise HTTPException(400, "Max usage and per-owner limit must be at least 1")
    try:
        start, end = date.fromisoformat(str(c.get("start_date"))), date.fromisoformat(str(c.get("end_date")))
    except ValueError:
        raise HTTPException(400, "Start and end dates must be valid YYYY-MM-DD dates")
    if end <= start:
        raise HTTPException(400, "End date must be after start date")


ELIGIBILITY = {"all_owners": ("owner", False), "selected_owner": ("owner", True), "selected_owners": ("owner", True),
               "all_tenants": ("tenant", False), "selected_tenant": ("tenant", True), "selected_tenants": ("tenant", True), "both": (None, False)}


async def validate_coupon_targets(c):
    el = c.get("eligibility") or "all_owners"
    if el not in ELIGIBILITY:
        raise HTTPException(400, f"Eligibility must be one of {list(ELIGIBILITY)}")
    aud, selected = ELIGIBILITY[el]
    ids = list(dict.fromkeys(c.get("eligible_ids") or []))
    if not selected:
        if ids:
            raise HTTPException(400, "Selected users are only allowed for selected-user eligibility")
        return
    if not ids:
        raise HTTPException(400, "Select at least one user")
    if el in ("selected_owner", "selected_tenant") and len(ids) != 1:
        raise HTTPException(400, "Select exactly one user for single-user eligibility")
    coll = "owners" if aud == "owner" else "tenants"
    found = await db[coll].count_documents({"id": {"$in": ids}})
    if found != len(ids):
        raise HTTPException(400, f"Some selected users are not valid {aud}s")


def check_perm(admin, module, level):
    if LEVELS.get(admin["permissions"].get(module, "none"), 0) < LEVELS[level]:
        raise HTTPException(403, f"Permission denied: {module} ({level})")


def get_cfg(entity):
    if entity not in ENTITIES:
        raise HTTPException(404, "Unknown entity")
    return ENTITIES[entity]


async def names(coll, ids, field="name"):
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    return {d["id"]: d.get(field) async for d in db[coll].find({"id": {"$in": ids}}, {"_id": 0, "id": 1, field: 1})}


async def enrich(entity, items):
    if not items:
        return items
    on = await names("owners", [i.get("owner_id") for i in items])
    tn = await names("tenants", [i.get("tenant_id") for i in items])
    pn = await names("properties", [i.get("property_id") for i in items])
    an = await names("admins", [i.get("assigned_to") for i in items])
    for i in items:
        if "owner_id" in i:
            i["owner_name"] = on.get(i["owner_id"])
        if "tenant_id" in i:
            i["tenant_name"] = tn.get(i["tenant_id"])
        if "property_id" in i:
            i["property_name"] = pn.get(i["property_id"])
        if i.get("assigned_to"):
            i["assigned_to_name"] = an.get(i["assigned_to"])
    if entity == "owners":
        ids = [i["id"] for i in items]

        async def group(coll, match):
            res = {}
            async for g in db[coll].aggregate([{"$match": {"owner_id": {"$in": ids}, **match}}, {"$group": {"_id": "$owner_id", "n": {"$sum": 1}}}]):
                res[g["_id"]] = g["n"]
            return res
        props = await group("properties", {})
        active = await group("properties", {"status": "active"})
        arch = await group("properties", {"status": "archived"})
        tens = await group("tenants", {"status": {"$ne": "archived"}})
        agrs = await group("agreements", {})
        paid, outstanding = {}, {}
        async for g in db.payments.aggregate([{"$match": {"owner_id": {"$in": ids}, "purpose": {"$in": ["platform_fee", "agreement_fee"]}}},
                                              {"$group": {"_id": {"o": "$owner_id", "s": "$status"}, "amt": {"$sum": "$amount"}}}]):
            o, s = g["_id"]["o"], g["_id"]["s"]
            if s in ("success", "approved"):
                paid[o] = paid.get(o, 0) + g["amt"]
            if s == "pending":
                outstanding[o] = outstanding.get(o, 0) + g["amt"]
        for i in items:
            oid = i["id"]
            i.update(property_count=props.get(oid, 0), active_property_count=active.get(oid, 0), archived_property_count=arch.get(oid, 0),
                     tenant_count=tens.get(oid, 0), agreement_count=agrs.get(oid, 0), fees_paid=paid.get(oid, 0),
                     outstanding=outstanding.get(oid, 0))
    if entity == "payments":
        for i in items:
            i.update(gst_split(i.get("amount"), i.get("gst_rate", GST_RATE_DEFAULT)))
    if entity == "agreements":
        for i in items:
            es = i.get("esign") or {}
            i["owner_esign"] = (es.get("owner") or {}).get("status", "pending")
            i["tenant_esign"] = (es.get("tenant") or {}).get("status", "pending")
    if entity == "complaints":
        for i in items:
            i["message_count"] = len(i.get("messages") or [])
    if entity == "leaving":
        rooms = {d["id"]: d.get("room") async for d in db.tenants.find({"id": {"$in": [i["tenant_id"] for i in items]}}, {"_id": 0, "id": 1, "room": 1})}
        for i in items:
            st, ap = i.get("settlement") or {}, i.get("approval") or {}
            i.update(room=rooms.get(i["tenant_id"]), approved_by=ap.get("by_name"), approved_by_type=ap.get("by_type"), approval_date=ap.get("at"),
                     outstanding_rent=st.get("outstanding_rent"), deductions=st.get("total_deductions"))
            i.setdefault("settlement_status", "pending")
            i.setdefault("move_out_status", "not_started")
            if not i.get("requested_by_name"):
                i["requested_by_name"] = i.get("tenant_name") if i.get("requested_by", "tenant") == "tenant" else i.get("owner_name")
    if entity == "properties":
        for i in items:
            i["fee_category"] = fee_category(i)
        ids = [i["id"] for i in items]
        occ = {}
        async for g in db.tenants.aggregate([{"$match": {"property_id": {"$in": ids}, "status": {"$in": ["active", "blocked", "suspended"]}, "leave_date": None}},
                                             {"$group": {"_id": "$property_id", "n": {"$sum": 1}}}]):
            occ[g["_id"]] = g["n"]
        for i in items:
            i["occupied_units"] = occ.get(i["id"], 0)
            i["occupancy"] = f"{i['occupied_units']}/{i.get('total_units', 0)}"
    return items


def build_query(cfg, params):
    q = {}
    text = params.get("q")
    if text:
        rx = {"$regex": re.escape(text), "$options": "i"}
        q["$or"] = [{f: rx} for f in cfg["search"]]
    for f in cfg["filters"]:
        v = params.get(f)
        if v not in (None, "", "all"):
            q[f] = v
    if cfg["archivable"] and not params.get("status") and params.get("include_archived") != "true":
        q["status"] = {"$ne": "archived"}
    if cfg.get("hidden_status") and not params.get("status"):
        q["status"] = {"$ne": cfg["hidden_status"]}
    rng = {}
    if params.get("from"):
        rng["$gte"] = params["from"]
    if params.get("to"):
        rng["$lte"] = params["to"] + "T23:59:59.999999"
    if rng:
        q["created_at"] = rng
    return q


@router.get("/{entity}")
async def list_entity(entity: str, request: Request, admin=Depends(current_admin)):
    cfg = get_cfg(entity)
    check_perm(admin, cfg["module"], "view")
    p = dict(request.query_params)
    q = build_query(cfg, p)
    try:
        page = int(p.get("page", 1))
        size = int(p.get("page_size", 25))
    except ValueError:
        raise HTTPException(400, "Invalid page or page_size: must be whole numbers")
    if page < 1 or not 1 <= size <= 200:
        raise HTTPException(400, "page must be ≥ 1 and page_size between 1 and 200")
    sort = p.get("sort", "seq" if entity == "audit_logs" else "created_at")
    order = 1 if p.get("order") == "asc" else -1
    if entity == "banners" and "sort" not in p:
        sort, order = "order", 1
    total = await db[entity].count_documents(q)
    items = [clean(d) async for d in db[entity].find(q).sort(sort, order).skip((page - 1) * size).limit(size)]
    return {"items": await enrich(entity, items), "total": total, "page": page, "page_size": size}


@router.get("/{entity}/export")
async def export_entity(entity: str, request: Request, admin=Depends(current_admin)):
    cfg = get_cfg(entity)
    check_perm(admin, cfg["module"], "view")
    check_perm(admin, "reports", "view")
    p = dict(request.query_params)
    fmt = p.get("format", "csv")
    if fmt not in ("csv", "xlsx", "pdf"):
        raise HTTPException(400, "Invalid format")
    items = [clean(d) async for d in db[entity].find(build_query(cfg, p)).sort("created_at", -1).limit(10000)]
    items = await enrich(entity, items)
    await audit(admin, "export", cfg["module"], entity, new={"format": fmt, "count": len(items), "filters": {k: v for k, v in p.items() if k != "format"}})
    return export_response(items, cfg["columns"], fmt, entity.replace("_", " ").title())


@router.get("/{entity}/{rid}")
async def get_entity(entity: str, rid: str, admin=Depends(current_admin)):
    cfg = get_cfg(entity)
    check_perm(admin, cfg["module"], "view")
    doc = clean(await db[entity].find_one({"id": rid}))
    if not doc:
        raise HTTPException(404, "Not found")
    return (await enrich(entity, [doc]))[0]


class EditIn(BaseModel):
    changes: Dict[str, Any]
    reason: str


@router.patch("/{entity}/{rid}")
async def edit_entity(entity: str, rid: str, body: EditIn, admin=Depends(current_admin)):
    cfg = get_cfg(entity)
    check_perm(admin, cfg["module"], "edit")
    reason = require_reason(body.reason)
    doc = await db[entity].find_one({"id": rid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    changes = {k: v for k, v in body.changes.items() if k in cfg["editable"]}
    if not changes:
        raise HTTPException(400, "No editable fields provided")
    if entity == "admins" and "role" in changes and changes["role"] != doc.get("role"):
        if rid == admin["id"]:
            raise HTTPException(403, "You cannot change your own role")
        if doc.get("role") == "Super Admin":
            raise HTTPException(403, "The Super Admin's role cannot be changed")
        if not await db.roles.find_one({"name": changes["role"]}):
            raise HTTPException(400, "Unknown role")
    if entity == "coupons":
        validate_coupon({**doc, **changes})
        await validate_coupon_targets({**doc, **changes})
    old = {k: doc.get(k) for k in changes}
    entry = {"at": now_iso(), "by": admin["email"], "action": "edit", "old": old, "new": changes, "reason": reason}
    await audit(admin, "edit", cfg["module"], rid, old, changes, reason)
    await db[entity].update_one({"id": rid}, {"$set": {**changes, "updated_at": now_iso()}, "$push": {"history": entry}})
    return clean(await db[entity].find_one({"id": rid}))


class StatusIn(BaseModel):
    status: str
    reason: str


@router.post("/{entity}/{rid}/status")
async def change_status(entity: str, rid: str, body: StatusIn, admin=Depends(current_admin)):
    cfg = get_cfg(entity)
    check_perm(admin, cfg["module"], "edit")
    reason = require_reason(body.reason)
    allowed = cfg.get("manual_statuses", cfg["statuses"])
    if body.status not in allowed:
        raise HTTPException(400, f"Invalid status. Allowed: {allowed}")
    doc = await db[entity].find_one({"id": rid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    if entity == "admins" and rid == admin["id"]:
        raise HTTPException(400, "You cannot change your own status")
    old = doc.get("status")
    if entity == "agreements" and old == "completed" and body.status != "archived":
        raise HTTPException(400, "A signed/completed agreement can only be archived")
    if old == body.status:
        raise HTTPException(400, "Record already has this status")
    upd = {"status": body.status, "updated_at": now_iso()}
    if body.status == "archived":
        upd.update(archived_at=now_iso(), archived_by=admin["email"], archive_reason=reason, archived_source="admin", status_before_archive=old)
    entry = {"at": now_iso(), "by": admin["email"], "action": "status", "old": old, "new": body.status, "reason": reason}
    await audit(admin, "archive" if body.status == "archived" else "status_change", cfg["module"], rid, {"status": old}, {"status": body.status}, reason)
    await db[entity].update_one({"id": rid}, {"$set": upd, "$push": {"status_history": entry}})
    return clean(await db[entity].find_one({"id": rid}))


class RemarkIn(BaseModel):
    text: str


@router.post("/{entity}/{rid}/remarks")
async def add_remark(entity: str, rid: str, body: RemarkIn, admin=Depends(current_admin)):
    cfg = get_cfg(entity)
    check_perm(admin, cfg["module"], "edit")
    text = require_reason(body.text)
    if not await db[entity].find_one({"id": rid}):
        raise HTTPException(404, "Not found")
    r = {"at": now_iso(), "by": admin["email"], "by_name": admin["name"], "text": text}
    await audit(admin, "remark", cfg["module"], rid, None, {"remark": text}, text)
    await db[entity].update_one({"id": rid}, {"$push": {"remarks": r}})
    return r
