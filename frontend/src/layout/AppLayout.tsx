import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { AlertToaster } from "../components/alerts/AlertToaster";
import { Button } from "../components/ui/Button";

interface NavItem {
  to: string;
  label: string;
  permission?: string;
}
// Pages are added to this list by the phase that delivers them (nothing is shown that does not work).
const NAV: NavItem[] = [
  { to: "/", label: "System Status" },
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
  return (
    <div className="flex min-h-screen flex-col font-sans text-slate-900 md:flex-row">
      <nav
        aria-label="Main"
        className="shrink-0 border-b border-slate-200 bg-slate-50 p-4 md:w-56 md:border-b-0 md:border-r"
      >
        <div className="flex items-center justify-between">
          <p className="text-lg font-semibold">FinGuard</p>
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
                end={n.to === "/"}
                className={({ isActive }) =>
                  `block rounded-md px-3 py-2 text-sm ${isActive ? "bg-slate-900 text-white" : "hover:bg-slate-200"}`
                }
              >
                {n.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-end gap-x-4 gap-y-2 border-b border-slate-200 px-4 py-3 text-sm md:px-6">
          <span>
            {user?.full_name} ·{" "}
            <span className="text-slate-600">{user?.role_label}</span>
          </span>
          <Button variant="secondary" onClick={() => void logout()}>
            Sign out
          </Button>
        </header>
        <main className="p-4 md:p-6">
          <AlertToaster />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
