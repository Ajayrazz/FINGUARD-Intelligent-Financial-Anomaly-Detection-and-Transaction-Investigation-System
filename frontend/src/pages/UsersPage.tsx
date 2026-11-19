import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api, ApiError } from '../api/client'
import type { Paginated, PermissionInfo, Role, User } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/states'
import { useToast } from '../components/ui/Toast'

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const details = Object.entries(e.details)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`)
      .join(' · ')
    return details || e.message
  }
  return 'Unexpected error'
}

export default function UsersPage() {
  const [tab, setTab] = useState<'users' | 'roles'>('users')
  const { can } = useAuth()
  return (
    <section>
      <h1 className="text-2xl font-semibold">User management</h1>
      <div role="tablist" className="mt-4 flex gap-2 border-b border-slate-200">
        {(['users', 'roles'] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            disabled={t === 'roles' && !can('roles.read')}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm capitalize ${tab === t ? 'border-b-2 border-slate-900 font-medium' : 'text-slate-600'}`}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="mt-4">{tab === 'users' ? <UsersTab /> : <RolesTab />}</div>
    </section>
  )
}

// ------------------------------------------------------------------ users
const createSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email'),
  full_name: z.string().min(1, 'Name is required'),
  role: z.string().min(1, 'Select a role'),
  password: z.string().min(12, 'At least 12 characters'),
})
type CreateValues = z.infer<typeof createSchema>

