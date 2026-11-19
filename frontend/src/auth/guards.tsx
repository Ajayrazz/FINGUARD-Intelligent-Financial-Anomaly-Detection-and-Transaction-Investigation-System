import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { LoadingState } from '../components/ui/states'
import { useAuth } from './AuthContext'

/** Redirects anonymous visitors to /login; optionally requires a permission (else shows 403 page). */
export function ProtectedRoute({ permission }: { permission?: string }) {
  const { status, can } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingState label="Restoring session…" />
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (permission && !can(permission)) return <Forbidden />
  return <Outlet />
}

export function Forbidden() {
  return (
    <div role="alert" className="p-8">
      <h1 className="text-xl font-semibold">Access denied</h1>
      <p className="mt-2 text-slate-600">Your role does not include access to this page.</p>
    </div>
  )
}

/** Hides children when the user lacks the permission. Cosmetic only; the API still enforces access. */
export function PermissionGate({
  permission,
  children,
  fallback = null,
}: {
  permission: string
  children: ReactNode
  fallback?: ReactNode
}) {
  const { can } = useAuth()
  return <>{can(permission) ? children : fallback}</>
}
