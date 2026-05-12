import { useState, FormEvent } from 'react'
import { Link, useNavigate, Navigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchFreelancers, createContract } from '../api/contracts'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../api/client'

export default function NewContract() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [freelancer, setFreelancer] = useState('')
  const [dailyRate, setDailyRate] = useState('500')
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10))
  const [endDate, setEndDate] = useState('')
  const [contractStatus, setContractStatus] = useState<'active' | 'closed'>('active')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const freelancersQuery = useQuery({
    queryKey: ['freelancers'],
    queryFn: fetchFreelancers,
    enabled: isAdmin,
  })

  const mutation = useMutation({
    mutationFn: () =>
      createContract({
        freelancer: Number(freelancer),
        daily_rate: dailyRate,
        start_date: startDate,
        end_date: endDate,
        status: contractStatus,
      }),
    onSuccess: (contract) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      navigate(`/contracts/${contract.id}`)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.data?.end_date) {
        setErrorMsg(String(err.data.end_date))
      } else {
        setErrorMsg('Failed to create contract. Check the fields and try again.')
      }
    },
  })

  if (!isAdmin) {
    return <Navigate to="/contracts" replace />
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErrorMsg(null)
    if (!freelancer) {
      setErrorMsg('Please choose a freelancer.')
      return
    }
    mutation.mutate()
  }

  return (
    <div className="max-w-md">
      <Link to="/contracts" className="text-indigo-600 hover:text-indigo-800 text-sm mb-4 inline-block">
        ← Back to contracts
      </Link>
      <h1 className="text-xl font-semibold text-slate-900 mb-1">New contract</h1>
      <p className="text-slate-500 text-sm mb-6">
        Create a contract for a freelancer at your company.
      </p>

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
          <label htmlFor="freelancer" className="block text-sm font-medium text-slate-700 mb-1">
            Freelancer
          </label>
          <select
            id="freelancer"
            value={freelancer}
            onChange={(e) => setFreelancer(e.target.value)}
            required
            disabled={freelancersQuery.isLoading}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="" disabled>
              {freelancersQuery.isLoading ? 'Loading…' : 'Select a freelancer'}
            </option>
            {freelancersQuery.data?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
          {freelancersQuery.isError && (
            <p className="text-red-600 text-xs mt-1">Failed to load freelancers.</p>
          )}
        </div>

        <div>
          <label htmlFor="daily_rate" className="block text-sm font-medium text-slate-700 mb-1">
            Daily rate (£)
          </label>
          <input
            id="daily_rate"
            type="number"
            min="0"
            step="0.01"
            value={dailyRate}
            onChange={(e) => setDailyRate(e.target.value)}
            required
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex gap-3">
          <div className="flex-1">
            <label htmlFor="start_date" className="block text-sm font-medium text-slate-700 mb-1">
              Start date
            </label>
            <input
              id="start_date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="end_date" className="block text-sm font-medium text-slate-700 mb-1">
              End date
            </label>
            <input
              id="end_date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div>
          <label htmlFor="status" className="block text-sm font-medium text-slate-700 mb-1">
            Status
          </label>
          <select
            id="status"
            value={contractStatus}
            onChange={(e) => setContractStatus(e.target.value as 'active' | 'closed')}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="active">Active</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? 'Creating…' : 'Create contract'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/contracts')}
            className="text-slate-600 text-sm px-4 py-2 rounded hover:bg-slate-100"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
