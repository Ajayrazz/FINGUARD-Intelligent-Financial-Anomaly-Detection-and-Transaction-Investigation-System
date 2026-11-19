import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { fetchBlob } from '../../api/client'

/** Shows an invoice image from an authenticated endpoint (a plain <img src> cannot send the bearer token). */
export function AuthImage({ path, alt }: { path: string; alt: string }) {
  const q = useQuery({ queryKey: ['blob', path], queryFn: () => fetchBlob(path), staleTime: 5 * 60_000 })
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!q.data) return
    const u = URL.createObjectURL(q.data)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [q.data])
  if (q.isError) return <p className="text-sm text-slate-500">Preview unavailable (a PDF or a removed file).</p>
  if (!url) return <p className="text-sm text-slate-500">Loading image…</p>
  if (q.data?.type === 'application/pdf') return <a className="text-sm text-blue-700 hover:underline" href={url} target="_blank" rel="noreferrer">Open PDF</a>
  return <img src={url} alt={alt} className="max-h-96 w-full rounded border border-slate-300 object-contain" />
}
