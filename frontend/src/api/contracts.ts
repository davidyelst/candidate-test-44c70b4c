import { api, Contract, FreelancerProfile } from './client'

export function fetchContracts(): Promise<Contract[]> {
  return api.get('/api/contracts/')
}

export function fetchContract(id: number): Promise<Contract> {
  return api.get(`/api/contracts/${id}/`)
}

export function fetchFreelancers(): Promise<FreelancerProfile[]> {
  return api.get('/api/freelancers/')
}

export interface NewContractInput {
  freelancer: number
  daily_rate: string
  start_date: string
  end_date: string
  status: 'active' | 'closed'
}

export function createContract(data: NewContractInput): Promise<Contract> {
  return api.post('/api/contracts/', data)
}
