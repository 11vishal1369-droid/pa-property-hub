import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, PieChart, Pie, Cell } from "recharts";
import { PageHeader, Section } from "../components/Common";
import { api, errMsg, inr, fmtDateTime, label } from "../lib/api";

const RANGES = [["all", "All time"], ["today", "Today"], ["yesterday", "Yesterday"], ["last7", "Last 7 days"], ["last30", "Last 30 days"],
  ["this_month", "This month"], ["prev_month", "Previous month"], ["this_year", "This year"], ["custom", "Custom"]];

const GROUPS = [
  ["Owners", "/owners", [["owners_total", "Total owners"], ["owners_active", "Active owners", "active"], ["owners_blocked", "Blocked owners", "blocked"], ["owners_deactivated", "Deactivated owners", "deactivated"]]],
  ["Tenants", "/tenants", [["tenants_total", "Total tenants"], ["tenants_active", "Active tenants", "active"], ["tenants_blocked", "Blocked tenants", "blocked"], ["tenants_deactivated", "Deactivated tenants", "deactivated"]]],
  ["Properties", "/properties", [["properties_total", "Total properties"], ["properties_active", "Active"], ["properties_occupied", "Occupied"], ["properties_vacant", "Vacant"],
    ["properties_archived", "Archived"], ["pg_count", "PG"], ["residential_count", "Residential"], ["commercial_count", "Commercial"]]],
  ["Agreements", "/agreements", [["agreements_total", "Total agreements"], ["agreements_pending", "Pending"], ["agreements_completed", "Completed / verified"]]],
  ["Finance", "/finance", [["agreement_fees", "Agreement fees", null, true], ["subscription_fees", "Subscription fees", null, true], ["coupon_discounts", "Coupon discounts", null, true],
    ["online_payments", "Online payments", null, true], ["manual_submissions", "Manual submissions"], ["pending_approvals", "Pending approvals"], ["refunds_settlements", "Refunds & settlements", null, true]]],
  ["Operations", "/complaints", [["complaints_total", "Total complaints"], ["complaints_pending", "Pending complaints"], ["leaving_pending", "Pending leaving requests", null, false, "/leaving"]]],
];
const COLORS = ["#1E3A8A", "#EA580C", "#16A34A", "#D97706", "#DC2626", "#8B5CF6", "#0284C7"];

const Kpi = ({ k, title, value, money, onClick, i }) => (
  <button onClick={onClick} data-testid={`kpi-${k}`} style={{ animationDelay: `${i * 25}ms` }}
    className="pa-card pa-rise group p-4 text-left transition-[border-color,transform] hover:-translate-y-0.5 hover:border-blue-300">
    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 group-hover:text-[#1E3A8A]">{title}</p>
    <p className={`tabular mt-2 break-words font-semibold text-slate-900 ${money ? "text-lg" : "text-2xl"}`} data-testid={`kpi-${k}-value`}>{money ? inr(value) : (value ?? "—").toLocaleString("en-IN")}</p>
  </button>
);

export default function Dashboard() {
  const nav = useNavigate();
  const [range, setRange] = useState("all");
  const [frm, setFrm] = useState("");
  const [to, setTo] = useState("");
  const [d, setD] = useState(null);

  useEffect(() => {
    if (range === "custom" && (!frm || !to)) return;
    api.get("/dashboard", { params: { range, frm: frm || undefined, to: to || undefined } }).then((r) => setD(r.data)).catch(async (e) => toast.error(await errMsg(e)));
  }, [range, frm, to]);

  let i = 0;
  return (
    <div>
      <PageHeader title="Dashboard" subtitle={d?.range?.from ? `Showing ${d.range.from} → ${d.range.to}` : "Showing all-time platform data"}>
        <select value={range} onChange={(e) => setRange(e.target.value)} data-testid="dashboard-range-select"
          className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm">
          {RANGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        {range === "custom" && (<>
          <input type="date" value={frm} onChange={(e) => setFrm(e.target.value)} className="h-9 rounded-md border border-slate-200 px-2 text-sm" data-testid="dashboard-from-date" />
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-9 rounded-md border border-slate-200 px-2 text-sm" data-testid="dashboard-to-date" />
        </>)}
      </PageHeader>
      {!d ? <p className="text-slate-400">Loading…</p> : (
        <div className="space-y-8">
          {GROUPS.map(([g, path, cards]) => (
            <div key={g}>
              <h2 className="mb-3 flex items-center gap-2 font-heading text-sm font-bold uppercase tracking-widest text-slate-500"><span className="h-3 w-1 rounded bg-[#EA580C]" />{g}</h2>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
                {cards.map(([k, t, st, money, p2]) => (
                  <Kpi key={k} k={k} title={t} value={d.cards[k]} money={money} i={i++} onClick={() => nav(`${p2 || path}${st ? `?status=${st}` : ""}`)} />
                ))}
              </div>
            </div>
          ))}
          <div className="grid gap-6 lg:grid-cols-12">
            <div className="lg:col-span-8"><Section title="Collections by month">
              <div className="h-64" data-testid="revenue-chart">
                <ResponsiveContainer><AreaChart data={d.monthly_revenue}>
                  <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1E3A8A" stopOpacity={0.25} /><stop offset="100%" stopColor="#1E3A8A" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} tickFormatter={(v) => `₹${Math.round(v / 1000)}k`} />
                  <Tooltip formatter={(v) => inr(v)} /><Area dataKey="amount" stroke="#1E3A8A" strokeWidth={2} fill="url(#g1)" />
                </AreaChart></ResponsiveContainer>
              </div>
            </Section></div>
            <div className="lg:col-span-4"><Section title="Payment status mix">
              <div className="h-64" data-testid="payment-status-chart">
                <ResponsiveContainer><PieChart><Pie data={d.payment_status} dataKey="count" nameKey="status" innerRadius={50} outerRadius={85} paddingAngle={2}>
                  {d.payment_status.map((_, j) => <Cell key={j} fill={COLORS[j % COLORS.length]} />)}</Pie><Tooltip formatter={(v, n) => [v, label(n)]} /></PieChart></ResponsiveContainer>
              </div>
            </Section></div>
          </div>
          <Section title="Recent admin activity">
            <ul className="divide-y divide-slate-100" data-testid="recent-activity">
              {d.recent_activity.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                  <span className="tabular text-xs text-slate-400">{fmtDateTime(a.created_at)}</span>
                  <span className="font-medium text-slate-800">{a.admin_email}</span>
                  <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-[#1E3A8A]">{label(a.action)}</span>
                  <span className="text-slate-500">{a.module} · {a.record_id}</span>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      )}
    </div>
  );
}
