import { FormEvent, useState } from 'react'
import { CreateEndpointInput } from '../../api/webhooks'

interface Props {
  onSubmit: (input: CreateEndpointInput) => Promise<unknown>
  isPending: boolean
}

export function WebhookForm({ onSubmit, isPending }: Props) {
  const [url, setUrl] = useState('')
  const [description, setDescription] = useState('')
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSuccessMsg(null)
    setErrorMsg(null)
    try {
      await onSubmit({ url, description: description || undefined })
      setSuccessMsg(`Endpoint saved: ${url}`)
      setUrl('')
      setDescription('')
    } catch {
      setErrorMsg('Failed to save endpoint. Please try again.')
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-6">
      <h2 className="text-base font-medium text-slate-800 mb-4">Add webhook destination</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="webhook-url" className="block text-sm font-medium text-slate-700 mb-1">
            Destination URL
          </label>
          <input
            id="webhook-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            placeholder="https://example.com/webhook"
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <p className="text-slate-400 text-xs mt-1">
            For local testing, use{' '}
            <code className="bg-slate-100 px-1 rounded">http://localhost:8027/hook</code>
          </p>
        </div>
        <div>
          <label htmlFor="webhook-description" className="block text-sm font-medium text-slate-700 mb-1">
            Description <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <input
            id="webhook-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Accounting system — invoices"
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <button
          type="submit"
          disabled={isPending}
          className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isPending ? 'Saving…' : 'Save endpoint'}
        </button>
      </form>

      {successMsg && (
        <div className="mt-4 bg-green-50 border border-green-200 text-green-800 text-sm rounded px-3 py-2">
          {successMsg}
        </div>
      )}
      {errorMsg && (
        <div className="mt-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded px-3 py-2">
          {errorMsg}
        </div>
      )}
    </div>
  )
}
