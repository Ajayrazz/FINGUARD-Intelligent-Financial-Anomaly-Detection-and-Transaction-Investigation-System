const tones: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  pending: 'bg-amber-100 text-amber-800',
  failed: 'bg-red-100 text-red-800',
  reversed: 'bg-slate-200 text-slate-800',
}

/** Status is always shown as text, never by colour alone. */
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium capitalize ${tones[status] ?? 'bg-slate-100 text-slate-800'}`}>
      {status}
    </span>
  )
}
