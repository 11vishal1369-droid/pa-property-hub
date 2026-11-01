# PA Super Admin Panel - backend regression tests (auth, RBAC, data CRUD, ops, finance, settings, audit)
import os
import time
import uuid
import concurrent.futures as cf
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"
UID = uuid.uuid4().hex[:6].upper()


def login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {login('admin@pa.com', 'Admin@123')}"
    return s


@pytest.fixture(scope="session")
def finance():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {login('finance@pa.com', 'Staff@123')}"
    return s


@pytest.fixture(scope="session")
def readonly():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {login('readonly@pa.com', 'Staff@123')}"
    return s


def first(s, entity, **params):
    r = s.get(f"{API}/data/{entity}", params={"page_size": 50, **params})
    assert r.status_code == 200, r.text
    return r.json()


# --- Auth
class TestAuth:
    def test_login_ok(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@pa.com", "password": "Admin@123"})
        assert r.status_code == 200
        d = r.json()
        assert d["token"] and d["admin"]["role"] == "Super Admin"
        assert "password_hash" not in d["admin"] and "_id" not in d["admin"]

    def test_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": "property@pa.com", "password": "nope"})
        assert r.status_code == 401

    def test_me_requires_token(self):
        assert requests.get(f"{API}/auth/me").status_code == 401

    def test_bruteforce_lockout(self):
        email = f"lock_{UID.lower()}@pa.com"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429, codes


# --- Dashboard
class TestDashboard:
    def test_cards_count(self, admin):
        r = admin.get(f"{API}/dashboard")
        assert r.status_code == 200
        cards = r.json()["cards"]
        assert len(cards) == 29, len(cards)

    def test_range_changes(self, admin):
        a = admin.get(f"{API}/dashboard").json()["cards"]
        t = admin.get(f"{API}/dashboard", params={"range": "today"}).json()["cards"]
        c = admin.get(f"{API}/dashboard", params={"range": "custom", "frm": "2020-01-01", "to": "2020-01-02"}).json()["cards"]
        assert a["owners_total"] >= t["owners_total"] and c["owners_total"] == 0


# --- Generic data list/export
class TestData:
    @pytest.mark.parametrize("entity", ["owners", "tenants", "properties", "agreements", "payments", "subscriptions", "coupons",
                                        "complaints", "leaving", "banners", "notifications", "admins", "audit_logs"])
    def test_list(self, admin, entity):
        d = first(admin, entity)
        assert d["total"] >= 1 and isinstance(d["items"], list)
        assert all("_id" not in i and "aadhaar_enc" not in i for i in d["items"])

    def test_pagination_sort_search(self, admin):
        p1 = first(admin, "owners", page=1, page_size=5, sort="name", order="asc")
        p2 = first(admin, "owners", page=2, page_size=5, sort="name", order="asc")
        assert len(p1["items"]) == 5 and p1["items"][0]["id"] != p2["items"][0]["id"]
        names = [i["name"] for i in p1["items"]]
        assert names == sorted(names)
        o = p1["items"][0]
        s = first(admin, "owners", q=o["mobile"])
        assert any(i["id"] == o["id"] for i in s["items"])

    def test_filter_status(self, admin):
        d = first(admin, "owners", status="active")
        assert all(i["status"] == "active" for i in d["items"])

    def test_invalid_page_param(self, admin):
        r = admin.get(f"{API}/data/owners", params={"page": "abc"})
        assert r.status_code in (400, 422), f"non-numeric page -> {r.status_code}"

    @pytest.mark.parametrize("fmt,ctype", [("csv", "text/csv"), ("xlsx", "spreadsheet"), ("pdf", "pdf")])
    def test_export(self, admin, fmt, ctype):
        r = admin.get(f"{API}/data/owners/export", params={"format": fmt})
        assert r.status_code == 200 and ctype in r.headers.get("content-type", "") and len(r.content) > 100

    def test_tenant_aadhaar_masked(self, admin):
        t = first(admin, "tenants")["items"][0]
        assert t["aadhaar_masked"].startswith("XXXX-XXXX-")


# --- Edit/status/remark/archive/restore + audit
class TestRecordLifecycle:
    def test_edit_requires_reason(self, admin):
        o = first(admin, "owners")["items"][0]
        r = admin.patch(f"{API}/data/owners/{o['id']}", json={"changes": {"city": "X"}, "reason": " "})
        assert r.status_code == 400

    def test_edit_status_remark_archive_restore(self, admin):
        o = first(admin, "owners", status="active")["items"][-1]
        oid, city = o["id"], o.get("city")
        r = admin.patch(f"{API}/data/owners/{oid}", json={"changes": {"city": "TEST_City"}, "reason": "test edit"})
        assert r.status_code == 200 and r.json()["city"] == "TEST_City"
        assert admin.get(f"{API}/data/owners/{oid}").json()["city"] == "TEST_City"
        admin.patch(f"{API}/data/owners/{oid}", json={"changes": {"city": city}, "reason": "revert"})
        assert admin.post(f"{API}/data/owners/{oid}/remarks", json={"text": "TEST remark"}).status_code == 200
        assert admin.post(f"{API}/data/owners/{oid}/status", json={"status": "archived", "reason": ""}).status_code == 400
        r = admin.post(f"{API}/data/owners/{oid}/status", json={"status": "archived", "reason": "test archive"})
        assert r.status_code == 200 and r.json()["status"] == "archived"
        assert not any(i["id"] == oid for i in first(admin, "owners", q=oid)["items"])
        assert any(i["id"] == oid for i in first(admin, "owners", status="archived", q=oid)["items"])
        gs = admin.get(f"{API}/search", params={"q": oid}).json()["results"]
        assert any(i["id"] == oid for i in gs["owners"])
        r = admin.post(f"{API}/archive/owners/{oid}/restore", json={"reason": "test restore"})
        assert r.status_code == 200 and r.json()["status"] == "active"
        logs = first(admin, "audit_logs", q=oid)["items"]
        actions = {l["action"] for l in logs}
        assert {"edit", "remark", "archive", "restore"} <= actions, actions


# --- Aadhaar
class TestAadhaar:
    def test_reveal_superadmin_logged(self, admin):
        t = first(admin, "tenants")["items"][0]
        assert admin.post(f"{API}/tenants/{t['id']}/aadhaar/reveal", json={"reason": ""}).status_code == 400
        r = admin.post(f"{API}/tenants/{t['id']}/aadhaar/reveal", json={"reason": "TEST kyc check"})
        assert r.status_code == 200 and r.json()["aadhaar"].endswith(t["aadhaar_masked"][-4:])
        logs = first(admin, "audit_logs", q=t["id"])["items"]
        assert any(l["action"] == "aadhaar_view" for l in logs)

    def test_reveal_readonly_forbidden(self, admin, readonly):
        t = first(admin, "tenants")["items"][0]
        assert readonly.post(f"{API}/tenants/{t['id']}/aadhaar/reveal", json={"reason": "x"}).status_code == 403


# --- Agreements
class TestAgreements:
    def test_versions_pdf_verify(self, admin):
        a = first(admin, "agreements", status="pending_verification")["items"][0]
        aid, v = a["id"], a["current_version"]
        r = admin.post(f"{API}/agreements/{aid}/versions", json={"content": "TEST new terms", "reason": "test"})
        assert r.status_code == 200 and r.json()["version"] == v + 1
        d = admin.get(f"{API}/agreements/{aid}/detail").json()["agreement"]
        assert len(d["versions"]) >= 2 and d["current_version"] == v + 1
        for ver in (v, v + 1):
            p = admin.get(f"{API}/agreements/{aid}/pdf", params={"version": ver})
            assert p.status_code == 200 and p.content[:4] == b"%PDF"
        assert admin.get(f"{API}/agreements/{aid}/pdf", params={"version": 99}).status_code == 404
        assert admin.post(f"{API}/agreements/{aid}/verify", json={"decision": "verified", "reason": ""}).status_code == 400
        r = admin.post(f"{API}/agreements/{aid}/verify", json={"decision": "rejected", "reason": "TEST reject"})
        assert r.status_code == 200
        assert admin.get(f"{API}/data/agreements/{aid}").json()["status"] == "rejected"


# --- Finance
class TestFinance:
    def test_manual_payment_dup_and_approve_receipt_refund(self, admin):
        owner = first(admin, "owners")["items"][0]
        ref = f"TEST_TXN_{UID}"
        body = {"owner_id": owner["id"], "purpose": "agreement_fee", "amount": 99, "txn_ref": ref, "reason": "test"}
        r = admin.post(f"{API}/payments/manual", json=body)
        assert r.status_code == 200 and r.json()["status"] == "pending"
        pid = r.json()["id"]
        assert admin.post(f"{API}/payments/manual", json=body).status_code == 409
        assert admin.get(f"{API}/payments/{pid}/receipt").status_code == 400
        r = admin.post(f"{API}/payments/{pid}/approve", json={"reason": "TEST ok"})
        assert r.status_code == 200 and r.json()["receipt_no"]
        assert admin.post(f"{API}/payments/{pid}/approve", json={"reason": "again"}).status_code == 400
        rc = admin.get(f"{API}/payments/{pid}/receipt")
        assert rc.status_code == 200 and rc.content[:4] == b"%PDF"
        assert admin.post(f"{API}/payments/{pid}/refund", json={"amount": 100, "reason": "x"}).status_code == 400
        assert admin.post(f"{API}/payments/{pid}/refund", json={"amount": 0, "reason": "x"}).status_code == 400
        r = admin.post(f"{API}/payments/{pid}/refund", json={"amount": 40, "reason": "TEST partial"})
        assert r.status_code == 200 and r.json()["status"] == "partially_refunded"
        assert admin.post(f"{API}/payments/{pid}/refund", json={"amount": 59, "reason": "x"}).status_code == 200
        assert admin.get(f"{API}/data/payments/{pid}").json()["status"] == "refunded"

    def test_reject_pending(self, admin):
        owner = first(admin, "owners")["items"][0]
        r = admin.post(f"{API}/payments/manual", json={"owner_id": owner["id"], "purpose": "platform_fee", "amount": 99,
                                                       "txn_ref": f"TEST_REJ_{UID}", "reason": "test"})
        pid = r.json()["id"]
        assert admin.post(f"{API}/payments/{pid}/reject", json={"reason": "TEST bad"}).status_code == 200

    def test_finance_summary(self, admin):
        d = admin.get(f"{API}/finance/summary").json()
        assert "by_status" in d and "refunds" in d


# --- Subscriptions & coupons
class TestSubsCoupons:
    def test_extend_cancel(self, admin):
        s = first(admin, "subscriptions", status="active")["items"][-1]
        r = admin.post(f"{API}/subscriptions/{s['id']}/extend", json={"days": 30, "reason": "TEST extend"})
        assert r.status_code == 200 and r.json()["expiry_date"] > s["expiry_date"]
        assert admin.post(f"{API}/subscriptions/{s['id']}/extend", json={"days": 0, "reason": "x"}).status_code == 400
        r = admin.post(f"{API}/data/subscriptions/{s['id']}/status", json={"status": "cancelled", "reason": "TEST cancel"})
        assert r.status_code == 200 and r.json()["status"] == "cancelled"

    def test_coupon_crud_validate(self, admin):
        code = f"TEST{UID}"
        body = {"code": code, "discount_type": "percent", "value": 50, "max_discount": 30, "min_amount": 50,
                "start_date": "2024-01-01", "end_date": "2030-12-31", "max_usage": 5, "per_owner_limit": 1,
                "applies_to": "agreement_fee", "reason": "test"}
        r = admin.post(f"{API}/coupons", json=body)
        assert r.status_code == 200
        cid = r.json()["id"]
        assert admin.post(f"{API}/coupons", json=body).status_code == 409
        assert admin.post(f"{API}/coupons", json={**body, "code": code + "X", "value": 150}).status_code == 400
        v = admin.post(f"{API}/coupons/validate", json={"code": code, "amount": 99, "fee_type": "agreement_fee"}).json()
        assert v["valid"] and v["discount"] == 30 and v["final_amount"] == 69
        assert not admin.post(f"{API}/coupons/validate", json={"code": code, "amount": 99, "fee_type": "platform_fee"}).json()["valid"]
        assert not admin.post(f"{API}/coupons/validate", json={"code": code, "amount": 10, "fee_type": "agreement_fee"}).json()["valid"]
        assert admin.patch(f"{API}/data/coupons/{cid}", json={"changes": {"description": "TEST edit"}, "reason": "t"}).status_code == 200
        assert admin.post(f"{API}/data/coupons/{cid}/status", json={"status": "inactive", "reason": "t"}).status_code == 200
        assert not admin.post(f"{API}/coupons/validate", json={"code": code, "amount": 99, "fee_type": "agreement_fee"}).json()["valid"]
        assert admin.get(f"{API}/coupons/{cid}/usage").status_code == 200

    def test_coupon_edit_bypasses_validation(self, admin):
        """PATCH should validate percent value like create does"""
        c = first(admin, "coupons", q=f"TEST{UID}")["items"][0]
        r = admin.patch(f"{API}/data/coupons/{c['id']}", json={"changes": {"discount_type": "percent", "value": 500}, "reason": "t"})
        assert r.status_code == 400, "edit allowed percent=500"


# --- Complaints & leaving
class TestComplaintsLeaving:
    def test_complaint_flow(self, admin):
        c = first(admin, "complaints", status="open")["items"][0]
        cid = c["id"]
        ad = first(admin, "admins")["items"][0]
        for body in [{"action": "status", "value": "in_progress"}, {"action": "assign", "value": ad["id"]},
                     {"action": "escalate"}, {"action": "remark"}, {"action": "close"}, {"action": "reopen"}]:
            r = admin.post(f"{API}/complaints/{cid}/action", json={**body, "reason": "TEST step"})
            assert r.status_code == 200, (body, r.text)
        d = r.json()
        assert d["status"] == "reopened" and d["assigned_to"] == ad["id"] and len(d["timeline"]) >= 6

    def test_leaving_flow(self, admin):
        lr = first(admin, "leaving", status="pending")["items"][0]
        lid = lr["id"]
        s = admin.post(f"{API}/leaving/{lid}/settlement", json={"outstanding_rent": 1000, "utilities": 200, "other_charges": 0,
                                                                "damage": 300, "deposit": 5000, "reason": "TEST"}).json()
        tenant = admin.get(f"{API}/data/tenants/{lr['tenant_id']}").json()
        assert s["deposit"] == tenant["deposit"], "deposit must come from tenant record, not request"
        assert s["total_deductions"] == 1500 and s["refund_amount"] == max(tenant["deposit"] - 1500, 0)
        assert admin.post(f"{API}/leaving/{lid}/action", json={"action": "complete", "reason": "x"}).status_code == 400
        assert admin.post(f"{API}/leaving/{lid}/action", json={"action": "approve", "reason": "TEST"}).json()["status"] == "approved"
        assert admin.post(f"{API}/leaving/{lid}/action", json={"action": "complete", "reason": "TEST"}).json()["status"] == "completed"


# --- Banners & notifications
class TestBannersNotif:
    def test_banner_flow(self, admin):
        r = admin.post(f"{API}/banners", json={"title": f"TEST Banner {UID}", "image_url": "https://example.com/a.jpg",
                                              "start_date": "2024-01-01", "end_date": "2030-01-01", "audience": "owner", "reason": "t"})
        assert r.status_code == 200
        bid = r.json()["id"]
        pub = requests.get(f"{API}/public/banners", params={"audience": "owner"}).json()
        assert any(b["id"] == bid for b in pub)
        assert all(b["audience"] in ("owner", "both") for b in pub)
        assert not any(b["id"] == bid for b in requests.get(f"{API}/public/banners", params={"audience": "tenant"}).json())
        ids = [b["id"] for b in first(admin, "banners")["items"]]
        new = [bid] + [i for i in ids if i != bid]
        assert admin.post(f"{API}/banners/reorder", json={"ids": new, "reason": "t"}).status_code == 200
        assert first(admin, "banners")["items"][0]["id"] == bid
        assert admin.post(f"{API}/data/banners/{bid}/status", json={"status": "inactive", "reason": "t"}).status_code == 200
        assert not any(b["id"] == bid for b in requests.get(f"{API}/public/banners", params={"audience": "owner"}).json())

    def test_notification_retry(self, admin):
        n = first(admin, "notifications", status="failed")["items"][0]
        assert admin.post(f"{API}/notifications/{n['id']}/retry", json={"reason": "TEST"}).status_code == 200
        assert admin.post(f"{API}/notifications/{n['id']}/retry", json={"reason": "TEST"}).status_code == 400


# --- Admins, roles, RBAC
class TestAdminsRBAC:
    def test_admin_create_edit_reset_deactivate(self, admin):
        email = f"test_{UID.lower()}@pa.com"
        r = admin.post(f"{API}/admins", json={"name": "TEST Admin", "email": email, "password": "Temp@1234", "role": "Read-Only Admin", "reason": "t"})
        assert r.status_code == 200
        aid = r.json()["id"]
        assert admin.patch(f"{API}/data/admins/{aid}", json={"changes": {"role": "Finance Admin"}, "reason": "t"}).json()["role"] == "Finance Admin"
        assert admin.post(f"{API}/admins/{aid}/reset-password", json={"new_password": "New@12345", "reason": "t"}).status_code == 200
        login(email, "New@12345")
        assert admin.post(f"{API}/data/admins/{aid}/status", json={"status": "inactive", "reason": "t"}).status_code == 200
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "New@12345"}).status_code == 403

    def test_role_matrix(self, admin):
        roles = admin.get(f"{API}/roles").json()["roles"]
        ro = next(r for r in roles if r["name"] == "Read-Only Admin")
        r = admin.put(f"{API}/roles/Read-Only Admin", json={"permissions": ro["permissions"], "reason": "TEST save"})
        assert r.status_code == 200
        assert admin.put(f"{API}/roles/Super Admin", json={"permissions": {}, "reason": "t"}).status_code == 400

    def test_finance_forbidden(self, finance):
        me = finance.get(f"{API}/auth/me").json()
        assert me["role"] == "Finance Admin"
        assert finance.get(f"{API}/data/payments").status_code == 200
        for path in ["/data/admins", "/settings", "/data/complaints"]:
            if me["permissions"].get({"/data/admins": "admins", "/settings": "settings", "/data/complaints": "complaints"}[path], "none") == "none":
                assert finance.get(f"{API}{path}").status_code == 403, path
        assert finance.post(f"{API}/admins", json={"name": "x", "email": "x@x.com", "password": "12345678", "role": "Finance Admin", "reason": "t"}).status_code == 403

    def test_readonly_cannot_edit(self, admin, readonly):
        o = first(admin, "owners")["items"][0]
        assert readonly.patch(f"{API}/data/owners/{o['id']}", json={"changes": {"city": "x"}, "reason": "t"}).status_code == 403


