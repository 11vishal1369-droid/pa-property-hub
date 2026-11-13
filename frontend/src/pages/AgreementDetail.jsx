import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Send, Download, FilePlus2, ShieldCheck, FileText } from "lucide-react";
import { Button } from "../components/ui/button";
import { PageHeader, KV, MiniTable, Section } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { RecordControls } from "../components/RecordControls";
import { useDialog } from "../components/FormDialog";
import { useProfile, BackButton, ProfileTabs, ActivityPanel } from "../components/Profile";
import { useAuth } from "../context/AuthContext";
import { api, download, errMsg, fmtDate, fmtDateTime, inr, label, dispId } from "../lib/api";
import { payCols } from "./OwnerDetail";

const path = (id) => `/agreements/${id}/detail`;
const EDIT = [{ name: "start_date", label: "Start date", type: "date" }, { name: "end_date", label: "End date", type: "date" }, { name: "rent", label: "Rent", type: "number" }, { name: "deposit", label: "Deposit", type: "number" }];

function PdfViewer({ id, version }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let u;
    api.get(`/agreements/${id}/pdf`, { params: { version }, responseType: "blob" })
      .then((r) => { u = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" })); setUrl(u); })
      .catch(async (e) => toast.error(await errMsg(e)));
    return () => u && URL.revokeObjectURL(u);
  }, [id, version]);
  return url ? <iframe title="Agreement PDF" src={url} className="h-[70vh] w-full rounded-lg border border-slate-200" data-testid="agreement-pdf-frame" /> : <p className="text-slate-400">Loading PDF…</p>;
}

