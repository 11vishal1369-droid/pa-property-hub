import { useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Power, ListChecks, BadgeCheck } from "lucide-react";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { DataTable } from "../components/DataTable";
import { PageHeader, MiniTable } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, errMsg, fmtDate, inr, label } from "../lib/api";

const ELIG = [{ value: "all_owners", label: "All Owners" }, { value: "selected_owner", label: "Selected Owner" }, { value: "selected_owners", label: "Multiple Selected Owners" },
  { value: "all_tenants", label: "All Tenants" }, { value: "selected_tenant", label: "Selected Tenant" }, { value: "selected_tenants", label: "Multiple Selected Tenants" },
  { value: "both", label: "Both Owners and Tenants" }];
const FIELDS = [{ name: "description", label: "Description", full: true }, { name: "discount_type", label: "Discount type", type: "select", options: ["percent", "fixed"], required: true },
  { name: "value", label: "Value", type: "number", required: true }, { name: "max_discount", label: "Max discount (₹)", type: "number" }, { name: "min_amount", label: "Min amount (₹)", type: "number" },
  { name: "start_date", label: "Start date", type: "date", required: true }, { name: "end_date", label: "End date", type: "date", required: true },
  { name: "max_usage", label: "Max total usage", type: "number", required: true }, { name: "per_owner_limit", label: "Per-owner limit", type: "number", required: true },
  { name: "applies_to", label: "Applies to", type: "select", options: ["agreement_fee", "platform_fee", "both"], required: true },
  { name: "eligibility", label: "Eligible users", type: "select", required: true, options: ELIG },
  { name: "eligible_ids", label: "Select users", type: "users", userType: (v) => (v.eligibility || "").includes("tenant") ? "tenant" : "owner",
    single: (v) => ["selected_owner", "selected_tenant"].includes(v.eligibility), show: (v) => (v.eligibility || "").startsWith("selected") }];
const eligLabel = (r) => (ELIG.find((e) => e.value === r.eligibility)?.label || "All Owners") + (r.eligible_ids?.length ? ` (${r.eligible_ids.length})` : "");

