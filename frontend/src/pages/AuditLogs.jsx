import { useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, Eye } from "lucide-react";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { DataTable } from "../components/DataTable";
import { PageHeader, KV } from "../components/Common";
import { api, errMsg, fmtDateTime, label } from "../lib/api";

const MODS = ["auth", "owners", "tenants", "properties", "agreements", "finance", "subscriptions", "coupons", "complaints", "leaving", "banners", "notifications", "admins", "settings", "archive", "audit"];
const Json = ({ v }) => <pre className="max-h-48 overflow-auto rounded-md bg-slate-900 p-3 text-[11px] text-slate-100">{v == null ? "—" : JSON.stringify(v, null, 2)}</pre>;

export default function AuditLogs() {
  const [sel, setSel] = useState(null);
  const [chain, setChain] = useState(null);
  const verify = async () => {
    try { const { data } = await api.get("/audit/verify"); setChain(data); data.valid ? toast.success(`Chain intact · ${data.checked} entries verified`) : toast.error(`Tampering detected at ${data.broken_at}`); }
    catch (e) { toast.error(await errMsg(e)); }
  };
  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="Append-only, hash-chained log of every admin action. Entries cannot be edited or deleted.">
        {chain && <span className={`self-center text-xs font-medium ${chain.valid ? "text-emerald-600" : "text-red-600"}`} data-testid="audit-chain-status">{chain.valid ? `Verified ${chain.checked} entries` : `Broken at ${chain.broken_at}`}</span>}
        <Button variant="outline" onClick={verify} data-testid="verify-audit-chain-button"><ShieldCheck className="mr-1.5 h-4 w-4" />Verify integrity</Button>
      </PageHeader>
      <DataTable entity="audit_logs" testid="audit" onRowClick={setSel} filters={[{ key: "module", label: "Module", options: MODS }]}
        columns={[{ key: "id", label: "Log ID", render: (r) => <span className="tabular text-xs">{r.id}</span> }, { key: "created_at", label: "Time", render: (r) => fmtDateTime(r.created_at) },
          { key: "admin_email", label: "Admin" }, { key: "action", label: "Action", render: (r) => <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-[#1E3A8A]">{label(r.action)}</span> },
          { key: "module", label: "Module" }, { key: "record_id", label: "Record", render: (r) => <span className="tabular text-xs">{r.record_id}</span> },
          { key: "reason", label: "Reason", render: (r) => <span className="block max-w-[240px] truncate">{r.reason || "—"}</span> }, { key: "ip", label: "IP" }]}
        rowActions={(r) => <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setSel(r)} data-testid={`view-audit-${r.id}`}><Eye className="h-4 w-4" /></Button>} />
      <Dialog open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <DialogContent className="max-w-2xl" data-testid="audit-detail-dialog">
          <DialogHeader><DialogTitle>{sel?.id} · {label(sel?.action)}</DialogTitle></DialogHeader>
          {sel && <div className="space-y-4">
            <KV cols={2} items={[["Admin", `${sel.admin_name} (${sel.admin_email})`], ["Time", fmtDateTime(sel.created_at)], ["Module", sel.module], ["Record", sel.record_id], ["IP", sel.ip], ["Reason", sel.reason]]} />
            <div className="grid gap-3 sm:grid-cols-2"><div><p className="th mb-1">Old value</p><Json v={sel.old_value} /></div><div><p className="th mb-1">New value</p><Json v={sel.new_value} /></div></div>
            <p className="break-all font-mono text-[10px] text-slate-400">hash {sel.hash}<br />prev {sel.prev_hash}</p>
          </div>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
