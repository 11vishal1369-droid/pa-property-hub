import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RotateCw, Send } from "lucide-react";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { DataTable } from "../components/DataTable";
import { PageHeader, MiniTable } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, fmtDateTime, label } from "../lib/api";

function Campaigns({ audience, refresh }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get("/notifications/campaigns", { params: { audience } }).then((r) => setRows(r.data)); }, [audience, refresh]);
  return (
    <MiniTable testid={`campaigns-${audience}`} rows={rows} empty="No notifications sent from the admin panel yet"
      columns={[{ key: "id", label: "Send ID" }, { key: "created_at", label: "Created", render: (r) => fmtDateTime(r.created_at) },
        { key: "scheduled_at", label: "Scheduled for", render: (r) => r.scheduled_at ? fmtDateTime(r.scheduled_at) : "Immediate" },
        { key: "target", label: "Recipients", render: (r) => `${label(r.target)} (${r.recipient_count})` }, { key: "title", label: "Title" },
        { key: "delivery", label: "Delivery", render: (r) => Object.entries(r.delivery || {}).map(([k, v]) => `${label(k)}: ${v}`).join(" · ") },
        { key: "created_by", label: "By" }]} />
  );
}

function AudienceView({ audience }) {
  const { can } = useAuth();
  const [key, setKey] = useState(0);
  const [dialog, open] = useDialog();
  const who = audience === "owner" ? "Owners" : "Tenants";
  const send = () => open({ title: `Send notification to ${who}`, wide: true, confirmLabel: "Send",
    description: `Goes only to ${who.toLowerCase()}. It's delivered in-app when the ${label(audience)} App fetches its inbox.`, initial: { target: "all", recipient_ids: [] },
    fields: [{ name: "target", label: "Recipients", type: "select", options: [{ value: "all", label: `All ${who}` }, { value: "selected", label: `Selected ${who}` }], required: true },
      { name: "recipient_ids", label: `Select ${who.toLowerCase()}`, type: "users", userType: audience, show: (v) => v.target === "selected" },
      { name: "title", label: "Title", required: true, full: true }, { name: "message", label: "Message", type: "textarea", required: true },
      { name: "scheduled_at", label: "Schedule (optional)", type: "datetime-local" }],
    onSubmit: async (v, reason) => {
      const r = await api.post("/notifications/send", { audience, target: v.target, recipient_ids: v.target === "selected" ? v.recipient_ids : [], title: v.title, message: v.message,
        scheduled_at: v.scheduled_at ? new Date(v.scheduled_at).toISOString() : null, reason });
      toast.success(`${r.data.scheduled_at ? "Scheduled" : "Sent"} to ${r.data.recipient_count} ${who.toLowerCase()}`); setKey((k) => k + 1);
    } });
  const retry = (n) => open({ title: "Re-queue failed notification", description: "Status becomes Queued until the app picks it up.",
    onSubmit: async (_, reason) => { await api.post(`/notifications/${n.id}/retry`, { reason }); toast.success("Re-queued"); setKey((k) => k + 1); } });
  return (
    <div className="space-y-6">
      {dialog}
      {can("notifications", "edit") && <Button onClick={send} className="bg-[#EA580C] hover:bg-[#c2410c]" data-testid={`send-notification-${audience}`}><Send className="mr-1.5 h-4 w-4" />Send to {who}</Button>}
      <div><h3 className="mb-2 font-heading font-semibold">Send history</h3><Campaigns audience={audience} refresh={key} /></div>
      <DataTable entity="notifications" testid={`notifications-${audience}`} baseParams={{ recipient_type: audience }} refreshKey={key}
        filters={[{ key: "status", label: "Delivery", options: ["scheduled", "queued", "sent", "delivered", "read", "failed"] },
          { key: "channel", label: "Channel", options: ["in_app", "push", "sms", "email"] },
          { key: "type", label: "Type", options: ["announcement", "payment_success", "subscription_expiry", "agreement_verified", "complaint_update", "rent_reminder", "leaving_update"] }]}
        columns={[{ key: "id", label: "ID", render: (r) => <span className="tabular text-xs">{r.id}</span> }, { key: "recipient_name", label: "Recipient" },
          { key: "type", label: "Type", render: (r) => label(r.type) },
          { key: "channel", label: "Channel", render: (r) => label(r.channel) }, { key: "title", label: "Title" },
          { key: "scheduled_at", label: "Scheduled", render: (r) => r.scheduled_at ? fmtDateTime(r.scheduled_at) : "—" },
          { key: "status", label: "Delivery", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Date", render: (r) => fmtDateTime(r.created_at) }]}
        rowActions={(r) => r.status === "failed" && can("notifications", "edit") && (
          <Button size="sm" variant="ghost" onClick={() => retry(r)} data-testid={`retry-notification-${r.id}`}><RotateCw className="mr-1 h-3.5 w-3.5" />Retry</Button>
        )} />
    </div>
  );
}

export default function Notifications() {
  return (
    <div>
      <PageHeader title="Notifications" subtitle="Owner and tenant notifications are kept separate. Owners never get tenant notifications, and the other way round." />
      <Tabs defaultValue="owner">
        <TabsList className="mb-4 bg-white shadow-sm ring-1 ring-slate-200">
          <TabsTrigger value="owner" data-testid="notifications-tab-owner">Owner Notifications</TabsTrigger>
          <TabsTrigger value="tenant" data-testid="notifications-tab-tenant">Tenant Notifications</TabsTrigger>
        </TabsList>
        <TabsContent value="owner"><AudienceView audience="owner" /></TabsContent>
        <TabsContent value="tenant"><AudienceView audience="tenant" /></TabsContent>
      </Tabs>
    </div>
  );
}
