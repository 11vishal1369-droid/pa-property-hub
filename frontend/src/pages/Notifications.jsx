import { useState } from "react";
import { toast } from "sonner";
import { RotateCw } from "lucide-react";
import { Button } from "../components/ui/button";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, fmtDateTime, label } from "../lib/api";

export default function Notifications() {
  const { can } = useAuth();
  const [key, setKey] = useState(0);
  const [dialog, open] = useDialog();
  const retry = (n) => open({ title: "Re-queue failed notification", description: "Status becomes Queued; delivery is confirmed only by the messaging provider.",
    onSubmit: async (_, reason) => { await api.post(`/notifications/${n.id}/retry`, { reason }); toast.success("Re-queued"); setKey((k) => k + 1); } });
  return (
    <div>
      {dialog}
      <PageHeader title="Notifications" subtitle="Monitor notifications sent to owners and tenants" />
      <DataTable entity="notifications" refreshKey={key}
        filters={[{ key: "status", label: "Delivery", options: ["delivered", "sent", "failed", "queued"] }, { key: "recipient_type", label: "Recipient", options: ["owner", "tenant"] },
          { key: "channel", label: "Channel", options: ["push", "sms", "email"] },
          { key: "type", label: "Type", options: ["payment_success", "subscription_expiry", "agreement_verified", "complaint_update", "rent_reminder", "leaving_update"] }]}
        columns={[{ key: "id", label: "ID", render: (r) => <span className="tabular text-xs">{r.id}</span> }, { key: "recipient_name", label: "Recipient" },
          { key: "recipient_type", label: "Recipient type", render: (r) => label(r.recipient_type) }, { key: "type", label: "Type", render: (r) => label(r.type) },
          { key: "channel", label: "Channel", render: (r) => label(r.channel) }, { key: "title", label: "Title" },
          { key: "status", label: "Delivery", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Date", render: (r) => fmtDateTime(r.created_at) }]}
        rowActions={(r) => r.status === "failed" && can("notifications", "edit") && (
          <Button size="sm" variant="ghost" onClick={() => retry(r)} data-testid={`retry-notification-${r.id}`}><RotateCw className="mr-1 h-3.5 w-3.5" />Retry</Button>
        )} />
    </div>
  );
}
