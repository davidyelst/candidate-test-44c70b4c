import { z } from 'zod'
import { api } from './client'

// Schema-first: the Zod schemas are the single source of truth and the TS types are
// inferred from them (z.infer), so there's no hand-written interface to drift from the
// validator. Responses are parsed at the boundary — a shape the backend didn't promise
// throws here, not three layers deep in a component. (This is the pattern; the rest of
// the client predates it and still uses the inline interfaces in client.ts.)

const webhookDeliveryStatusSchema = z.enum(['pending', 'success', 'failed', 'exhausted'])

const webhookEndpointSchema = z.object({
  id: z.number().int(),
  url: z.url(),
  description: z.string(),
  is_active: z.boolean(),
  secret: z.string(),
  created_at: z.string(),
  last_delivery: z
    .object({ status: webhookDeliveryStatusSchema, at: z.string() })
    .nullable(),
})

const webhookDeliverySchema = z.object({
  id: z.number().int(),
  event_id: z.uuid(),
  event_type: z.string(),
  status: webhookDeliveryStatusSchema,
  attempt_count: z.number().int(),
  last_response_code: z.number().int().nullable(),
  last_error: z.string(),
  last_attempt_at: z.string().nullable(),
  created_at: z.string(),
})

export type WebhookEndpoint = z.infer<typeof webhookEndpointSchema>
export type WebhookDeliveryStatus = z.infer<typeof webhookDeliveryStatusSchema>
export type WebhookDelivery = z.infer<typeof webhookDeliverySchema>

export interface CreateEndpointInput {
  url: string
  description?: string
}

export type UpdateEndpointInput = Partial<Pick<WebhookEndpoint, 'url' | 'description' | 'is_active'>>

export async function fetchWebhookEndpoints(): Promise<WebhookEndpoint[]> {
  return webhookEndpointSchema.array().parse(await api.get('/api/webhook-endpoints/'))
}

export async function createWebhookEndpoint(input: CreateEndpointInput): Promise<WebhookEndpoint> {
  return webhookEndpointSchema.parse(await api.post('/api/webhook-endpoints/', input))
}

export async function updateWebhookEndpoint(id: number, patch: UpdateEndpointInput): Promise<WebhookEndpoint> {
  return webhookEndpointSchema.parse(await api.patch(`/api/webhook-endpoints/${id}/`, patch))
}

export async function deleteWebhookEndpoint(id: number): Promise<void> {
  await api.delete(`/api/webhook-endpoints/${id}/`)
}

export async function sendTestEvent(id: number): Promise<WebhookDelivery> {
  return webhookDeliverySchema.parse(await api.post(`/api/webhook-endpoints/${id}/test/`, {}))
}

export async function fetchDeliveries(id: number): Promise<WebhookDelivery[]> {
  return webhookDeliverySchema.array().parse(await api.get(`/api/webhook-endpoints/${id}/deliveries/`))
}
