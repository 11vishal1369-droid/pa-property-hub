import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Button } from "../components/ui/button";
import { DataTable } from "../components/DataTable";
import { PageHeader, KV, Timeline } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, fmtDateTime, label } from "../lib/api";

const STATUSES = ["open", "in_progress", "escalated", "resolved", "closed", "reopened"];

export default function Complaints() {
  const { can } = useAuth();
  const [key, setKey] = useState(0);
  const [sel, setSel] = useState(null);
  const [admins, setAdmins] = useState([]);
  const [dialog, open] = useDialog();
  const edit = can("complaints", "edit");

  useEffect(() => { api.get("/data/admins", { params: { page_size: 100, status: "active" } }).then((r) => setAdmins(r.data.items)).catch(() => {}); }, []);
  const reload = async (id) => { const { data } = await api.get(`/data/complaints/${id}`); setSel(data); setKey((k) => k + 1); };

  const action = (act, extra = {}) => open({ title: `${label(act)} complaint`, danger: act === "close", ...extra,
    onSubmit: async (v, reason) => { await api.post(`/complaints/${sel.id}/action`, { action: act, value: v.value || null, reason }); toast.success({ status: "Status updated", assign: "Complaint assigned", escalate: "Complaint escalated", remark: "Remark added", reopen: "Complaint reopened", close: "Complaint closed" }[act]); reload(sel.id); } });

  return (
    <div>
      {dialog}
      <PageHeader title="Complaints" subtitle="Track, assign, escalate and close complaints from owners and tenants" />
      <DataTable entity="complaints" refreshKey={key} onRowClick={setSel}
        filters={[{ key: "status", label: "Status", options: STATUSES }, { key: "priority", label: "Priority", options: ["low", "medium", "high", "urgent"] },
          { key: "category", label: "Category", options: ["Maintenance", "Amenities", "Payment", "Behaviour", "Agreement"] }]}
        columns={[{ key: "id", label: "ID", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{r.id}</span> }, { key: "subject", label: "Subject" }, { key: "category", label: "Category" },
          { key: "priority", label: "Priority", render: (r) => <StatusBadge value={r.priority} /> }, { key: "raised_by", label: "By", render: (r) => label(r.raised_by) },
          { key: "tenant_name", label: "Tenant", sortable: false }, { key: "property_name", label: "Property", sortable: false },
          { key: "assigned_to_name", label: "Assigned", sortable: false, render: (r) => r.assigned_to_name || <span className="text-slate-400">Unassigned</span> },
          { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Created", render: (r) => fmtDateTime(r.created_at) }]} />
      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl" data-testid="complaint-sheet">
          {sel && (<>
            <SheetHeader><SheetTitle className="font-heading">{sel.subject}</SheetTitle></SheetHeader>
            <div className="mt-2 flex gap-2"><StatusBadge value={sel.status} testid="complaint-status" /><StatusBadge value={sel.priority} /></div>
            <p className="mt-4 text-sm text-slate-600">{sel.description}</p>
            <div className="mt-5"><KV cols={2} items={[["ID", sel.id], ["Category", sel.category], ["Tenant", sel.tenant_name], ["Owner", sel.owner_name], ["Property", sel.property_name],
              ["Assigned to", sel.assigned_to_name], ["Escalation level", sel.escalation_level], ["Reopened", `${sel.reopen_count || 0} times`], ["Close reason", sel.close_reason]]} /></div>
            {edit && (
              <div className="mt-6 flex flex-wrap gap-2" data-testid="complaint-actions">
                <Button size="sm" variant="outline" data-testid="complaint-status-button" onClick={() => action("status", { fields: [{ name: "value", label: "Status", type: "select", options: ["open", "in_progress", "resolved"], required: true }] })}>Update status</Button>
                <Button size="sm" variant="outline" data-testid="complaint-assign-button" onClick={() => action("assign", { fields: [{ name: "value", label: "Assign to admin", type: "select", options: admins.map((a) => ({ value: a.id, label: `${a.name} (${a.role})` })), required: true }] })}>Assign</Button>
                <Button size="sm" variant="outline" data-testid="complaint-escalate-button" onClick={() => action("escalate")}>Escalate</Button>
                <Button size="sm" variant="outline" data-testid="complaint-remark-button" onClick={() => action("remark", { title: "Add remark" })}>Remark</Button>
                {["resolved", "closed"].includes(sel.status) && <Button size="sm" variant="outline" data-testid="complaint-reopen-button" onClick={() => action("reopen")}>Reopen</Button>}
                {sel.status !== "closed" && <Button size="sm" className="bg-red-600 hover:bg-red-700" data-testid="complaint-close-button" onClick={() => action("close")}>Close</Button>}
              </div>
            )}
            <h4 className="mb-3 mt-8 font-heading font-semibold">Timeline</h4>
            <Timeline items={[...(sel.timeline || [])].reverse()} testid="complaint-timeline" />
          </>)}
        </SheetContent>
      </Sheet>
    </div>
  );
}
