import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CaseDetail, CaseEventRow, CaseNoteRow, CaseRow, CaseSummary, Me } from '../api/types'
import { AuthContext, type AuthValue } from '../auth/AuthContext'
import { ToastProvider } from '../components/ui/Toast'
import CaseDetailPage from './CaseDetailPage'
import CasesPage from './CasesPage'

afterEach(() => vi.unstubAllGlobals())

const me = (permissions: string[]): Me => ({
  id: 7, email: 'inv@example.com', full_name: 'Inv', role: 'fraud_investigator', role_label: 'Investigator', is_active: true,
  last_login: null, created_at: '2026-01-01T00:00:00Z', permissions,
})
const auth = (permissions: string[]): AuthValue => ({ status: 'authenticated', user: me(permissions), login: vi.fn(), logout: vi.fn(), can: (p) => permissions.includes(p) })
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response

const row = (over: Partial<CaseRow> = {}): CaseRow => ({
  id: 2, case_ref: 'FG-2026-000002', title: 'Burst of transactions: 5 transactions by C1', priority: 'critical', status: 'new', dataset: 1, assignee: null, assignee_email: null,
  created_by_email: null, auto_created: true, opened_at: '2026-01-01T10:00:00Z', outcome: '', closed_at: null, alert_count: 2, transaction_count: 5, ...over,
})
const summary: CaseSummary = { by_status: { new: 1 }, open_by_priority: { critical: 1, high: 0, medium: 0, low: 0 }, outcomes: {}, unassigned_open: 1 }

function renderCases(perms: string[], rows: CaseRow[] = [row()], posts: { url: string; body: unknown }[] = []) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') { posts.push({ url, body: JSON.parse(String(init.body)) }); return ok(row({ id: 9, case_ref: 'FG-2026-000009', auto_created: false })) }
    if (url.includes('/summary/')) return ok(summary)
    return ok({ count: rows.length, next: null, previous: null, results: rows })
  })
  vi.stubGlobal('fetch', fetchMock)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><ToastProvider><AuthContext.Provider value={auth(perms)}><MemoryRouter><Routes><Route path="/" element={<CasesPage />} /><Route path="/cases/:id" element={<p>case page</p>} /></Routes></MemoryRouter></AuthContext.Provider></ToastProvider></QueryClientProvider>)
  return fetchMock
}

describe('CasesPage', () => {
  it('lists cases with priority, status, auto-created marker and counts; search and filters go to the API', async () => {
    const fetchMock = renderCases(['cases.read', 'cases.summary'])
    expect(await screen.findByRole('link', { name: 'FG-2026-000002' })).toHaveAttribute('href', '/cases/2')
    expect(screen.getByText('auto')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: /open cases by priority/i })).toHaveTextContent('Unassigned open 1')
    await userEvent.type(screen.getByLabelText('Search'), 'FG-2026')
    await userEvent.selectOptions(screen.getByLabelText('Priority'), 'critical')
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('search=FG-2026') && String(c[0]).includes('priority=critical'))).toBe(true)
    expect(screen.queryByRole('button', { name: 'New case' })).not.toBeInTheDocument() // no cases.create
  })
  it('opens a new case and goes to it', async () => {
    const posts: { url: string; body: unknown }[] = []
    renderCases(['cases.read', 'cases.create'], [row()], posts)
    await userEvent.click(await screen.findByRole('button', { name: 'New case' }))
    const open = screen.getByRole('button', { name: 'Open case' })
    expect(open).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Title'), 'Suspicious refunds')
    await userEvent.click(open)
    expect(await screen.findByText('case page')).toBeInTheDocument()
    expect(posts[0]!.body).toMatchObject({ title: 'Suspicious refunds', priority: 'medium' })
  })
  it('explains an empty result', async () => {
    renderCases(['cases.read'], [])
    expect(await screen.findByText('No cases match')).toBeInTheDocument()
  })
})

