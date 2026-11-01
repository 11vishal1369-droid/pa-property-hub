import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, Users, UserRound, Building2, FileSignature, Wallet, CalendarClock, TicketPercent, MessageSquareWarning,
  DoorOpen, Image, Bell, FileBarChart, Archive, ShieldCheck, ScrollText, Settings, Search, LogOut, Menu, KeyRound } from "lucide-react";
import { Input } from "./ui/input";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { useAuth } from "../context/AuthContext";
import { Avatar } from "./Common";

export const NAV = [
  ["Dashboard", "/", LayoutDashboard, "dashboard"], ["Owners", "/owners", Users, "owners"], ["Tenants", "/tenants", UserRound, "tenants"],
  ["Properties", "/properties", Building2, "properties"], ["Agreements", "/agreements", FileSignature, "agreements"],
  ["Payments & Finance", "/finance", Wallet, "finance"], ["Subscriptions", "/subscriptions", CalendarClock, "subscriptions"],
  ["Coupon Management", "/coupons", TicketPercent, "coupons"], ["Complaints", "/complaints", MessageSquareWarning, "complaints"],
  ["Leaving Requests", "/leaving", DoorOpen, "leaving"], ["Banners", "/banners", Image, "banners"], ["Notifications", "/notifications", Bell, "notifications"],
  ["Reports", "/reports", FileBarChart, "reports"], ["Archived Records", "/archive", Archive, "archive"],
  ["Admin Users & Permissions", "/admins", ShieldCheck, "admins"], ["Audit Logs", "/audit", ScrollText, "audit"], ["Settings", "/settings", Settings, "settings"],
];

const Sidebar = ({ open, close }) => {
  const { can } = useAuth();
  return (
    <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-[#0B1530] text-slate-300 transition-transform duration-300 lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`} data-testid="sidebar">
      <div className="flex h-16 items-center gap-3 border-b border-white/10 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#EA580C] font-heading text-sm font-extrabold text-white shadow-lg shadow-orange-900/40">PA</div>
        <div>
          <p className="font-heading text-sm font-bold leading-tight text-white">PA Super Admin</p>
          <p className="text-[11px] text-slate-400">Property Management Platform</p>
        </div>
      </div>
      <nav className="pa-scroll flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        {NAV.filter((n) => can(n[3])).map(([name, to, Icon]) => (
          <NavLink key={to} to={to} end={to === "/"} onClick={close} data-testid={`nav-${to === "/" ? "dashboard" : to.slice(1)}`}
            className={({ isActive }) => `group flex items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${isActive ? "bg-[#1E3A8A] text-white shadow-inner" : "hover:bg-white/5 hover:text-white"}`}>
            {({ isActive }) => (<>
              <Icon className={`h-4 w-4 ${isActive ? "text-orange-400" : "text-slate-500 group-hover:text-slate-300"}`} />
              <span className="truncate">{name}</span>
              {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-orange-400" />}
            </>)}
          </NavLink>
        ))}
      </nav>
      <p className="border-t border-white/10 px-5 py-3 text-[10px] text-slate-500">No hard deletes · All actions audited</p>
    </aside>
  );
};

export default function Layout() {
  const { admin, logout } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-[#F4F6FA]">
      <Sidebar open={open} close={() => setOpen(false)} />
      {open && <div className="fixed inset-0 z-40 bg-slate-900/40 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/85 px-4 backdrop-blur-md md:px-8">
          <button className="lg:hidden" onClick={() => setOpen(true)} data-testid="sidebar-toggle"><Menu className="h-5 w-5" /></button>
          <form className="relative max-w-xl flex-1" onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/search?q=${encodeURIComponent(q.trim())}`); }}>
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search history: Owner / Tenant / Property / Agreement / Payment ID, mobile, email, name…"
              className="h-9 rounded-full border-slate-200 bg-slate-50 pl-9" data-testid="global-search-input" />
          </form>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden rounded-full border border-orange-200 bg-orange-50 px-2.5 py-1 text-[11px] font-semibold text-orange-700 md:inline" data-testid="role-badge">{admin?.role}</span>
            <DropdownMenu>
              <DropdownMenuTrigger className="flex items-center gap-2 rounded-full p-0.5 hover:bg-slate-100" data-testid="profile-menu-trigger">
                <Avatar name={admin?.name} size="h-8 w-8" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <p className="text-sm">{admin?.name}</p>
                  <p className="text-xs font-normal text-slate-500">{admin?.email}</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => nav("/account/password")} data-testid="menu-change-password"><KeyRound className="mr-2 h-4 w-4" />Change password</DropdownMenuItem>
                <DropdownMenuItem onClick={logout} data-testid="logout-button"><LogOut className="mr-2 h-4 w-4" />Log out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="mx-auto max-w-[1600px] p-4 md:p-8"><Outlet /></main>
      </div>
    </div>
  );
}
