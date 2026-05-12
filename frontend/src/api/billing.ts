import { api, BillingRunResult, Invoice } from './client'

export function runBilling(month: string): Promise<BillingRunResult> {
  return api.post('/api/billing/runs/', { month })
}

export function fetchInvoices(month: string): Promise<Invoice[]> {
  return api.get(`/api/invoices/?month=${month}`)
}

export function fetchInvoice(id: string | number): Promise<Invoice> {
  return api.get(`/api/invoices/${id}/`)
}
