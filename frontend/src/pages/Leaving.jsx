import { useState } from "react";
import { toast } from "sonner";
import { Calculator } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Button } from "../components/ui/button";
import { DataTable } from "../components/DataTable";
import { PageHeader, KV, Timeline } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, fmtDate, fmtDateTime, inr, label } from "../lib/api";

const NUMS = [["outstanding_rent", "Outstanding rent"], ["utilities", "Utilities"], ["other_charges", "Other charges"], ["damage", "Damage"]];

export default function Leaving() {
  const { can } = useAuth();
  const [key, setKey] = useState(0);
  const [sel, setSel] = useState(null);
  const [dialog, open] = useDialog();
  const edit = can("leaving", "edit");
  const reload = async (id) => { const { data } = await api.get(`/data/leaving/${id}`); setSel(data); setKey((k) => k + 1); };

  const settle = () => open({ title: "Calculate settlement", wide: true, confirmLabel: "Calculate & save",
    description: `Refund = recorded deposit ${inr(sel.deposit)} − (Outstanding rent + Utilities + Other charges + Damage). The deposit comes from the tenant record. Each calculation is versioned.`,
    initial: { ...Object.fromEntries(NUMS.map(([k]) => [k, sel.settlement?.[k] ?? 0])), notes: sel.settlement?.notes || "" },
    fields: [...NUMS.map(([name, l]) => ({ name, label: `${l} (₹)`, type: "number", required: true })), { name: "notes", label: "Notes", type: "textarea", rows: 2 }],
    onSubmit: async (v, reason) => { const { data } = await api.post(`/leaving/${sel.id}/settlement`, { ...v, reason }); toast.success(`Refund ${inr(data.refund_amount)}`); reload(sel.id); } });
  const act = (a) => open({ title: `${label(a)} leaving request`, danger: a === "reject",
    onSubmit: async (_, reason) => { await api.post(`/leaving/${sel.id}/action`, { action: a, reason }); toast.success(`Request ${a}d`); reload(sel.id); } });
  const s = sel?.settlement;

  return (
    <div>
      {dialog}
      <PageHeader title="Leaving Requests" subtitle="Move-out requests with full deposit settlement calculation" />
      <DataTable entity="leaving" refreshKey={key} onRowClick={setSel} filters={[{ key: "status", label: "Status", options: ["pending", "approved", "rejected", "completed"] }]}
        columns={[{ key: "id", label: "Request", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{r.id}</span> }, { key: "tenant_name", label: "Tenant", sortable: false },
          { key: "owner_name", label: "Owner", sortable: false }, { key: "property_name", label: "Property", sortable: false },
          { key: "requested_leave_date", label: "Leave date", render: (r) => fmtDate(r.requested_leave_date) }, { key: "deposit", label: "Deposit", render: (r) => inr(r.deposit) },
          { key: "refund_amount", label: "Refund", render: (r) => r.refund_amount != null ? inr(r.refund_amount) : "—" },
          { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Created", render: (r) => fmtDate(r.created_at) }]} />
      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl" data-testid="leaving-sheet">
          {sel && (<>
            <SheetHeader><SheetTitle className="font-heading">{sel.id} · {sel.tenant_name}</SheetTitle></SheetHeader>
            <div className="mt-2"><StatusBadge value={sel.status} testid="leaving-status" /></div>
            <div className="mt-5"><KV cols={2} items={[["Property", sel.property_name], ["Owner", sel.owner_name], ["Leave date", fmtDate(sel.requested_leave_date)], ["Reason", sel.reason_text], ["Deposit", inr(sel.deposit)]]} /></div>
            <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="settlement-summary">
              <p className="th mb-3">Settlement {s && `· v${s.version}`}</p>
              {s ? (<div className="space-y-1.5 text-sm">
                {NUMS.map(([k, l]) => <div key={k} className="flex justify-between"><span className="text-slate-500">{l}</span><span className="tabular">− {inr(s[k])}</span></div>)}
                <div className="flex justify-between"><span className="text-slate-500">Recorded deposit</span><span className="tabular">{inr(s.deposit)}</span></div>
                <div className="flex justify-between border-t border-slate-200 pt-2 font-semibold"><span>Refund to tenant</span><span className="tabular text-emerald-700" data-testid="settlement-refund">{inr(s.refund_amount)}</span></div>
                {s.payable_by_tenant > 0 && <div className="flex justify-between font-semibold text-red-600"><span>Payable by tenant</span><span className="tabular">{inr(s.payable_by_tenant)}</span></div>}
                <p className="pt-1 text-xs text-slate-400">By {s.calculated_by} · {fmtDateTime(s.calculated_at)}</p>
              </div>) : <p className="text-sm text-slate-400">Not calculated yet</p>}
            </div>
            {edit && (
              <div className="mt-4 flex flex-wrap gap-2">
                {!["completed", "rejected"].includes(sel.status) && <Button size="sm" variant="outline" onClick={settle} data-testid="calculate-settlement-button"><Calculator className="mr-1.5 h-3.5 w-3.5" />Calculate settlement</Button>}
                {sel.status === "pending" && <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => act("approve")} data-testid="approve-leaving-button">Approve</Button>}
                {sel.status === "approved" && <Button size="sm" className="bg-[#1E3A8A]" onClick={() => act("complete")} data-testid="complete-leaving-button">Complete move-out</Button>}
                {["pending", "approved"].includes(sel.status) && <Button size="sm" variant="outline" className="text-red-600" onClick={() => act("reject")} data-testid="reject-leaving-button">Reject</Button>}
              </div>
            )}
            <h4 className="mb-3 mt-8 font-heading font-semibold">Settlement history</h4>
            <Timeline items={(sel.settlement_history || []).map((h) => ({ at: h.calculated_at, by: h.calculated_by, action: `v${h.version} refund ${inr(h.refund_amount)}`, reason: h.reason }))} />
            <h4 className="mb-3 mt-6 font-heading font-semibold">Status history</h4>
            <Timeline items={sel.timeline || []} />
          </>)}
        </SheetContent>
      </Sheet>
    </div>
  );
}
