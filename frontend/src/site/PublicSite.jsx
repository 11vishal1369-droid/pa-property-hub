import { useEffect } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Toaster } from "../components/ui/sonner";
import SiteLayout from "./SiteLayout";
import HomePage from "./HomePage";
import LegalPage from "./LegalPage";
import ContactPage from "./ContactPage";
import WebContent from "./editor/WebContent";

const TITLES = { "/": "Propertys Available", "/terms-conditions": "Terms & Conditions", "/privacy-policy": "Privacy Policy",
  "/refund-policy": "Refund & Cancellation Policy", "/contact-us": "Contact Us" };

function Titled({ path, children }) {
  useEffect(() => { document.title = path === "/" ? TITLES[path] : `${TITLES[path]} · Propertys Available`; }, [path]);
  return children;
}

const NotFound = () => (
  <div className="site-wrap py-32 text-center" data-testid="site-not-found">
    <p className="site-display text-4xl text-[#1f3d2b]">Page not found</p>
    <Link to="/" className="site-link mt-4 inline-block">Back to the homepage</Link>
  </div>
);

export default function PublicSite() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/webcontent/*" element={<WebContent />} />
        <Route element={<SiteLayout />}>
          <Route index element={<Titled path="/"><HomePage /></Titled>} />
          {["terms-conditions", "privacy-policy", "refund-policy"].map((s) => <Route key={s} path={s} element={<Titled path={`/${s}`}><LegalPage slug={s} /></Titled>} />)}
          <Route path="contact-us" element={<Titled path="/contact-us"><ContactPage /></Titled>} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      <Toaster position="top-right" richColors />
    </BrowserRouter>
  );
}
