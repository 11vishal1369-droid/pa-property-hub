import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Power, KeyRound, Save, Lock } from "lucide-react";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useDialog } from "../components/FormDialog";
import { useAuth } from "../context/AuthContext";
import { api, errMsg, fmtDateTime, label } from "../lib/api";

function Matrix({ roles, modules, levels, reload, edit }) {
  const [draft, setDraft] = useState({});
  const [dialog, open] = useDialog();
  useEffect(() => { setDraft(Object.fromEntries(roles.map((r) => [r.name, { ...r.permissions }]))); }, [roles]);
  const save = (r) => open({ title: `Save permissions · ${r.name}`, onSubmit: async (_, reason) => { await api.put(`/roles/${encodeURIComponent(r.name)}`, { permissions: draft[r.name], reason }); toast.success("Permissions saved"); reload(); } });
  const addRole = () => open({ title: "Create custom role", fields: [{ name: "name", label: "Role name", required: true }, { name: "description", label: "Description" }],
    onSubmit: async (v, reason) => { await api.post("/roles", { ...v, reason }); toast.success("Role created"); reload(); } });
  return (
    <div className="pa-card overflow-x-auto" data-testid="permissions-matrix">
      {dialog}
      {edit && <div className="flex justify-end border-b border-slate-200 p-3"><Button size="sm" variant="outline" onClick={addRole} data-testid="create-role-button"><Plus className="mr-1 h-3.5 w-3.5" />Custom role</Button></div>}
      <table className="w-full text-xs">
        <thead className="bg-slate-50"><tr><th className="th sticky left-0 bg-slate-50 px-3 py-2 text-left">Module</th>
          {roles.map((r) => <th key={r.name} className="th min-w-[120px] px-2 py-2 text-left">{r.name}{r.locked && <Lock className="ml-1 inline h-3 w-3" />}</th>)}</tr></thead>
        <tbody>
          {modules.map((m) => (
            <tr key={m} className="border-t border-slate-100">
              <td className="sticky left-0 bg-white px-3 py-1.5 font-medium text-slate-700">{label(m)}</td>
              {roles.map((r) => (
                <td key={r.name} className="px-2 py-1.5">
                  <select disabled={r.locked || !edit} value={draft[r.name]?.[m] || "none"} data-testid={`perm-${r.name.replace(/\s+/g, "-").toLowerCase()}-${m}`}
                    onChange={(e) => setDraft((d) => ({ ...d, [r.name]: { ...d[r.name], [m]: e.target.value } }))}
                    className={`h-7 w-full rounded border border-slate-200 px-1 ${draft[r.name]?.[m] === "edit" ? "bg-blue-50 text-[#1E3A8A]" : draft[r.name]?.[m] === "view" ? "bg-slate-50" : "text-slate-400"}`}>
                    {levels.map((l) => <option key={l} value={l}>{l}</option>)}
                  </select>
                </td>
              ))}
            </tr>
          ))}
          {edit && <tr className="border-t border-slate-200"><td className="sticky left-0 bg-white px-3 py-2" />
            {roles.map((r) => <td key={r.name} className="px-2 py-2">{!r.locked && <Button size="sm" className="h-7 bg-[#1E3A8A]" onClick={() => save(r)} data-testid={`save-role-${r.name.replace(/\s+/g, "-").toLowerCase()}`}><Save className="mr-1 h-3 w-3" />Save</Button>}</td>)}</tr>}
        </tbody>
      </table>
    </div>
  );
}

