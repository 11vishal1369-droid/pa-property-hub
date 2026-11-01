import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowUp, ArrowDown, Plus, Pencil, Power } from "lucide-react";
import { Button } from "../components/ui/button";
import { PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, errMsg, fmtDate, label } from "../lib/api";

const FIELDS = [{ name: "title", label: "Title", required: true, full: true }, { name: "description", label: "Description", type: "textarea", rows: 2 },
  { name: "image_url", label: "Image URL", required: true, full: true }, { name: "button_text", label: "Button text" }, { name: "destination", label: "Destination link" },
  { name: "start_date", label: "Start date", type: "date", required: true }, { name: "end_date", label: "End date", type: "date", required: true },
  { name: "audience", label: "Audience", type: "select", options: ["owner", "tenant", "both"], required: true }];

export default function Banners() {
  const { can } = useAuth();
  const [items, setItems] = useState([]);
  const [dialog, open] = useDialog();
  const edit = can("banners", "edit");
  const load = useCallback(() => api.get("/data/banners", { params: { page_size: 100 } }).then((r) => setItems(r.data.items)), []);
  useEffect(() => { load(); }, [load]);
  const done = (m) => { toast.success(m); load(); };

  const create = () => open({ title: "New banner", wide: true, fields: FIELDS, initial: { audience: "both" },
    onSubmit: async (v, reason) => { await api.post("/banners", { ...v, reason }); done("Banner created"); } });
  const editB = (b) => open({ title: "Edit banner", wide: true, fields: FIELDS, initial: Object.fromEntries(FIELDS.map((f) => [f.name, b[f.name]])),
    onSubmit: async (v, reason) => { await api.patch(`/data/banners/${b.id}`, { changes: v, reason }); done("Banner updated"); } });
  const toggle = (b) => open({ title: `${b.status === "active" ? "Deactivate" : "Activate"} banner`, description: "History is preserved.",
    onSubmit: async (_, reason) => { await api.post(`/data/banners/${b.id}/status`, { status: b.status === "active" ? "inactive" : "active", reason }); done("Banner status updated"); } });
  const move = async (i, dir) => {
    const ids = items.map((b) => b.id);
    [ids[i], ids[i + dir]] = [ids[i + dir], ids[i]];
    try { await api.post("/banners/reorder", { ids, reason: "Reordered from admin panel" }); done("Order saved"); } catch (e) { toast.error(await errMsg(e)); }
  };

  return (
    <div>
      {dialog}
      <PageHeader title="Banners" subtitle={<>Shown in Owner/Tenant apps via public API <code className="tabular rounded bg-slate-100 px-1 text-xs">GET /api/public/banners?audience=owner|tenant</code></>}>
        {edit && <Button onClick={create} className="bg-[#EA580C] hover:bg-[#c2410c]" data-testid="create-banner-button"><Plus className="mr-1.5 h-4 w-4" />New banner</Button>}
      </PageHeader>
      <div className="space-y-3" data-testid="banners-list">
        {items.map((b, i) => (
          <div key={b.id} className="pa-card flex flex-col gap-4 p-3 sm:flex-row sm:items-center" data-testid={`banner-${b.id}`}>
            <img src={b.image_url} alt={b.title} className="h-24 w-full rounded-md object-cover sm:w-44" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><span className="tabular text-xs text-slate-400">#{b.order}</span><h3 className="font-heading font-semibold">{b.title}</h3>
                <StatusBadge value={b.status} /><span className="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-[#1E3A8A]">{label(b.audience)}</span></div>
              <p className="mt-1 text-sm text-slate-500">{b.description}</p>
              <p className="mt-1 text-xs text-slate-400">{fmtDate(b.start_date)} → {fmtDate(b.end_date)} · Button “{b.button_text}” → {b.destination}</p>
            </div>
            {edit && (
              <div className="flex gap-1">
                <Button size="icon" variant="ghost" disabled={i === 0} onClick={() => move(i, -1)} data-testid={`banner-up-${b.id}`}><ArrowUp className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" disabled={i === items.length - 1} onClick={() => move(i, 1)} data-testid={`banner-down-${b.id}`}><ArrowDown className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" onClick={() => editB(b)} data-testid={`banner-edit-${b.id}`}><Pencil className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" onClick={() => toggle(b)} data-testid={`banner-toggle-${b.id}`}><Power className="h-4 w-4" /></Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