function SignCard({ party, e = {}, canSend, onSend }) {
  return (
    <div className="pa-card p-5" data-testid={`esign-${party}-card`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-heading font-semibold"><ShieldCheck className="h-4 w-4 text-orange-500" />{label(party)} Aadhaar e-Sign</h3>
        <StatusBadge value={e.status === "signed" ? "completed" : e.status === "initiated" ? "in_progress" : e.status || "pending"} testid={`esign-${party}-status`} />
      </div>
      <KV cols={2} items={[["Status", label(e.status || "pending")], ["Signed at", fmtDateTime(e.signed_at)], ["Provider", e.provider], ["Provider reference", e.provider_ref],
        ["Verification result", e.verification_result], ["Signer name (provider)", e.signer_name], ["Request ID", e.request_id], ["Attempts", e.attempts || 0],
        ["Failure reason", e.failure_reason]]} />
      {canSend && e.status !== "signed" && (
        <Button size="sm" variant="outline" className="mt-4" onClick={onSend} data-testid={`esign-${party}-send-button`}><Send className="mr-1.5 h-3.5 w-3.5" />{e.status === "initiated" || e.status === "failed" ? "Resend" : "Send"} e-Sign request</Button>
      )}
    </div>
  );
}

export default function AgreementDetail() {
  const nav = useNavigate();
  const { can } = useAuth();
  const { data, err, load } = useProfile(path);
  const [dialog, open] = useDialog();
  const [evidence, setEvidence] = useState([]);
  const [ver, setVer] = useState(null);
  useEffect(() => { if (data) api.get(`/agreements/${data.agreement.id}/esign/evidence`).then((r) => setEvidence(r.data)).catch(() => {}); }, [data]);
  if (err) return <p className="text-red-600" data-testid="profile-error">{err}</p>;
  if (!data) return <p className="text-slate-400">Loading…</p>;
  const a = data.agreement;
  const o = a.owner || {}, t = a.tenant || {}, p = a.property || {}, pay = a.payment;
  const es = a.esign || {};
  const editable = can("agreements", "edit");
  const send = async (party) => {
    try { const { data: r } = await api.post(`/agreements/${a.id}/esign/initiate`, { party }); toast.success(`e-Sign request sent to ${party} (${r.request_id})`); load(); }
    catch (e) { toast.error(await errMsg(e)); }
  };
  const newVersion = () => open({ title: "Create new version", description: "Only possible before anyone has signed. Previous versions are preserved.", wide: true,
    initial: { content: a.versions[a.versions.length - 1].content }, fields: [{ name: "content", label: "Agreement content", type: "textarea", rows: 10, required: true }],
    onSubmit: async (v, reason) => { await api.post(`/agreements/${a.id}/versions`, { content: v.content, reason }); toast.success("New version saved"); load(); } });
  const dl = (v) => download(`/agreements/${a.id}/pdf`, { version: v }).catch(async (e) => toast.error(await errMsg(e)));
  const link = (to, txt) => <button className="text-[#1E3A8A] hover:underline" onClick={() => nav(to)}>{txt}</button>;
  const unsigned = es.owner?.status !== "signed" && es.tenant?.status !== "signed";
  return (
    <div data-testid="agreement-detail">
      {dialog}
      <BackButton />
      <PageHeader title={`Agreement ${dispId(a)}`} subtitle={<span className="flex items-center gap-2">{a.category} <StatusBadge value={a.status} testid="agreement-status" /></span>}>
        <Button size="sm" variant="outline" onClick={() => dl(a.current_version)} data-testid="download-agreement-button"><Download className="mr-1.5 h-3.5 w-3.5" />Download agreement</Button>
        {editable && unsigned && a.status !== "completed" && <Button size="sm" variant="outline" onClick={newVersion} data-testid="new-version-button"><FilePlus2 className="mr-1.5 h-3.5 w-3.5" />New version</Button>}
        <RecordControls entity="agreements" module="agreements" record={a} statuses={["cancelled", "expired"]} editFields={EDIT} onDone={load} />
      </PageHeader>
      <div className="mb-2 rounded-lg border border-orange-200 bg-orange-50 px-4 py-2.5 text-sm text-orange-800" data-testid="esign-policy-note">
        Completion happens only when both owner and tenant finish Aadhaar e-Sign with the authorised provider. Admins can't approve agreements manually.
      </div>
      <ProfileTabs tabs={[
        ["overview", "Overview", <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Owner details"><KV cols={2} items={[["Owner ID", link(`/owners/${o.id}`, dispId(o))], ["Name", o.name], ["Mobile", o.mobile], ["Email", o.email], ["Address", o.address]]} /></Section>
            <Section title="Tenant details"><KV cols={2} items={[["Tenant ID", link(`/tenants/${t.id}`, dispId(t))], ["Name", t.name], ["Mobile", t.mobile], ["Email", t.email], ["Room/Bed", t.room]]} /></Section>
          </div>
          <Section title="Property & term"><KV items={[["Property ID", link(`/properties/${p.id}`, dispId(p))], ["Property", p.name], ["Property category", p.fee_category],
            ["Address", `${p.address || ""}, ${p.city || ""}`], ["Term", `${fmtDate(a.start_date)} → ${fmtDate(a.end_date)}`], ["Rent / Deposit", `${inr(a.rent)} / ${inr(a.deposit)}`]]} /></Section>
          <Section title="Fee & payment"><KV items={[["Agreement fee", inr(a.fee)], ["Coupon discount", a.discount ? `${inr(a.discount)} (${a.coupon_code})` : inr(0)],
            ["Final amount paid", pay ? inr(pay.total_received) : "Not paid"], ["Base amount", pay && inr(pay.base_amount)], [`GST (${pay?.gst_rate ?? 18}%, inclusive)`, pay && inr(pay.gst_amount)],
            ["Total", pay && inr(pay.total)], ["Payment date", pay && fmtDateTime(pay.created_at)], ["Payment method", pay && label(pay.method)],
            ["Transaction ID", pay?.txn_ref], ["Payment status", pay ? <StatusBadge value={pay.status} testid="agreement-payment-status" /> : "—"]]} /></Section>
        </div>],
        ["esign", "e-Sign", <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {["owner", "tenant"].map((party) => <SignCard key={party} party={party} e={es[party]} canSend={editable && a.status === "pending_signature"} onSend={() => send(party)} />)}
          </div>
          <Section title="Provider evidence (verified callbacks, kept permanently)">
            <MiniTable testid="esign-evidence" rows={evidence} empty="No provider callbacks received yet" columns={[{ key: "received_at", label: "Received", render: (r) => fmtDateTime(r.received_at) },
              { key: "party", label: "Party", render: (r) => label(r.party) }, { key: "status", label: "Result", render: (r) => <StatusBadge value={r.status === "signed" ? "completed" : r.status} /> },
              { key: "request_id", label: "Request" }, { key: "payload_sha256", label: "Payload SHA-256", render: (r) => <span className="tabular text-[10px]">{r.payload_sha256.slice(0, 24)}…</span> }]} />
          </Section>
        </div>],
        ["document", "Agreement PDF", <div className="space-y-3">
          <div className="flex flex-wrap gap-2">{[...a.versions].reverse().map((v) => (
            <Button key={v.version} size="sm" variant={(ver || a.current_version) === v.version ? "default" : "outline"} onClick={() => setVer(v.version)} data-testid={`pdf-version-v${v.version}`}>
              <FileText className="mr-1.5 h-3.5 w-3.5" />v{v.version}{v.version === a.current_version ? " (current)" : ""}</Button>))}
            <Button size="sm" variant="outline" onClick={() => dl(ver || a.current_version)} data-testid="download-pdf-version"><Download className="mr-1.5 h-3.5 w-3.5" />Download</Button>
          </div>
          <PdfViewer id={a.id} version={ver || a.current_version} />
        </div>],
        ["payments", "Payments", <MiniTable rows={data.payments} columns={payCols} />],
        ["activity", "Activity", <ActivityPanel record={a} activity={data.activity} />],
      ]} />
    </div>
  );
}
