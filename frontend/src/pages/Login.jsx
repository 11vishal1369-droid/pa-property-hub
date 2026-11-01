import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Lock, Mail, ShieldCheck } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { useAuth } from "../context/AuthContext";
import { errMsg } from "../lib/api";

export default function Login() {
  const { admin, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (admin) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try { await login(email, password); nav("/"); } catch (e2) { setErr(await errMsg(e2)); } finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden bg-[#0B1530] p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-[#1E3A8A] opacity-60 blur-3xl" />
        <div className="absolute -bottom-32 left-10 h-80 w-80 rounded-full bg-[#EA580C] opacity-25 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#EA580C] font-heading font-extrabold text-white">PA</div>
          <span className="font-heading text-lg font-bold text-white">PA Property Management</span>
        </div>
        <div className="relative max-w-lg">
          <h1 className="font-heading text-4xl font-extrabold leading-tight text-white xl:text-5xl">One command centre for every owner, tenant and rupee.</h1>
          <p className="mt-5 text-slate-300">Owners, properties, agreements, payments and historical records — controlled, audited and never deleted.</p>
        </div>
        <div className="relative flex gap-8 text-sm text-slate-400">
          <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-orange-400" />Tamper-resistant audit</span>
          <span className="flex items-center gap-2"><Lock className="h-4 w-4 text-orange-400" />Encrypted Aadhaar</span>
        </div>
      </div>
      <div className="flex items-center justify-center bg-white p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5 pa-rise" data-testid="login-form">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-orange-600">Admin access</p>
            <h2 className="mt-2 font-heading text-3xl font-bold text-slate-900">Sign in</h2>
            <p className="mt-1 text-sm text-slate-500">Use your individual admin account.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <div className="relative"><Mail className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-10 pl-9" data-testid="login-email-input" /></div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <div className="relative"><Lock className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="h-10 pl-9" data-testid="login-password-input" /></div>
          </div>
          {err && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="login-error">{err}</p>}
          <Button type="submit" disabled={busy} className="h-10 w-full bg-[#1E3A8A] hover:bg-[#172f70]" data-testid="login-submit-button">{busy ? "Signing in…" : "Sign in"}</Button>
        </form>
      </div>
    </div>
  );
}
