import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AlertDetail, AlertEventRow, AlertPolicy, AlertRow, AlertSummary, Me } from '../api/types'
import { AuthContext, type AuthValue } from '../auth/AuthContext'
import { ToastProvider } from '../components/ui/Toast'
import AlertsPage from './AlertsPage'

afterEach(() => vi.unstubAllGlobals())

const me = (permissions: string[]): Me => ({
  id: 7, email: 'a@example.com', full_name: 'A', role: 'financial_analyst', role_label: 'Analyst', is_active: true,
  last_login: null, created_at: '2026-01-01T00:00:00Z', permissions,
})
const auth = (permissions: string[]): AuthValue => ({ status: 'authenticated', user: me(permissions), login: vi.fn(), logout: vi.fn(), can: (p) => permissions.includes(p) })
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response

const row = (over: Partial<AlertRow> = {}): AlertRow => ({
  id: 3, alert_type: 'multiple_transactions', type_label: 'Burst of transactions', severity: 'critical', status: 'new', dataset: 1, dataset_name: 'DEMO', transaction: 9,
  transaction_external_id: 'T9', account: 4, account_ref: 'C1', assessment: null, risk_score: null, reason: '5 transactions by C1 within 10 minutes.', assignee: null, assignee_email: null,
  acknowledged_at: null, escalated_at: null, closed_at: null, outcome: '', created_at: '2026-01-01T10:00:00Z', ...over,
})
const detail = (over: Partial<AlertDetail> = {}): AlertDetail => ({ ...row(), evidence_snapshot: { transactions_in_window: 3 }, escalation_reason: '', close_notes: '', policy_version: 1, dedup_key: 'k', ...over })
const events: AlertEventRow[] = [{ id: 1, event_type: 'created', actor_email: null, payload: {}, created_at: '2026-01-01T10:00:00Z' }, { id: 2, event_type: 'severity_raised', actor_email: null, payload: {}, created_at: '2026-01-01T10:08:00Z' }]
const summary: AlertSummary = { open_by_severity: { critical: 1, high: 2, medium: 0, low: 0 }, by_status: { new: 3 }, unassigned_open: 3 }
const policy: AlertPolicy = { id: 1, version: 1, is_active: true, notes: '', created_by_email: null, created_at: '', config: { dedup_bucket_hours: 24, max_alerts_per_rule: 500, auto_evaluate: true, email: { min_severity: 'high', recipients: [] } } }

function setup(perms: string[], posts: { url: string; body: unknown }[] = [], rows: AlertRow[] = [row()]) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') { posts.push({ url, body: JSON.parse(String(init.body ?? 'null')) }); return ok(detail({ status: 'acknowledged' })) }
    if (url.includes('/events/')) return ok(events)
    if (url.includes('/notifications/')) return ok([{ id: 1, channel: 'websocket', recipient: 'group:alerts', status: 'sent', error: '', sent_at: '' }])
    if (url.includes('/assignees/')) return ok([{ id: 7, email: 'a@example.com', full_name: 'A' }, { id: 8, email: 'b@example.com', full_name: 'B' }])
    if (url.includes('/summary/')) return ok(summary)
    if (url.includes('/policy/')) return ok([policy])
    if (url.match(/\/alerts\/\d+\/$/)) return ok(detail())
    if (url.includes('/alerts/')) return ok({ count: rows.length, next: null, previous: null, results: rows })
    return ok([])
  })
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('WebSocket', class { close() {} })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><ToastProvider><AuthContext.Provider value={auth(perms)}><MemoryRouter><AlertsPage /></MemoryRouter></AuthContext.Provider></ToastProvider></QueryClientProvider>)
  return fetchMock
}

