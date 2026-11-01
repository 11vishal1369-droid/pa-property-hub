import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { PageHeader, Section } from "../components/Common";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, errMsg, fmtDateTime } from "../lib/api";

const Num = ({ l, v, on, id, disabled }) => (
  <div className="space-y-1.5"><Label className="text-xs text-slate-600">{l}</Label>
    <Input type="number" value={v ?? ""} disabled={disabled} onChange={(e) => on(e.target.value === "" ? "" : Number(e.target.value))} data-testid={`setting-${id}`} /></div>
);
const Txt = ({ l, v, on, id, disabled, type = "text" }) => (
  <div className="space-y-1.5"><Label className="text-xs text-slate-600">{l}</Label><Input type={type} value={v ?? ""} disabled={disabled} onChange={(e) => on(e.target.value)} data-testid={`setting-${id}`} /></div>
);
const Tog = ({ l, v, on, id, disabled }) => (
  <label className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm"><span>{l}</span><Switch checked={!!v} disabled={disabled} onCheckedChange={on} data-testid={`setting-${id}`} /></label>
);

export function PasswordCard() {
  const [f, setF] = useState({ current_password: "", new_password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (f.new_password !== f.confirm) return toast.error("New passwords do not match");
    setBusy(true);
    try { await api.post("/auth/change-password", { current_password: f.current_password, new_password: f.new_password }); toast.success("Password changed"); setF({ current_password: "", new_password: "", confirm: "" }); }
    catch (e2) { toast.error(await errMsg(e2)); } finally { setBusy(false); }
  };
  return (
    <Section title="Change your admin password">
      <form onSubmit={submit} className="grid max-w-md gap-3" data-testid="change-password-form">
        {[["current_password", "Current password"], ["new_password", "New password (min 8 characters)"], ["confirm", "Confirm new password"]].map(([k, l]) => (
          <div key={k} className="space-y-1.5"><Label className="text-xs text-slate-600">{l}</Label>
            <Input type="password" required value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`password-${k}-input`} /></div>
        ))}
        <Button type="submit" disabled={busy} className="w-fit bg-[#1E3A8A]" data-testid="change-password-submit">{busy ? "Saving…" : "Update password"}</Button>
      </form>
    </Section>
  );
}

