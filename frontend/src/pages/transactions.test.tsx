import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Dataset, TransactionRow } from '../api/types'
import { TransactionTable } from '../components/transactions/TransactionTable'
import { formatAmount } from '../lib/format'
import TransactionsPage from './TransactionsPage'

afterEach(() => vi.unstubAllGlobals())

const dataset: Dataset = { id: 7, name: 'MOCK demo', source_type: 'custom', is_synthetic: true, description: '', row_count: 2, created_at: '2026-01-01T00:00:00Z' }
const row = (over: Partial<TransactionRow>): TransactionRow => ({
  id: 1, dataset: 7, transaction_id: 'T1', sender: 10, sender_ref: 'C10', receiver: 11, receiver_ref: 'C11',
  amount: '1234.50', currency: '', tx_type: 'TRANSFER', occurred_at: '2026-01-01T10:00:00Z', status: 'completed', ...over,
})
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response

function renderPage(fetchMock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal('fetch', fetchMock)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/transactions']}><TransactionsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TransactionsPage', () => {
  it('loads datasets then lists transactions of the first dataset', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes('/datasets/') ? ok([dataset])
        : ok({ count: 2, next: null, previous: null, results: [row({}), row({ id: 2, transaction_id: 'T2', receiver: null, receiver_ref: null })] }))
    renderPage(fetchMock)
    expect(await screen.findByText('T1')).toBeInTheDocument()
    expect(screen.getByText('T2')).toBeInTheDocument()
    expect(screen.getByText('2 transactions', { exact: false })).toBeInTheDocument()
    const txCall = fetchMock.mock.calls.map((c) => String(c[0])).find((u) => u.includes('/transactions/'))
    expect(txCall).toContain('dataset=7')
    expect(txCall).toContain('ordering=-occurred_at')
  })

  it('shows an empty state when no transactions match', async () => {
    renderPage(vi.fn(async (url: string) => (url.includes('/datasets/') ? ok([dataset]) : ok({ count: 0, next: null, previous: null, results: [] }))))
    expect(await screen.findByText('No transactions match these filters')).toBeInTheDocument()
  })

  it('shows an empty state when there are no datasets', async () => {
    renderPage(vi.fn(async () => ok([])))
    expect(await screen.findByText('No datasets yet')).toBeInTheDocument()
  })

  it('shows an error state with retry when the API fails', async () => {
    renderPage(vi.fn(async (url: string) =>
      url.includes('/datasets/') ? ok([dataset])
        : ({ ok: false, status: 500, statusText: 'x', json: async () => ({ error: { code: 'server_error', message: 'Boom' } }) }) as Response))
    expect(await screen.findByRole('alert')).toHaveTextContent('Boom')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('requests descending amount order when the Amount header is clicked', async () => {
    const fetchMock = vi.fn(async (url: string) => (url.includes('/datasets/') ? ok([dataset]) : ok({ count: 1, next: null, previous: null, results: [row({})] })))
    renderPage(fetchMock)
    await screen.findByText('T1')
    await userEvent.click(screen.getByRole('button', { name: /Amount/ }))
    await screen.findByText('T1')
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('ordering=-amount'))).toBe(true)
  })
})

describe('TransactionTable', () => {
  it('links rows to transaction and account pages and marks the sort column', () => {
    render(
      <MemoryRouter>
        <TransactionTable rows={[row({})]} sort={{ field: 'amount', desc: true }} onSort={() => {}} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'T1' })).toHaveAttribute('href', '/transactions/1')
    expect(screen.getByRole('link', { name: 'C10' })).toHaveAttribute('href', '/accounts/10')
    expect(within(screen.getByRole('columnheader', { name: /Amount/ })).getByRole('button')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /Amount/ })).toHaveAttribute('aria-sort', 'descending')
  })
})

describe('formatAmount', () => {
  it('formats decimals and only shows currency when provided', () => {
    expect(formatAmount('1234.5')).toBe('1,234.50')
    expect(formatAmount('10', 'INR')).toBe('INR 10.00')
  })
})
