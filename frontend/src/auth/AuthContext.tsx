import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, refreshAccessToken, setAccessToken, setSessionExpiredHandler } from '../api/client'
import type { Me } from '../api/types'

export type AuthStatus = 'loading' | 'anonymous' | 'authenticated'

export interface AuthValue {
  status: AuthStatus
  user: Me | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** UI convenience only — the backend enforces every permission. */
  can: (permission: string) => boolean
}

export const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<Me | null>(null)

  const clear = useCallback(() => {
    setAccessToken(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(clear)
    let cancelled = false
    refreshAccessToken()
      .then(() => api.get<Me>('/auth/me/'))
      .then((me) => {
        if (cancelled) return
        setUser(me)
        setStatus('authenticated')
      })
      .catch(() => {
        if (!cancelled) clear()
      })
    return () => {
      cancelled = true
      setSessionExpiredHandler(null)
    }
  }, [clear])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access: string; user: Me }>('/auth/login/', { email, password }, { skipAuthRetry: true })
    setAccessToken(res.access)
    setUser(res.user)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout/', undefined, { skipAuthRetry: true })
    } finally {
      clear()
    }
  }, [clear])

  const value = useMemo<AuthValue>(
    () => ({ status, user, login, logout, can: (p) => user?.permissions.includes(p) ?? false }),
    [status, user, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
