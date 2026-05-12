import { useState, FormEvent } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchWebhookEndpoints, createWebhookEndpoint, deleteWebhookEndpoint } from '../api/webhooks'
import { WebhookEndpoint } from '../api/client'

export default function DeveloperSettings() {
  const [url, setUrl] = useState('')
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const endpointsQuery = useQuery({
    queryKey: ['webhook-endpoints'],
    queryFn: fetchWebhookEndpoints,
  })

  const createMutation = useMutation({
    mutationFn: () => createWebhookEndpoint(url),
    onSuccess: (data: WebhookEndpoint) => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
      setSuccessMsg(`Endpoint saved: ${data.url}`)
      setErrorMsg(null)
      setUrl('')
    },
    onError: () => {
      setErrorMsg('Failed to save endpoint. Please try again.')
      setSuccessMsg(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string | number) => deleteWebhookEndpoint(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
    },
  })

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSuccessMsg(null)
    setErrorMsg(null)
    createMutation.mutate()
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 mb-1">Developer settings</h1>
        <p className="text-slate-500 text-sm">
          Configure webhook endpoints to receive event notifications from YunoJuno.
        </p>
      </div>

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
              <code className="bg-slate-100 px-1 rounded">http://webhook-receiver:8027/hook</code>
            </p>
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {createMutation.isPending ? 'Saving…' : 'Save endpoint'}
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

      <div>
        <h2 className="text-base font-medium text-slate-800 mb-3">Configured endpoints</h2>

        {endpointsQuery.isLoading ? (
          <p className="text-slate-500 text-sm">Loading…</p>
        ) : endpointsQuery.isError ? (
          <p className="text-red-600 text-sm">Failed to load endpoints.</p>
        ) : !endpointsQuery.data || endpointsQuery.data.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-lg px-6 py-10 text-center">
            <p className="text-slate-500 text-sm">No webhook endpoints configured.</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">URL</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {endpointsQuery.data.map((ep) => (
                  <tr key={String(ep.id)}>
                    <td className="px-4 py-3 text-slate-700 font-mono text-xs">{ep.url}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${ep.active ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-500'}`}
                      >
                        {ep.active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => deleteMutation.mutate(ep.id)}
                        disabled={deleteMutation.isPending}
                        className="text-red-600 hover:text-red-800 text-xs disabled:opacity-50"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
