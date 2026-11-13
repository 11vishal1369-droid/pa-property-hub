import { useNavigate, useSearchParams } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { PageHeader, Avatar } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { fmtDate, inr, dispId } from "../lib/api";

const STD = ["active", "blocked", "suspended", "deactivated", "archived"];
export const PROP_TYPES = ["PG", "Flat", "Apartment", "Independent House", "Office", "Chawl", "Shop", "Godown", "Shed", "Warehouse", "Open Space", "Other"];
const nameCell = (r) => <div className="flex items-center gap-2.5"><Avatar name={r.name} src={r.photo} size="h-7 w-7" /><span className="font-medium text-slate-900">{r.name}</span></div>;
const idCell = (r) => <span className="tabular text-xs text-[#1E3A8A]">{dispId(r)}</span>;
const useInitialFilter = () => {
  const [sp] = useSearchParams();
  return sp.get("status") ? { status: sp.get("status") } : {};
};

export function OwnersList() {
  const nav = useNavigate();
  const init = useInitialFilter();
  return (
    <div>
      <PageHeader title="Owners" subtitle="All registered property owners with subscriptions and fees" />
      <DataTable entity="owners" baseParams={init} onRowClick={(r) => nav(`/owners/${r.id}`)}
        filters={[{ key: "status", label: "Status", options: STD }, { key: "gender", label: "Gender", options: ["Male", "Female"] },
          { key: "subscription_status", label: "Subscription", options: ["active", "expired", "pending", "none"] }]}
        columns={[{ key: "id", label: "Owner ID", render: idCell }, { key: "name", label: "Name", render: nameCell }, { key: "gender", label: "Gender" },
          { key: "dob", label: "DOB", render: (r) => fmtDate(r.dob) }, { key: "mobile", label: "Mobile" }, { key: "email", label: "Email" },
          { key: "created_at", label: "Registered", render: (r) => fmtDate(r.created_at) }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> },
          { key: "property_count", label: "Props (act/arch)", sortable: false, render: (r) => `${r.property_count} (${r.active_property_count}/${r.archived_property_count})` },
          { key: "tenant_count", label: "Tenants", sortable: false }, { key: "agreement_count", label: "Agreements", sortable: false },
          { key: "subscription_status", label: "Subscription", render: (r) => <StatusBadge value={r.subscription_status} /> },
          { key: "subscription_expiry", label: "Expiry", render: (r) => fmtDate(r.subscription_expiry) },
          { key: "fees_paid", label: "Fees paid", sortable: false, render: (r) => inr(r.fees_paid) },
          { key: "outstanding", label: "Outstanding", sortable: false, render: (r) => inr(r.outstanding) }]} />
    </div>
  );
}

export function TenantsList() {
  const nav = useNavigate();
  const init = useInitialFilter();
  return (
    <div>
      <PageHeader title="Tenants" subtitle="Tenant directory across all properties. Aadhaar is masked." />
      <DataTable entity="tenants" baseParams={init} onRowClick={(r) => nav(`/tenants/${r.id}`)}
        filters={[{ key: "status", label: "Status", options: STD }, { key: "gender", label: "Gender", options: ["Male", "Female"] },
          { key: "aadhaar_status", label: "Aadhaar", options: ["verified", "pending", "failed"] }]}
        columns={[{ key: "id", label: "Tenant ID", render: idCell }, { key: "name", label: "Name", render: nameCell }, { key: "gender", label: "Gender" },
          { key: "mobile", label: "Mobile" }, { key: "property_name", label: "Property", sortable: false }, { key: "owner_name", label: "Owner", sortable: false },
          { key: "rental_code", label: "Rental ID", render: (r) => <span className="tabular text-xs">{r.rental_code || "—"}</span> }, { key: "room", label: "Room/Bed" }, { key: "join_date", label: "Joined", render: (r) => fmtDate(r.join_date) },
          { key: "leave_date", label: "Left", render: (r) => fmtDate(r.leave_date) }, { key: "rent", label: "Rent", render: (r) => inr(r.rent) },
          { key: "deposit", label: "Deposit", render: (r) => inr(r.deposit) }, { key: "agreement_status", label: "Agreement", render: (r) => r.agreement_status ? <StatusBadge value={r.agreement_status} /> : "—" },
          { key: "aadhaar_masked", label: "Aadhaar", sortable: false, render: (r) => r.aadhaar_masked ? <span className="tabular text-xs">{r.aadhaar_masked}</span> : <span className="text-xs text-slate-400">Not provided</span> },
          { key: "aadhaar_status", label: "Aadhaar status", render: (r) => <StatusBadge value={r.aadhaar_status} /> },
          { key: "status", label: "Account", render: (r) => <StatusBadge value={r.status} /> }]} />
    </div>
  );
}

export function PropertiesList() {
  const nav = useNavigate();
  const init = useInitialFilter();
  return (
    <div>
      <PageHeader title="Properties" subtitle="PG, residential and commercial listings" />
      <DataTable entity="properties" baseParams={init} onRowClick={(r) => nav(`/properties/${r.id}`)}
        filters={[{ key: "status", label: "Status", options: ["active", "inactive", "blocked", "deactivated", "closed", "archived"] },
          { key: "category", label: "Category", options: ["PG", "Residential", "Commercial"] }, { key: "type", label: "Type", options: PROP_TYPES }]}
        columns={[{ key: "id", label: "Property ID", render: idCell },
          { key: "name", label: "Property", render: (r) => <div className="flex items-center gap-2.5">{r.photos?.[0] && <img src={r.photos[0]} alt="" className="h-8 w-11 rounded object-cover" />}<span className="font-medium text-slate-900">{r.name}</span></div> },
          { key: "owner_name", label: "Owner", sortable: false }, { key: "category", label: "Category" }, { key: "type", label: "Type" },
          { key: "address", label: "Address" }, { key: "city", label: "City" }, { key: "occupancy", label: "Occupancy", sortable: false },
          { key: "rent", label: "Rent", render: (r) => inr(r.rent) }, { key: "deposit", label: "Deposit", render: (r) => inr(r.deposit) },
          { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }]} />
    </div>
  );
}
