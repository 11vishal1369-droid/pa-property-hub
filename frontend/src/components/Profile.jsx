import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Button } from "./ui/button";
import { Timeline } from "./Common";
import { api } from "../lib/api";

export function useProfile(path) {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const load = useCallback(() => api.get(path(id)).then((r) => setData(r.data)).catch((e) => setErr(e.response?.data?.detail || "Failed to load")), [id, path]);
  useEffect(() => { load(); }, [load]);
  return { id, data, err, load };
}

export const BackButton = () => {
  const nav = useNavigate();
  return <Button variant="ghost" size="sm" className="mb-3 -ml-2 text-slate-500" onClick={() => nav(-1)} data-testid="back-button"><ArrowLeft className="mr-1 h-4 w-4" />Back</Button>;
};

export const ProfileTabs = ({ tabs }) => (
  <Tabs defaultValue={tabs[0][0]} className="mt-6">
    <TabsList className="h-auto flex-wrap justify-start bg-white p-1 shadow-sm ring-1 ring-slate-200">
      {tabs.map(([k, l]) => <TabsTrigger key={k} value={k} data-testid={`tab-${k}`} className="data-[state=active]:bg-[#1E3A8A] data-[state=active]:text-white">{l}</TabsTrigger>)}
    </TabsList>
    {tabs.map(([k, , el]) => <TabsContent key={k} value={k} className="mt-4">{el}</TabsContent>)}
  </Tabs>
);

export const ActivityPanel = ({ record, activity }) => {
  const merged = [...(record.status_history || []), ...(record.remarks || []).map((r) => ({ ...r, action: "remark" })), ...(record.history || [])]
    .sort((a, b) => (b.at || "").localeCompare(a.at || ""));
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="pa-card p-5"><h3 className="mb-4 font-heading font-semibold">Status changes, edits & remarks</h3><Timeline items={merged} testid="record-history" /></div>
      <div className="pa-card p-5"><h3 className="mb-4 font-heading font-semibold">Audit trail</h3>
        <Timeline items={activity.map((a) => ({ at: a.created_at, by: a.admin_email, action: a.action, reason: a.reason }))} testid="audit-trail" /></div>
    </div>
  );
};
