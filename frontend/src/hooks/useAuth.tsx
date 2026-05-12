import { createContext, useContext, useState, ReactNode } from 'react'
import { AuthUser } from '../api/client'

interface AuthState {
  token: string | null
  user: AuthUser | null
}

interface AuthContextValue extends AuthState {
  setAuth: (token: string, user: AuthUser) => void
  clearAuth: () => void
  isAdmin: boolean
  isFreelancer: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const token = localStorage.getItem('token')
    const userStr = localStorage.getItem('user')
    return {
      token,
      user: userStr ? (JSON.parse(userStr) as AuthUser) : null,
    }
  })

  function setAuth(token: string, user: AuthUser) {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    setState({ token, user })
  }

  function clearAuth() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setState({ token: null, user: null })
  }

  return (
    <AuthContext.Provider
      value={{
        ...state,
        setAuth,
        clearAuth,
        isAdmin: state.user?.role === 'admin',
        isFreelancer: state.user?.role === 'freelancer',
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
