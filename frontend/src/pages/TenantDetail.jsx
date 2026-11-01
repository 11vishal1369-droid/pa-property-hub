import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Eye, Lock } from "lucide-react";
import { Button } from "../components/ui/button";
import { PageHeader, KV, MiniTable, Section, Avatar } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { RecordControls } from "../components/RecordControls";
import { useDialog } from "../components/FormDialog";
import { useProfile, BackButton, ProfileTabs, ActivityPanel } from "../components/Profile";
import { useAuth } from "../context/AuthContext";
import { api, fmtDate, inr, label } from "../lib/api";
import { payCols, agrCols } from "./OwnerDetail";

const path = (id) => `/tenants/${id}/profile`;
const EDIT = [["name", "Name"], ["gender", "Gender", "select", ["Male", "Female", "Other"]], ["dob", "Date of birth", "date"], ["mobile", "Mobile"], ["email", "Email", "email"],
  ["father_name", "Father's name"], ["mother_name", "Mother's name"], ["occupation", "Occupation"], ["room", "Room/Bed"], ["rent", "Rent", "number"], ["deposit", "Deposit", "number"],
  ["emergency_contact_name", "Emergency contact"], ["emergency_contact_phone", "Emergency phone"], ["permanent_address", "Permanent address", "textarea"], ["current_address", "Current address", "textarea"]]
  .map(([name, l, type, options]) => ({ name, label: l, type, options }));

function Identity({ t }) {
  const { can } = useAuth();
  const [full, setFull] = useState(null);
  const [dialog, open] = useDialog();
  const reveal = () => open({
    title: "View full Aadhaar", description: "This access will be permanently recorded in the audit log.", confirmLabel: "Reveal",
    onSubmit: async (_, reason) => { const { data } = await api.post(`/tenants/${t.id}/aadhaar/reveal`, { reason }); setFull(data.aadhaar); toast.success("Access logged"); },
  });
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {dialog}
      <Section title="Aadhaar" action={can("aadhaar") ? <Button size="sm" variant="outline" onClick={reveal} data-testid="reveal-aadhaar-button"><Eye className="mr-1.5 h-3.5 w-3.5" />View full</Button>
        : <span className="flex items-center gap-1 text-xs text-slate-400"><Lock className="h-3 w-3" />Restricted</span>}>
        <p className="tabular text-2xl tracking-widest text-slate-900" data-testid="aadhaar-value">{full || t.aadhaar_masked}</p>
        <div className="mt-3 flex items-center gap-2 text-sm text-slate-500">Verification: <StatusBadge value={t.aadhaar_status} /></div>
        <p className="mt-3 text-xs text-slate-400">Stored encrypted at rest. OTPs are never stored. Masked by default.</p>
      </Section>
      <Section title="Documents">
        <ul className="space-y-2">{(t.documents || []).map((d) => <li key={d.name} className="flex justify-between text-sm"><span>{d.name}</span><StatusBadge value={d.status === "uploaded" ? "sent" : d.status} /></li>)}</ul>
        <div className="mt-4 flex h-24 w-24 items-center justify-center rounded-lg border border-dashed border-slate-300 text-xs text-slate-400">{t.selfie ? <img src={t.selfie} alt="selfie" /> : "Selfie on file"}</div>
      </Section>
    </div>
  );
}

export default function TenantDetail() {
  const nav = useNavigate();
  const { data, err, load } = useProfile(path);
  if (err) return <p className="text-red-600" data-testid="profile-error">{err}</p>;
  if (!data) return <p className="text-slate-400">Loading…</p>;
  const t = data.tenant;
  return (
    <div data-testid="tenant-profile">
      <BackButton />
      <PageHeader title={<span className="flex items-center gap-3"><Avatar name={t.name} src={t.photo} size="h-11 w-11" />{t.name}</span>}
        subtitle={<span className="flex items-center gap-2"><span className="tabular">{t.id}</span> · {t.property_name} · Room {t.room} <StatusBadge value={t.status} testid="tenant-status" /></span>}>
        <RecordControls entity="tenants" module="tenants" record={t} statuses={["active", "blocked", "suspended", "deactivated"]} editFields={EDIT} onDone={load} />
      </PageHeader>
      <ProfileTabs tabs={[
        ["personal", "Personal", <Section title="Personal details"><KV items={[["Tenant ID", t.id], ["Name", t.name], ["Gender", t.gender], ["Date of birth", fmtDate(t.dob)],
          ["Mobile", t.mobile], ["Email", t.email], ["Father's name", t.father_name], ["Mother's name", t.mother_name], ["Occupation", t.occupation],
          ["Permanent address", t.permanent_address], ["Current address", t.current_address], ["Emergency contact", `${t.emergency_contact_name || "—"} · ${t.emergency_contact_phone || ""}`],
          ["Owner", t.owner_name], ["Joined", fmtDate(t.join_date)], ["Left", fmtDate(t.leave_date)], ["Rent / Deposit", `${inr(t.rent)} / ${inr(t.deposit)}`]]} /></Section>],
        ["identity", "Identity & Documents", <Identity t={t} />],
        ["history", "Property history", <MiniTable testid="tenant-tenancies" rows={data.tenancies} onRowClick={(r) => nav(`/properties/${r.property_id}`)}
          columns={[{ key: "property_name", label: "Property" }, { key: "owner_name", label: "Owner" }, { key: "room", label: "Room/Bed" }, { key: "join_date", label: "Joined", render: (r) => fmtDate(r.join_date) },
            { key: "leave_date", label: "Left", render: (r) => fmtDate(r.leave_date) }, { key: "rent", label: "Rent", render: (r) => inr(r.rent) }, { key: "active", label: "Current", render: (r) => r.active ? "Yes" : "No" }]} />],
        ["agreements", "Agreements", <MiniTable testid="tenant-agreements" rows={data.agreements} columns={agrCols} onRowClick={(r) => nav(`/agreements/${r.id}`)} />],
        ["ledger", "Financial ledger", <MiniTable testid="tenant-ledger" rows={data.payments} columns={payCols} />],
        ["complaints", "Complaints & Leaving", <div className="space-y-4">
          <MiniTable testid="tenant-complaints" rows={data.complaints} columns={[{ key: "id", label: "ID" }, { key: "subject", label: "Subject" }, { key: "priority", label: "Priority", render: (r) => <StatusBadge value={r.priority} /> },
            { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Date", render: (r) => fmtDate(r.created_at) }]} />
          <MiniTable testid="tenant-leaving" rows={data.leaving} columns={[{ key: "id", label: "Request" }, { key: "requested_leave_date", label: "Leave date", render: (r) => fmtDate(r.requested_leave_date) },
            { key: "reason_text", label: "Reason" }, { key: "refund_amount", label: "Refund", render: (r) => inr(r.refund_amount) }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }]} />
        </div>],
        ["activity", "Activity", <ActivityPanel record={t} activity={data.activity} />],
      ]} />
    </div>
  );
}
