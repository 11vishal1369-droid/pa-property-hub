import hashlib
import hmac
import json
import os
from datetime import date, timedelta, datetime, timezone
import httpx
import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"
APPH = {"X-App-Key": os.environ["APP_API_KEY"]}
HOOK_SECRET = "mock-webhook-secret"


@pytest.fixture(scope="module")
def c():
    with httpx.Client(timeout=60) as cl:
        t = cl.post(f"{API}/auth/login", json={"email": "admin@pa.com", "password": "Admin@123"}).json()["token"]
        cl.headers["Authorization"] = f"Bearer {t}"
        yield cl


def items(c, ent, **p):
    return c.get(f"{API}/data/{ent}", params={"page_size": 50, **p}).json()["items"]


def test_gst_split(c):
    p = items(c, "payments", status="success")[0]
    assert p["base_amount"] == round(p["total_received"] / 1.18, 2)
    assert round(p["base_amount"] + p["gst_amount"], 2) == p["total"] == p["total_received"]
    r = c.get(f"{API}/data/payments/export", params={"format": "csv"})
    assert "Base Amount" in r.text.splitlines()[0] and "GST Amount" in r.text.splitlines()[0]


def test_fee_categories_and_quote(c):
    s = c.get(f"{API}/settings").json()
    assert len(s["agreement_fees"]) == 13 and "PG – Co-living/Mixed" in s["agreement_fees"]
    fees = dict(s["agreement_fees"], **{"Shop": 149})
    r = c.put(f"{API}/settings", json={"settings": {"agreement_fees": fees}, "reason": "TEST fee"})
    assert r.status_code == 200
    bad = c.put(f"{API}/settings", json={"settings": {"agreement_fees": {"Shop": 1}}, "reason": "TEST"})
    assert bad.status_code == 400
    shop = items(c, "properties", type="Shop")[0]
    q = httpx.post(f"{API}/app/fees/quote", headers=APPH, json={"fee_type": "agreement_fee", "property_id": shop["id"], "user_type": "owner", "user_id": shop["owner_id"]})
    owner_ok = q.status_code == 200 or "account is" in q.text
    assert owner_ok
    f = httpx.get(f"{API}/app/fees", headers=APPH, params={"property_id": shop["id"]}).json()
    assert f["property"]["fee_category"] == "Shop" and f["property"]["agreement_fee"] == 149 and f["property"]["gst"]["base_amount"] == round(149 / 1.18, 2)
    assert httpx.get(f"{API}/app/fees").status_code == 401


def test_no_manual_agreement_approval(c):
    a = items(c, "agreements", status="pending_signature")[0]
    assert c.post(f"{API}/agreements/{a['id']}/verify", json={"decision": "verified", "reason": "x"}).status_code in (404, 405)
    assert c.post(f"{API}/data/agreements/{a['id']}/status", json={"status": "completed", "reason": "x"}).status_code == 400
    r = c.post(f"{API}/agreements/{a['id']}/esign/initiate", json={"party": "owner"})
    assert r.status_code == 400


