import { fmtDateTime, label } from "../lib/api";
import { StatusBadge } from "./StatusBadge";

export const PageHeader = ({ title, subtitle, children }) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-4 pa-rise">
    <div>
      <h1 className="font-heading text-2xl font-bold tracking-tight text-slate-900 md:text-3xl" data-testid="page-title">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
    </div>
    <div className="flex flex-wrap gap-2">{children}</div>
  </div>
);

export const KV = ({ items, cols = 3 }) => (
  <dl className={`grid gap-x-6 gap-y-4 sm:grid-cols-2 ${cols === 2 ? "" : "lg:grid-cols-3"}`}>
    {items.map(([k, v]) => (
      <div key={k} className="min-w-0">
        <dt className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{k}</dt>
        <dd className="mt-0.5 break-words text-sm text-slate-800" data-testid={`kv-${k.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}>{v ?? "—"}</dd>
      </div>
    ))}
  </dl>
);

export const MiniTable = ({ rows, columns, empty = "No records", testid, onRowClick }) => (
  <div className="overflow-x-auto rounded-lg border border-slate-200" data-testid={testid}>
    <table className="w-full text-sm">
      <thead className="bg-slate-50"><tr>{columns.map((c) => <th key={c.key} className="th px-3 py-2 text-left">{c.label}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.id || i} className={`border-t border-slate-100 ${onRowClick ? "cursor-pointer hover:bg-blue-50/40" : ""}`} onClick={() => onRowClick?.(r)}>
            {columns.map((c) => <td key={c.key} className="whitespace-nowrap px-3 py-2 text-slate-700">{c.render ? c.render(r) : (r[c.key] ?? "—")}</td>)}
          </tr>
        ))}
        {!rows.length && <tr><td colSpan={columns.length} className="px-3 py-8 text-center text-slate-400">{empty}</td></tr>}
      </tbody>
    </table>
  </div>
);

export const Section = ({ title, children, action }) => (
  <section className="pa-card p-5">
    <div className="mb-4 flex items-center justify-between gap-2">
      <h3 className="font-heading text-base font-semibold text-slate-900">{title}</h3>
      {action}
    </div>
    {children}
  </section>
);

export const Timeline = ({ items = [], testid = "timeline" }) => (
  <ol className="space-y-3" data-testid={testid}>
    {items.map((it, i) => (
      <li key={i} className="relative border-l-2 border-orange-200 pl-4">
        <span className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full bg-orange-500" />
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="font-mono">{fmtDateTime(it.at || it.created_at)}</span>
          <span>·</span><span>{it.by || it.admin_email}</span>
          {(it.action) && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-600">{label(it.action)}</span>}
          {it.new && typeof it.new === "string" && <StatusBadge value={it.new} />}
        </div>
        {(it.reason || it.text) && <p className="mt-1 text-sm text-slate-700">{it.reason || it.text}</p>}
      </li>
    ))}
    {!items.length && <p className="text-sm text-slate-400">No history yet</p>}
  </ol>
);

export const Avatar = ({ name, src, size = "h-9 w-9" }) =>
  src ? <img src={src} alt={name} className={`${size} rounded-full object-cover`} /> : (
    <div className={`${size} flex shrink-0 items-center justify-center rounded-full bg-blue-100 font-heading text-xs font-bold text-[#1E3A8A]`}>
      {(name || "?").split(" ").map((p) => p[0]).slice(0, 2).join("")}
    </div>
  );
