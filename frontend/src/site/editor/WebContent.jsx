import { useCallback, useEffect, useState } from "react";
import { ExternalLink, History, KeyRound, LogOut, Save } from "lucide-react";
import { toast } from "sonner";
import { getToken, setToken, web } from "../webApi";
import { FieldEditor } from "./FieldEditor";
import "./editor.css";

const PAGES = [["home", "Homepage", "/"], ["terms-conditions", "Terms & Conditions", "/terms-conditions"], ["privacy-policy", "Privacy Policy", "/privacy-policy"],
  ["refund-policy", "Refund Policy", "/refund-policy"], ["contact-us", "Contact Us", "/contact-us"]];
const when = (v) => (v ? new Date(v).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "");

function Login({ onDone }) {
  const [f, setF] = useState({ email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { const d = await web("/auth/login", { method: "POST", body: f }); setToken(d.token); onDone(d.editor); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="wc-root flex min-h-screen items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm" data-testid="webcontent-login-form">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">Website editor</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">Sign in to edit the website</h1>
        <p className="mt-1 text-sm text-slate-500">This login is separate from the admin panel.</p>
        <label className="mt-6 block text-sm font-medium text-slate-700">Email<input type="email" required className="wc-input mt-1 w-full" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="webcontent-login-email" /></label>
        <label className="mt-4 block text-sm font-medium text-slate-700">Password<input type="password" required className="wc-input mt-1 w-full" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="webcontent-login-password" /></label>
        {err && <p className="mt-3 text-sm text-red-600" data-testid="webcontent-login-error">{err}</p>}
        <button disabled={busy} className="wc-primary mt-6 w-full justify-center" data-testid="webcontent-login-submit">{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  );
}

function PasswordForm({ onClose }) {
  const [f, setF] = useState({ current_password: "", new_password: "" });
  const save = async (e) => {
    e.preventDefault();
    try { await web("/auth/change-password", { method: "POST", body: f, auth: true }); toast.success("Password changed"); onClose(); } catch (x) { toast.error(x.message); }
  };
  return (
    <form onSubmit={save} className="mb-6 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-[1fr_1fr_auto]" data-testid="webcontent-password-form">
      <input type="password" placeholder="Current password" required className="wc-input" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} data-testid="webcontent-current-password" />
      <input type="password" placeholder="New password (min 8)" required className="wc-input" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} data-testid="webcontent-new-password" />
      <button className="wc-primary" data-testid="webcontent-password-save">Update</button>
    </form>
  );
}

function HistoryPanel({ slug, onRestored }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { web(`/pages/${slug}/history`, { auth: true }).then(setRows).catch(() => setRows([])); }, [slug]);
  const restore = async (v) => {
    if (!window.confirm(`Restore version ${v}? The current text will be kept in history.`)) return;
    try { await web(`/pages/${slug}/restore/${v}`, { method: "POST", auth: true }); toast.success(`Version ${v} restored and published`); onRestored(); } catch (x) { toast.error(x.message); }
  };
  return (
    <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4" data-testid="webcontent-history">
      {!rows ? <p className="text-sm text-slate-400">Loading…</p> : !rows.length ? <p className="text-sm text-slate-500">No earlier versions yet.</p> : (
        <ul className="divide-y divide-slate-100 text-sm">{rows.map((h) => (
          <li key={h.version} className="flex items-center justify-between py-2"><span>Version {h.version} · saved {when(h.saved_at)} by {h.saved_by}</span>
            <button className="wc-ghost" onClick={() => restore(h.version)} data-testid={`webcontent-restore-${h.version}`}>Restore</button></li>))}</ul>)}
    </div>
  );
}

