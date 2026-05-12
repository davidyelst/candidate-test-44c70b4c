import { api, WebhookEndpoint } from './client'

export function fetchWebhookEndpoints(): Promise<WebhookEndpoint[]> {
  return api.get('/api/webhook-endpoints/')
}

export function createWebhookEndpoint(url: string): Promise<WebhookEndpoint> {
  return api.post('/api/webhook-endpoints/', { url })
}

export function deleteWebhookEndpoint(id: string | number): Promise<void> {
  return api.delete(`/api/webhook-endpoints/${id}/`)
}
