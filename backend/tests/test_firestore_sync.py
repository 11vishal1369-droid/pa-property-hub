import asyncio
import os
from datetime import datetime, timezone

import httpx
import pytest

import firebase_sync as fsync
from core import db, decrypt

LOOP = asyncio.new_event_loop()
run = LOOP.run_until_complete
T = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)  # noqa: E731


class FakeDoc:
    def __init__(self, store, coll, did):
        self.store, self.coll, self.id = store, coll, did


class FakeFirestore:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        fs = self

        class C:
            def document(self, did):
                return FakeDoc(fs.store, name, did)
        return C()

    def batch(self):
        fs = self

        class B:
            ops = []

            def set(self, ref, data, merge=False):
                self.ops.append((ref, data))

            def commit(self):
                for ref, data in self.ops:
                    fs.store.setdefault(ref.coll, {}).setdefault(ref.id, {}).update(data)
        return B()


RAW = {
    "users": [{"id": "u-own", "role": "owner", "full_name": "Owner One", "owner_code": "OWN100001", "mobile": "9000000001"},
              {"id": "u-ten", "role": "tenant", "full_name": "Tenant One", "tenant_code": "TEN100001", "gender": "female"}],
    "properties": [{"id": "p1", "owner_id": "u-own", "name": "Girls PG", "property_code": "PROP100001", "category": "PG/Hostel", "pg_gender": "Girls", "status": "active"}],
    "units": [{"id": "un1", "property_id": "p1", "name": "Room 101", "parent_unit_id": None},
              {"id": "un2", "property_id": "p1", "name": "Room 101 - Bed 1", "parent_unit_id": "un1", "monthly_rent": 7500.0, "security_deposit": 12000.0}],
    "rental_accounts": [{"id": "ra1", "tenant_id": "u-ten", "owner_id": "u-own", "property_id": "p1", "unit_name": "Room 101 - Bed 1", "rental_code": "RENT100001",
                         "status": "active", "monthly_rent": 7500.0, "security_deposit": 12000.0, "rent_start_date": "2026-06-01", "identity_status": "verified_demo"}],
    "agreements": [{"id": "a1", "tenant_id": "u-ten", "owner_id": "u-own", "property_id": "p1", "rental_account_id": "ra1", "status": "finalized",
                    "agreement_number": "AGR-2026-10001", "template_key": "pg_girls", "owner_confirmed_at": T("2026-06-01"), "tenant_accepted_at": T("2026-06-02"),
                    "tenant_details": {"aadhaar_number": "456700000004", "full_name": "Tenant One"}, "terms": {"start_date": "2026-06-01", "end_date": "2027-05-01"}}],
    "subscriptions": [{"id": f"s{i}", "owner_id": "u-own", "status": "active", "starts_at": T(f"{2026 + i}-10-31"), "expires_at": T(f"{2027 + i}-10-30")} for i in range(3)],
    "payments": [{"id": "pay1", "kind": "rent", "status": "pending", "payment_method": "upi", "amount": 7500, "transaction_id": "UPI1", "receipt_number": "RCPT900001",
                  "owner_id": "u-own", "tenant_id": "u-ten", "property_id": "p1"}],
    "notifications": [{"id": f"n{i}", "user_id": "u-ten" if i % 2 else "u-own", "title": "t", "body": "b", "type": "rent_due", "read": False} for i in range(50)],
    "complaints": [], "leaving_requests": [], "banners": [], "coupons": [], "fee_orders": [],
}


@pytest.fixture(autouse=True, scope="module")
def loaded():
    assert os.environ["DB_NAME"] == "pa_regression_sync" and not os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]
    for c in fsync.SOURCES:
        fsync.cache[c] = {d["id"]: dict(d) for d in RAW.get(c, [])}
    fsync._memo.clear()

    async def go():
        for c in fsync.SAMPLE_COLLS + ["tenancies"]:
            await db[c].delete_many({})
        await db.owners.insert_one({"id": "OWN-SAMPLE", "name": "Sample", "status": "active"})
        await db.migrations.delete_many({})
        await fsync.cutover()
        groups = {}
        for t, i in fsync.all_targets():
            groups.setdefault(t, []).append(i)
        for t, ids in groups.items():
            await fsync.apply(t, ids)
    run(go())


def one(coll, rid):
    return run(db[coll].find_one({"id": rid}, {"_id": 0}))


def test_cutover_removes_sample_only():
    assert one("owners", "OWN-SAMPLE") is None
    assert one("owners", "u-own")["source"] == "firestore"


def test_readable_codes():
    assert one("owners", "u-own")["code"] == "OWN100001"
    t = one("tenants", "u-ten")
    assert t["code"] == "TEN100001" and t["rental_code"] == "RENT100001"
    assert one("properties", "p1")["code"] == "PROP100001"
    assert one("agreements", "a1")["code"] == "AGR-2026-10001"
    assert one("payments", "pay1")["code"] == "RCPT900001"