const detail = (over: Partial<CaseDetail> = {}): CaseDetail => ({
  ...row(), description: 'desc', resolution_summary: '', resolved_at: null, resolved_by_email: null, closed_by_email: null, allowed_transitions: ['under_review'], read_only_reason: null,
  alerts: [{ id: 5, alert_type: 'multiple_transactions', type_label: 'Burst of transactions', severity: 'critical', status: 'new', dataset: 1, dataset_name: 'D', transaction: 9, transaction_external_id: 'T9', account: 4, account_ref: 'C1', assessment: null, risk_score: null, reason: '5 transactions', assignee: null, assignee_email: null, acknowledged_at: null, escalated_at: null, closed_at: null, outcome: '', created_at: '' }],
  ...over,
})
const note = (over: Partial<CaseNoteRow> = {}): CaseNoteRow => ({ id: 1, kind: 'note', author: 7, author_email: 'inv@example.com', body: 'first text', revision_count: 1, edited: false, created_at: '2026-01-02T00:00:00Z', ...over })
const events: CaseEventRow[] = [{ id: 1, event_type: 'created', actor_email: null, from_status: '', to_status: 'new', payload: {}, created_at: '2026-01-01T10:00:00Z' }]

function renderDetail(perms: string[], c: CaseDetail, notes: CaseNoteRow[] = [], posts: { url: string; method: string; body: unknown }[] = []) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST' || init?.method === 'PATCH') { posts.push({ url: url.replace(/^.*\/api\/v1/, ''), method: init.method, body: init.body instanceof FormData ? 'form' : JSON.parse(String(init.body)) }); return ok(c) }
    if (url.match(/\/notes\/\d+\/$/)) return ok([{ revision: 1, body: 'first text', edited_by: 'inv@example.com' }, { revision: 2, body: 'second text', edited_by: 'inv@example.com' }])
    if (url.includes('/notes/')) return ok(notes)
    if (url.includes('/events/')) return ok(events)
    if (url.includes('/transactions/')) return ok([{ id: 1, transaction: 9, external_id: 'T9', amount: '40000.00', tx_type: 'PAYMENT', occurred_at: '2026-01-01T10:00:00Z', sender: 'C1', receiver: 'N1', note: 'from alert #5' }])
    if (url.includes('/accounts/')) return ok([{ id: 4, account_ref: 'C1', account_type: 'customer', roles: ['sender'] }])
    if (url.includes('/evidence/')) return ok([{ id: 1, original_name: 'statement.pdf', sha256: 'a'.repeat(64), mime: 'application/pdf', size: 2048, description: '', uploaded_by_email: 'inv@example.com', created_at: '2026-01-02T00:00:00Z' }])
    if (url.includes('/assignees/')) return ok([{ id: 7, email: 'inv@example.com', full_name: 'Inv' }])
    return ok(c)
  })
  vi.stubGlobal('fetch', fetchMock)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><ToastProvider><AuthContext.Provider value={auth(perms)}><MemoryRouter initialEntries={['/cases/2']}><Routes><Route path="/cases/:id" element={<CaseDetailPage />} /></Routes></MemoryRouter></AuthContext.Provider></ToastProvider></QueryClientProvider>)
}
const ALL = ['cases.read', 'cases.create', 'cases.update', 'cases.assign', 'cases.transition', 'cases.escalate', 'cases.resolve', 'cases.close', 'cases.comment', 'cases.note', 'cases.evidence']

