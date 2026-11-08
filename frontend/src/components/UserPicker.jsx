import { useEffect, useState } from "react";
import { X, Search } from "lucide-react";
import { Input } from "./ui/input";
import { api } from "../lib/api";

export function UserPicker({ type, value = [], onChange, single, testid = "user-picker" }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  const [names, setNames] = useState({});
  const prefix = type === "owner" ? "OWN-" : "TNT-";

  useEffect(() => {
    const kept = value.filter((id) => id.startsWith(prefix));
    const next = single ? kept.slice(-1) : kept;
    if (next.length !== value.length) onChange(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, single]);

  useEffect(() => {
    const missing = value.filter((id) => !names[id]);
    if (missing.length) api.get("/lookup/users", { params: { type, ids: missing.join(",") } }).then((r) => setNames((n) => ({ ...n, ...Object.fromEntries(r.data.map((u) => [u.id, u.name])) })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.join(","), type]);

  useEffect(() => {
    const t = setTimeout(() => api.get("/lookup/users", { params: { type, q } }).then((r) => setRes(r.data)), 250);
    return () => clearTimeout(t);
  }, [q, type]);

  const add = (u) => {
    setNames((n) => ({ ...n, [u.id]: u.name }));
    onChange(single ? [u.id] : value.includes(u.id) ? value : [...value, u.id]);
  };
  return (
    <div className="space-y-2" data-testid={testid}>
      <div className="flex flex-wrap gap-1.5">
        {value.map((id) => (
          <span key={id} className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-[#1E3A8A]" data-testid={`${testid}-chip-${id}`}>
            {names[id] || id} <span className="tabular text-[10px] opacity-60">{id}</span>
            <button type="button" onClick={() => onChange(value.filter((v) => v !== id))}><X className="h-3 w-3" /></button>
          </span>
        ))}
        {!value.length && <span className="text-xs text-slate-400">No {type}s selected</span>}
      </div>
      <div className="relative"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${type}s by name, mobile or ID`} className="h-9 pl-8" data-testid={`${testid}-search`} /></div>
      <div className="max-h-40 overflow-y-auto rounded-md border border-slate-200">
        {res.map((u) => (
          <button type="button" key={u.id} onClick={() => add(u)} data-testid={`${testid}-option-${u.id}`}
            className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-blue-50 ${value.includes(u.id) ? "bg-blue-50/60" : ""}`}>
            <span className="tabular text-xs text-[#1E3A8A]">{u.id}</span><span className="font-medium">{u.name}</span><span className="text-xs text-slate-500">{u.mobile}</span>
          </button>
        ))}
        {!res.length && <p className="px-3 py-2 text-xs text-slate-400">No matches</p>}
      </div>
    </div>
  );
}
