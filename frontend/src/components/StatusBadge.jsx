import { Badge } from "./ui/badge";
import { label } from "../lib/api";

const TONES = {
  green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  red: "bg-red-50 text-red-700 border-red-200",
  blue: "bg-blue-50 text-blue-800 border-blue-200",
  slate: "bg-slate-100 text-slate-600 border-slate-200",
  orange: "bg-orange-50 text-orange-700 border-orange-200",
  violet: "bg-violet-50 text-violet-700 border-violet-200",
};
const MAP = {
  active: "green", success: "green", approved: "green", verified: "green", completed: "green", delivered: "green", resolved: "green",
  pending: "amber", pending_verification: "amber", open: "amber", in_progress: "blue", queued: "slate", sent: "blue", draft: "slate",
  blocked: "red", failed: "red", rejected: "red", suspended: "orange", escalated: "orange", reopened: "violet",
  deactivated: "slate", inactive: "slate", archived: "slate", closed: "slate", expired: "slate", cancelled: "slate", none: "slate",
  refunded: "violet", partially_refunded: "violet", occupied: "blue", vacant: "amber",
  urgent: "red", high: "orange", medium: "amber", low: "slate",
};

export const StatusBadge = ({ value, testid }) => (
  <Badge variant="outline" data-testid={testid} className={`rounded-md font-medium text-[11px] px-2 py-0.5 whitespace-nowrap ${TONES[MAP[value] || "slate"]}`}>
    {label(value)}
  </Badge>
);
