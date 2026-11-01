import os
import asyncio
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
fernet = Fernet(os.environ["AADHAAR_ENC_KEY"].encode())
JWT_ALG = "HS256"

MODULES = ["dashboard", "owners", "tenants", "properties", "agreements", "finance", "subscriptions",
           "coupons", "complaints", "leaving", "banners", "notifications", "reports", "archive",
           "admins", "audit", "settings", "aadhaar"]
LEVELS = {"none": 0, "view": 1, "edit": 2}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())


def encrypt(v):
    return fernet.encrypt(v.encode()).decode()


def decrypt(v):
    return fernet.decrypt(v.encode()).decode()


def mask_aadhaar(last4):
    return f"XXXX-XXXX-{last4}" if last4 else None


def create_token(admin_id, email):
    payload = {"sub": admin_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALG)


async def next_id(prefix):
    doc = await db.counters.find_one_and_update({"_id": prefix}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return f"{prefix}-{10000 + doc['seq']}"


SENSITIVE = {"aadhaar_enc", "password_hash", "gateway_secret_enc"}


def clean(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    for k in SENSITIVE:
        doc.pop(k, None)
    return doc


async def get_permissions(role):
    r = await db.roles.find_one({"name": role}, {"_id": 0})
    return r["permissions"] if r else {}


async def current_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    admin = await db.admins.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not admin or admin.get("status") != "active":
        raise HTTPException(401, "Account inactive or not found")
    admin["permissions"] = await get_permissions(admin["role"])
    admin["ip"] = request.client.host if request.client else ""
    xf = request.headers.get("x-forwarded-for")
    if xf:
        admin["ip"] = xf.split(",")[0].strip()
    return admin


def require(module, level="view"):
    async def dep(admin=Depends(current_admin)):
        if LEVELS.get(admin["permissions"].get(module, "none"), 0) < LEVELS[level]:
            raise HTTPException(403, f"Permission denied: {module} ({level})")
        return admin
    return dep


_audit_lock = asyncio.Lock()


async def audit(admin, action, module, record_id, old=None, new=None, reason=None):
    async with _audit_lock:
        for _ in range(5):
            last = await db.audit_logs.find_one(sort=[("seq", -1)])
            seq = (last["seq"] + 1) if last else 1
            entry = {"id": f"AUD-{100000 + seq}", "seq": seq, "admin_id": admin.get("id"), "admin_email": admin.get("email"),
                     "admin_name": admin.get("name"), "action": action, "module": module, "record_id": record_id,
                     "old_value": old, "new_value": new, "reason": reason, "ip": admin.get("ip", ""),
                     "created_at": now_iso(), "prev_hash": last["hash"] if last else "GENESIS"}
            entry["hash"] = hash_entry(entry)
            try:
                await db.audit_logs.insert_one(entry)
                return
            except DuplicateKeyError:
                continue
        raise HTTPException(503, "Could not write audit entry, please retry")


async def audited(admin, action, module, record_id, old, new, reason, write, undo):
    result = await write()
    try:
        await audit(admin, action, module, record_id, old, new, reason)
    except Exception:
        await undo()
        raise
    return result


def hash_entry(e):
    body = {k: e[k] for k in ["seq", "admin_id", "action", "module", "record_id", "old_value", "new_value",
                              "reason", "ip", "created_at", "prev_hash"]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def require_reason(reason):
    if not reason or not str(reason).strip():
        raise HTTPException(400, "Reason is required")
    return reason.strip()
