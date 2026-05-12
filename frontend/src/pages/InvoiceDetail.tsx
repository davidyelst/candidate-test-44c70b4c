import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { fetchInvoice } from '../api/billing'
import { ApiError } from '../api/client'

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => fetchInvoice(id!),
    retry: false,
  })

  const isNotFound = isError && error instanceof ApiError && error.status === 404

  if (isLoading) {
    return <p className="text-slate-500">Loading invoice…</p>
  }

  if (isNotFound) {
    return (
      <div>
        <Link to="/billing" className="text-indigo-600 hover:text-indigo-800 text-sm mb-4 inline-block">
          ← Billing
        </Link>
        <div className="bg-white border border-slate-200 rounded-lg px-6 py-12 text-center max-w-md">
          <p className="text-slate-800 font-medium">Invoice not found</p>
          <p className="text-slate-500 text-sm mt-1">
            This invoice doesn't exist yet — billing may not have run for this period.
          </p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
        Failed to load invoice.
      </div>
    )
  }

  return (
    <div>
      <Link to="/billing" className="text-indigo-600 hover:text-indigo-800 text-sm mb-4 inline-block">
        ← Billing
      </Link>
      <h1 className="text-xl font-semibold text-slate-900 mb-4">Invoice #{id}</h1>
      <pre className="bg-white border border-slate-200 rounded-lg p-4 text-sm text-slate-700 overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  )
}
