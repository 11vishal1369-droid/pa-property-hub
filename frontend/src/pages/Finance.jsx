import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, X, RotateCcw, Receipt, History, Plus } from "lucide-react";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { DataTable } from "../components/DataTable";
import { PageHeader, Timeline } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, errMsg, fmtDateTime, inr, label, openPdf } from "../lib/api";

const ICON = "h-7 w-7";

export default function Finance() {
  const { can } = useAuth();
  const [sum, setSum] = useState(null);
  const [key, setKey] = useState(0);
  const [hist, setHist] = useState(null);
  const [dialog, open] = useDialog();
  const edit = can("finance", "edit");

  useEffect(() => { api.get("/finance/summary").then((r) => setSum(r.data)); }, [key]);
  const done = (msg) => { toast.success(msg); setKey((k) => k + 1); };

  const act = (p, kind) => open({
    title: `${label(kind)} payment ${p.id}`, danger: kind === "reject", confirmLabel: label(kind),
    description: `${label(p.purpose)} · ${inr(p.amount)} · Txn ${p.txn_ref}`,
    onSubmit: async (_, reason) => { await api.post(`/payments/${p.id}/${kind}`, { reason }); done(`Payment ${kind === "reject" ? "rejected" : "approved"}`); },
  });
  const refund = (p) => open({
    title: `Refund ${p.id}`, description: `Paid ${inr(p.amount)} · already refunded ${inr(p.refunded_amount || 0)}`, confirmLabel: "Record refund",
    initial: { amount: p.amount - (p.refunded_amount || 0) }, fields: [{ name: "amount", label: "Refund amount (₹)", type: "number", required: true }],
    onSubmit: async (v, reason) => { await api.post(`/payments/${p.id}/refund`, { amount: v.amount, reason }); done("Refund recorded"); },
  });
  const manual = () => open({
    title: "Record manual payment submission", description: "Created as Pending — must be approved separately. Duplicate transaction references are rejected.", wide: true,
    fields: [{ name: "owner_id", label: "Owner ID", required: true }, { name: "purpose", label: "Purpose", type: "select", options: ["platform_fee", "agreement_fee", "rent"], required: true },
      { name: "amount", label: "Amount (₹)", type: "number", required: true }, { name: "txn_ref", label: "UTR / Transaction ref", required: true },
      { name: "tenant_id", label: "Tenant ID (optional)" }, { name: "agreement_id", label: "Agreement ID (optional)" }],
    onSubmit: async (v, reason) => { await api.post("/payments/manual", { ...v, tenant_id: v.tenant_id || null, agreement_id: v.agreement_id || null, reason }); done("Manual payment recorded"); },
  });
  const showHistory = async (p) => {
    try { const { data } = await api.get(`/payments/${p.id}/history`); setHist({ p, ...data }); } catch (e) { toast.error(await errMsg(e)); }
  };
  const receipt = (p) => openPdf(`/payments/${p.id}/receipt`).catch(async (e) => toast.error(await errMsg(e)));

  const tiles = sum ? [["Agreement fees", sum.by_purpose.agreement_fee], ["Platform fees", sum.by_purpose.platform_fee], ["Rent collected", sum.by_purpose.rent],
    ["Online", sum.by_method.online], ["Manual", sum.by_method.manual], ["Pending", sum.by_status.pending?.amount, sum.by_status.pending?.count],
    ["Failed", sum.by_status.failed?.amount, sum.by_status.failed?.count], ["Refunds", sum.refunds.amount, sum.refunds.count]] : [];

  return (
    <div>
      {dialog}
      <PageHeader title="Payments & Finance" subtitle="Every amount or status change requires a reason and creates an audit entry">
        {edit && <Button onClick={manual} className="bg-[#EA580C] hover:bg-[#c2410c]" data-testid="record-manual-payment-button"><Plus className="mr-1.5 h-4 w-4" />Record manual payment</Button>}
      </PageHeader>
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8" data-testid="finance-summary">
        {tiles.map(([k, v, n]) => (
          <div key={k} className="pa-card p-4"><p className="th">{k}</p><p className="tabular mt-1 text-lg font-semibold">{inr(v || 0)}</p>{n != null && <p className="text-xs text-slate-400">{n} txns</p>}</div>
        ))}
      </div>
      <DataTable entity="payments" refreshKey={key}
        filters={[{ key: "status", label: "Status", options: ["success", "pending", "approved", "rejected", "failed", "refunded", "partially_refunded"] },
          { key: "method", label: "Method", options: ["online", "manual"] }, { key: "purpose", label: "Purpose", options: ["platform_fee", "agreement_fee", "rent"] }]}
        columns={[{ key: "id", label: "Payment ID", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{r.id}</span> }, { key: "txn_ref", label: "Txn ref", render: (r) => <span className="tabular text-xs">{r.txn_ref}</span> },
          { key: "purpose", label: "Purpose", render: (r) => label(r.purpose) }, { key: "owner_name", label: "Owner", sortable: false }, { key: "tenant_name", label: "Tenant", sortable: false },
          { key: "amount", label: "Total received", render: (r) => <span className="tabular">{inr(r.total_received)}</span> },
          { key: "base_amount", label: "Base", sortable: false, render: (r) => <span className="tabular">{inr(r.base_amount)}</span> },
          { key: "gst_amount", label: "GST", sortable: false, render: (r) => <span className="tabular">{inr(r.gst_amount)}</span> },
          { key: "total", label: "Total", sortable: false, render: (r) => <span className="tabular font-medium">{inr(r.total)}</span> }, { key: "discount", label: "Discount", render: (r) => r.discount ? inr(r.discount) : "—" },
          { key: "refunded_amount", label: "Refunded", render: (r) => r.refunded_amount ? inr(r.refunded_amount) : "—" }, { key: "method", label: "Method", render: (r) => label(r.method) },
          { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Date", render: (r) => fmtDateTime(r.created_at) }]}
        rowActions={(r) => (
          <div className="flex justify-end gap-1">
            {edit && r.method === "manual" && r.status === "pending" && (<>
              <Button size="icon" variant="ghost" className={`${ICON} text-emerald-600`} title="Approve" onClick={() => act(r, "approve")} data-testid={`approve-payment-${r.id}`}><Check className="h-4 w-4" /></Button>
              <Button size="icon" variant="ghost" className={`${ICON} text-red-600`} title="Reject" onClick={() => act(r, "reject")} data-testid={`reject-payment-${r.id}`}><X className="h-4 w-4" /></Button>
            </>)}
            {edit && ["success", "approved", "partially_refunded"].includes(r.status) && <Button size="icon" variant="ghost" className={ICON} title="Refund" onClick={() => refund(r)} data-testid={`refund-payment-${r.id}`}><RotateCcw className="h-4 w-4" /></Button>}
            {["success", "approved", "refunded", "partially_refunded"].includes(r.status) && <Button size="icon" variant="ghost" className={ICON} title="Receipt" onClick={() => receipt(r)} data-testid={`receipt-payment-${r.id}`}><Receipt className="h-4 w-4" /></Button>}
            <Button size="icon" variant="ghost" className={ICON} title="History" onClick={() => showHistory(r)} data-testid={`history-payment-${r.id}`}><History className="h-4 w-4" /></Button>
          </div>
        )} />
      <Dialog open={!!hist} onOpenChange={(o) => !o && setHist(null)}>
        <DialogContent data-testid="payment-history-dialog">
          <DialogHeader><DialogTitle>History · {hist?.p.id}</DialogTitle></DialogHeader>
          <Timeline items={hist?.history || []} />
          {hist?.refunds?.length > 0 && <div className="mt-2 text-sm"><p className="th mb-1">Refunds</p>{hist.refunds.map((r) => <p key={r.id}>{r.id}: {inr(r.amount)} — {r.reason}</p>)}</div>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