# --- Audit & settings
class TestAuditSettings:
    def test_settings_update_history_secret(self, admin):
        s = admin.get(f"{API}/settings").json()
        v = s["version"]
        r = admin.put(f"{API}/settings", json={"settings": {"agreement_fee_default": s["agreement_fee_default"]}, "reason": "", "gateway_secret": None})
        assert r.status_code == 400
        r = admin.put(f"{API}/settings", json={"settings": {"agreement_fee_default": s["agreement_fee_default"]}, "reason": "TEST save", "gateway_secret": "sk_test_ABCD1234"})
        assert r.status_code == 200
        d = r.json()
        assert d["version"] == v + 1 and d["gateway"]["secret_masked"].endswith("1234")
        assert "sk_test" not in r.text and "gateway_secret_enc" not in r.text
        h = admin.get(f"{API}/settings/history").json()
        assert h and h[0]["version"] == v

    def test_fee_defaults(self, admin):
        s = admin.get(f"{API}/settings").json()
        print({k: s.get(k) for k in s if "fee" in k or "valid" in k})

    def test_change_password_roundtrip(self):
        tok = login("ownersupport@pa.com", "Staff@123")
        h = {"Authorization": f"Bearer {tok}"}
        assert requests.post(f"{API}/auth/change-password", headers=h, json={"current_password": "bad", "new_password": "Temp@12345"}).status_code == 400
        assert requests.post(f"{API}/auth/change-password", headers=h, json={"current_password": "Staff@123", "new_password": "Temp@12345"}).status_code == 200
        tok2 = login("ownersupport@pa.com", "Temp@12345")
        assert requests.post(f"{API}/auth/change-password", headers={"Authorization": f"Bearer {tok2}"},
                             json={"current_password": "Temp@12345", "new_password": "Staff@123"}).status_code == 200

    def test_audit_verify(self, admin):
        r = admin.get(f"{API}/audit/verify")
        assert r.status_code == 200 and r.json()["valid"] is True, r.json()

    def test_concurrent_audit_writes(self, admin):
        """Concurrent mutating requests must not 500 due to audit seq race"""
        o = first(admin, "owners")["items"][0]
        with cf.ThreadPoolExecutor(8) as ex:
            codes = list(ex.map(lambda i: admin.post(f"{API}/data/owners/{o['id']}/remarks", json={"text": f"TEST conc {i}"}).status_code, range(8)))
        assert all(c == 200 for c in codes), codes
        assert admin.get(f"{API}/audit/verify").json()["valid"] is True