function Editor({ editor, onLogout }) {
  const [slug, setSlug] = useState("home");
  const [page, setPage] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState(null);
  const dirty = page && JSON.stringify(page.content) !== JSON.stringify(draft);
  const load = useCallback(() => {
    setPage(null);
    web(`/pages/${slug}`, { auth: true }).then((p) => { setPage(p); setDraft(p.content); }).catch((x) => (x.status === 401 ? onLogout() : toast.error(x.message)));
  }, [slug, onLogout]);
  useEffect(load, [load]);
  useEffect(() => {
    const warn = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const pick = (s) => { if (dirty && !window.confirm("You have unsaved changes. Discard them?")) return; setPanel(null); setSlug(s); };
  const save = async () => {
    setBusy(true);
    try { const r = await web(`/pages/${slug}`, { method: "PUT", auth: true, body: { content: draft, version: page.version } }); setPage({ ...page, ...r, content: draft }); toast.success("Saved. The public page is updated."); }
    catch (x) { x.status === 401 ? onLogout() : toast.error(x.message); } finally { setBusy(false); }
  };
  const cur = PAGES.find((p) => p[0] === slug);
  return (
    <div className="wc-root min-h-screen" data-testid="webcontent-editor">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-3">
          <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">Website editor</p><p className="text-sm text-slate-500" data-testid="webcontent-editor-email">{editor.email}</p></div>
          <div className="flex items-center gap-2">
            <button className="wc-ghost" onClick={() => setPanel(panel === "pw" ? null : "pw")} data-testid="webcontent-password-toggle"><KeyRound className="h-4 w-4" />Password</button>
            <button className="wc-ghost" onClick={onLogout} data-testid="webcontent-logout"><LogOut className="h-4 w-4" />Sign out</button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-6 pb-3">
          {PAGES.map(([s, l]) => <button key={s} onClick={() => pick(s)} className={`wc-tab ${s === slug ? "is-active" : ""}`} data-testid={`webcontent-tab-${s}`}>{l}</button>)}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {panel === "pw" && <PasswordForm onClose={() => setPanel(null)} />}
        {!page || !draft ? <p className="text-slate-400" data-testid="webcontent-loading">Loading…</p> : (
          <>
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold text-slate-900" data-testid="webcontent-page-title">{cur[1]}</h1>
                <p className="text-sm text-slate-500" data-testid="webcontent-page-meta">Version {page.version} · last saved {when(page.updated_at)} by {page.updated_by}{dirty && <span className="ml-2 font-medium text-amber-700" data-testid="webcontent-unsaved">· Unsaved changes</span>}</p>
              </div>
              <div className="flex gap-2">
                <a href={cur[2]} target="_blank" rel="noopener noreferrer" className="wc-ghost" data-testid="webcontent-view-page"><ExternalLink className="h-4 w-4" />View page</a>
                <button className="wc-ghost" onClick={() => setPanel(panel === "hist" ? null : "hist")} data-testid="webcontent-history-toggle"><History className="h-4 w-4" />History</button>
                {dirty && <button className="wc-ghost" onClick={() => setDraft(page.content)} data-testid="webcontent-discard">Discard</button>}
                <button className="wc-primary" disabled={!dirty || busy} onClick={save} data-testid="webcontent-save"><Save className="h-4 w-4" />{busy ? "Saving…" : "Save & publish"}</button>
              </div>
            </div>
            {panel === "hist" && <HistoryPanel slug={slug} onRestored={() => { setPanel(null); load(); }} />}
            <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">Links: type <code>[link text](https://address)</code>. Web addresses, emails and 10-digit mobile numbers become clickable automatically.</p>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-6"><FieldEditor value={draft} onChange={setDraft} path={[slug]} /></div>
          </>
        )}
      </main>
    </div>
  );
}

export default function WebContent() {
  const [editor, setEditor] = useState(undefined);
  useEffect(() => {
    document.title = "Website editor · Propertys Available";
    if (!getToken()) return setEditor(null);
    web("/auth/me", { auth: true }).then(setEditor).catch(() => { setToken(null); setEditor(null); });
  }, []);
  const logout = useCallback(() => { setToken(null); setEditor(null); }, []);
  if (editor === undefined) return <div className="wc-root flex min-h-screen items-center justify-center text-slate-400">Loading…</div>;
  return editor ? <Editor editor={editor} onLogout={logout} /> : <Login onDone={setEditor} />;
}
