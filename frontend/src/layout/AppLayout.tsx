import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { AlertToaster } from "../components/alerts/AlertToaster";
import { NetworkBackground } from "../components/fx/NetworkBackground";
import { Logo } from "../components/fx/Logo";
import { Button } from "../components/ui/Button";

interface NavItem {
  to: string;
  label: string;
  permission?: string;
}
// Pages are added to this list by the phase that delivers them (nothing is shown that does not work).
const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard" },
  {
    to: "/transactions",
    label: "Transactions",
    permission: "transactions.read",
  },
  { to: "/imports", label: "Imports", permission: "imports.read" },
  {
    to: "/detection",
    label: "Anomaly Detection",
    permission: "detection.read",
  },
  { to: "/graph", label: "Relationship Graph", permission: "graph.read" },
  {
    to: "/duplicates",
    label: "Duplicate Detection",
    permission: "duplicates.read",
  },
  { to: "/risk", label: "Risk Analysis", permission: "risk.read" },
  { to: "/alerts", label: "Alerts", permission: "alerts.read" },
  { to: "/cases", label: "Investigations", permission: "cases.read" },
  { to: "/models", label: "Model Performance", permission: "models.read" },
  { to: "/users", label: "User Management", permission: "users.read" },
  { to: "/audit", label: "Audit Logs", permission: "audit.read" },
];

export default function AppLayout() {
  const { user, can, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  return (
    <div className="relative flex min-h-screen flex-col font-sans text-slate-800 md:flex-row">
      <a href="#content" className="skip-link">
        Skip to content
      </a>
      <NetworkBackground />
      <nav
        aria-label="Main"
        className="glass relative z-10 shrink-0 border-0 border-b p-4 md:sticky md:top-0 md:h-screen md:w-60 md:overflow-y-auto md:border-b-0 md:border-r"
      >
        <div className="flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-2 text-lg font-semibold tracking-wide"
            aria-label="FinGuard home"
          >
            <Logo />
            <span className="gradient-text">FinGuard</span>
          </Link>
          <button
            type="button"
            className="rounded-md border border-slate-300 px-3 py-1 text-sm md:hidden"
            aria-expanded={open}
            aria-controls="main-menu"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? "Close menu" : "Menu"}
          </button>
        </div>
        <ul
          id="main-menu"
          className={`mt-6 space-y-1 ${open ? "block" : "hidden"} md:block`}
          onClick={() => setOpen(false)}
        >
          {NAV.filter((n) => !n.permission || can(n.permission)).map((n) => (
            <li key={n.to}>
              <NavLink
                to={n.to}
                end={n.to === "/dashboard"}
                className={({ isActive }) =>
                  `block rounded-lg px-3 py-2 text-sm transition-all duration-200 ${isActive ? "btn-glow text-white" : "text-slate-700 hover:translate-x-1 hover:bg-white/10"}`
                }
              >
                {n.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="relative z-10 min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-end gap-x-4 gap-y-2 px-4 py-3 text-sm md:px-6">
          <span>
            {user?.full_name} ·{" "}
            <span className="text-slate-600">{user?.role_label}</span>
          </span>
          <Button variant="secondary" onClick={() => void logout()}>
            Sign out
          </Button>
        </header>
        <main
          id="content"
          tabIndex={-1}
          className="glass animate-rise mb-4 rounded-xl p-3 outline-none md:mx-6 md:mb-6 md:rounded-2xl md:p-6"
          key={pathname}
        >
          <AlertToaster />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