function UsersTab() {
  const { can, user: me } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [toggling, setToggling] = useState<User | null>(null)
  const [resetting, setResetting] = useState<User | null>(null)

  const params = new URLSearchParams({ page: String(page) })
  if (search) params.set('search', search)
  const users = useQuery({
    queryKey: ['users', search, page],
    queryFn: ({ signal }) => api.get<Paginated<User>>(`/users/?${params.toString()}`, signal),
  })
  const roles = useQuery({ queryKey: ['roles'], queryFn: ({ signal }) => api.get<Role[]>('/roles/', signal) })

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Pick<User, 'role' | 'is_active'>> }) =>
      api.patch<User>(`/users/${id}/`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      toast('success', 'User updated')
    },
    onError: (e) => toast('error', errorText(e)),
  })

  return (
    <div>
      <div className="flex items-end justify-between gap-3">
        <label className="text-sm">
          Search
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            placeholder="Name or email"
            className="mt-1 block rounded-md border border-slate-300 px-2 py-1"
          />
        </label>
        {can('users.create') && <Button onClick={() => setCreating(true)}>Add user</Button>}
      </div>

      <div className="mt-4">
        {users.isPending && <LoadingState />}
        {users.isError && <ErrorState message={users.error.message} onRetry={() => void users.refetch()} />}
        {users.data && users.data.results.length === 0 && <EmptyState title="No users found" />}
        {users.data && users.data.results.length > 0 && (
          <>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-300 text-slate-600">
                <tr>
                  <th className="py-2">Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last login</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.data.results.map((u) => (
                  <tr key={u.id} className="border-b border-slate-100">
                    <td className="py-2">{u.full_name}</td>
                    <td>{u.email}</td>
                    <td>
                      {can('users.update') && roles.data && u.id !== me?.id ? (
                        <select
                          aria-label={`Role for ${u.email}`}
                          value={u.role}
                          onChange={(e) => patch.mutate({ id: u.id, body: { role: e.target.value } })}
                          className="rounded-md border border-slate-300 px-1 py-0.5"
                        >
                          {roles.data.map((r) => (
                            <option key={r.id} value={r.name}>{r.label}</option>
                          ))}
                        </select>
                      ) : (
                        u.role_label
                      )}
                    </td>
                    <td>
                      <span className={u.is_active ? 'text-risk-low' : 'text-slate-500'}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>{u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}</td>
                    <td className="space-x-2 text-right">
                      {can('users.update') && u.id !== me?.id && (
                        <>
                          <Button variant="secondary" onClick={() => setResetting(u)}>Reset password</Button>
                          <Button variant={u.is_active ? 'danger' : 'secondary'} onClick={() => setToggling(u)}>
                            {u.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex items-center gap-3 text-sm">
              <Button variant="secondary" disabled={!users.data.previous} onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <span>Page {page} · {users.data.count} users</span>
              <Button variant="secondary" disabled={!users.data.next} onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          </>
        )}
      </div>

      <CreateUserDialog open={creating} roles={roles.data ?? []} onClose={() => setCreating(false)} />

      <Dialog open={toggling !== null} title={toggling?.is_active ? 'Deactivate user?' : 'Activate user?'} onClose={() => setToggling(null)}>
        <p className="text-sm">
          {toggling?.is_active
            ? `${toggling.email} will be signed out everywhere and unable to log in.`
            : `${toggling?.email ?? ''} will be able to log in again.`}
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setToggling(null)}>Cancel</Button>
          <Button
            onClick={() => {
              if (toggling) patch.mutate({ id: toggling.id, body: { is_active: !toggling.is_active } })
              setToggling(null)
            }}
          >
            Confirm
          </Button>
        </div>
      </Dialog>

      <ResetPasswordDialog user={resetting} onClose={() => setResetting(null)} />
    </div>
  )
}

function CreateUserDialog({ open, roles, onClose }: { open: boolean; roles: Role[]; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues>({ resolver: zodResolver(createSchema), defaultValues: { role: '' } })

  const submit = async (v: CreateValues) => {
    setServerError(null)
    try {
      await api.post<User>('/users/', v)
      await qc.invalidateQueries({ queryKey: ['users'] })
      toast('success', `Created ${v.email}`)
      reset()
      onClose()
    } catch (e) {
      setServerError(errorText(e))
    }
  }
  const field = 'mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5'
  return (
    <Dialog open={open} title="Add user" onClose={onClose}>
      <form onSubmit={handleSubmit(submit)} noValidate className="space-y-3">
        <label className="block text-sm">Full name
          <input className={field} {...register('full_name')} />
          {errors.full_name && <span className="text-red-700">{errors.full_name.message}</span>}
        </label>
        <label className="block text-sm">Email
          <input type="email" className={field} {...register('email')} />
          {errors.email && <span className="text-red-700">{errors.email.message}</span>}
        </label>
        <label className="block text-sm">Role
          <select className={field} {...register('role')}>
            <option value="">Select…</option>
            {roles.map((r) => <option key={r.id} value={r.name}>{r.label}</option>)}
          </select>
          {errors.role && <span className="text-red-700">{errors.role.message}</span>}
        </label>
        <label className="block text-sm">Initial password
          <input type="password" autoComplete="new-password" className={field} {...register('password')} />
          {errors.password && <span className="text-red-700">{errors.password.message}</span>}
        </label>
        {serverError && <p role="alert" className="text-sm text-red-700">{serverError}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={isSubmitting}>Create</Button>
        </div>
      </form>
    </Dialog>
  )
}

function ResetPasswordDialog({ user, onClose }: { user: User | null; onClose: () => void }) {
  const toast = useToast()
  const [pw, setPw] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const submit = async () => {
    if (!user) return
    setErr(null)
    try {
      await api.post(`/users/${user.id}/reset-password/`, { new_password: pw })
      toast('success', `Password reset for ${user.email}`)
      setPw('')
      onClose()
    } catch (e) {
      setErr(errorText(e))
    }
  }
  return (
    <Dialog open={user !== null} title="Reset password" onClose={onClose}>
      <label className="block text-sm">New password for {user?.email}
        <input
          type="password"
          autoComplete="new-password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5"
        />
      </label>
      {err && <p role="alert" className="mt-2 text-sm text-red-700">{err}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={() => void submit()} disabled={pw.length < 12}>Reset</Button>
      </div>
    </Dialog>
  )
}

// ------------------------------------------------------------------ roles
function RolesTab() {
  const { can } = useAuth()
  const roles = useQuery({ queryKey: ['roles'], queryFn: ({ signal }) => api.get<Role[]>('/roles/', signal) })
  const perms = useQuery({ queryKey: ['permissions'], queryFn: ({ signal }) => api.get<PermissionInfo[]>('/permissions/', signal) })

  if (roles.isPending || perms.isPending) return <LoadingState />
  if (roles.isError) return <ErrorState message={roles.error.message} onRetry={() => void roles.refetch()} />
  if (perms.isError) return <ErrorState message={perms.error.message} onRetry={() => void perms.refetch()} />
  return (
    <div className="space-y-4">
      {roles.data.map((r) => (
        <RoleCard key={r.id} role={r} all={perms.data} editable={can('roles.update') && r.name !== 'super_admin'} />
      ))}
    </div>
  )
}

function RoleCard({ role, all, editable }: { role: Role; all: PermissionInfo[]; editable: boolean }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [selected, setSelected] = useState<Set<string>>(new Set(role.permissions))
  const dirty = selected.size !== role.permissions.length || role.permissions.some((p) => !selected.has(p))
  const save = useMutation({
    mutationFn: () => api.patch<Role>(`/roles/${role.id}/`, { permissions: [...selected] }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['roles'] })
      toast('success', `${role.label} permissions saved`)
    },
    onError: (e) => toast('error', errorText(e)),
  })
  return (
    <fieldset className="rounded-lg border border-slate-200 p-4" disabled={!editable}>
      <legend className="px-1 font-medium">{role.label}</legend>
      <p className="text-sm text-slate-600">{role.description}</p>
      <div className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
        {all.map((p) => (
          <label key={p.codename} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.has(p.codename)}
              onChange={(e) => {
                const next = new Set(selected)
                if (e.target.checked) next.add(p.codename)
                else next.delete(p.codename)
                setSelected(next)
              }}
            />
            <span className="font-mono">{p.codename}</span>
            <span className="text-slate-500">{p.description}</span>
          </label>
        ))}
      </div>
      {editable && (
        <div className="mt-3">
          <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save permissions</Button>
        </div>
      )}
      {role.name === 'super_admin' && <p className="mt-2 text-xs text-slate-500">Super Admin always holds every permission.</p>}
    </fieldset>
  )
}
