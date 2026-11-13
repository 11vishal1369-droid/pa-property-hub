import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { api, fmtDate, label, dispId } from "../lib/api";

const LINK = { owners: "/owners/", tenants: "/tenants/", properties: "/properties/", agreements: "/agreements/", payments: "/finance", complaints: "/complaints", leaving: "/leaving" };
const desc = (k, r) => ({ owners: `${r.mobile} · ${r.email}`, tenants: `${r.mobile} · ${r.email}`, properties: `${r.type} · ${r.address}, ${r.city}`,
  agreements: r.category, payments: `${label(r.purpose)} · ₹${r.amount} · ${r.txn_ref}`, complaints: r.subject, leaving: `Leave ${fmtDate(r.requested_leave_date)}` }[k]);

export default function SearchPage() {
  const [sp] = useSearchParams();
  const q = sp.get("q") || "";
  const nav = useNavigate();
  const [res, setRes] = useState(null);
  useEffect(() => { setRes(null); api.get("/search", { params: { q } }).then((r) => setRes(r.data.results)); }, [q]);
  const groups = res ? Object.entries(res).filter(([, v]) => v.length) : [];
  return (
    <div>
      <PageHeader title={`Search: “${q}”`} subtitle="Central historical search across active and archived records" />
      {!res ? <p className="text-slate-400">Searching…</p> : !groups.length ? <p className="pa-card p-10 text-center text-slate-500" data-testid="search-empty">No matching records</p> : (
        <div className="space-y-6" data-testid="search-results">
          {groups.map(([k, rows]) => (
            <div key={k}>
              <h2 className="mb-2 font-heading text-sm font-bold uppercase tracking-widest text-slate-500">{label(k)} <span className="text-orange-600">{rows.length}</span></h2>
              <div className="pa-card divide-y divide-slate-100">
                {rows.map((r) => (
                  <button key={r.id} onClick={() => nav(LINK[k].endsWith("/") ? LINK[k] + r.id : LINK[k])} data-testid={`search-result-${r.id}`}
                    className="flex w-full flex-wrap items-center gap-3 px-4 py-3 text-left hover:bg-blue-50/40">
                    <span className="tabular text-xs text-[#1E3A8A]">{dispId(r)}</span><span className="font-medium text-slate-900">{r.name || r.subject || r.category || r.txn_ref}</span>
                    <span className="text-sm text-slate-500">{desc(k, r)}</span><span className="ml-auto"><StatusBadge value={r.status} /></span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
