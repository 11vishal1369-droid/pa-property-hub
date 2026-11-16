import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { web } from "./webApi";
import "./site.css";

export const NAV = [["/", "Home"], ["/terms-conditions", "Terms & Conditions"], ["/privacy-policy", "Privacy Policy"],
  ["/refund-policy", "Refund Policy"], ["/contact-us", "Contact Us"]];

export function usePage(slug) {
  const [state, setState] = useState({ content: null, error: null });
  useEffect(() => {
    let live = true;
    setState({ content: null, error: null });
    web(`/public/pages/${slug}`).then((d) => live && setState({ content: d.content, updated: d.updated_at }))
      .catch((e) => live && setState({ content: null, error: e.message }));
    return () => { live = false; };
  }, [slug]);
  return state;
}

export function PageState({ error }) {
  return <div className="site-wrap py-32 text-center" data-testid="site-page-state">{error ? <p className="text-[#c2410c]">Could not load this page. Please try again shortly.</p> : <div className="site-loader" />}</div>;
}

function Footer() {
  const [f, setF] = useState(null);
  useEffect(() => { web("/public/site").then((d) => setF(d.footer)).catch(() => {}); }, []);
  return (
    <footer className="site-footer" data-testid="site-footer">
      <div className="site-wrap grid gap-10 py-14 md:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="flex items-center gap-4">
            <img src="/site/logo-128.png" alt="" className="h-16 w-16 rounded-2xl bg-white p-1.5 object-contain shadow-lg" />
            <p className="site-display text-2xl text-[#ffffff]" data-testid="footer-brand">{f?.footer_brand || "Propertys Available"}</p>
          </div>
          <p className="mt-2 text-sm text-[#a9bbe8]" data-testid="footer-byline">{f?.footer_byline}</p>
        </div>
        <nav className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {NAV.map(([to, l]) => <Link key={to} to={to} className="text-[#dbe5ff] transition-colors hover:text-[#f97316]" data-testid={`footer-link-${to.replace("/", "") || "home"}`}>{l}</Link>)}
        </nav>
      </div>
      <div className="border-t border-white/10"><p className="site-wrap py-5 text-xs text-[#8ea2d4]" data-testid="footer-copyright">{f?.footer_copyright}</p></div>
    </footer>
  );
}

export default function SiteLayout() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [pathname]);
  return (
    <div className="site-root" data-testid="public-site">
      <header className="site-header">
        <div className="site-wrap flex h-16 items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5" data-testid="site-logo">
            <img src="/site/logo-128.png" alt="Propertys Available logo" className="h-11 w-11 object-contain" data-testid="site-logo-img" />
            <span className="site-display text-lg text-[#0b1b3f]">Propertys Available</span>
          </Link>
          <nav className="hidden items-center gap-1 lg:flex">
            {NAV.map(([to, l]) => <NavLink key={to} to={to} end className={({ isActive }) => `site-nav ${isActive ? "is-active" : ""}`} data-testid={`nav-${to.replace("/", "") || "home"}`}>{l}</NavLink>)}
          </nav>
          <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label="Menu" data-testid="site-menu-toggle">{open ? <X /> : <Menu />}</button>
        </div>
        {open && <nav className="site-wrap flex flex-col gap-1 pb-4 lg:hidden" data-testid="site-mobile-nav">
          {NAV.map(([to, l]) => <NavLink key={to} to={to} end className={({ isActive }) => `site-nav ${isActive ? "is-active" : ""}`}>{l}</NavLink>)}
        </nav>}
      </header>
      <main><Outlet /></main>
      <Footer />
    </div>
  );
}
