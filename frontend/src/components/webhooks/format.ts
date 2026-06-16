// Relative "2m ago" for at-a-glance times; absolute (locale) for precise hover titles.

export function timeAgo(iso: string): string {
  const secs = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (secs < 60) return `${secs}s ago`
  const mins = Math.round(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

export function formatAbsolute(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '—'
}