export default function Admins() {
  const { can, admin: me } = useAuth();
  const [roles, setRoles] = useState({ roles: [], modules: [], levels: [] });
  const [key, setKey] = useState(0);
  const [dialog, open] = useDialog();
  const edit = can("admins", "edit");
  const loadRoles = useCallback(() => api.get("/roles").then((r) => setRoles(r.data)).catch(async (e) => toast.error(await errMsg(e))), []);
  useEffect(() => { loadRoles(); }, [loadRoles]);
  const done = (m) => { toast.success(m); setKey((k) => k + 1); };
  const roleOpts = roles.roles.map((r) => r.name);

  const create = () => open({ title: "Create admin user", wide: true,
    fields: [{ name: "name", label: "Full name", required: true }, { name: "email", label: "Email", type: "email", required: true }, { name: "mobile", label: "Mobile" },
      { name: "role", label: "Role", type: "select", options: roleOpts, required: true }, { name: "password", label: "Initial password (min 8)", type: "password", required: true }],
    onSubmit: async (v, reason) => { await api.post("/admins", { ...v, reason }); done("Admin created"); } });
  const editA = (a) => open({ title: `Edit ${a.name}`, initial: { name: a.name, role: a.role, mobile: a.mobile },
    fields: [{ name: "name", label: "Name", required: true }, { name: "mobile", label: "Mobile" }, { name: "role", label: "Role", type: "select", options: roleOpts, required: true }],
    onSubmit: async (v, reason) => { await api.patch(`/data/admins/${a.id}`, { changes: v, reason }); done("Admin updated"); } });
  const toggle = (a) => open({ title: `${a.status === "active" ? "Deactivate" : "Activate"} ${a.name}`, danger: a.status === "active",
    onSubmit: async (_, reason) => { await api.post(`/data/admins/${a.id}/status`, { status: a.status === "active" ? "inactive" : "active", reason }); done("Admin status updated"); } });
  const reset = (a) => open({ title: `Reset password · ${a.name}`, fields: [{ name: "new_password", label: "New password (min 8)", type: "password", required: true }],
    onSubmit: async (v, reason) => { await api.post(`/admins/${a.id}/reset-password`, { new_password: v.new_password, reason }); done("Password reset"); } });

  return (
    <div>
      {dialog}
      <PageHeader title="Admin Users & Permissions" subtitle="Individual admin logins with configurable role-based access">
        {edit && <Button onClick={create} className="bg-[#EA580C] hover:bg-[#c2410c]" data-testid="create-admin-button"><Plus className="mr-1.5 h-4 w-4" />New admin</Button>}
      </PageHeader>
      <Tabs defaultValue="users">
        <TabsList className="bg-white shadow-sm ring-1 ring-slate-200"><TabsTrigger value="users" data-testid="tab-admin-users">Admin users</TabsTrigger><TabsTrigger value="roles" data-testid="tab-roles">Roles & permissions</TabsTrigger></TabsList>
        <TabsContent value="users" className="mt-4">
          <DataTable entity="admins" refreshKey={key} dateFilter={false} filters={[{ key: "status", label: "Status", options: ["active", "inactive"] }, { key: "role", label: "Role", options: roleOpts }]}
            columns={[{ key: "id", label: "ID", render: (r) => <span className="tabular text-xs">{r.id}</span> }, { key: "name", label: "Name" }, { key: "email", label: "Email" },
              { key: "role", label: "Role", render: (r) => <span className="rounded bg-orange-50 px-2 py-0.5 text-xs font-medium text-orange-700">{r.role}</span> },
              { key: "status", label: "Status", render: (r) => <StatusBadge value={r.status} /> }, { key: "last_login", label: "Last login", render: (r) => fmtDateTime(r.last_login) }]}
            rowActions={(r) => edit && (
              <div className="flex justify-end gap-1">
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => editA(r)} data-testid={`edit-admin-${r.id}`}><Pencil className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => reset(r)} data-testid={`reset-admin-${r.id}`}><KeyRound className="h-4 w-4" /></Button>
                {r.id !== me.id && <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => toggle(r)} data-testid={`toggle-admin-${r.id}`}><Power className="h-4 w-4" /></Button>}
              </div>
            )} />
        </TabsContent>
        <TabsContent value="roles" className="mt-4"><Matrix {...roles} reload={loadRoles} edit={edit} /></TabsContent>
      </Tabs>
    </div>
  );
}