describe('CaseDetailPage', () => {
  it('shows the workspace: alerts, transactions, accounts with network links, evidence hash, timeline and the non-proof note', async () => {
    renderDetail([...ALL, 'graph.read'], detail(), [note()])
    expect(await screen.findByText(/FG-2026-000002/)).toBeInTheDocument()
    expect(screen.getByText(/opened .* automatically/)).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'T9' })).toHaveAttribute('href', '/transactions/9')
    expect(screen.getByRole('link', { name: 'network' })).toHaveAttribute('href', '/accounts/4/graph')
    expect(screen.getByRole('link', { name: 'Burst of transactions' })).toHaveAttribute('href', '/alerts?open=5')
    expect(await screen.findByText(/SHA-256 aaaaaaaaaaaaaaaa…/)).toBeInTheDocument()
    expect(await screen.findByText(/created \(start → New\) · automatic/)).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(/not proof of wrongdoing/)
  })
  it('offers only the transitions the server allows and sends the right request', async () => {
    const posts: { url: string; method: string; body: unknown }[] = []
    renderDetail(ALL, detail({ allowed_transitions: ['under_review'] }), [], posts)
    await userEvent.click(await screen.findByRole('button', { name: 'Take for review' }))
    expect(posts[0]).toMatchObject({ url: '/cases/2/transition/', body: { to_status: 'under_review' } })
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument()
  })
  it('requires a reason to escalate and an outcome plus summary to resolve', async () => {
    const posts: { url: string; method: string; body: unknown }[] = []
    renderDetail(ALL, detail({ status: 'investigation', allowed_transitions: ['escalated', 'resolved'] }), [], posts)
    expect(await screen.findByRole('button', { name: 'Escalate' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Resolve' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/escalation reason/i), 'needs a lead')
    await userEvent.click(screen.getByRole('button', { name: 'Escalate' }))
    await userEvent.selectOptions(screen.getByLabelText('Outcome'), 'false_positive')
    await userEvent.type(screen.getByLabelText(/resolution summary/i), 'legitimate payments')
    await userEvent.click(screen.getByRole('button', { name: 'Resolve' }))
    expect(posts.map((p) => [p.url, p.body])).toEqual([['/cases/2/escalate/', { reason: 'needs a lead' }], ['/cases/2/resolve/', { outcome: 'false_positive', summary: 'legitimate payments' }]])
  })
  it('a closed case is read-only: banner, outcome, no actions or forms, history still visible', async () => {
    renderDetail(ALL, detail({ status: 'closed', allowed_transitions: [], read_only_reason: 'This case is closed: it is read-only, but its history remains viewable.', outcome: 'false_positive', resolution_summary: 'legit', resolved_by_email: 'inv@example.com' }), [note()])
    expect(await screen.findByText(/read-only, but its history remains viewable/)).toBeInTheDocument()
    expect(screen.getByText(/Outcome \(set by inv@example.com\)/)).toBeInTheDocument()
    expect(screen.getByText(/No further actions: the case is closed/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Post' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Add evidence/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add' })).not.toBeInTheDocument()
    expect(await screen.findByText('first text')).toBeInTheDocument()
    expect(screen.getByText(/created/)).toBeInTheDocument()
  })
  it('lets the author edit a note and shows earlier versions; others cannot edit', async () => {
    const posts: { url: string; method: string; body: unknown }[] = []
    renderDetail(ALL, detail(), [note({ edited: true, revision_count: 2, body: 'second text' }), note({ id: 2, author: 99, author_email: 'other@example.com', body: 'theirs' })], posts)
    expect(await screen.findByText(/edited \(2 versions\)/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Edit' })).toHaveLength(1) // only my own note
    await userEvent.click(screen.getByRole('button', { name: 'Show earlier versions' }))
    expect(await screen.findByRole('region', { name: /earlier versions/i })).toHaveTextContent('v1 (inv@example.com): first text')
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.clear(screen.getByLabelText('Edit text'))
    await userEvent.type(screen.getByLabelText('Edit text'), 'third text')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(posts[0]).toMatchObject({ method: 'PATCH', url: '/cases/2/notes/1/', body: { body: 'third text' } })
  })
  it('an analyst can comment but not write investigation notes or change status', async () => {
    renderDetail(['cases.read', 'cases.comment'], detail({ allowed_transitions: [] }))
    expect(await screen.findByRole('button', { name: 'Post' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Type')).not.toBeInTheDocument()
    expect(screen.getByText(/cannot move this case further with your permissions/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()
  })
})
