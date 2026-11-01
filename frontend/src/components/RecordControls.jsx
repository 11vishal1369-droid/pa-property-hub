import { toast } from "sonner";
import { Pencil, ShieldAlert, MessageSquarePlus, Archive } from "lucide-react";
import { Button } from "./ui/button";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useDialog } from "./FormDialog";

export function RecordControls({ entity, module, record, statuses, editFields, onDone }) {
  const { can } = useAuth();
  const [dialog, open] = useDialog();
  if (!can(module, "edit")) return <span className="text-xs text-slate-400" data-testid="read-only-note">View-only access</span>;

  const edit = () => open({
    title: `Edit ${record.name || record.id}`, wide: true, fields: editFields, confirmLabel: "Save changes",
    initial: Object.fromEntries(editFields.map((f) => [f.name, record[f.name]])),
    onSubmit: async (v, reason) => { await api.patch(`/data/${entity}/${record.id}`, { changes: v, reason }); toast.success("Changes saved"); onDone(); },
  });
  const status = () => open({
    title: "Change status", description: `Current status: ${record.status}`,
    fields: [{ name: "status", label: "New status", type: "select", options: statuses.filter((s) => s !== record.status && s !== "archived"), required: true }],
    onSubmit: async (v, reason) => { await api.post(`/data/${entity}/${record.id}/status`, { status: v.status, reason }); toast.success("Status updated"); onDone(); },
  });
  const remark = () => open({
    title: "Add remark", requireReason: false, fields: [{ name: "text", label: "Remark", type: "textarea", required: true }],
    onSubmit: async (v) => { await api.post(`/data/${entity}/${record.id}/remarks`, { text: v.text }); toast.success("Remark added"); onDone(); },
  });
  const archive = () => open({
    title: "Archive record", danger: true, confirmLabel: "Archive",
    description: "Records are never deleted. Archived records stay searchable and can be restored from Archived Records.",
    onSubmit: async (_, reason) => { await api.post(`/data/${entity}/${record.id}/status`, { status: "archived", reason }); toast.success("Record archived"); onDone(); },
  });

  return (
    <div className="flex flex-wrap gap-2" data-testid="record-controls">
      {dialog}
      <Button size="sm" variant="outline" onClick={edit} data-testid="edit-record-button"><Pencil className="mr-1.5 h-3.5 w-3.5" />Edit</Button>
      <Button size="sm" variant="outline" onClick={status} data-testid="change-status-button"><ShieldAlert className="mr-1.5 h-3.5 w-3.5" />Status</Button>
      <Button size="sm" variant="outline" onClick={remark} data-testid="add-remark-button"><MessageSquarePlus className="mr-1.5 h-3.5 w-3.5" />Remark</Button>
      {record.status !== "archived" && (
        <Button size="sm" variant="outline" className="border-red-200 text-red-600 hover:bg-red-50" onClick={archive} data-testid="archive-record-button"><Archive className="mr-1.5 h-3.5 w-3.5" />Archive</Button>
      )}
    </div>
  );
}
