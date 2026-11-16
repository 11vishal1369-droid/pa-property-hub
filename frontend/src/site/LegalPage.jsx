import { RichText } from "./RichText";
import { PageState, usePage } from "./SiteLayout";

const fmt = (v) => new Date(v).toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" });

function Blocks({ blocks }) {
  const out = [];
  let list = [];
  const flush = (k) => { if (list.length) { out.push(<ul key={`ul${k}`} className="legal-list">{list}</ul>); list = []; } };
  blocks.forEach((b, i) => {
    if (b.type === "bullet") { list.push(<li key={i}><RichText text={b.text} /></li>); return; }
    flush(i);
    out.push(b.type === "heading"
      ? <h2 key={i} className="legal-h2" data-testid={`legal-heading-${i}`}>{b.text}</h2>
      : <p key={i} className="legal-p"><RichText text={b.text} /></p>);
  });
  flush("end");
  return out;
}

export default function LegalPage({ slug }) {
  const { content: c, error, updated } = usePage(slug);
  if (!c) return <PageState error={error} />;
  return (
    <article className="site-wrap py-16 lg:py-20" data-testid={`legal-page-${slug}`}>
      <div className="mx-auto max-w-3xl">
        <p className="site-eyebrow">Legal</p>
        <h1 className="site-display mt-4 text-4xl text-[#0b1b3f] sm:text-5xl" data-testid="legal-title">{c.title}</h1>
        {updated && <p className="mt-3 text-sm text-[#5b6b8c]" data-testid="legal-updated">Page last updated {fmt(updated)}</p>}
        <div className="legal-body mt-10"><Blocks blocks={c.blocks} /></div>
      </div>
    </article>
  );
}
