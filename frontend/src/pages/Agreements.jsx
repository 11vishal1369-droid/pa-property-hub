import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, XCircle, FilePlus2, FileText, Download } from "lucide-react";
import { Button } from "../components/ui/button";
import { DataTable } from "../components/DataTable";
import { PageHeader, KV, MiniTable, Section, Timeline } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { RecordControls } from "../components/RecordControls";
import { useDialog } from "../components/FormDialog";
import { useProfile, BackButton, ProfileTabs, ActivityPanel } from "../components/Profile";
import { useAuth } from "../context/AuthContext";
import { api, download, errMsg, fmtDate, fmtDateTime, inr } from "../lib/api";
import { payCols } from "./OwnerDetail";

export const AGR_CATS = ["Flat Rent Agreement (Marathi)", "Independent House Rent Agreement (English)", "Boys PG Terms & Conditions (Marathi)", "Girls PG Terms & Conditions (Marathi)", "Commercial Rent Agreement"];
const STATUSES = ["draft", "pending_verification", "verified", "rejected", "completed", "expired", "archived"];

export function AgreementsList() {
  const nav = useNavigate();
  return (
    <div>
      <PageHeader title="Agreements" subtitle="All rent agreements and PG terms with versions and verification" />
      <DataTable entity="agreements" onRowClick={(r) => nav(`/agreements/${r.id}`)}
        filters={[{ key: "status", label: "Status", options: STATUSES }, { key: "category", label: "Category", options: AGR_CATS }]}
        columns={[{ key: "id", label: "Agreement ID", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{r.id}</span> }, { key: "category", label: "Category" },
          { key: "owner_name", label: "Owner", sortable: false }, { key: "tenant_name", label: "Tenant", sortable: false }, { key: "property_name", label: "Property", sortable: false },
          { key: "fee", label: "Fee", render: (r) => inr(r.fee) }, { key: "discount", label: "Discount", render: (r) => r.discount ? `${inr(r.discount)} (${r.coupon_code})` : "—" },
          { key: "fee_paid", label: "Paid", render: (r) => <StatusBadge value={r.fee_paid ? "success" : "pending"} /> },
          { key: "current_version", label: "Ver.", render: (r) => `v${r.current_version}` }, { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> },
          { key: "created_at", label: "Created", render: (r) => fmtDate(r.created_at) }]} />
    </div>
  );
}

const path = (id) => `/agreements/${id}/detail`;
const EDIT = [{ name: "start_date", label: "Start date", type: "date" }, { name: "end_date", label: "End date", type: "date" }, { name: "rent", label: "Rent", type: "number" }, { name: "deposit", label: "Deposit", type: "number" }];

