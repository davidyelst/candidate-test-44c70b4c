import { FormEvent, useState } from 'react'
import { UpdateEndpointInput, WebhookDelivery, WebhookEndpoint } from '../../api/webhooks'
import { StatusBadge } from '../StatusBadge'
import { WebhookDeliveriesTable } from './WebhookDeliveriesTable'
import { timeAgo } from './format'

interface Props {
  endpoint: WebhookEndpoint
  isDeliveriesOpen: boolean
  onToggleDeliveries: () => void
  onToggleActive: () => void
  isToggling: boolean
  onSave: (patch: UpdateEndpointInput) => Promise<unknown>
  isSaving: boolean
  onDelete: () => void
  isDeleting: boolean
  onSendTest: () => Promise<unknown>
  isTesting: boolean
  deliveries: WebhookDelivery[]
  deliveriesLoading: boolean
}

function LastDelivery({ last }: { last: WebhookEndpoint['last_delivery'] }) {
  if (!last) {
    return <span className="text-xs text-slate-400">No deliveries yet</span>
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
      last delivery <StatusBadge status={last.status} /> · {timeAgo(last.at)}
    </span>
  )
}

export function WebhookEndpointCard({
  endpoint,
  isDeliveriesOpen,
  onToggleDeliveries,
  onToggleActive,
  isToggling,
  onSave,
  isSaving,
  onDelete,
  isDeleting,
  onSendTest,
  isTesting,
  deliveries,
  deliveriesLoading,
}: Props) {
  const [revealed, setRevealed] = useState(false)
  const [copied, setCopied] = useState(false)
  const [editing, setEditing] = useState(false)
  const [urlDraft, setUrlDraft] = useState(endpoint.url)
  const [descDraft, setDescDraft] = useState(endpoint.description)
  const [saveError, setSaveError] = useState<string | null>(null)

  function copySecret() {
    navigator.clipboard?.writeText(endpoint.secret)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function startEdit() {
    setUrlDraft(endpoint.url)
    setDescDraft(endpoint.description)
    setSaveError(null)
    setEditing(true)
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setSaveError(null)
    try {
      await onSave({ url: urlDraft, description: descDraft })
      setEditing(false)
    } catch {
      setSaveError('Failed to save changes. Please try again.')
    }
  }

  const btn =
    'text-xs px-3 py-1.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50'
  const input =
    'w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'

  if (editing) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <form onSubmit={handleSave} className="space-y-3">
          <div>
            <label htmlFor={`edit-url-${endpoint.id}`} className="block text-xs font-medium text-slate-600 mb-1">
              Destination URL
            </label>
            <input
              id={`edit-url-${endpoint.id}`}
              type="url"
              required
              value={urlDraft}
              onChange={(e) => setUrlDraft(e.target.value)}
              className={input}
            />
          </div>
          <div>
            <label htmlFor={`edit-desc-${endpoint.id}`} className="block text-xs font-medium text-slate-600 mb-1">
              Description <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <input
              id={`edit-desc-${endpoint.id}`}
              type="text"
              value={descDraft}
              onChange={(e) => setDescDraft(e.target.value)}
              className={input}
            />
          </div>
          {saveError && <p className="text-red-600 text-xs">{saveError}</p>}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={isSaving}
              className="text-xs px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSaving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" onClick={() => setEditing(false)} className={btn}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    )
  }

  return (
    <div className={`bg-white border border-slate-200 rounded-lg p-4 ${endpoint.is_active ? '' : 'opacity-75'}`}>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-slate-800 truncate">{endpoint.url}</span>
          <StatusBadge status={endpoint.is_active ? 'active' : 'disabled'} />
        </div>
        {endpoint.description && <p className="text-slate-500 text-xs mt-0.5">{endpoint.description}</p>}
        <div className="mt-1">
          <LastDelivery last={endpoint.last_delivery} />
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 text-xs">
        <span className="text-slate-400">Secret</span>
        <div className="inline-flex items-center gap-2 border border-slate-200 bg-slate-50 rounded px-2 py-1">
          <code className="text-slate-600 tracking-tight">
            {revealed ? endpoint.secret : '•'.repeat(16)}
          </code>
          <button onClick={() => setRevealed((v) => !v)} className="text-slate-500 hover:text-slate-800">
            {revealed ? 'Hide' : 'Show'}
          </button>
          <button
            onClick={copySecret}
            className={copied ? 'text-green-600' : 'text-slate-500 hover:text-slate-800'}
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={() => void onSendTest()}
          disabled={isTesting}
          className="text-xs px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isTesting ? 'Sending…' : 'Send test'}
        </button>
        <button
          onClick={onToggleDeliveries}
          className={`text-xs px-3 py-1.5 rounded border ${
            isDeliveriesOpen
              ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
              : 'border-slate-200 text-slate-600 hover:bg-slate-50'
          }`}
        >
          Deliveries
        </button>
        <button onClick={startEdit} className={btn}>
          Edit
        </button>
        <button onClick={onToggleActive} disabled={isToggling} className={btn}>
          {endpoint.is_active ? 'Disable' : 'Enable'}
        </button>
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className={`${btn} hover:bg-red-50 hover:text-red-600 hover:border-red-200`}
        >
          Remove
        </button>
      </div>

      {isDeliveriesOpen && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <WebhookDeliveriesTable deliveries={deliveries} isLoading={deliveriesLoading} />
        </div>
      )}
    </div>
  )
}
