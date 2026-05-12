import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { fetchContract } from '../api/contracts'
import { fetchTimesheets } from '../api/timesheets'
import { StatusBadge } from '../components/StatusBadge'
import { useAuth } from '../hooks/useAuth'
import { Contract, TimesheetEntry } from '../api/client'

// Props are passed down from ContractDetail — a candidate might reach for context here instead.
function TimesheetTable({ entries, contract }: { entries: TimesheetEntry[]; contract: Contract }) {
  if (entries.length === 0) {
    return <p className="text-slate-500 text-sm">No timesheet entries yet.</p>
  }

  const totalHours = entries.reduce((sum, e) => sum + Number(e.hours), 0)

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-slate-600">Date</th>
            <th className="text-left px-4 py-3 font-medium text-slate-600">Hours</th>
            <th className="text-left px-4 py-3 font-medium text-slate-600">Status</th>
            <th className="text-left px-4 py-3 font-medium text-slate-600">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {entries.map((entry) => (
            <tr key={entry.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 text-slate-700">{entry.date}</td>
              <td className="px-4 py-3 text-slate-700">{entry.hours}h</td>
              <td className="px-4 py-3">
                <StatusBadge status={entry.status} />
              </td>
              <td className="px-4 py-3 text-slate-500 text-xs italic">
                {entry.rejection_reason ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot className="bg-slate-50 border-t border-slate-200">
          <tr>
            <td className="px-4 py-2 text-slate-500 text-xs">
              {entries.length} entries &mdash; £{(totalHours * Number(contract.daily_rate) / 8).toFixed(2)} est.
            </td>
            <td className="px-4 py-2 font-medium text-slate-700">{totalHours}h total</td>
            <td colSpan={2} />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

export default function ContractDetail() {
  const { id } = useParams<{ id: string }>()
  const numId = Number(id)
  const { isFreelancer } = useAuth()

  const contractQuery = useQuery({
    queryKey: ['contract', numId],
    queryFn: () => fetchContract(numId),
  })

  const entriesQuery = useQuery({
    queryKey: ['timesheets', { contract: numId }],
    queryFn: () => fetchTimesheets({ contract: numId }),
    enabled: !!contractQuery.data,
  })

  if (contractQuery.isLoading) {
    return <p className="text-slate-500">Loading…</p>
  }

  if (contractQuery.isError) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
        Contract not found or you don't have access.
      </div>
    )
  }

  const contract = contractQuery.data!

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link to="/contracts" className="text-indigo-600 hover:text-indigo-800 text-sm mb-2 inline-block">
            ← Contracts
          </Link>
          <h1 className="text-xl font-semibold text-slate-900">
            {contract.freelancer.name} @ {contract.company.name}
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            £{Number(contract.daily_rate).toFixed(2)}/day &middot; {contract.start_date} – {contract.end_date}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={contract.status} />
          {isFreelancer && contract.status === 'active' && (
            <Link
              to={`/contracts/${contract.id}/submit`}
              className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700"
            >
              Log hours
            </Link>
          )}
        </div>
      </div>

      <div>
        <h2 className="text-base font-medium text-slate-800 mb-3">Timesheet entries</h2>
        {entriesQuery.isLoading ? (
          <p className="text-slate-500 text-sm">Loading entries…</p>
        ) : entriesQuery.isError ? (
          <p className="text-red-600 text-sm">Failed to load timesheet entries.</p>
        ) : (
          <TimesheetTable entries={entriesQuery.data ?? []} contract={contract} />
        )}
      </div>
    </div>
  )
}
