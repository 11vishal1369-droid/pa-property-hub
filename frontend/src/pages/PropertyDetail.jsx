import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ImagePlus, X } from "lucide-react";
import { Button } from "../components/ui/button";
import { PageHeader, KV, MiniTable, Section } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { RecordControls } from "../components/RecordControls";
import { useDialog } from "../components/FormDialog";
import { useProfile, BackButton, ProfileTabs, ActivityPanel } from "../components/Profile";
import { useAuth } from "../context/AuthContext";
import { api, fmtDate, fmtDateTime, inr } from "../lib/api";
import { payCols, agrCols } from "./OwnerDetail";
import { PROP_TYPES } from "./Directories";

const path = (id) => `/properties/${id}/profile`;
const EDIT = [["name", "Name"], ["category", "Category", "select", ["PG", "Residential", "Commercial"]], ["type", "Type", "select", PROP_TYPES],
  ["pg_gender", "PG type (PG only)", "select", ["Boys", "Girls", "Co-living"]], ["city", "City"],
  ["rent", "Rent", "number"], ["deposit", "Deposit", "number"], ["total_units", "Total rooms/beds/seats", "number"], ["address", "Address", "textarea"]]
  .map(([name, l, type, options]) => ({ name, label: l, type, options }));
const tenCols = [{ key: "tenant_name", label: "Tenant" }, { key: "room", label: "Room/Bed" }, { key: "join_date", label: "Joined", render: (r) => fmtDate(r.join_date) },
  { key: "leave_date", label: "Left", render: (r) => fmtDate(r.leave_date) }, { key: "rent", label: "Rent", render: (r) => inr(r.rent) }];

function Photos({ p, load }) {
  const { can } = useAuth();
  const [dialog, open] = useDialog();
  const add = () => open({ title: "Add photo", fields: [{ name: "url", label: "Image URL", required: true }],
    onSubmit: async (v, reason) => { await api.post(`/properties/${p.id}/photos`, { url: v.url, reason }); toast.success("Photo added"); load(); } });
  const remove = (url) => open({ title: "Remove photo", danger: true, description: "The photo is kept in removed-photo history.",
    onSubmit: async (_, reason) => { await api.post(`/properties/${p.id}/photos/remove`, { url, reason }); toast.success("Photo removed"); load(); } });
  return (
    <Section title="Photos" action={can("properties", "edit") && <Button size="sm" variant="outline" onClick={add} data-testid="add-photo-button"><ImagePlus className="mr-1.5 h-3.5 w-3.5" />Add</Button>}>
      {dialog}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="property-photos">
        {(p.photos || []).map((u) => (
          <div key={u} className="group relative aspect-[4/3] overflow-hidden rounded-lg bg-slate-100">
            <img src={u} alt="" className="h-full w-full object-cover" />
            {can("properties", "edit") && <button onClick={() => remove(u)} className="absolute right-1.5 top-1.5 rounded-full bg-white/90 p-1 opacity-0 transition-opacity group-hover:opacity-100" data-testid="remove-photo-button"><X className="h-3.5 w-3.5" /></button>}
          </div>
        ))}
        {!p.photos?.length && <p className="text-sm text-slate-400">No photos</p>}
      </div>
    </Section>
  );
}

export default function PropertyDetail() {
  const nav = useNavigate();
  const { data, err, load } = useProfile(path);
  if (err) return <p className="text-red-600" data-testid="profile-error">{err}</p>;
  if (!data) return <p className="text-slate-400">Loading…</p>;
  const p = data.property;
  const occupied = new Set(data.current_tenants.map((t) => t.room));
  return (
    <div data-testid="property-profile">
      <BackButton />
      <PageHeader title={p.name} subtitle={<span className="flex items-center gap-2"><span className="tabular">{p.id}</span> · {p.category} / {p.type} · {p.city} <StatusBadge value={p.status} testid="property-status" /></span>}>
        <RecordControls entity="properties" module="properties" record={p} statuses={["active", "inactive", "blocked", "deactivated", "closed"]} editFields={EDIT} onDone={load} />
      </PageHeader>
      <ProfileTabs tabs={[
        ["overview", "Overview", <div className="space-y-4">
          <Section title="Property overview"><KV items={[["Owner", <button className="text-[#1E3A8A] underline-offset-2 hover:underline" onClick={() => nav(`/owners/${p.owner_id}`)}>{p.owner_name}</button>],
            ["Category", p.category], ["Type", p.type], ["PG for", p.pg_gender], ["Fee category", p.fee_category], ["Address", `${p.address}, ${p.city}`], ["Occupancy", p.occupancy],
            ["Rent", inr(p.rent)], ["Deposit", inr(p.deposit)], ["Created", fmtDateTime(p.created_at)], ["Archived by", p.archived_source && `${p.archived_source} (${p.archived_by})`], ["Archive reason", p.archive_reason]]} /></Section>
          <Photos p={p} load={load} />
        </div>],
        ["units", `${p.unit_label || "Units"} (${p.total_units})`, <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 lg:grid-cols-10" data-testid="property-units">
          {(p.units || []).map((u) => <div key={u.label} className={`rounded-md border p-2 text-center text-xs ${occupied.has(u.label) ? "border-blue-200 bg-blue-50 text-[#1E3A8A]" : "border-slate-200 bg-white text-slate-500"}`}>
            <p className="font-semibold">{u.label}</p><p>{occupied.has(u.label) ? "Occupied" : "Vacant"}</p></div>)}
        </div>],
        ["tenants", "Tenants", <div className="space-y-4">
          <Section title={`Current tenants (${data.current_tenants.length})`}><MiniTable testid="current-tenants" rows={data.current_tenants} columns={tenCols} onRowClick={(r) => nav(`/tenants/${r.tenant_id}`)} /></Section>
          <Section title={`Previous tenants (${data.previous_tenants.length})`}><MiniTable testid="previous-tenants" rows={data.previous_tenants} columns={tenCols} onRowClick={(r) => nav(`/tenants/${r.tenant_id}`)} /></Section>
        </div>],
        ["agreements", "Agreements", <MiniTable testid="property-agreements" rows={data.agreements} columns={agrCols} onRowClick={(r) => nav(`/agreements/${r.id}`)} />],
        ["payments", "Payments", <MiniTable testid="property-payments" rows={data.payments} columns={payCols} />],
        ["complaints", "Complaints & Leaving", <div className="space-y-4">
          <MiniTable rows={data.complaints} columns={[{ key: "id", label: "ID" }, { key: "subject", label: "Subject" }, { key: "tenant_name", label: "Tenant" }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }]} />
          <MiniTable rows={data.leaving} columns={[{ key: "id", label: "Request" }, { key: "tenant_name", label: "Tenant" }, { key: "requested_leave_date", label: "Leave date", render: (r) => fmtDate(r.requested_leave_date) }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }]} />
        </div>],
        ["activity", "Activity", <ActivityPanel record={p} activity={data.activity} />],
      ]} />
    </div>
  );
}
