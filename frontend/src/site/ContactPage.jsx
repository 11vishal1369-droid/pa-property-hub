import { Building2, Clock, Globe, Mail, MapPin, Phone, ShieldCheck, User } from "lucide-react";
import { RichText } from "./RichText";
import { PageState, usePage } from "./SiteLayout";

const icon = (label) => {
  const l = label.toLowerCase();
  if (l.includes("mail")) return Mail;
  if (l.includes("phone") || l.includes("number")) return Phone;
  if (l.includes("address")) return MapPin;
  if (l.includes("hour")) return Clock;
  if (l.includes("website")) return Globe;
  if (l.includes("officer")) return User;
  return Building2;
};

function Rows({ rows, prefix }) {
  return (
    <dl className="divide-y divide-[#1f3d2b]/10">
      {rows.map((r, i) => {
        const I = icon(r.label);
        return (
          <div key={i} className="grid gap-1 py-4 sm:grid-cols-[220px_1fr] sm:gap-6" data-testid={`${prefix}-row-${i}`}>
            <dt className="flex items-center gap-2 text-sm font-medium text-[#7a6d58]"><I className="h-4 w-4 text-[#c97a17]" />{r.label}</dt>
            <dd className="text-[#1f2a22]"><RichText text={r.value} /></dd>
          </div>
        );
      })}
    </dl>
  );
}

export default function ContactPage() {
  const { content: c, error } = usePage("contact-us");
  if (!c) return <PageState error={error} />;
  return (
    <div className="site-wrap py-16 lg:py-20" data-testid="contact-page">
      <p className="site-eyebrow">Get in touch</p>
      <h1 className="site-display mt-4 text-4xl text-[#1f3d2b] sm:text-5xl" data-testid="contact-title">{c.title}</h1>
      <p className="mt-4 max-w-2xl text-lg text-[#4a4134]" data-testid="contact-intro"><RichText text={c.intro} /></p>
      <div className="mt-12 grid gap-8 lg:grid-cols-[1.3fr_1fr]">
        <section className="rounded-3xl border border-[#1f3d2b]/15 bg-white/70 p-8" data-testid="contact-details"><Rows rows={c.details} prefix="contact" /></section>
        <section className="rounded-3xl bg-[#1f3d2b] p-8 text-[#f5efe4]" data-testid="contact-grievance">
          <p className="flex items-center gap-2 site-display text-2xl text-[#f2a541]"><ShieldCheck className="h-6 w-6" />{c.grievance_title}</p>
          <dl className="mt-4 space-y-4">
            {c.grievance.map((r, i) => (
              <div key={i} data-testid={`grievance-row-${i}`}><dt className="text-xs uppercase tracking-widest text-[#cdbfa8]">{r.label}</dt><dd className="mt-1 text-[#f5efe4] [&_a]:text-[#f2a541]"><RichText text={r.value} /></dd></div>
            ))}
          </dl>
        </section>
      </div>
    </div>
  );
}
