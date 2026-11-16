import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

const human = (k) => String(k).replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const blank = (v) => (Array.isArray(v) ? [] : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, k === "type" ? x : blank(x)])) : "");
const tid = (path) => path.join("-").replace(/[^a-zA-Z0-9-]/g, "");

function TextField({ name, value, onChange, path }) {
  if (name === "type") {
    return (
      <select value={value} onChange={(e) => onChange(e.target.value)} className="wc-input w-40" data-testid={`field-${tid(path)}`}>
        {["heading", "paragraph", "bullet"].map((o) => <option key={o} value={o}>{human(o)}</option>)}
      </select>
    );
  }
  const long = value.length > 70 || /text|value|intro/.test(String(name));
  const Tag = long ? "textarea" : "input";
  return <Tag value={value} onChange={(e) => onChange(e.target.value)} rows={long ? Math.min(10, Math.max(2, Math.ceil(value.length / 90))) : undefined}
    className="wc-input w-full" data-testid={`field-${tid(path)}`} />;
}

function ListField({ value, onChange, path }) {
  const move = (i, d) => { const n = [...value]; [n[i], n[i + d]] = [n[i + d], n[i]]; onChange(n); };
  return (
    <div className="space-y-2">
      {value.map((item, i) => (
        <div key={i} className="flex gap-2 rounded-xl border border-slate-200 bg-white p-3" data-testid={`item-${tid(path)}-${i}`}>
          <div className="min-w-0 flex-1"><FieldEditor value={item} onChange={(v) => onChange(value.map((x, j) => (j === i ? v : x)))} path={[...path, i]} /></div>
          <div className="flex shrink-0 flex-col gap-1">
            <button type="button" className="wc-icon" disabled={i === 0} onClick={() => move(i, -1)} title="Move up" data-testid={`up-${tid(path)}-${i}`}><ArrowUp className="h-3.5 w-3.5" /></button>
            <button type="button" className="wc-icon" disabled={i === value.length - 1} onClick={() => move(i, 1)} title="Move down" data-testid={`down-${tid(path)}-${i}`}><ArrowDown className="h-3.5 w-3.5" /></button>
            <button type="button" className="wc-icon text-red-600" onClick={() => onChange(value.filter((_, j) => j !== i))} title="Remove" data-testid={`remove-${tid(path)}-${i}`}><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
        </div>
      ))}
      {value.length > 0 && <button type="button" className="wc-add" onClick={() => onChange([...value, blank(value[value.length - 1])])} data-testid={`add-${tid(path)}`}><Plus className="h-3.5 w-3.5" />Add item</button>}
    </div>
  );
}

export function FieldEditor({ value, onChange, path = [] }) {
  if (typeof value === "string") return <TextField name={path[path.length - 1]} value={value} onChange={onChange} path={path} />;
  if (Array.isArray(value)) return <ListField value={value} onChange={onChange} path={path} />;
  const entries = Object.entries(value);
  const inline = entries.length <= 3 && entries.every(([, v]) => typeof v === "string");
  return (
    <div className={inline ? "grid gap-2 sm:grid-cols-[auto_1fr] sm:items-start" : "space-y-5"}>
      {entries.map(([k, v]) => (
        <label key={k} className={inline ? "contents" : "block"}>
          <span className={`block text-xs font-semibold uppercase tracking-wider text-slate-500 ${inline ? "pt-2" : "mb-1.5"}`}>{human(k)}</span>
          <FieldEditor value={v} onChange={(nv) => onChange({ ...value, [k]: nv })} path={[...path, k]} />
        </label>
      ))}
    </div>
  );
}
