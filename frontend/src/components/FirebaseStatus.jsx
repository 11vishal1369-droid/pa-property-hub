import { useEffect, useState } from "react";
import { RefreshCw, CheckCircle2, AlertTriangle, Radio } from "lucide-react";
import { Button } from "./ui/button";
import { Section } from "./Common";
import { api, fmtDateTime } from "../lib/api";

const Tile = ({ label, value, testid }) => (
  <div className="rounded-md border border-slate-200 p-2 text-xs" data-testid={testid}><p className="text-slate-500">{label}</p><p className="tabular text-base font-semibold">{value}</p></div>
);

export function FirebaseStatus() {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const check = () => { setBusy(true); api.get("/firebase/status").then((r) => setS(r.data)).finally(() => setBusy(false)); };
  useEffect(check, []);
  const sync = s?.sync;
  const live = sync?.running && sync?.initial_load_done;
  return (
    <Section title="Firebase (Firestore) connection" action={<Button size="sm" variant="outline" onClick={check} disabled={busy} data-testid="firebase-check-button"><RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />Check</Button>}>
      {!s ? <p className="text-sm text-slate-400">Checking…</p> : (
        <div className="space-y-4" data-testid="firebase-status">
          <p className={`flex items-center gap-2 text-sm font-medium ${s.connected ? "text-emerald-700" : "text-red-600"}`} data-testid="firebase-status-text">
            {s.connected ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
            {s.connected ? "Connected" : "Not connected"} · project {s.project_id} · checked {fmtDateTime(s.checked_at)}
          </p>
          {s.error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="firebase-error">{s.error}</p>}
          <p className={`flex items-center gap-2 text-sm ${live ? "text-emerald-700" : "text-amber-700"}`} data-testid="firebase-sync-state">
            <Radio className="h-4 w-4" />
            {live ? `Live sync on · last change ${sync.last_event_at ? fmtDateTime(sync.last_event_at) : "—"}` : `Sync starting (${sync?.ready || 0}/${sync?.total_sources || 0} collections loaded)`}
          </p>
          {s.connected && <div><p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">In Firestore</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">{Object.entries(s.collections).map(([k, v]) => <Tile key={k} label={k} value={v} testid={`fs-count-${k}`} />)}</div></div>}
          {s.panel_counts && <div><p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Shown in panel</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">{Object.entries(s.panel_counts).map(([k, v]) => <Tile key={k} label={k} value={v} testid={`panel-count-${k}`} />)}</div></div>}
          {sync?.cutover && <p className="text-xs text-slate-500" data-testid="firebase-cutover">Sample data removed on {fmtDateTime(sync.cutover.at)}. The panel now shows the app's real data.</p>}
          {sync?.errors?.length > 0 && <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800" data-testid="firebase-sync-errors">
            {sync.errors.slice(-3).map((e, i) => <p key={i}>{fmtDateTime(e.at)} · {e.collection}: {e.error}</p>)}</div>}
          <p className="text-xs text-slate-400">Banners, coupons and notifications you change here are written to the app's Firestore and show in the app straight away. Everything else is read from the app; audit, archive and remarks stay in the panel.</p>
        </div>
      )}
    </Section>
  );
}