def sign(body):
    return hmac.new(HOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_esign_flow(c):
    s = c.get(f"{API}/settings").json()
    es = {**s["esign"], "provider_name": "MockSign", "api_base_url": "http://127.0.0.1:8099", "enabled": True}
    r = c.put(f"{API}/settings", json={"settings": {"esign": es}, "reason": "TEST esign", "esign_api_key": "mock-api-key", "esign_webhook_secret": HOOK_SECRET})
    assert r.status_code == 200 and r.json()["esign"]["api_key_set"]
    a = next(x for x in items(c, "agreements", status="pending_signature") if x["fee_paid"])
    rid = {}
    for party in ("owner", "tenant"):
        r = c.post(f"{API}/agreements/{a['id']}/esign/initiate", json={"party": party})
        assert r.status_code == 200, r.text
        rid[party] = r.json()["request_id"]
    body = json.dumps({"request_id": rid["owner"], "status": "signed", "signed_at": "2026-11-01T10:00:00Z", "provider_ref": "MS-1", "verification_result": "aadhaar_otp_verified"}).encode()
    assert httpx.post(f"{API}/esign/webhook", content=body, headers={"X-Esign-Signature": "bad"}).status_code == 401
    assert httpx.post(f"{API}/esign/webhook", content=body, headers={"X-Esign-Signature": sign(body)}).json()["agreement_status"] == "pending_signature"
    assert httpx.post(f"{API}/esign/webhook", content=body, headers={"X-Esign-Signature": sign(body)}).json().get("duplicate")
    body2 = json.dumps({"request_id": rid["tenant"], "status": "signed", "signed_at": "2026-11-01T11:00:00Z", "provider_ref": "MS-2", "verification_result": "aadhaar_otp_verified"}).encode()
    assert httpx.post(f"{API}/esign/webhook", content=body2, headers={"X-Esign-Signature": sign(body2)}).json()["agreement_status"] == "completed"
    d = c.get(f"{API}/agreements/{a['id']}/detail").json()["agreement"]
    assert d["status"] == "completed" and d["esign"]["owner"]["provider_ref"] == "MS-1" and d["owner"]["mobile"]
    assert len(c.get(f"{API}/agreements/{a['id']}/esign/evidence").json()) == 2
    assert c.post(f"{API}/agreements/{a['id']}/versions", json={"content": "x", "reason": "x"}).status_code == 400
    assert c.post(f"{API}/data/agreements/{a['id']}/status", json={"status": "cancelled", "reason": "x"}).status_code == 400
    assert c.get(f"{API}/agreements/{a['id']}/pdf").status_code == 200


def test_complaint_thread(c):
    t = next(x for x in items(c, "tenants", status="active") if x.get("leave_date") is None)
    r = httpx.post(f"{API}/app/complaints", headers=APPH, json={"user_type": "tenant", "user_id": t["id"], "property_id": t["property_id"], "subject": "TEST leak",
                                                              "description": "Tap leaking", "attachments": ["https://example.com/a.jpg"]})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert httpx.post(f"{API}/app/complaints/{cid}/messages", headers=APPH, json={"user_type": "owner", "user_id": t["owner_id"], "text": "Plumber coming"}).status_code in (200, 403)
    assert httpx.post(f"{API}/app/complaints/{cid}/messages", headers=APPH, json={"user_type": "owner", "user_id": "OWN-99999", "text": "x"}).status_code == 404
    owner_list = items(c, "complaints", raised_by="tenant")
    assert all(x["raised_by"] == "tenant" for x in owner_list)
    r = c.post(f"{API}/complaints/{cid}/action", json={"action": "status", "value": "resolved", "reason": "Fixed tap"})
    assert r.json()["resolution"] == "Fixed tap"


def test_leaving_owner_approval(c):
    lr = items(c, "leaving", status="pending")[0]
    owner = c.get(f"{API}/data/owners/{lr['owner_id']}").json()
    r = httpx.post(f"{API}/app/leaving/{lr['id']}/action", headers=APPH, json={"owner_id": "OWN-10001" if lr["owner_id"] != "OWN-10001" else "OWN-10002", "action": "approve", "reason": "x"})
    assert r.status_code in (403, 404)
    r = httpx.post(f"{API}/app/leaving/{lr['id']}/action", headers=APPH, json={"owner_id": lr["owner_id"], "action": "approve", "reason": "TEST ok"})
    if owner["status"] != "active":
        assert r.status_code == 403
        return
    assert r.status_code == 200
    d = c.get(f"{API}/data/leaving/{lr['id']}").json()
    assert d["approval"]["by_type"] == "owner" and d["approved_by_type"] == "owner"
    assert c.post(f"{API}/leaving/{lr['id']}/status", json={"field": "move_out_status", "value": "scheduled", "reason": "TEST"}).status_code == 200
    assert c.post(f"{API}/leaving/{lr['id']}/status", json={"field": "settlement_status", "value": "paid", "reason": "TEST"}).status_code == 400


def test_banners_split(c):
    today = date.today()
    base = {"title": "TEST banner", "image_url": "https://example.com/b.jpg", "start_date": today.isoformat(), "end_date": (today + timedelta(days=5)).isoformat(), "reason": "TEST"}
    assert c.post(f"{API}/banners", json={**base, "audience": "both"}).status_code == 400
    b = c.post(f"{API}/banners", json={**base, "audience": "tenant"}).json()
    assert b["id"] in [x["id"] for x in httpx.get(f"{API}/public/banners", params={"audience": "tenant"}).json()]
    assert b["id"] not in [x["id"] for x in httpx.get(f"{API}/public/banners", params={"audience": "owner"}).json()]
    assert all(x["audience"] in ("owner", "tenant") for x in items(c, "banners"))
    o = items(c, "banners", audience="owner")[0]
    assert c.post(f"{API}/banners/reorder", json={"ids": [b["id"], o["id"]], "reason": "x"}).status_code == 400
    assert c.post(f"{API}/data/banners/{b['id']}/status", json={"status": "removed", "reason": "TEST"}).status_code == 200
    assert b["id"] not in [x["id"] for x in items(c, "banners")]


def test_notifications(c):
    t = items(c, "tenants", status="active")[0]
    o = items(c, "owners", status="active")[0]
    assert c.post(f"{API}/notifications/send", json={"audience": "owner", "target": "selected", "recipient_ids": [t["id"]], "title": "x", "message": "x", "reason": "x"}).status_code == 400
    r = c.post(f"{API}/notifications/send", json={"audience": "owner", "target": "selected", "recipient_ids": [o["id"]], "title": "TEST hello", "message": "Hi", "reason": "TEST"})
    assert r.status_code == 200 and r.json()["recipient_count"] == 1
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r2 = c.post(f"{API}/notifications/send", json={"audience": "owner", "target": "selected", "recipient_ids": [o["id"]], "title": "TEST later", "message": "Later", "scheduled_at": future, "reason": "TEST"})
    assert r2.status_code == 200
    inbox = httpx.get(f"{API}/app/notifications", headers=APPH, params={"user_type": "owner", "user_id": o["id"]}).json()
    titles = [n["title"] for n in inbox]
    assert "TEST hello" in titles and "TEST later" not in titles
    tin = httpx.get(f"{API}/app/notifications", headers=APPH, params={"user_type": "tenant", "user_id": t["id"]}).json()
    assert "TEST hello" not in [n["title"] for n in tin]
    camps = c.get(f"{API}/notifications/campaigns", params={"audience": "owner"}).json()
    assert camps[0]["delivery"]


def test_coupon_eligibility(c):
    today = date.today()
    owners = items(c, "owners", status="active")
    tenant = items(c, "tenants", status="active")[0]
    base = {"discount_type": "fixed", "value": 10, "start_date": (today - timedelta(days=1)).isoformat(), "end_date": (today + timedelta(days=30)).isoformat(),
            "max_usage": 10, "per_owner_limit": 1, "applies_to": "both", "reason": "TEST"}
    assert c.post(f"{API}/coupons", json={**base, "code": "TESTSEL1", "eligibility": "selected_owner", "eligible_ids": [owners[0]["id"], owners[1]["id"]]}).status_code == 400
    assert c.post(f"{API}/coupons", json={**base, "code": "TESTSEL2", "eligibility": "selected_owners", "eligible_ids": [tenant["id"]]}).status_code == 400
    assert c.post(f"{API}/coupons", json={**base, "code": "TESTSEL3", "eligibility": "selected_owners", "eligible_ids": [owners[0]["id"], owners[1]["id"]]}).status_code == 200
    v = lambda ut, uid: c.post(f"{API}/coupons/validate", json={"code": "TESTSEL3", "amount": 99, "fee_type": "agreement_fee", "user_type": ut, "user_id": uid}).json()
    assert v("owner", owners[0]["id"])["valid"]
    assert not v("owner", owners[2]["id"])["valid"]
    assert not v("tenant", tenant["id"])["valid"]
    assert c.post(f"{API}/coupons", json={**base, "code": "TESTTEN", "eligibility": "all_tenants"}).status_code == 200
    assert not c.post(f"{API}/coupons/validate", json={"code": "TESTTEN", "amount": 99, "fee_type": "agreement_fee", "user_type": "owner", "user_id": owners[0]["id"]}).json()["valid"]
    assert len(c.get(f"{API}/lookup/users", params={"type": "tenant", "q": tenant["name"][:4]}).json()) > 0
