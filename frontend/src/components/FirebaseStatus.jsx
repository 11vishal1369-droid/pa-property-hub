import { useEffect, useState } from "react";
import { RefreshCw, CheckCircle2, AlertTriangle } from "lucide-react";
import { Button } from "./ui/button";
import { Section } from "./Common";
import { api, fmtDateTime } from "../lib/api";

export function FirebaseStatus() {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const check = () => { setBusy(true); api.get("/firebase/status").then((r) => setS(r.data)).finally(() => setBusy(false)); };
  useEffect(check, []);
  return (
    <Section title="Firebase (Firestore) connection" action={<Button size="sm" variant="outline" onClick={check} disabled={busy} data-testid="firebase-check-button"><RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />Check</Button>}>
      {!s ? <p className="text-sm text-slate-400">Checking…</p> : (
        <div className="space-y-3" data-testid="firebase-status">
          <p className={`flex items-center gap-2 text-sm font-medium ${s.connected ? "text-emerald-700" : "text-red-600"}`} data-testid="firebase-status-text">
            {s.connected ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
            {s.connected ? "Connected" : "Not connected"} · project {s.project_id} · checked {fmtDateTime(s.checked_at)}
          </p>
          {s.error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="firebase-error">{s.error}</p>}
          {s.connected && <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {Object.entries(s.collections).map(([k, v]) => <div key={k} className="rounded-md border border-slate-200 p-2 text-xs"><p className="text-slate-500">{k}</p><p className="tabular text-base font-semibold">{v}</p></div>)}
          </div>}
          <p className="text-xs text-slate-400">The panel still shows sample data. Live Firestore sync starts once the connection works and the real schema has been mapped.</p>
        </div>
      )}
    </Section>
  );
}
