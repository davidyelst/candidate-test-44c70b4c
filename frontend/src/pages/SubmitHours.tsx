import { useState, FormEvent } from 'react'
import { Link, useNavigate, useParams, Navigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchContract } from '../api/contracts'
import { createTimesheetEntry } from '../api/timesheets'
import { useAuth } from '../hooks/useAuth'

export default function SubmitHours() {
  const { id } = useParams<{ id: string }>()
  const numId = Number(id)
  const { isFreelancer } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [hours, setHours] = useState('8')
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const contractQuery = useQuery({
    queryKey: ['contract', numId],
    queryFn: () => fetchContract(numId),
  })

  const mutation = useMutation({
    mutationFn: () => createTimesheetEntry({ contract: numId, date, hours }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', { contract: numId }] })
      setSuccessMsg(`Entry for ${date} submitted.`)
      setDate(new Date().toISOString().slice(0, 10))
      setHours('8')
      setErrorMsg(null)
    },
    onError: () => {
      setErrorMsg('Failed to submit entry. Check the date and try again.')
      setSuccessMsg(null)
    },
  })

  if (!isFreelancer) {
    return <Navigate to={`/contracts/${id}`} replace />
  }

  if (contractQuery.isLoading) {
    return <p className="text-slate-500">Loading…</p>
  }

  if (contractQuery.isError) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
        Contract not found.
      </div>
    )
  }

  const contract = contractQuery.data!

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErrorMsg(null)
    setSuccessMsg(null)
    mutation.mutate()
  }

  return (
    <div className="max-w-md">
      <Link to={`/contracts/${numId}`} className="text-indigo-600 hover:text-indigo-800 text-sm mb-4 inline-block">
        ← Back to contract
      </Link>
      <h1 className="text-xl font-semibold text-slate-900 mb-1">Log hours</h1>
      <p className="text-slate-500 text-sm mb-6">
        {contract.freelancer.name} @ {contract.company.name} &middot; £{Number(contract.daily_rate).toFixed(2)}/day
      </p>

      {successMsg && (
        <div className="bg-green-50 border border-green-200 text-green-800 text-sm rounded px-3 py-2 mb-4">
          {successMsg}
        </div>
      )}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded px-3 py-2 mb-4">
          {errorMsg}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-white border border-slate-200 rounded-lg p-6 space-y-4"
      >
        <div>
          <label htmlFor="date" className="block text-sm font-medium text-slate-700 mb-1">
            Date
          </label>
          <input
            id="date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label htmlFor="hours" className="block text-sm font-medium text-slate-700 mb-1">
            Hours worked
          </label>
          <input
            id="hours"
            type="number"
            min="0.5"
            max="24"
            step="0.5"
            value={hours}
            onChange={(e) => setHours(e.target.value)}
            required
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? 'Submitting…' : 'Submit entry'}
          </button>
          <button
            type="button"
            onClick={() => navigate(`/contracts/${numId}`)}
            className="text-slate-600 text-sm px-4 py-2 rounded hover:bg-slate-100"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
