import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Button } from "../components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import { DataTable } from "../components/DataTable";
import { PageHeader, KV, Timeline } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, fmtDateTime, label, dispId } from "../lib/api";

const STATUSES = ["open", "in_progress", "escalated", "resolved", "closed", "reopened"];

export default function Complaints() {
  const { can } = useAuth();
  const [key, setKey] = useState(0);
  const [sel, setSel] = useState(null);
  const [tab, setTab] = useState("owner");
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
      <PageHeader title="Complaints" subtitle="Owner and tenant complaints with their reply threads. Admins watch the thread and update status." />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4 bg-white shadow-sm ring-1 ring-slate-200">
          <TabsTrigger value="owner" data-testid="complaints-tab-owner">Owner Complaints</TabsTrigger>
          <TabsTrigger value="tenant" data-testid="complaints-tab-tenant">Tenant Complaints</TabsTrigger>
        </TabsList>
      </Tabs>
      <DataTable key={tab} entity="complaints" testid={`complaints-${tab}`} baseParams={{ raised_by: tab }} refreshKey={key} onRowClick={setSel}
        filters={[{ key: "status", label: "Status", options: STATUSES }, { key: "priority", label: "Priority", options: ["low", "medium", "high", "urgent"] },
          { key: "category", label: "Category", options: ["Maintenance", "Amenities", "Payment", "Behaviour", "Agreement"] }]}
        columns={[{ key: "id", label: "ID", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{dispId(r)}</span> }, { key: "subject", label: "Subject" }, { key: "category", label: "Category" },
          { key: "priority", label: "Priority", render: (r) => <StatusBadge value={r.priority} /> }, { key: "raised_by", label: "By", render: (r) => label(r.raised_by) },
          { key: "tenant_name", label: "Tenant", sortable: false }, { key: "property_name", label: "Property", sortable: false },
          { key: "assigned_to_name", label: "Assigned", sortable: false, render: (r) => r.assigned_to_name || <span className="text-slate-400">Unassigned</span> },
          { key: "message_count", label: "Replies", sortable: false },
          { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Created", render: (r) => fmtDateTime(r.created_at) }]} />
      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl" data-testid="complaint-sheet">
          {sel && (<>
            <SheetHeader><SheetTitle className="font-heading">{sel.subject}</SheetTitle></SheetHeader>
            <div className="mt-2 flex gap-2"><StatusBadge value={sel.status} testid="complaint-status" /><StatusBadge value={sel.priority} /></div>
            <p className="mt-4 text-sm text-slate-600">{sel.description}</p>
            <div className="mt-5"><KV cols={2} items={[["Complaint ID", sel.id], ["Raised by", `${label(sel.raised_by)} (${sel.raised_by_id || "—"})`], ["Category", sel.category],
              ["Tenant", sel.tenant_name ? `${sel.tenant_name} (${sel.tenant_id})` : "—"], ["Owner", `${sel.owner_name} (${sel.owner_id})`], ["Property", `${sel.property_name} (${sel.property_id})`],
              ["Assigned to", sel.assigned_to_name], ["Escalation level", sel.escalation_level], ["Reopened", `${sel.reopen_count || 0} times`], ["Resolution", sel.resolution]]} /></div>
            <h4 className="mb-2 mt-6 font-heading font-semibold">Photos / Videos</h4>
            <div className="flex flex-wrap gap-2" data-testid="complaint-attachments">
              {[...(sel.attachments || []), ...(sel.messages || []).flatMap((m) => m.attachments || [])].map((u, i) => /\.(mp4|mov|webm)(\?|$)/i.test(u)
                ? <video key={i} src={u} controls className="h-24 rounded-md" /> : <a key={i} href={u} target="_blank" rel="noreferrer"><img src={u} alt="" className="h-24 w-32 rounded-md object-cover" /></a>)}
              {![...(sel.attachments || []), ...(sel.messages || []).flatMap((m) => m.attachments || [])].length && <p className="text-sm text-slate-400">No attachments</p>}
            </div>
            <h4 className="mb-2 mt-6 font-heading font-semibold">Replies ({(sel.messages || []).length})</h4>
            <div className="space-y-2 rounded-lg bg-slate-50 p-3" data-testid="complaint-conversation">
              {(sel.messages || []).map((m) => (
                <div key={m.id} className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.sender_type === "owner" ? "bg-blue-100 text-blue-950" : "ml-auto bg-orange-100 text-orange-950"}`}>
                  <p className="text-[11px] font-semibold">{label(m.sender_type)} · {m.sender_name} <span className="font-normal opacity-60">{fmtDateTime(m.at)}</span></p>
                  <p className="mt-0.5">{m.text}</p>
                </div>
              ))}
              {!(sel.messages || []).length && <p className="text-sm text-slate-400">No replies yet</p>}
            </div>
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
