const money = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** Format a decimal string from the API. Currency is shown only when the dataset provides one. */
export function formatAmount(amount: string, currency = ''): string {
  const n = Number(amount)
  const body = Number.isFinite(n) ? money.format(n) : amount
  return currency ? `${currency} ${body}` : body
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
}