export function AgreementDetail() {
  const nav = useNavigate();
  const { can } = useAuth();
  const { data, err, load } = useProfile(path);
  const [dialog, open] = useDialog();
  if (err) return <p className="text-red-600" data-testid="profile-error">{err}</p>;
  if (!data) return <p className="text-slate-400">Loading…</p>;
  const a = data.agreement;
  const pdf = (v, dl) => {
    const p = `/agreements/${a.id}/pdf`;
    (dl ? download(p, { version: v }) : api.get(p, { params: { version: v }, responseType: "blob" }).then((r) => window.open(URL.createObjectURL(new Blob([r.data], { type: "application/pdf" })), "_blank")))
      .catch(async (e) => toast.error(await errMsg(e)));
  };
  const verify = (decision) => open({ title: decision === "verified" ? "Verify agreement" : "Reject agreement", danger: decision === "rejected", confirmLabel: decision === "verified" ? "Verify" : "Reject",
    onSubmit: async (_, reason) => { await api.post(`/agreements/${a.id}/verify`, { decision, reason }); toast.success(`Agreement ${decision}`); load(); } });
  const newVersion = () => open({ title: "Create new version", description: "Previous versions are preserved and never overwritten.", wide: true,
    initial: { content: a.versions[a.versions.length - 1].content }, fields: [{ name: "content", label: "Agreement content", type: "textarea", rows: 10, required: true }],
    onSubmit: async (v, reason) => { await api.post(`/agreements/${a.id}/versions`, { content: v.content, reason }); toast.success("New version saved"); load(); } });
  const canVerify = can("agreements", "edit") && ["pending_verification", "draft", "rejected"].includes(a.status);
  return (
    <div data-testid="agreement-detail">
      {dialog}
      <BackButton />
      <PageHeader title={a.id} subtitle={<span className="flex items-center gap-2">{a.category} <StatusBadge value={a.status} testid="agreement-status" /></span>}>
        {canVerify && <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => verify("verified")} data-testid="verify-agreement-button"><CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />Verify</Button>}
        {canVerify && a.status !== "rejected" && <Button size="sm" variant="outline" className="border-red-200 text-red-600" onClick={() => verify("rejected")} data-testid="reject-agreement-button"><XCircle className="mr-1.5 h-3.5 w-3.5" />Reject</Button>}
        {can("agreements", "edit") && <Button size="sm" variant="outline" onClick={newVersion} data-testid="new-version-button"><FilePlus2 className="mr-1.5 h-3.5 w-3.5" />New version</Button>}
        <RecordControls entity="agreements" module="agreements" record={a} statuses={STATUSES} editFields={EDIT} onDone={load} />
      </PageHeader>
      <ProfileTabs tabs={[
        ["overview", "Overview", <div className="space-y-4">
          <Section title="Parties & terms"><KV items={[["Owner", <button className="text-[#1E3A8A] hover:underline" onClick={() => nav(`/owners/${a.owner_id}`)}>{a.owner_name}</button>],
            ["Tenant", <button className="text-[#1E3A8A] hover:underline" onClick={() => nav(`/tenants/${a.tenant_id}`)}>{a.tenant_name}</button>],
            ["Property", <button className="text-[#1E3A8A] hover:underline" onClick={() => nav(`/properties/${a.property_id}`)}>{a.property_name}</button>],
            ["Term", `${fmtDate(a.start_date)} → ${fmtDate(a.end_date)}`], ["Rent", inr(a.rent)], ["Deposit", inr(a.deposit)]]} /></Section>
          <Section title="Fees & acceptance"><KV items={[["Agreement fee", inr(a.fee)], ["Coupon", a.coupon_code], ["Discount", inr(a.discount)], ["Fee paid", a.fee_paid ? "Yes" : "No"],
            ["Owner accepted", fmtDateTime(a.owner_accepted_at)], ["Tenant accepted", fmtDateTime(a.tenant_accepted_at)],
            ["Verified by", a.verification?.by], ["Verified at", fmtDateTime(a.verification?.at)], ["Verification remarks", a.verification?.remarks]]} /></Section>
        </div>],
        ["versions", `Versions (${a.versions.length})`, <div className="space-y-3" data-testid="agreement-versions">
          {[...a.versions].reverse().map((v) => (
            <div key={v.version} className="pa-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2"><span className="rounded bg-[#1E3A8A] px-2 py-0.5 text-xs font-semibold text-white">v{v.version}</span>
                  {v.version === a.current_version && <span className="text-xs font-semibold text-orange-600">Current</span>}
                  <span className="text-xs text-slate-500">{fmtDateTime(v.created_at)} · {v.created_by}</span></div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => pdf(v.version)} data-testid={`view-pdf-v${v.version}`}><FileText className="mr-1.5 h-3.5 w-3.5" />View PDF</Button>
                  <Button size="sm" variant="outline" onClick={() => pdf(v.version, true)} data-testid={`download-pdf-v${v.version}`}><Download className="mr-1.5 h-3.5 w-3.5" />Download</Button>
                </div>
              </div>
              {v.reason && <p className="mt-2 text-xs text-slate-500">Reason: {v.reason}</p>}
              <p className="mt-2 line-clamp-3 text-sm text-slate-600">{v.content}</p>
            </div>
          ))}
        </div>],
        ["verification", "Verification history", <Section title="Verification decisions"><Timeline items={(a.verification_history || []).map((v) => ({ at: v.at, by: v.by, new: v.decision, reason: v.remarks }))} /></Section>],
        ["payments", "Payments", <MiniTable rows={data.payments} columns={payCols} />],
        ["activity", "Activity", <ActivityPanel record={a} activity={data.activity} />],
      ]} />
    </div>
  );
}