export default function SettingsPage() {
  const { can } = useAuth();
  const [sp] = useSearchParams();
  const [tab, setTab] = useState(sp.get("tab") || "fees");
  const [s, setS] = useState(null);
  const [secret, setSecret] = useState("");
  const [hist, setHist] = useState([]);
  const [dialog, open] = useDialog();
  const ro = !can("settings", "edit");
  const load = () => { api.get("/settings").then((r) => setS(r.data)); api.get("/settings/history").then((r) => setHist(r.data)); };
  useEffect(load, []);
  const set = (k, v) => setS((x) => ({ ...x, [k]: v }));
  const setIn = (k, sub, v) => setS((x) => ({ ...x, [k]: { ...x[k], [sub]: v } }));
  const save = () => open({ title: "Save platform settings", description: "Previous settings are versioned in settings history.",
    onSubmit: async (_, reason) => {
      const { key, version, updated_at, updated_by, ...rest } = s;
      await api.put("/settings", { settings: rest, reason, gateway_secret: secret || null }); setSecret(""); toast.success("Settings saved"); load();
    } });
  if (!s) return <p className="text-slate-400">Loading…</p>;
  return (
    <div>
      {dialog}
      <PageHeader title="Settings" subtitle={`Version ${s.version} · last updated ${fmtDateTime(s.updated_at)}${s.updated_by ? ` by ${s.updated_by}` : ""}`}>
        {!ro && ["fees", "renewal", "gateway", "tax"].includes(tab) && <Button onClick={save} className="bg-[#EA580C] hover:bg-[#c2410c]" data-testid="save-settings-button">Save settings</Button>}
      </PageHeader>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="h-auto flex-wrap bg-white shadow-sm ring-1 ring-slate-200">
          {[["fees", "Fees"], ["renewal", "Renewal & coupons"], ["gateway", "Payment gateway"], ["tax", "Tax & legal"], ["password", "Change password"], ["history", "History"]].map(([k, l]) =>
            <TabsTrigger key={k} value={k} data-testid={`settings-tab-${k}`}>{l}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="fees" className="mt-4 space-y-4">
          <Section title="Owner platform fee"><div className="grid gap-3 sm:grid-cols-3">
            <Num l="Platform fee (₹)" id="owner-platform-fee" v={s.owner_platform_fee} on={(v) => set("owner_platform_fee", v)} disabled={ro} />
            <Num l="Validity (days)" id="platform-validity-days" v={s.platform_validity_days} on={(v) => set("platform_validity_days", v)} disabled={ro} />
            <Num l="Default agreement fee (₹)" id="agreement-fee-default" v={s.agreement_fee_default} on={(v) => set("agreement_fee_default", v)} disabled={ro} /></div></Section>
          <Section title="Agreement fee per category"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(s.agreement_fees).map(([k, v]) => <Num key={k} l={k} id={`agreement-fee-${k.slice(0, 10).replace(/\W/g, "")}`} v={v} on={(x) => setIn("agreement_fees", k, x)} disabled={ro} />)}</div></Section>
          <Section title="Tenant fees"><div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(s.tenant_fees).map(([k, v]) => <Num key={k} l={`Tenant ${k} fee (₹)`} id={`tenant-fee-${k}`} v={v} on={(x) => setIn("tenant_fees", k, x)} disabled={ro} />)}</div></Section>
        </TabsContent>
        <TabsContent value="renewal" className="mt-4 grid gap-4 lg:grid-cols-2">
          <Section title="Renewal rules"><div className="grid gap-3">
            <Num l="Grace period (days)" id="grace-days" v={s.renewal.grace_days} on={(v) => setIn("renewal", "grace_days", v)} disabled={ro} />
            <Num l="Reminder before expiry (days)" id="reminder-days" v={s.renewal.reminder_days_before} on={(v) => setIn("renewal", "reminder_days_before", v)} disabled={ro} />
            <Tog l="Auto-block properties on expiry" id="auto-block" v={s.renewal.auto_block_on_expiry} on={(v) => setIn("renewal", "auto_block_on_expiry", v)} disabled={ro} /></div></Section>
          <Section title="Coupon applicability"><div className="grid gap-3">
            <Tog l="Coupons allowed on agreement fee" id="coupon-agreement" v={s.coupon_applicability.agreement_fee} on={(v) => setIn("coupon_applicability", "agreement_fee", v)} disabled={ro} />
            <Tog l="Coupons allowed on platform fee" id="coupon-platform" v={s.coupon_applicability.platform_fee} on={(v) => setIn("coupon_applicability", "platform_fee", v)} disabled={ro} /></div></Section>
        </TabsContent>
        <TabsContent value="gateway" className="mt-4">
          <Section title="Generic payment gateway"><div className="grid gap-3 sm:grid-cols-2">
            <Txt l="Provider name" id="gw-provider" v={s.gateway.provider_name} on={(v) => setIn("gateway", "provider_name", v)} disabled={ro} />
            <div className="space-y-1.5"><Label className="text-xs text-slate-600">Mode</Label>
              <select disabled={ro} value={s.gateway.mode} onChange={(e) => setIn("gateway", "mode", e.target.value)} className="h-9 w-full rounded-md border border-slate-200 px-2 text-sm" data-testid="setting-gw-mode"><option value="test">Test</option><option value="live">Live</option></select></div>
            <Txt l="Key ID / Public key" id="gw-key" v={s.gateway.key_id} on={(v) => setIn("gateway", "key_id", v)} disabled={ro} />
            <Txt l="Merchant ID" id="gw-merchant" v={s.gateway.merchant_id} on={(v) => setIn("gateway", "merchant_id", v)} disabled={ro} />
            <Txt l={`Secret key ${s.gateway.secret_set ? `(saved: ${s.gateway.secret_masked})` : "(not set)"}`} id="gw-secret" type="password" v={secret} on={setSecret} disabled={ro} />
            <Txt l="Webhook URL" id="gw-webhook" v={s.gateway.webhook_url} on={(v) => setIn("gateway", "webhook_url", v)} disabled={ro} />
            <Tog l="Gateway enabled" id="gw-enabled" v={s.gateway.enabled} on={(v) => setIn("gateway", "enabled", v)} disabled={ro} /></div>
            <p className="mt-3 text-xs text-slate-400">Secrets are encrypted at rest and never displayed again. Payment success is only recorded from confirmed gateway responses.</p></Section>
        </TabsContent>
        <TabsContent value="tax" className="mt-4 grid gap-4 lg:grid-cols-2">
          <Section title="Tax"><div className="grid gap-3">
            <Tog l="GST enabled" id="gst-enabled" v={s.tax.gst_enabled} on={(v) => setIn("tax", "gst_enabled", v)} disabled={ro} />
            <Num l="GST %" id="gst-percent" v={s.tax.gst_percent} on={(v) => setIn("tax", "gst_percent", v)} disabled={ro} />
            <Txt l="GSTIN" id="gstin" v={s.tax.gstin} on={(v) => setIn("tax", "gstin", v)} disabled={ro} /></div></Section>
          <Section title="Stamp duty & registration (separate from service charges)"><div className="grid gap-3">
            <Label className="text-xs text-slate-600">Stamp duty information</Label><Textarea disabled={ro} value={s.stamp_duty_info} onChange={(e) => set("stamp_duty_info", e.target.value)} data-testid="setting-stamp-duty" />
            <Label className="text-xs text-slate-600">Registration information</Label><Textarea disabled={ro} value={s.registration_info} onChange={(e) => set("registration_info", e.target.value)} data-testid="setting-registration" /></div></Section>
        </TabsContent>
        <TabsContent value="password" className="mt-4"><PasswordCard /></TabsContent>
        <TabsContent value="history" className="mt-4">
          <Section title="Previous versions"><ul className="divide-y divide-slate-100 text-sm" data-testid="settings-history">
            {hist.map((h, i) => <li key={i} className="flex flex-wrap gap-3 py-2"><span className="tabular text-xs text-slate-400">v{h.version}</span><span>{fmtDateTime(h.archived_at)}</span><span className="text-slate-500">replaced by {h.replaced_by}</span><span className="text-slate-700">— {h.reason}</span></li>)}
            {!hist.length && <li className="py-2 text-slate-400">No changes yet</li>}</ul></Section>
        </TabsContent>
      </Tabs>
    </div>
  );
}
