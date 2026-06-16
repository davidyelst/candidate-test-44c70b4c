import { useState } from 'react'
import { WebhookForm } from '../components/webhooks/WebhookForm'
import { WebhookEndpointCard } from '../components/webhooks/WebhookEndpointCard'
import {
  useCreateWebhookEndpoint,
  useDeleteWebhookEndpoint,
  useDeliveries,
  useSendTestEvent,
  useUpdateWebhookEndpoint,
  useWebhookEndpoints,
} from '../hooks/useWebhooks'

export default function DeveloperSettings() {
  const endpointsQuery = useWebhookEndpoints()
  const createMutation = useCreateWebhookEndpoint()
  const toggleMutation = useUpdateWebhookEndpoint()
  const saveMutation = useUpdateWebhookEndpoint()
  const deleteMutation = useDeleteWebhookEndpoint()
  const testMutation = useSendTestEvent()

  // Which endpoint's delivery log is expanded (one at a time); drives the deliveries query.
  const [openId, setOpenId] = useState<number | null>(null)
  const deliveriesQuery = useDeliveries(openId)

  const endpoints = endpointsQuery.data ?? []

  async function handleSendTest(id: number) {
    await testMutation.mutateAsync(id)
    setOpenId(id) // surface the log so the new delivery is visible
  }

  async function handleDelete(id: number) {
    await deleteMutation.mutateAsync(id)
    if (openId === id) setOpenId(null)
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 mb-1">Developer settings</h1>
        <p className="text-slate-500 text-sm">
          Configure webhook endpoints to receive event notifications from YunoJuno.
        </p>
      </div>

      <WebhookForm
        onSubmit={(input) => createMutation.mutateAsync(input)}
        isPending={createMutation.isPending}
      />

      <div>
        <h2 className="text-base font-medium text-slate-800 mb-3">Configured endpoints</h2>

        {endpointsQuery.isLoading ? (
          <p className="text-slate-500 text-sm">Loading…</p>
        ) : endpointsQuery.isError ? (
          <p className="text-red-600 text-sm">Failed to load endpoints.</p>
        ) : endpoints.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-lg px-6 py-10 text-center">
            <p className="text-slate-500 text-sm">No webhook endpoints configured.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {endpoints.map((ep) => (
              <WebhookEndpointCard
                key={ep.id}
                endpoint={ep}
                isDeliveriesOpen={openId === ep.id}
                onToggleDeliveries={() => setOpenId((cur) => (cur === ep.id ? null : ep.id))}
                onToggleActive={() => toggleMutation.mutate({ id: ep.id, patch: { is_active: !ep.is_active } })}
                isToggling={toggleMutation.isPending && toggleMutation.variables?.id === ep.id}
                onSave={(patch) => saveMutation.mutateAsync({ id: ep.id, patch })}
                isSaving={saveMutation.isPending && saveMutation.variables?.id === ep.id}
                onDelete={() => handleDelete(ep.id)}
                isDeleting={deleteMutation.isPending && deleteMutation.variables === ep.id}
                onSendTest={() => handleSendTest(ep.id)}
                isTesting={testMutation.isPending && testMutation.variables === ep.id}
                deliveries={openId === ep.id ? deliveriesQuery.data ?? [] : []}
                deliveriesLoading={openId === ep.id && deliveriesQuery.isLoading}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
