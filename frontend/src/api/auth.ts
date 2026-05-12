import { api, AuthUser } from './client'

export async function login(email: string, password: string): Promise<{ token: string; user: AuthUser }> {
  return api.post('/api/auth/login/', { email, password })
}