def test_aadhaar_encrypted_and_masked():
    t = one("tenants", "u-ten")
    assert t["aadhaar_masked"] == "XXXX-XXXX-0004" and decrypt(t["aadhaar_enc"]) == "456700000004"
    assert "aadhaar_number" not in one("agreements", "a1")["tenant_details"]


def test_property_and_agreement_mapping():
    p = one("properties", "p1")
    assert p["category"] == "PG" and p["total_units"] == 1 and p["occupancy_state"] == "occupied" and p["fee_category"] == "PG – Girls"
    a = one("agreements", "a1")
    assert a["status"] == "completed" and a["esign"]["owner"]["status"] == "signed" and a["esign"]["tenant"]["status"] == "signed"


def test_stacked_subscriptions_owner_period():
    o = one("owners", "u-own")
    today = datetime.now(timezone.utc).date().isoformat()
    assert o["subscription_expiry"] == "2029-10-30" and o["subscription_status"] == "active"
    assert o["subscription_start"] <= today
    assert {s["start_date"] for s in run(db.subscriptions.find({}, {"_id": 0}).to_list(10))} == {"2026-10-31", "2027-10-31", "2028-10-31"}


def test_admin_status_survives_resync_until_app_changes():
    run(db.owners.update_one({"id": "u-own"}, {"$set": {"status": "blocked"}}))
    run(fsync.apply("owners", ["u-own"]))
    assert one("owners", "u-own")["status"] == "blocked"
    run(db.payments.update_one({"id": "pay1"}, {"$set": {"status": "approved"}}))
    fsync.cache["payments"]["pay1"]["status"] = "rejected"
    run(fsync.apply("payments", ["pay1"]))
    assert one("payments", "pay1")["status"] == "rejected"


def test_app_delete_archives_not_deletes():
    fsync.cache["properties"].pop("p1")
    fsync._memo.clear()
    run(fsync.apply("properties", ["p1"]))
    p = one("properties", "p1")
    assert p["status"] == "archived" and p["archived_source"] == "app"
    fsync.cache["properties"]["p1"] = dict(RAW["properties"][0])
    fsync._memo.clear()


def test_notifications_bulk_and_recipient_type():
    assert run(db.notifications.count_documents({"source": "firestore"})) == 50
    assert one("notifications", "n1")["recipient_type"] == "tenant" and one("notifications", "n0")["recipient_type"] == "owner"


def test_push_writes_to_fake_firestore_only(monkeypatch):
    fake = FakeFirestore()
    monkeypatch.setattr(fsync, "client", lambda: fake)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", "{}")
    run(db.banners.insert_one({"id": "BNR-T1", "title": "T", "status": "inactive", "audience": "owner", "start_date": "2026-01-01", "end_date": "2026-02-01"}))
    run(db.notifications.insert_many([{"id": "NTF-T1", "recipient_id": "u-own", "title": "x", "message": "y", "status": "queued"},
                                      {"id": "NTF-T2", "recipient_id": "u-own", "title": "x", "message": "y", "status": "scheduled"}]))
    run(fsync.push("banners", ["BNR-T1"]))
    run(fsync.push("notifications", ["NTF-T1", "NTF-T2"]))
    assert fake.store["banners"]["BNR-T1"]["active"] is False and fake.store["banners"]["BNR-T1"]["removed"] is False
    assert set(fake.store["notifications"]) == {"NTF-T1"} and fake.store["notifications"]["NTF-T1"]["body"] == "y"


def test_test_server_has_firestore_disabled():
    r = httpx.post(f"{os.environ['TEST_API']}/auth/login", json={"email": "admin@pa.com", "password": "Admin@123"})
    s = httpx.get(f"{os.environ['TEST_API']}/firebase/status", headers={"Authorization": f"Bearer {r.json()['token']}"}, timeout=60).json()
    assert s["sync"]["running"] is False


def test_fee_config_published_to_fake_firestore(monkeypatch):
    fake = FakeFirestore()
    written = {}

    class Doc:
        def set(self, data):
            written.update(data)

    class Coll:
        def document(self, d):
            assert d == "fees"
            return Doc()
    fake.collection = lambda name: (written.__setitem__("_coll", name), Coll())[1]
    monkeypatch.setattr(fsync, "client", lambda: fake)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", "{}")
    run(db.settings.update_one({"key": "global"}, {"$set": {"agreement_duration_fees": [{"days": 30, "fee": 149.0}, {"days": 90, "fee": 249.0}],
                                                            "owner_platform_fee": 99, "platform_validity_days": 365, "tenant_fees": {"monthly": 0},
                                                            "tax": {"gst_percent": 18}, "version": 7}}, upsert=True))
    assert run(fsync.publish_fees()) is True
    assert written["_coll"] == "app_config" and [t["fee"] for t in written["agreement_duration_fees"]] == [149.0, 249.0]
    assert written["agreement_duration_fees"][0]["gst"]["base_amount"] == round(149 / 1.18, 2) and written["platform_fee"] == 99
