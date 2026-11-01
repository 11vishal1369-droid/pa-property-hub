import { useState } from "react";
import { toast } from "sonner";
import { FileSpreadsheet, FileText, FileDown } from "lucide-react";
import { Button } from "../components/ui/button";
import { PageHeader } from "../components/Common";
import { useAuth } from "../context/AuthContext";
import { download, errMsg } from "../lib/api";

const REPORTS = [["owners", "Owners report", "owners", ["active", "blocked", "suspended", "deactivated", "archived"]],
  ["tenants", "Tenants report (Aadhaar masked)", "tenants", ["active", "blocked", "suspended", "deactivated", "archived"]],
  ["properties", "Properties & occupancy", "properties", ["active", "inactive", "blocked", "closed", "archived"]],
  ["agreements", "Agreements report", "agreements", ["pending_verification", "verified", "completed", "rejected", "archived"]],
  ["payments", "Payments & revenue", "finance", ["success", "pending", "approved", "rejected", "failed", "refunded"]],
  ["subscriptions", "Subscriptions", "subscriptions", ["active", "expired", "cancelled"]], ["coupons", "Coupons", "coupons", ["active", "inactive"]],
  ["complaints", "Complaints", "complaints", ["open", "in_progress", "escalated", "resolved", "closed"]], ["leaving", "Leaving & settlements", "leaving", ["pending", "approved", "completed", "rejected"]],
  ["notifications", "Notification delivery", "notifications", ["delivered", "sent", "failed", "queued"]], ["audit_logs", "Audit logs", "audit", []]];

const Card = ({ r }) => {
  const [entity, title, , statuses] = r;
  const [st, setSt] = useState("");
  const [frm, setFrm] = useState("");
  const [to, setTo] = useState("");
  const go = async (format) => {
    try {
      await download(`/data/${entity}/export`, { format, ...(st && { status: st }), ...(frm && { from: frm }), ...(to && { to }), ...(st === "archived" && { include_archived: "true" }) });
      toast.success(`${title} downloaded`);
    } catch (e) { toast.error(await errMsg(e)); }
  };
  const inp = "h-8 rounded-md border border-slate-200 px-2 text-xs";
  return (
    <div className="pa-card flex flex-col p-5" data-testid={`report-card-${entity}`}>
      <h3 className="font-heading font-semibold text-slate-900">{title}</h3>
      <div className="mt-3 flex flex-wrap gap-2">
        {statuses.length > 0 && <select className={inp} value={st} onChange={(e) => setSt(e.target.value)} data-testid={`report-${entity}-status`}>
          <option value="">All statuses</option>{statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select>}
        <input type="date" className={inp} value={frm} onChange={(e) => setFrm(e.target.value)} data-testid={`report-${entity}-from`} />
        <input type="date" className={inp} value={to} onChange={(e) => setTo(e.target.value)} data-testid={`report-${entity}-to`} />
      </div>
      <div className="mt-4 flex gap-2">
        <Button size="sm" variant="outline" onClick={() => go("xlsx")} data-testid={`report-${entity}-xlsx`}><FileSpreadsheet className="mr-1.5 h-3.5 w-3.5 text-emerald-600" />Excel</Button>
        <Button size="sm" variant="outline" onClick={() => go("csv")} data-testid={`report-${entity}-csv`}><FileDown className="mr-1.5 h-3.5 w-3.5 text-blue-700" />CSV</Button>
        <Button size="sm" variant="outline" onClick={() => go("pdf")} data-testid={`report-${entity}-pdf`}><FileText className="mr-1.5 h-3.5 w-3.5 text-red-600" />PDF</Button>
      </div>
    </div>
  );
};

export default function Reports() {
  const { can } = useAuth();
  return (
    <div>
      <PageHeader title="Reports" subtitle="Downloads respect your permissions; sensitive data such as Aadhaar is always masked. Every export is audited." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{REPORTS.filter((r) => can(r[2])).map((r) => <Card key={r[0]} r={r} />)}</div>
    </div>
  );
}
