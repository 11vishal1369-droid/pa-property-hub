import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Download, Search, ArrowUpDown, RefreshCw } from "lucide-react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { api, download, errMsg, label } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const sel = "h-9 rounded-md border border-slate-200 bg-white px-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-800/30";

export function DataTable({ entity, columns, filters = [], baseParams = {}, onRowClick, rowActions, toolbar, refreshKey = 0, dateFilter = true, testid, emptyText = "No records found" }) {
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  const [f, setF] = useState({});
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [sort, setSort] = useState(null);
  const [res, setRes] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => { const t = setTimeout(() => { setDq(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);

  const params = useCallback(() => {
    const p = { ...baseParams, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) };
    if (dq) p.q = dq;
    if (sort) { p.sort = sort.key; p.order = sort.order; }
    return p;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(baseParams), f, dq, sort]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    api.get(`/data/${entity}`, { params: { ...params(), page, page_size: size } })
      .then((r) => live && setRes(r.data))
      .catch(async (e) => toast.error(await errMsg(e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [entity, params, page, size, refreshKey, tick]);

  const doExport = async (format) => {
    try {
      await download(`/data/${entity}/export`, { ...params(), format });
      toast.success(`Exported ${format.toUpperCase()}`);
    } catch (e) { toast.error(await errMsg(e)); }
  };

  const pages = Math.max(1, Math.ceil(res.total / size));
  const tid = testid || entity;

  return (
    <div className="pa-card overflow-hidden" data-testid={`${tid}-table`}>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 p-3">
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="h-9 pl-8" data-testid={`${tid}-search-input`} />
        </div>
        {filters.map((fl) => (
          <select key={fl.key} className={sel} value={f[fl.key] || ""} data-testid={`${tid}-filter-${fl.key}`}
            onChange={(e) => { setF((s) => ({ ...s, [fl.key]: e.target.value })); setPage(1); }}>
            <option value="">{fl.label}: All</option>
            {fl.options.map((o) => {
              const v = typeof o === "string" ? o : o.value;
              return <option key={v} value={v}>{typeof o === "string" ? label(o) : o.label}</option>;
            })}
          </select>
        ))}
        {dateFilter && (
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <input type="date" className={sel} value={f.from || ""} onChange={(e) => { setF((s) => ({ ...s, from: e.target.value })); setPage(1); }} data-testid={`${tid}-filter-from`} />
            <span>to</span>
            <input type="date" className={sel} value={f.to || ""} onChange={(e) => { setF((s) => ({ ...s, to: e.target.value })); setPage(1); }} data-testid={`${tid}-filter-to`} />
          </div>
        )}
        <div className="ml-auto flex items-center gap-2">
          {toolbar}
          <Button variant="ghost" size="icon" onClick={() => setTick((t) => t + 1)} data-testid={`${tid}-refresh-button`}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></Button>
          {can("reports") && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-9" data-testid={`${tid}-export-button`}><Download className="mr-1.5 h-4 w-4" />Export</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => doExport("xlsx")} data-testid={`${tid}-export-xlsx`}>Excel (.xlsx)</DropdownMenuItem>
                <DropdownMenuItem onClick={() => doExport("csv")} data-testid={`${tid}-export-csv`}>CSV</DropdownMenuItem>
                <DropdownMenuItem onClick={() => doExport("pdf")} data-testid={`${tid}-export-pdf`}>PDF</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50/80">
            <tr>
              {columns.map((c) => (
                <th key={c.key} className="th whitespace-nowrap px-3 py-2.5 text-left">
                  {c.sortable === false ? c.label : (
                    <button className="inline-flex items-center gap-1 hover:text-slate-900" data-testid={`${tid}-sort-${c.key}`}
                      onClick={() => setSort((s) => ({ key: c.key, order: s?.key === c.key && s.order === "desc" ? "asc" : "desc" }))}>
                      {c.label}<ArrowUpDown className="h-3 w-3 opacity-50" />
                    </button>
                  )}
                </th>
              ))}
              {rowActions && <th className="th px-3 py-2.5 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {res.items.map((r) => (
              <tr key={r.id} data-testid={`${tid}-row-${r.id}`} onClick={() => onRowClick?.(r)}
                className={`border-t border-slate-100 transition-colors hover:bg-blue-50/40 ${onRowClick ? "cursor-pointer" : ""}`}>
                {columns.map((c) => (
                  <td key={c.key} className="whitespace-nowrap px-3 py-2.5 text-slate-700">{c.render ? c.render(r) : (r[c.key] ?? "—")}</td>
                ))}
                {rowActions && <td className="px-3 py-2 text-right" onClick={(e) => e.stopPropagation()}>{rowActions(r, () => setTick((t) => t + 1))}</td>}
              </tr>
            ))}
            {!res.items.length && (
              <tr><td colSpan={columns.length + 1} className="px-3 py-12 text-center text-slate-400" data-testid={`${tid}-empty`}>{loading ? "Loading…" : emptyText}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-slate-200 px-3 py-2 text-xs text-slate-500">
        <span data-testid={`${tid}-total`}>{res.total} records</span>
        <div className="flex items-center gap-2">
          <select className={`${sel} h-8`} value={size} onChange={(e) => { setSize(Number(e.target.value)); setPage(1); }} data-testid={`${tid}-page-size`}>
            {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}
          </select>
          <Button variant="outline" size="icon" className="h-8 w-8" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid={`${tid}-prev-page`}><ChevronLeft className="h-4 w-4" /></Button>
          <span data-testid={`${tid}-page-indicator`}>Page {page} of {pages}</span>
          <Button variant="outline" size="icon" className="h-8 w-8" disabled={page >= pages} onClick={() => setPage(page + 1)} data-testid={`${tid}-next-page`}><ChevronRight className="h-4 w-4" /></Button>
        </div>
      </div>
    </div>
  );
}
