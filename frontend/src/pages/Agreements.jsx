import { useNavigate } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { fmtDate, inr, dispId } from "../lib/api";

export const AGR_CATS = ["Flat Rent Agreement (Marathi)", "Independent House Rent Agreement (English)", "Boys PG Terms & Conditions (Marathi)", "Girls PG Terms & Conditions (Marathi)", "Commercial Rent Agreement"];
const STATUSES = ["draft", "pending_signature", "completed", "cancelled", "expired", "archived"];
const esignBadge = (s) => <StatusBadge value={s === "signed" ? "completed" : s === "initiated" ? "in_progress" : s || "pending"} />;

export function AgreementsList() {
  const nav = useNavigate();
  return (
    <div>
      <PageHeader title="Agreements" subtitle="Completed only after Aadhaar e-Sign by both owner and tenant" />
      <DataTable entity="agreements" onRowClick={(r) => nav(`/agreements/${r.id}`)}
        filters={[{ key: "status", label: "Status", options: STATUSES }, { key: "category", label: "Category", options: AGR_CATS }]}
        columns={[{ key: "id", label: "Agreement No.", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{dispId(r)}</span> }, { key: "category", label: "Category" },
          { key: "owner_name", label: "Owner", sortable: false }, { key: "tenant_name", label: "Tenant", sortable: false }, { key: "property_name", label: "Property", sortable: false },
          { key: "fee", label: "Fee", render: (r) => r.discount ? `${inr(r.fee)} (−${inr(r.discount)})` : inr(r.fee) },
          { key: "fee_paid", label: "Paid", render: (r) => <StatusBadge value={r.fee_paid ? "success" : "pending"} /> },
          { key: "owner_esign", label: "Owner e-Sign", sortable: false, render: (r) => esignBadge(r.owner_esign) },
          { key: "tenant_esign", label: "Tenant e-Sign", sortable: false, render: (r) => esignBadge(r.tenant_esign) },
          { key: "current_version", label: "Ver.", render: (r) => `v${r.current_version}` }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> },
          { key: "created_at", label: "Created", render: (r) => fmtDate(r.created_at) }]} />
    </div>
  );
}
