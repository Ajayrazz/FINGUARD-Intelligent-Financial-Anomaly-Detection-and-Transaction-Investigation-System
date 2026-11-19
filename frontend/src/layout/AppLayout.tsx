import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { AlertToaster } from "../components/alerts/AlertToaster";
import { Logo } from "../components/fx/Logo";
import { NetworkBackground } from "../components/fx/NetworkBackground";
import { Button } from "../components/ui/Button";

interface NavItem {
  to: string;
  label: string;
  hint: string;
  permission?: string;
}
interface NavGroup {
  label: string;
  items: NavItem[];
}

// Pages are added here by the phase that delivers them (nothing is shown that does not work).
const GROUPS: NavGroup[] = [
  {
    label: "Data",
    items: [
      {
        to: "/transactions",
        label: "Transactions",
        hint: "Search and inspect every payment",
        permission: "transactions.read",
      },
      {
        to: "/imports",
        label: "Imports",
        hint: "Bring in CSV and Excel files",
        permission: "imports.read",
      },
    ],
  },
  {
    label: "Detect",
    items: [
      {
        to: "/detection",
        label: "Anomaly Detection",
        hint: "Score data with trained models",
        permission: "detection.read",
      },
      {
        to: "/graph",
        label: "Relationship Graph",
        hint: "Who paid whom, and rings",
        permission: "graph.read",
      },
      {
        to: "/duplicates",
        label: "Duplicate Detection",
        hint: "Repeated payments and invoices",
        permission: "duplicates.read",
      },
      {
        to: "/risk",
        label: "Risk Analysis",
        hint: "One transparent 0–100 score",
        permission: "risk.read",
      },
    ],
  },
  {
    label: "Respond",
    items: [
      {
        to: "/alerts",
        label: "Alerts",
        hint: "Prioritised queue to review",
        permission: "alerts.read",
      },
      {
        to: "/cases",
        label: "Investigations",
        hint: "Cases, notes and evidence",
        permission: "cases.read",
      },
    ],
  },
  {
    label: "Govern",
    items: [
      {
        to: "/models",
        label: "Model Performance",
        hint: "How well each model performs",
        permission: "models.read",
      },
      {
        to: "/users",
        label: "User Management",
        hint: "People, roles and access",
        permission: "users.read",
      },
      {
        to: "/audit",
        label: "Audit Logs",
        hint: "Append-only record of actions",
        permission: "audit.read",
      },
    ],
  },
];

const linkCls = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2 text-sm transition ${isActive ? "btn-glow text-white" : "text-slate-800 hover:bg-white/10"}`;

export default function AppLayout() {
  const { user, can, logout } = useAuth();
  const [menu, setMenu] = useState(false); // mobile menu
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const { pathname } = useLocation();
  const navRef = useRef<HTMLElement>(null);

  const groups = GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => !i.permission || can(i.permission)),
  })).filter((g) => g.items.length > 0);

  // Close any open menu when the page changes, on Escape, or on a click outside the navigation.
  useEffect(() => {
    setOpenGroup(null);
    setMenu(false);
  }, [pathname]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenGroup(null);
    };
    const onDown = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node))
        setOpenGroup(null);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, []);

  return (
    <div className="relative min-h-screen font-sans text-slate-800">
      <a href="#content" className="skip-link">
        Skip to content
      </a>
      <NetworkBackground />

      <header className="sticky top-3 z-30 mx-auto w-[min(80rem,calc(100%-1rem))]">
        <nav
          aria-label="Main"
          ref={navRef}
          className="glass relative rounded-2xl px-3 py-2 md:rounded-full md:px-4"
        >
          <div className="flex items-center justify-between gap-3">
            <Link
              to="/dashboard"
              className="flex items-center gap-2 font-semibold tracking-wide"
              aria-label="FinGuard dashboard"
            >
              <Logo size={26} />
              <span className="gradient-text">FinGuard</span>
            </Link>

            {/* desktop: grouped menus */}
            <ul className="hidden items-center gap-1 md:flex">
              <li>
                <NavLink to="/dashboard" className={linkCls}>
                  Dashboard
                </NavLink>
              </li>
              {groups.map((g) => (
                <li key={g.label} className="relative">
                  <button
                    type="button"
                    aria-expanded={openGroup === g.label}
                    aria-haspopup="true"
                    onClick={() =>
                      setOpenGroup(openGroup === g.label ? null : g.label)
                    }
                    className={`rounded-lg px-3 py-2 text-sm transition hover:bg-white/10 ${openGroup === g.label ? "bg-white/10" : ""}`}
                  >
                    {g.label} <span aria-hidden="true">▾</span>
                  </button>
                  {openGroup === g.label && (
                    <ul
                      data-group-panel
                      className="glass animate-rise absolute left-0 top-full z-40 mt-3 w-72 space-y-1 rounded-2xl p-2"
                    >
                      {g.items.map((i) => (
                        <li key={i.to}>
                          <NavLink
                            to={i.to}
                            className={({ isActive }) =>
                              `block rounded-xl px-3 py-2 transition ${isActive ? "btn-glow text-white" : "hover:bg-white/10"}`
                            }
                          >
                            <span className="block text-sm font-medium">
                              {i.label}
                            </span>
                            <span className="block text-xs opacity-75">
                              {i.hint}
                            </span>
                          </NavLink>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>

            <div className="flex items-center gap-3 text-sm">
              <span className="hidden lg:inline">
                {user?.full_name} ·{" "}
                <span className="text-slate-600">{user?.role_label}</span>
              </span>
              <Button variant="secondary" onClick={() => void logout()}>
                Sign out
              </Button>
              <button
                type="button"
                className="rounded-md border border-slate-300 px-3 py-1 text-sm md:hidden"
                aria-expanded={menu}
                aria-controls="mobile-menu"
                onClick={() => setMenu((o) => !o)}
              >
                {menu ? "Close menu" : "Menu"}
              </button>
            </div>
          </div>

          {/* mobile: every page in one list */}
          {menu && (
            <div id="mobile-menu" className="mt-3 space-y-3 md:hidden">
              <NavLink to="/dashboard" className={linkCls}>
                Dashboard
              </NavLink>
              {groups.map((g) => (
                <div key={g.label}>
                  <p className="px-3 text-xs uppercase tracking-widest text-slate-500">
                    {g.label}
                  </p>
                  {g.items.map((i) => (
                    <NavLink key={i.to} to={i.to} className={linkCls}>
                      {i.label}
                    </NavLink>
                  ))}
                </div>
              ))}
            </div>
          )}
        </nav>
      </header>

      <main
        id="content"
        tabIndex={-1}
        key={pathname}
        className="animate-rise relative z-10 mx-auto w-[min(80rem,calc(100%-1rem))] pb-10 pt-6 outline-none"
      >
        <AlertToaster />
        <div className="glass rounded-2xl p-3 md:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
