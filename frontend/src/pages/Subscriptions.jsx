import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CalendarPlus, Ban } from "lucide-react";
import { Button } from "../components/ui/button";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, fmtDate, inr } from "../lib/api";

export default function Subscriptions() {
  const { can } = useAuth();
  const nav = useNavigate();
  const [key, setKey] = useState(0);
  const [dialog, open] = useDialog();
  const extend = (s) => open({ title: `Extend ${s.id}`, description: `Current expiry ${fmtDate(s.expiry_date)}`, initial: { days: 30 },
    fields: [{ name: "days", label: "Extend by (days)", type: "number", required: true }],
    onSubmit: async (v, reason) => { await api.post(`/subscriptions/${s.id}/extend`, { days: v.days, reason }); toast.success("Subscription extended"); setKey((k) => k + 1); } });
  const cancel = (s) => open({ title: `Cancel ${s.id}`, danger: true, confirmLabel: "Cancel subscription",
    onSubmit: async (_, reason) => { await api.post(`/data/subscriptions/${s.id}/status`, { status: "cancelled", reason }); toast.success("Subscription cancelled"); setKey((k) => k + 1); } });
  return (
    <div>
      {dialog}
      <PageHeader title="Subscriptions" subtitle="Owner platform fee subscriptions (₹99 / 365 days by default, configurable in Settings)" />
      <DataTable entity="subscriptions" refreshKey={key} filters={[{ key: "status", label: "Status", options: ["active", "expired", "cancelled"] }]}
        columns={[{ key: "id", label: "Sub ID", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{r.id}</span> },
          { key: "owner_name", label: "Owner", sortable: false, render: (r) => <button className="hover:underline" onClick={() => nav(`/owners/${r.owner_id}`)}>{r.owner_name}</button> },
          { key: "plan", label: "Plan" }, { key: "amount", label: "Amount", render: (r) => inr(r.amount) }, { key: "start_date", label: "Start", render: (r) => fmtDate(r.start_date) },
          { key: "expiry_date", label: "Expiry", render: (r) => fmtDate(r.expiry_date) }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }]}
        rowActions={(r) => can("subscriptions", "edit") && (
          <div className="flex justify-end gap-1">
            <Button size="sm" variant="ghost" onClick={() => extend(r)} data-testid={`extend-sub-${r.id}`}><CalendarPlus className="mr-1 h-3.5 w-3.5" />Extend</Button>
            {r.status === "active" && <Button size="sm" variant="ghost" className="text-red-600" onClick={() => cancel(r)} data-testid={`cancel-sub-${r.id}`}><Ban className="mr-1 h-3.5 w-3.5" />Cancel</Button>}
          </div>
        )} />
    </div>
  );
}
