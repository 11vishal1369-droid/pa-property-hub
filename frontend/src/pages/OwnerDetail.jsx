import { useNavigate } from "react-router-dom";
import { PageHeader, KV, MiniTable, Section, Avatar } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { RecordControls } from "../components/RecordControls";
import { useProfile, BackButton, ProfileTabs, ActivityPanel } from "../components/Profile";
import { fmtDate, fmtDateTime, inr, label } from "../lib/api";

const path = (id) => `/owners/${id}/profile`;
const EDIT = [["name", "Name"], ["gender", "Gender", "select", ["Male", "Female", "Other"]], ["dob", "Date of birth", "date"], ["mobile", "Mobile"],
  ["email", "Email", "email"], ["city", "City"], ["address", "Address", "textarea"], ["photo", "Photo URL"]].map(([name, l, type, options]) => ({ name, label: l, type, options }));

export const payCols = [{ key: "id", label: "Payment" }, { key: "purpose", label: "Purpose", render: (r) => label(r.purpose) }, { key: "amount", label: "Amount", render: (r) => inr(r.amount) },
  { key: "discount", label: "Discount", render: (r) => inr(r.discount) }, { key: "method", label: "Method", render: (r) => label(r.method) },
  { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Date", render: (r) => fmtDate(r.created_at) }];
export const agrCols = [{ key: "id", label: "Agreement" }, { key: "category", label: "Category" }, { key: "tenant_name", label: "Tenant" },
  { key: "property_name", label: "Property" }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "created_at", label: "Created", render: (r) => fmtDate(r.created_at) }];

export default function OwnerDetail() {
  const nav = useNavigate();
  const { data, err, load } = useProfile(path);
  if (err) return <p className="text-red-600" data-testid="profile-error">{err}</p>;
  if (!data) return <p className="text-slate-400">Loading…</p>;
  const o = data.owner;
  const sub = data.subscriptions[0];
  return (
    <div data-testid="owner-profile">
      <BackButton />
      <PageHeader title={<span className="flex items-center gap-3"><Avatar name={o.name} src={o.photo} size="h-11 w-11" />{o.name}</span>}
        subtitle={<span className="flex items-center gap-2"><span className="tabular">{o.id}</span> · Registered {fmtDate(o.created_at)} <StatusBadge value={o.status} testid="owner-status" /></span>}>
        <RecordControls entity="owners" module="owners" record={o} statuses={["active", "blocked", "suspended", "deactivated"]} editFields={EDIT} onDone={load} />
      </PageHeader>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[["Properties", o.property_count], ["Tenants", o.tenant_count], ["Agreements", o.agreement_count], ["Fees paid", inr(o.fees_paid)], ["Outstanding", inr(o.outstanding)]].map(([k, v]) => (
          <div key={k} className="pa-card p-4"><p className="th">{k}</p><p className="tabular mt-1 text-xl font-semibold">{v}</p></div>
        ))}
      </div>
      <ProfileTabs tabs={[
        ["personal", "Personal", <Section title="Personal details"><KV items={[["Owner ID", o.id], ["Name", o.name], ["Gender", o.gender], ["Date of birth", fmtDate(o.dob)],
          ["Mobile", o.mobile], ["Email", o.email], ["City", o.city], ["Address", o.address], ["Registered", fmtDateTime(o.created_at)],
          ["Archive reason", o.archive_reason]]} /></Section>],
        ["properties", `Properties (${data.properties.length})`, <MiniTable testid="owner-properties" rows={data.properties} onRowClick={(r) => nav(`/properties/${r.id}`)}
          columns={[{ key: "id", label: "ID" }, { key: "name", label: "Name" }, { key: "category", label: "Category" }, { key: "type", label: "Type" },
            { key: "occupancy", label: "Occupancy" }, { key: "rent", label: "Rent", render: (r) => inr(r.rent) }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }]} />],
        ["financial", "Financial", <div className="space-y-4">
          <Section title="Subscription"><KV items={[["Status", <StatusBadge value={o.subscription_status} />], ["Start", fmtDate(o.subscription_start)], ["Expiry", fmtDate(o.subscription_expiry)],
            ["Plan", sub?.plan], ["Amount", inr(sub?.amount)], ["Coupon uses", data.coupon_usage.length]]} /></Section>
          <MiniTable testid="owner-payments" rows={data.payments.filter((p) => p.purpose !== "rent")} columns={payCols} />
        </div>],
        ["agreements", `Agreements (${data.agreements.length})`, <MiniTable testid="owner-agreements" rows={data.agreements} columns={agrCols} onRowClick={(r) => nav(`/agreements/${r.id}`)} />],
        ["activity", "Activity", <ActivityPanel record={o} activity={data.activity} />],
      ]} />
    </div>
  );
}
