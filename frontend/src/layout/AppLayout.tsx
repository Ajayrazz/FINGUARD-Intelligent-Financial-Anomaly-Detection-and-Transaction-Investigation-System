import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui/Button'

interface NavItem {
  to: string
  label: string
  permission?: string
}
// Pages are added to this list by the phase that delivers them (nothing is shown that does not work).
const NAV: NavItem[] = [
  { to: '/', label: 'System Status' },
  { to: '/transactions', label: 'Transactions', permission: 'transactions.read' },
  { to: '/imports', label: 'Imports', permission: 'imports.read' },
  { to: '/users', label: 'User Management', permission: 'users.read' },
  { to: '/audit', label: 'Audit Logs', permission: 'audit.read' },
]

export default function AppLayout() {
  const { user, can, logout } = useAuth()
  return (
    <div className="flex min-h-screen font-sans text-slate-900">
      <nav aria-label="Main" className="w-56 shrink-0 border-r border-slate-200 bg-slate-50 p-4">
        <p className="text-lg font-semibold">FinGuard</p>
        <ul className="mt-6 space-y-1">
          {NAV.filter((n) => !n.permission || can(n.permission)).map((n) => (
            <li key={n.to}>
              <NavLink
                to={n.to}
                end={n.to === '/'}
                className={({ isActive }) =>
                  `block rounded-md px-3 py-2 text-sm ${isActive ? 'bg-slate-900 text-white' : 'hover:bg-slate-200'}`
                }
              >
                {n.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="flex-1">
        <header className="flex items-center justify-end gap-4 border-b border-slate-200 px-6 py-3 text-sm">
          <span>
            {user?.full_name} · <span className="text-slate-600">{user?.role_label}</span>
          </span>
          <Button variant="secondary" onClick={() => void logout()}>
            Sign out
          </Button>
        </header>
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
