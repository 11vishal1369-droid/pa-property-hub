import { ArrowRight, ArrowUpRight, Building2, Check, KeyRound, Smartphone } from "lucide-react";
import { RichText } from "./RichText";
import { PageState, usePage } from "./SiteLayout";

const ROLE = [{ Icon: KeyRound, cls: "role-tenant" }, { Icon: Building2, cls: "role-owner" }];

const RoleBtn = ({ b, i }) => {
  const { Icon, cls } = ROLE[i % 2];
  const ext = /^https?:/.test(b.url);
  return (
    <a href={b.url} className={`role-btn ${cls}`} data-testid={`home-login-btn-${i}`} {...(ext ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
      <span className="role-icon"><Icon className="h-7 w-7" strokeWidth={1.8} /></span>
      <span className="role-label">{b.label}</span>
      <ArrowRight className="role-arrow h-5 w-5" />
    </a>
  );
};

const Btn = ({ b, i, dark, blue, testid }) => {
  const ext = /^https?:/.test(b.url);
  return (
    <a href={b.url} className={`site-btn ${blue ? "site-btn-blue" : dark ? "site-btn-dark" : ""}`} data-testid={testid} {...(ext ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
      {b.label}<ArrowUpRight className="h-4 w-4" />
    </a>
  );
};

export default function HomePage() {
  const { content: c, error } = usePage("home");
  if (!c) return <PageState error={error} />;
  return (
    <div data-testid="home-page">
      <section className="site-hero">
        <div className="site-wrap grid items-center gap-12 py-16 lg:grid-cols-[1.05fr_1fr] lg:py-24">
          <div className="site-rise">
            <p className="site-eyebrow" data-testid="home-eyebrow">{c.eyebrow}</p>
            <h1 className="site-display hero-title mt-5 text-4xl sm:text-5xl lg:text-6xl" data-testid="home-brand">{c.brand}</h1>
            <p className="mt-5 max-w-xl text-lg text-[#c9d6f5]" data-testid="home-tagline">{c.tagline}</p>
            <div className="mt-10 grid max-w-xl gap-4">{c.login_buttons.map((b, i) => <RoleBtn key={i} b={b} i={i} />)}</div>
            <p className="site-soon mt-8" data-testid="home-coming-soon">{c.coming_soon}</p>
          </div>
          <div className="site-rise site-delay-1 relative">
            <img src="/site/hero.jpg" alt="Apartment balconies with house keys" className="aspect-[4/3] w-full rounded-[28px] object-cover shadow-[0_30px_60px_-30px_rgba(11,27,63,0.55)]" />
            <div className="site-hero-card">
              <p className="site-display text-xl text-[#0b1b3f]" data-testid="home-intro-title">{c.intro_title}</p>
              <p className="mt-2 text-sm text-[#3d4b66]" data-testid="home-intro-text"><RichText text={c.intro_text} /></p>
            </div>
          </div>
        </div>
      </section>

      <section className="site-wrap grid gap-10 py-20 lg:grid-cols-[0.8fr_1.2fr]" id="about">
        <h2 className="site-display text-3xl text-[#0b1b3f] lg:text-4xl" data-testid="home-about-title">{c.about_title}</h2>
        <p className="text-lg leading-relaxed text-[#2b3852]" data-testid="home-about-text"><RichText text={c.about_text} /></p>
      </section>

      <section className="site-dark py-20 text-[#ffffff]">
        <div className="site-wrap">
          <h2 className="site-display text-3xl lg:text-4xl" data-testid="home-features-title">{c.features_title}</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {c.features.map((f, i) => (
              <div key={i} className="rounded-3xl border border-[#2350d8]/40 bg-[#2350d8]/10 p-8 transition-transform duration-300 hover:-translate-y-1" data-testid={`home-feature-${i}`}>
                <p className="site-display text-2xl text-[#f97316]">{f.title}</p>
                <ul className="mt-6 space-y-3">{f.items.map((it, j) => <li key={j} className="flex gap-3 text-[#dbe5ff]"><Check className="mt-1 h-4 w-4 shrink-0 text-[#f97316]" /><RichText text={it} /></li>)}</ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="site-wrap py-20">
        <h2 className="site-display text-3xl text-[#0b1b3f] lg:text-4xl" data-testid="home-mission-title">{c.mission_title}</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {c.mission.map((m, i) => (
            <div key={i} className={`rounded-3xl p-8 ${i === 0 ? "bg-[#f97316]/10 border-l-4 border-[#f97316]" : "bg-[#e8eefc] border-l-4 border-[#2350d8]"}`} data-testid={`home-mission-${i}`}>
              <p className="site-eyebrow">{m.title}</p>
              <p className="mt-4 text-lg leading-relaxed text-[#2b3852]"><RichText text={m.text} /></p>
            </div>
          ))}
        </div>
      </section>

      <section className="site-wrap pb-20">
        <div className="site-glow-card rounded-[32px] p-10 lg:p-14">
          <h2 className="site-display text-3xl text-[#0b1b3f]" data-testid="home-simpler-title">{c.simpler_title}</h2>
          <p className="mt-4 max-w-3xl text-lg leading-relaxed text-[#2b3852]" data-testid="home-simpler-text"><RichText text={c.simpler_text} /></p>
        </div>
      </section>

      <section id="get-the-app" className="site-wrap pb-24">
        <div className="site-app-band flex flex-col items-start justify-between gap-8 rounded-[32px] p-10 lg:flex-row lg:items-center lg:p-14">
          <div className="flex items-start gap-4">
            <Smartphone className="mt-1 h-8 w-8 text-[#0b1b3f]" />
            <div>
              <h2 className="site-display text-3xl text-[#0b1b3f]" data-testid="home-app-title">{c.app_title}</h2>
              <p className="mt-2 text-[#0b1b3f]/80" data-testid="home-app-text">{c.app_text}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">{c.app_buttons.map((b, i) => <Btn key={i} b={b} dark testid={`home-app-btn-${i}`} />)}</div>
        </div>
      </section>
    </div>
  );
}
