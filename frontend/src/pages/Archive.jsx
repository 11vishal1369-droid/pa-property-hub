import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArchiveRestore } from "lucide-react";
import { Button } from "../components/ui/button";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Common";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, fmtDateTime, label } from "../lib/api";

const CATS = [["owners", "Owners"], ["tenants", "Tenants"], ["properties", "Properties"], ["agreements", "Agreements"]];

export default function ArchivePage() {
  const { can } = useAuth();
  const nav = useNavigate();
  const [cat, setCat] = useState("properties");
  const [sum, setSum] = useState({});
  const [key, setKey] = useState(0);
  const [dialog, open] = useDialog();
  useEffect(() => { api.get("/archive/summary").then((r) => setSum(r.data)); }, [key]);
  const restore = (r) => open({ title: `Restore ${r.id}`, confirmLabel: "Restore", description: "Record returns to its status before archival.",
    onSubmit: async (_, reason) => { await api.post(`/archive/${cat}/${r.id}/restore`, { reason }); toast.success("Record restored"); setKey((k) => k + 1); } });
  return (
    <div>
      {dialog}
      <PageHeader title="Archived Records" subtitle="Soft-deleted records — nothing is ever permanently deleted. Owner-removed properties appear here." />
      <div className="mb-4 flex flex-wrap gap-2">
        {CATS.map(([k, l]) => (
          <button key={k} onClick={() => setCat(k)} data-testid={`archive-tab-${k}`}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${cat === k ? "border-[#1E3A8A] bg-[#1E3A8A] text-white" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"}`}>
            {l} <span className={`ml-1 tabular text-xs ${cat === k ? "text-orange-300" : "text-slate-400"}`}>{sum[k] ?? 0}</span>
          </button>
        ))}
      </div>
      <DataTable key={cat} entity={cat} testid={`archive-${cat}`} baseParams={{ status: "archived" }} refreshKey={key}
        onRowClick={(r) => nav(`/${cat}/${r.id}`)}
        columns={[{ key: "id", label: "ID", render: (r) => <span className="tabular text-xs text-[#1E3A8A]">{r.id}</span> },
          { key: "name", label: "Name / Category", render: (r) => r.name || r.category }, { key: "owner_name", label: "Owner", sortable: false },
          { key: "archived_source", label: "Archived by", render: (r) => `${label(r.archived_source)} · ${r.archived_by || ""}` },
          { key: "archive_reason", label: "Reason" }, { key: "archived_at", label: "Archived at", render: (r) => fmtDateTime(r.archived_at) }]}
        rowActions={(r) => can("archive", "edit") && <Button size="sm" variant="ghost" onClick={() => restore(r)} data-testid={`restore-${r.id}`}><ArchiveRestore className="mr-1 h-3.5 w-3.5" />Restore</Button>} />
    </div>
  );
}
