import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Label } from "./ui/label";
import { errMsg, label } from "../lib/api";
import { UserPicker } from "./UserPicker";

const Field = ({ f, value, onChange, vals }) => {
  const id = `field-${f.name}`;
  if (f.type === "users") {
    const t = typeof f.userType === "function" ? f.userType(vals) : f.userType;
    return <UserPicker key={t} type={t} value={value || []} onChange={onChange} single={f.single?.(vals)} testid={`form-${f.name}-picker`} />;
  }
  if (f.type === "select")
    return (
      <select id={id} data-testid={`form-${f.name}-select`} value={value ?? ""} onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-800/30">
        <option value="">Select…</option>
        {f.options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          return <option key={v} value={v}>{typeof o === "string" ? label(o) : o.label}</option>;
        })}
      </select>
    );
  if (f.type === "textarea")
    return <Textarea id={id} data-testid={`form-${f.name}-input`} rows={f.rows || 4} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  return <Input id={id} data-testid={`form-${f.name}-input`} type={f.type || "text"} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
};

export function FormDialog({ open, onOpenChange, title, description, fields = [], initial = {}, onSubmit, confirmLabel = "Confirm", requireReason = true, danger, wide }) {
  const [vals, setVals] = useState({});
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) { setVals({ ...initial }); setReason(""); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = async () => {
    for (const f of fields) if ((!f.show || f.show(vals)) && f.required && (vals[f.name] === undefined || vals[f.name] === "")) return toast.error(`${f.label} is required`);
    if (requireReason && !reason.trim()) return toast.error("Reason is required for this action");
    const out = { ...vals };
    fields.forEach((f) => { if (f.type === "number" && out[f.name] !== "" && out[f.name] != null) out[f.name] = Number(out[f.name]); });
    setBusy(true);
    try {
      await onSubmit(out, reason.trim());
      onOpenChange(false);
    } catch (e) {
      toast.error(await errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={`${wide ? "max-w-2xl" : "max-w-lg"} max-h-[90vh] overflow-y-auto`} data-testid="form-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading">{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className={`grid gap-3 ${wide ? "sm:grid-cols-2" : ""}`}>
          {fields.filter((f) => !f.show || f.show(vals)).map((f) => (
            <div key={f.name} className={`space-y-1.5 ${f.type === "textarea" || f.type === "users" || f.full ? "sm:col-span-2" : ""}`}>
              <Label htmlFor={`field-${f.name}`} className="text-xs text-slate-600">{f.label}{f.required && " *"}</Label>
              <Field f={f} vals={vals} value={vals[f.name]} onChange={(v) => setVals((s) => ({ ...s, [f.name]: v }))} />
            </div>
          ))}
          {requireReason && (
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="reason" className="text-xs text-slate-600">Reason for action *</Label>
              <Textarea id="reason" data-testid="form-reason-input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Recorded in the audit log" />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="form-cancel-button">Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="form-submit-button"
            className={danger ? "bg-red-600 hover:bg-red-700" : "bg-[#1E3A8A] hover:bg-[#172f70]"}>
            {busy ? "Saving…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function useDialog() {
  const [cfg, setCfg] = useState(null);
  const dialog = cfg ? <FormDialog open={!!cfg} onOpenChange={(o) => !o && setCfg(null)} {...cfg} /> : null;
  return [dialog, setCfg];
}
