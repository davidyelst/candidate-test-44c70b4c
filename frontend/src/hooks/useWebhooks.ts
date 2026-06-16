import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CreateEndpointInput,
  UpdateEndpointInput,
  createWebhookEndpoint,
  deleteWebhookEndpoint,
  fetchDeliveries,
  fetchWebhookEndpoints,
  sendTestEvent,
  updateWebhookEndpoint,
} from '../api/webhooks'

// All webhook React Query lives here, so the components stay presentational.

const ENDPOINTS_KEY = ['webhook-endpoints']
const deliveriesKey = (endpointId: number) => ['webhook-deliveries', endpointId]

export function useWebhookEndpoints() {
  return useQuery({ queryKey: ENDPOINTS_KEY, queryFn: fetchWebhookEndpoints })
}

export function useCreateWebhookEndpoint() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateEndpointInput) => createWebhookEndpoint(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ENDPOINTS_KEY }),
  })
}

export function useUpdateWebhookEndpoint() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: UpdateEndpointInput }) =>
      updateWebhookEndpoint(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ENDPOINTS_KEY }),
  })
}

export function useDeleteWebhookEndpoint() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteWebhookEndpoint(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ENDPOINTS_KEY }),
  })
}

export function useSendTestEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => sendTestEvent(id),
    onSuccess: (_delivery, id) => qc.invalidateQueries({ queryKey: deliveriesKey(id) }),
  })
}

export function useDeliveries(endpointId: number | null) {
  return useQuery({
    queryKey: deliveriesKey(endpointId ?? 0),
    queryFn: () => fetchDeliveries(endpointId as number),
    enabled: endpointId != null,
    // Deliveries are processed async by the worker — poll while any are still pending so
    // the log reflects pending → success/failed without a manual refresh.
    refetchInterval: (q) => ((q.state.data ?? []).some((d) => d.status === 'pending') ? 2000 : false),
  })
}
