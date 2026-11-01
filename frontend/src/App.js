import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import { OwnersList, TenantsList, PropertiesList } from "./pages/Directories";
import OwnerDetail from "./pages/OwnerDetail";
import TenantDetail from "./pages/TenantDetail";
import PropertyDetail from "./pages/PropertyDetail";
import { AgreementsList, AgreementDetail } from "./pages/Agreements";
import Finance from "./pages/Finance";
import Subscriptions from "./pages/Subscriptions";
import Coupons from "./pages/Coupons";
import Complaints from "./pages/Complaints";
import Leaving from "./pages/Leaving";
import Banners from "./pages/Banners";
import Notifications from "./pages/Notifications";
import Reports from "./pages/Reports";
import ArchivePage from "./pages/Archive";
import Admins from "./pages/Admins";
import AuditLogs from "./pages/AuditLogs";
import SettingsPage from "./pages/Settings";
import SearchPage from "./pages/SearchPage";
import { PasswordCard } from "./pages/Settings";
import { PageHeader } from "./components/Common";

const Guard = ({ children }) => {
  const { admin } = useAuth();
  if (admin === null) return <div className="flex h-screen items-center justify-center text-slate-400" data-testid="auth-loading">Loading…</div>;
  if (!admin) return <Navigate to="/login" replace />;
  return children;
};

const Perm = ({ m, children }) => {
  const { can } = useAuth();
  return can(m) ? children : <div className="pa-card p-10 text-center text-slate-500" data-testid="no-permission">You do not have permission to view this section.</div>;
};

const routes = [
  ["owners", "owners", <OwnersList />], ["owners/:id", "owners", <OwnerDetail />], ["tenants", "tenants", <TenantsList />],
  ["tenants/:id", "tenants", <TenantDetail />], ["properties", "properties", <PropertiesList />], ["properties/:id", "properties", <PropertyDetail />],
  ["agreements", "agreements", <AgreementsList />], ["agreements/:id", "agreements", <AgreementDetail />], ["finance", "finance", <Finance />],
  ["subscriptions", "subscriptions", <Subscriptions />], ["coupons", "coupons", <Coupons />], ["complaints", "complaints", <Complaints />],
  ["leaving", "leaving", <Leaving />], ["banners", "banners", <Banners />], ["notifications", "notifications", <Notifications />],
  ["reports", "reports", <Reports />], ["archive", "archive", <ArchivePage />], ["admins", "admins", <Admins />], ["audit", "audit", <AuditLogs />],
  ["settings", "settings", <SettingsPage />],
];

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Guard><Layout /></Guard>}>
            <Route index element={<Perm m="dashboard"><Dashboard /></Perm>} />
            {routes.map(([p, m, el]) => <Route key={p} path={p} element={<Perm m={m}>{el}</Perm>} />)}
            <Route path="search" element={<SearchPage />} />
            <Route path="account/password" element={<div><PageHeader title="Change password" subtitle="Available to every admin, regardless of role" /><PasswordCard /></div>} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </AuthProvider>
  );
}

export default App;
