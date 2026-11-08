import asyncio
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import APIRouter, Depends
from core import require, now_iso

router = APIRouter(prefix="/api")
COLLECTIONS = ["users", "properties", "units", "rental_accounts", "agreements", "payments", "complaints", "leaving_requests", "notifications"]
_client = None


def client():
    global _client
    if _client is None:
        info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
        app = firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": os.environ["FIREBASE_PROJECT_ID"],
                                                                            "storageBucket": os.environ["FIREBASE_STORAGE_BUCKET"]}, name="pa-admin")
        _client = firestore.client(app)
    return _client


def probe():
    out = {"project_id": os.environ["FIREBASE_PROJECT_ID"], "checked_at": now_iso(), "collections": {}}
    try:
        db = client()
        for name in COLLECTIONS:
            out["collections"][name] = db.collection(name).count().get()[0][0].value
        out["connected"] = True
    except Exception as e:
        msg = str(e)
        out["connected"] = False
        out["error"] = ("Cloud Firestore API is disabled for this project. Enable it in Google Cloud Console → APIs & Services → Cloud Firestore API, "
                        "and make sure a Firestore database exists.") if "has not been used" in msg or "SERVICE_DISABLED" in msg else msg[:300]
    return out


@router.get("/firebase/status")
async def firebase_status(admin=Depends(require("settings", "view"))):
    return await asyncio.to_thread(probe)
