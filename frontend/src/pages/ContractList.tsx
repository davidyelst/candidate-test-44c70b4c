import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchContracts } from '../api/contracts'
import { StatusBadge } from '../components/StatusBadge'
import { useAuth } from '../hooks/useAuth'

function ContractsHeader({ isAdmin }: { isAdmin: boolean }) {
  return (
    <div className="flex items-center justify-between mb-6">
      <h1 className="text-xl font-semibold text-slate-900">Contracts</h1>
      {isAdmin && (
        <Link
          to="/contracts/new"
          className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700"
        >
          New contract
        </Link>
      )}
    </div>
  )
}

export default function ContractList() {
  const { isAdmin } = useAuth()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['contracts'],
    queryFn: fetchContracts,
  })

  if (isLoading) {
    return <p className="text-slate-500">Loading contracts…</p>
  }

  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
        Failed to load contracts. Please refresh the page.
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div>
        <ContractsHeader isAdmin={isAdmin} />
        <p className="text-slate-500 text-sm">No contracts found.</p>
      </div>
    )
  }

  return (
    <div>
      <ContractsHeader isAdmin={isAdmin} />
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Freelancer</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Company</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Daily rate</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Period</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((contract) => (
              <tr key={contract.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">{contract.freelancer.name}</td>
                <td className="px-4 py-3 text-slate-600">{contract.company.name}</td>
                <td className="px-4 py-3 text-slate-600">£{Number(contract.daily_rate).toFixed(2)}</td>
                <td className="px-4 py-3 text-slate-500">
                  {contract.start_date} – {contract.end_date}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={contract.status} />
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    to={`/contracts/${contract.id}`}
                    className="text-indigo-600 hover:text-indigo-800 font-medium"
                  >
                    View →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
