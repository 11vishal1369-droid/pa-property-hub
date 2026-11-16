import { Fragment } from "react";

// Renders plain text with [label](url) links plus auto-linked URLs, emails and Indian phone numbers.
const TOKEN = /\[([^\]]+)\]\(([^)\s]+)\)|((?:https?:\/\/|www\.)[^\s,;)]+[^\s,;.)])|([\w.+-]+@[\w-]+\.[\w.-]*\w)|(\b[6-9]\d{9}\b)/gi;

const hrefFor = (m) => {
  if (m[1]) return [m[1], m[2]];
  if (m[3]) return [m[3], m[3].startsWith("www.") ? `https://${m[3]}` : m[3]];
  if (m[4]) return [m[4], `mailto:${m[4].toLowerCase()}`];
  return [m[5], `tel:+91${m[5]}`];
};

export function RichText({ text, className = "" }) {
  const out = [];
  let last = 0;
  for (const m of String(text || "").matchAll(TOKEN)) {
    out.push(text.slice(last, m.index));
    const [label, href] = hrefFor(m);
    const ext = /^https?:/.test(href);
    out.push(<a key={m.index} href={href} className="site-link" {...(ext ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{label}</a>);
    last = m.index + m[0].length;
  }
  out.push(text?.slice(last));
  return <span className={className}>{out.map((x, i) => <Fragment key={i}>{x}</Fragment>)}</span>;
}
