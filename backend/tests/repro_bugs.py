import asyncio
import os
import httpx

API = os.environ["TEST_API"]


async def tok(c, email, pw):
    r = await c.post(f"{API}/auth/login", json={"email": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        H = await tok(c, "admin@pa.com", "Admin@123")
        res = {}
        owners = (await c.get(f"{API}/data/owners?page_size=1", headers=H)).json()["items"]
        oid = owners[0]["id"]
        before = (await c.get(f"{API}/data/audit_logs?page_size=1", headers=H)).json()["total"]
        rs = await asyncio.gather(*[c.post(f"{API}/data/owners/{oid}/remarks", json={"text": f"conc {i}"}, headers=H) for i in range(12)])
        after = (await c.get(f"{API}/data/audit_logs?page_size=1", headers=H)).json()["total"]
        res["1_concurrent_audit"] = f"codes={sorted(set(r.status_code for r in rs))} audit_added={after - before} (expect 12, all 200)"

        F = await tok(c, "finance@pa.com", "Staff@123")
        r = await c.post(f"{API}/auth/change-password", json={"current_password": "Staff@123", "new_password": "Staff@123"}, headers=F)
        res["2_finance_change_pw_api"] = r.status_code

        for i in range(6):
            r = await c.post(f"{API}/auth/login", json={"email": "readonly@pa.com", "password": "bad"}, headers={"X-Forwarded-For": f"10.0.0.{i}"})
        res["3_lockout_spoof_6th_attempt"] = f"{r.status_code} (expect 429)"
        await c.post(f"{API}/auth/login", json={"email": "readonly@pa.com", "password": "Staff@123"})

        r = await c.get(f"{API}/data/owners?page=abc", headers=H)
        res["4_bad_page"] = f"{r.status_code} {r.text[:80]}"

        cp = (await c.get(f"{API}/data/coupons?page_size=1&status=active", headers=H)).json()["items"][0]
        r1 = await c.patch(f"{API}/data/coupons/{cp['id']}", json={"changes": {"discount_type": "percent", "value": 500}, "reason": "t"}, headers=H)
        r2 = await c.patch(f"{API}/data/coupons/{cp['id']}", json={"changes": {"start_date": "2026-12-01", "end_date": "2026-11-01"}, "reason": "t"}, headers=H)
        r3 = await c.post(f"{API}/coupons", json={"code": "REPROBAD", "discount_type": "fixed", "value": 0, "start_date": "2026-12-01", "end_date": "2026-11-01", "reason": "t"}, headers=H)
        res["5_coupon_validation"] = f"edit500={r1.status_code} editDates={r2.status_code} createBad={r3.status_code} (expect 400s)"

        pays = (await c.get(f"{API}/data/payments?status=success&purpose=rent&page_size=1", headers=H)).json()["items"]
        p = pays[0]
        rs = await asyncio.gather(*[c.post(f"{API}/payments/{p['id']}/refund", json={"amount": p["amount"], "reason": "conc"}, headers=H) for _ in range(5)])
        pd = (await c.get(f"{API}/data/payments/{p['id']}", headers=H)).json()
        res["6_concurrent_refund"] = f"codes={[r.status_code for r in rs]} refunded={pd['refunded_amount']} amount={pd['amount']}"

        me = (await c.get(f"{API}/auth/me", headers=H)).json()
        r1 = await c.patch(f"{API}/data/admins/{me['id']}", json={"changes": {"role": "Read-Only Admin"}, "reason": "t"}, headers=H)
        if r1.status_code == 200:
            await c.patch(f"{API}/data/admins/{me['id']}", json={"changes": {"role": "Super Admin"}, "reason": "revert"}, headers=H)
        res["7_self_role_change"] = f"{r1.status_code} (expect 403)"

        lv = (await c.get(f"{API}/data/leaving?status=pending&page_size=1", headers=H)).json()["items"][0]
        r = await c.post(f"{API}/leaving/{lv['id']}/settlement", json={"deposit": 1, "damage": 0, "reason": "t"}, headers=H)
        res["8_settlement_deposit"] = f"{r.status_code} used={r.json().get('deposit')} recorded={lv['deposit']}"

        cm = (await c.get(f"{API}/data/complaints?status=open&page_size=1", headers=H)).json()["items"][0]
        await c.post(f"{API}/complaints/{cm['id']}/action", json={"action": "close", "reason": "closed for test"}, headers=H)
        r = await c.post(f"{API}/complaints/{cm['id']}/action", json={"action": "reopen", "reason": "reopen"}, headers=H)
        res["10_reopen_close_reason"] = f"close_reason after reopen={r.json().get('close_reason')!r} (expect None)"
        for k, v in res.items():
            print(k, "=>", v)


asyncio.run(main())
