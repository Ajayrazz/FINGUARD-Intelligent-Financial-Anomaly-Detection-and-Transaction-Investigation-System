import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Me } from '../api/types'
import LoginPage from '../pages/LoginPage'
import { AuthContext, type AuthValue } from './AuthContext'
import { PermissionGate, ProtectedRoute } from './guards'

const me = (permissions: string[]): Me => ({
  id: 1, email: 'a@example.com', full_name: 'A', role: 'auditor', role_label: 'Auditor',
  is_active: true, last_login: null, created_at: '2026-01-01T00:00:00Z', permissions,
})

function value(partial: Partial<AuthValue> & { permissions?: string[] }): AuthValue {
  const user = partial.status === 'anonymous' || partial.status === 'loading' ? null : me(partial.permissions ?? [])
  return {
    status: 'authenticated', user, login: vi.fn(), logout: vi.fn(),
    can: (p) => user?.permissions.includes(p) ?? false, ...partial,
  }
}

function renderAt(path: string, auth: AuthValue, ui = <ProtectedRoute permission="audit.read" />) {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route element={ui}>
            <Route path="/secret" element={<p>secret content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects anonymous visitors to the login page', () => {
    renderAt('/secret', value({ status: 'anonymous' }))
    expect(screen.getByText('login page')).toBeInTheDocument()
    expect(screen.queryByText('secret content')).not.toBeInTheDocument()
  })

  it('shows a loading state while the session is being restored', () => {
    renderAt('/secret', value({ status: 'loading' }))
    expect(screen.getByRole('status')).toHaveTextContent('Restoring session')
  })

  it('shows access denied when the role lacks the permission', () => {
    renderAt('/secret', value({ permissions: [] }))
    expect(screen.getByRole('alert')).toHaveTextContent('Access denied')
    expect(screen.queryByText('secret content')).not.toBeInTheDocument()
  })

  it('renders the page when the permission is held', () => {
    renderAt('/secret', value({ permissions: ['audit.read'] }))
    expect(screen.getByText('secret content')).toBeInTheDocument()
  })
})

describe('PermissionGate', () => {
  it('hides children without the permission and shows them with it', () => {
    const { rerender } = render(
      <AuthContext.Provider value={value({ permissions: [] })}>
        <PermissionGate permission="users.create"><button>Add user</button></PermissionGate>
      </AuthContext.Provider>,
    )
    expect(screen.queryByText('Add user')).not.toBeInTheDocument()
    rerender(
      <AuthContext.Provider value={value({ permissions: ['users.create'] })}>
        <PermissionGate permission="users.create"><button>Add user</button></PermissionGate>
      </AuthContext.Provider>,
    )
    expect(screen.getByText('Add user')).toBeInTheDocument()
  })
})

describe('LoginPage', () => {
  const renderLogin = (login: AuthValue['login']) =>
    render(
      <AuthContext.Provider value={value({ status: 'anonymous', login })}>
        <MemoryRouter><LoginPage /></MemoryRouter>
      </AuthContext.Provider>,
    )

  it('validates fields before calling the API', async () => {
    const login = vi.fn()
    renderLogin(login)
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Email is required')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('shows a generic error when credentials are rejected', async () => {
    const { ApiError } = await import('../api/client')
    const login = vi.fn().mockRejectedValue(new ApiError(401, 'invalid_credentials', 'nope'))
    renderLogin(login)
    await userEvent.type(screen.getByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
    expect(login).toHaveBeenCalledWith('a@example.com', 'wrong')
  })

  it('tells the user when they are rate-limited or locked out', async () => {
    const { ApiError } = await import('../api/client')
    renderLogin(vi.fn().mockRejectedValue(new ApiError(429, 'account_locked', 'locked')))
    await userEvent.type(screen.getByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts')
  })
})