export default function Coupons() {
  const { can } = useAuth();
  const [key, setKey] = useState(0);
  const [usage, setUsage] = useState(null);
  const [dialog, open] = useDialog();
  const edit = can("coupons", "edit");
  const done = (m) => { toast.success(m); setKey((k) => k + 1); };
  const clean = (v) => ({ ...v, max_discount: v.max_discount === "" || v.max_discount == null ? null : v.max_discount,
    eligible_ids: (v.eligibility || "").startsWith("selected") ? v.eligible_ids || [] : [] });

  const create = () => open({ title: "Create coupon", wide: true, initial: { discount_type: "percent", applies_to: "both", min_amount: 0, max_usage: 100, per_owner_limit: 1, eligibility: "all_owners", eligible_ids: [] },
    fields: [{ name: "code", label: "Code", required: true }, ...FIELDS],
    onSubmit: async (v, reason) => { await api.post("/coupons", { ...clean(v), reason }); done("Coupon created"); } });
  const editC = (c) => open({ title: `Edit ${c.code}`, wide: true, initial: Object.fromEntries(FIELDS.map((f) => [f.name, c[f.name]])), fields: FIELDS,
    onSubmit: async (v, reason) => { await api.patch(`/data/coupons/${c.id}`, { changes: clean(v), reason }); done("Coupon updated"); } });
  const toggle = (c) => open({ title: `${c.status === "active" ? "Deactivate" : "Activate"} ${c.code}`, danger: c.status === "active",
    onSubmit: async (_, reason) => { await api.post(`/data/coupons/${c.id}/status`, { status: c.status === "active" ? "inactive" : "active", reason }); done("Coupon status updated"); } });
  const validate = () => open({ title: "Test coupon (backend validation)", requireReason: false, confirmLabel: "Validate", initial: { fee_type: "agreement_fee", amount: 99 },
    fields: [{ name: "code", label: "Code", required: true }, { name: "amount", label: "Amount (₹)", type: "number", required: true },
      { name: "fee_type", label: "Fee type", type: "select", options: ["agreement_fee", "platform_fee"], required: true },
      { name: "user_type", label: "User type (optional)", type: "select", options: ["owner", "tenant"] }, { name: "user_id", label: "User ID (optional)" }],
    onSubmit: async (v) => {
      const { data } = await api.post("/coupons/validate", { ...v, user_type: v.user_type || null, user_id: v.user_id || null });
      data.valid ? toast.success(`Valid: discount ${inr(data.discount)}, payable ${inr(data.final_amount)}`) : toast.error(data.message);
    } });
  const showUsage = async (c) => { try { const { data } = await api.get(`/coupons/${c.id}/usage`); setUsage({ c, rows: data }); } catch (e) { toast.error(await errMsg(e)); } };

  return (
    <div>
      {dialog}
      <PageHeader title="Coupon Management" subtitle="Discounts on agreement and platform fees, validated by the backend">
        <Button variant="outline" onClick={validate} data-testid="validate-coupon-button"><BadgeCheck className="mr-1.5 h-4 w-4" />Test coupon</Button>
        {edit && <Button onClick={create} className="bg-[#EA580C] hover:bg-[#c2410c]" data-testid="create-coupon-button"><Plus className="mr-1.5 h-4 w-4" />New coupon</Button>}
      </PageHeader>
      <DataTable entity="coupons" refreshKey={key} filters={[{ key: "status", label: "Status", options: ["active", "inactive"] }, { key: "applies_to", label: "Applies", options: ["agreement_fee", "platform_fee", "both"] },
        { key: "eligibility", label: "Eligible", options: ELIG }]}
        columns={[{ key: "code", label: "Code", render: (r) => <span className="tabular rounded bg-orange-50 px-2 py-0.5 text-xs font-semibold text-orange-700">{r.code}</span> },
          { key: "discount_type", label: "Type", render: (r) => label(r.discount_type) }, { key: "value", label: "Value", render: (r) => r.discount_type === "percent" ? `${r.value}%` : inr(r.value) },
          { key: "max_discount", label: "Max disc.", render: (r) => r.max_discount ? inr(r.max_discount) : "—" }, { key: "min_amount", label: "Min amt", render: (r) => inr(r.min_amount) },
          { key: "applies_to", label: "Applies to", render: (r) => label(r.applies_to) }, { key: "eligibility", label: "Eligible", render: eligLabel }, { key: "start_date", label: "Valid", render: (r) => `${fmtDate(r.start_date)} → ${fmtDate(r.end_date)}` },
          { key: "used_count", label: "Used", render: (r) => `${r.used_count}/${r.max_usage}` }, { key: "per_owner_limit", label: "Per owner" },
          { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }]}
        rowActions={(r) => (
          <div className="flex justify-end gap-1">
            <Button size="icon" variant="ghost" className="h-7 w-7" title="Usage" onClick={() => showUsage(r)} data-testid={`coupon-usage-${r.id}`}><ListChecks className="h-4 w-4" /></Button>
            {edit && <Button size="icon" variant="ghost" className="h-7 w-7" title="Edit" onClick={() => editC(r)} data-testid={`edit-coupon-${r.id}`}><Pencil className="h-4 w-4" /></Button>}
            {edit && <Button size="icon" variant="ghost" className="h-7 w-7" title="Toggle" onClick={() => toggle(r)} data-testid={`toggle-coupon-${r.id}`}><Power className="h-4 w-4" /></Button>}
          </div>
        )} />
      <Dialog open={!!usage} onOpenChange={(o) => !o && setUsage(null)}>
        <DialogContent className="max-w-2xl" data-testid="coupon-usage-dialog">
          <DialogHeader><DialogTitle>Usage history · {usage?.c.code}</DialogTitle></DialogHeader>
          <MiniTable rows={usage?.rows || []} columns={[{ key: "owner_name", label: "Owner" }, { key: "payment_id", label: "Payment" }, { key: "discount", label: "Discount", render: (r) => inr(r.discount) }, { key: "created_at", label: "Date", render: (r) => fmtDate(r.created_at) }]} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
