from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import copy
import json
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

# Standalone service for the public website content. Own database, own login; never touches admin panel data or /api.
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["WEB_DB_NAME"]]
DEFAULTS = json.loads((Path(__file__).parent / "default_content.json").read_text(encoding="utf-8"))
SLUGS = list(DEFAULTS)
PREFIX = "/webcontent-api"
MAX_TEXT = 20000
app = FastAPI(title="PA Web Content", docs_url=None, redoc_url=None, openapi_url=None)


def now():
    return datetime.now(timezone.utc)


def token_for(editor):
    return jwt.encode({"sub": editor["email"], "type": "web_editor", "exp": now() + timedelta(hours=12)}, os.environ["WEB_JWT_SECRET"], algorithm="HS256")


async def current_editor(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        p = jwt.decode(auth[7:], os.environ["WEB_JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    ed = await db.editors.find_one({"email": p["sub"]}, {"_id": 0, "password_hash": 0})
    if p.get("type") != "web_editor" or not ed:
        raise HTTPException(401, "Invalid token")
    return ed


def conforms(value, template, path="content"):
    """Edited content must keep the shape of the original page (same keys, same kinds of values)."""
    if isinstance(template, dict):
        if not isinstance(value, dict) or set(value) != set(template):
            raise HTTPException(400, f"{path}: fields must be {sorted(template)}")
        for k in template:
            conforms(value[k], template[k], f"{path}.{k}")
    elif isinstance(template, list):
        if not isinstance(value, list) or len(value) > 500:
            raise HTTPException(400, f"{path}: must be a list (max 500 items)")
        for i, v in enumerate(value):
            conforms(v, template[0], f"{path}[{i}]")
    elif isinstance(template, str):
        if not isinstance(value, str) or len(value) > MAX_TEXT:
            raise HTTPException(400, f"{path}: must be text up to {MAX_TEXT} characters")
        if path.endswith(".type") and value not in ("heading", "paragraph", "bullet"):
            raise HTTPException(400, f"{path}: must be heading, paragraph or bullet")


async def get_page(slug):
    if slug not in DEFAULTS:
        raise HTTPException(404, "Page not found")
    doc = await db.pages.find_one({"slug": slug}, {"_id": 0})
    return doc


@app.on_event("startup")
async def startup():
    await db.editors.create_index("email", unique=True)
    await db.pages.create_index("slug", unique=True)
    await db.login_attempts.create_index("identifier")
    email = os.environ["WEB_EDITOR_EMAIL"].lower()
    if not await db.editors.find_one({"email": email}):
        pw = bcrypt.hashpw(os.environ["WEB_EDITOR_PASSWORD"].encode(), bcrypt.gensalt()).decode()
        await db.editors.insert_one({"email": email, "name": "Website Editor", "password_hash": pw, "created_at": now().isoformat()})
    for slug, content in DEFAULTS.items():
        await db.pages.update_one({"slug": slug}, {"$setOnInsert": {"slug": slug, "content": content, "version": 1, "updated_at": now().isoformat(),
                                                                    "updated_by": "imported from uploaded document"}}, upsert=True)


@app.get(f"{PREFIX}/")
async def health():
    return {"status": "ok", "service": "webcontent"}


@app.get(f"{PREFIX}/public/pages/{{slug}}")
async def public_page(slug: str):
    p = await get_page(slug)
    return {"slug": slug, "content": p["content"], "updated_at": p["updated_at"]}


@app.get(f"{PREFIX}/public/site")
async def public_site():
    contact = await get_page("contact-us")
    home = await get_page("home")
    return {"contact": contact["content"], "footer": {k: home["content"][k] for k in ("footer_brand", "footer_byline", "footer_copyright")}}


class LoginIn(BaseModel):
    email: str
    password: str


@app.post(f"{PREFIX}/auth/login")
async def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()
    ident = f"{request.client.host if request.client else ''}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and att["locked_until"] > now().isoformat():
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    ed = await db.editors.find_one({"email": email})
    if not ed or not bcrypt.checkpw(body.password.encode(), ed["password_hash"].encode()):
        if att and att["locked_until"] <= now().isoformat():
            await db.login_attempts.delete_one({"identifier": ident})
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$setOnInsert": {"locked_until": (now() + timedelta(minutes=15)).isoformat()}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    return {"token": token_for(ed), "editor": {"email": ed["email"], "name": ed["name"]}}


@app.get(f"{PREFIX}/auth/me")
async def me(ed=Depends(current_editor)):
    return ed


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@app.post(f"{PREFIX}/auth/change-password")
async def change_password(body: PasswordIn, ed=Depends(current_editor)):
    doc = await db.editors.find_one({"email": ed["email"]})
    if not bcrypt.checkpw(body.current_password.encode(), doc["password_hash"].encode()):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    await db.editors.update_one({"email": ed["email"]}, {"$set": {"password_hash": bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()}})
    return {"ok": True}


@app.get(f"{PREFIX}/pages")
async def list_pages(ed=Depends(current_editor)):
    return [{k: p[k] for k in ("slug", "version", "updated_at", "updated_by")} async for p in db.pages.find({}, {"_id": 0}).sort("slug", 1)]


@app.get(f"{PREFIX}/pages/{{slug}}")
async def editor_page(slug: str, ed=Depends(current_editor)):
    return await get_page(slug)


class PageIn(BaseModel):
    content: dict
    version: int


@app.put(f"{PREFIX}/pages/{{slug}}")
async def save_page(slug: str, body: PageIn, ed=Depends(current_editor)):
    cur = await get_page(slug)
    conforms(body.content, DEFAULTS[slug] if slug != "home" else DEFAULTS["home"])
    upd = {"content": body.content, "version": cur["version"] + 1, "updated_at": now().isoformat(), "updated_by": ed["email"]}
    r = await db.pages.update_one({"slug": slug, "version": body.version}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(409, "This page was changed in another window. Reload it before saving.")
    await db.page_history.insert_one({"slug": slug, "version": cur["version"], "content": copy.deepcopy(cur["content"]), "saved_at": cur["updated_at"],
                                      "saved_by": cur["updated_by"], "replaced_at": upd["updated_at"], "replaced_by": ed["email"]})
    return {"slug": slug, **upd}


@app.get(f"{PREFIX}/pages/{{slug}}/history")
async def page_history(slug: str, ed=Depends(current_editor)):
    await get_page(slug)
    return [h async for h in db.page_history.find({"slug": slug}, {"_id": 0, "content": 0}).sort("version", -1).limit(50)]


@app.post(f"{PREFIX}/pages/{{slug}}/restore/{{version}}")
async def restore(slug: str, version: int, ed=Depends(current_editor)):
    h = await db.page_history.find_one({"slug": slug, "version": version}, {"_id": 0})
    if not h:
        raise HTTPException(404, "Version not found")
    cur = await get_page(slug)
    return await save_page(slug, PageIn(content=h["content"], version=cur["version"]), ed)