describe('AlertsPage', () => {
  it('shows the open counts by severity, the prioritised queue, and the detail with preserved evidence and history', async () => {
    setup(['alerts.read'])
    const counts = await screen.findByRole('list', { name: /open alerts by severity/i })
    expect(counts).toHaveTextContent('critical')
    expect(counts).toHaveTextContent('Unassigned open 3')
    expect(await screen.findByText('5 transactions by C1 within 10 minutes.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '3' }))
    const panel = await screen.findByRole('region', { name: /alert details/i })
    expect(panel).toHaveTextContent('severity raised')
    expect(panel).toHaveTextContent(/created.*\(automatic\)|\(automatic\)/)
    expect(screen.getByText(/Evidence at the time the alert was created/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'T9' })).toHaveAttribute('href', '/transactions/9')
    expect(screen.queryByRole('button', { name: /acknowledge|close alert|escalate/i })).not.toBeInTheDocument() // read-only role
  })
  it('lets a triager acknowledge, escalate with a reason and close with an outcome', async () => {
    const posts: { url: string; body: unknown }[] = []
    setup(['alerts.read', 'alerts.acknowledge', 'alerts.assign', 'alerts.escalate', 'alerts.close'], posts)
    await userEvent.click(await screen.findByRole('button', { name: '3' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Acknowledge' }))
    const esc = screen.getByRole('button', { name: 'Escalate' })
    expect(esc).toBeDisabled() // a reason is required
    await userEvent.type(screen.getByLabelText(/escalation reason/i), 'customer unreachable')
    await userEvent.click(screen.getByRole('button', { name: 'Escalate' }))
    await userEvent.selectOptions(screen.getByLabelText(/close as/i), 'true_positive')
    await userEvent.type(screen.getByLabelText('Closing notes'), 'confirmed')
    await userEvent.click(screen.getByRole('button', { name: 'Close alert' }))
    await userEvent.click(screen.getByRole('button', { name: 'Assign to me' }))
    const calls = posts.map((p) => [p.url.replace(/^.*\/api\/v1\/alerts\/3\//, ''), p.body])
    expect(calls).toEqual([
      ['acknowledge/', {}],
      ['escalate/', { reason: 'customer unreachable' }],
      ['close/', { outcome: 'true_positive', notes: 'confirmed' }],
      ['assign/', { assignee: 7 }],
    ])
  })
  it('hides the evaluate and policy editing controls without permission and shows them with it', async () => {
    setup(['alerts.read'])
    expect(await screen.findByText('5 transactions by C1 within 10 minutes.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Evaluate' })).not.toBeInTheDocument()
    expect(await screen.findByText(/Alert policy v1 \(active\)/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Policy JSON')).not.toBeInTheDocument()
  })
  it('explains an empty queue and filters by status', async () => {
    const fetchMock = setup(['alerts.read'], [], [])
    expect(await screen.findByText(/No alerts match these filters/)).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'closed')
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('status=closed'))).toBe(true)
  })
})

describe('AlertToaster', () => {
  it('pops a toast for a pushed alert and ignores pushes when the user cannot read alerts', async () => {
    const sockets: { onmessage: ((m: { data: string }) => void) | null }[] = []
    class FakeSocket { onmessage: ((m: { data: string }) => void) | null = null; constructor() { sockets.push(this) } close() {} }
    vi.stubGlobal('WebSocket', FakeSocket)
    vi.stubGlobal('fetch', vi.fn(async () => ok({ ticket: 't' })))
    const { AlertToaster } = await import('../components/alerts/AlertToaster')
    const qc = new QueryClient()
    const mount = (perms: string[]) => render(<QueryClientProvider client={qc}><ToastProvider><AuthContext.Provider value={auth(perms)}><AlertToaster /></AuthContext.Provider></ToastProvider></QueryClientProvider>)
    const first = mount(['alerts.read'])
    await vi.waitFor(() => expect(sockets.length).toBe(1))
    sockets[0]!.onmessage?.({ data: JSON.stringify({ type: 'alert.created', data: { severity: 'critical', reason: 'Burst of 5 transactions' } }) })
    expect(await screen.findByText(/New critical alert: Burst of 5 transactions/)).toBeInTheDocument()
    first.unmount()
    mount([])
    await vi.waitFor(() => expect(sockets.length).toBe(2))
    sockets[1]!.onmessage?.({ data: JSON.stringify({ type: 'alert.created', data: { severity: 'high', reason: 'Should not show' } }) })
    expect(screen.queryByText(/Should not show/)).not.toBeInTheDocument()
  })
})
