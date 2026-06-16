import { WebhookDelivery } from '../../api/webhooks'
import { StatusBadge } from '../StatusBadge'
import { formatAbsolute, timeAgo } from './format'

interface Props {
  deliveries: WebhookDelivery[]
  isLoading: boolean
}

export function WebhookDeliveriesTable({ deliveries, isLoading }: Props) {
  if (isLoading) {
    return <p className="text-slate-400 text-xs py-2">Loading deliveries…</p>
  }
  if (deliveries.length === 0) {
    return (
      <p className="text-slate-400 text-xs py-2 text-center">
        No deliveries yet — send a test event to see one here.
      </p>
    )
  }

  return (
    <table className="w-full text-xs">
      <thead className="text-slate-500">
        <tr className="text-left">
          <th className="py-1 pr-3 font-medium">Event</th>
          <th className="py-1 pr-3 font-medium">Time</th>
          <th className="py-1 pr-3 font-medium">Status</th>
          <th className="py-1 pr-3 font-medium">Response</th>
          <th className="py-1 pr-3 font-medium">Attempt</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {deliveries.map((d) => {
          const when = d.last_attempt_at ?? d.created_at
          return (
            <tr key={d.id}>
              <td className="py-1.5 pr-3 font-mono text-slate-600">{d.event_type}</td>
              <td className="py-1.5 pr-3 text-slate-500" title={formatAbsolute(when)}>{timeAgo(when)}</td>
              <td className="py-1.5 pr-3">
                <StatusBadge status={d.status} />
                {d.last_error && (
                  <span className="text-slate-400 ml-1" title={d.last_error}>ⓘ</span>
                )}
              </td>
              <td className="py-1.5 pr-3 text-slate-600">{d.last_response_code ?? '—'}</td>
              <td className="py-1.5 pr-3 text-slate-600">{d.attempt_count}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
