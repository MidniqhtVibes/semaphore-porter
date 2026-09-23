import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setCsrfToken } from './api'
import type { User } from './types'

type AuthContextValue = {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const current = await api<User>('/auth/me')
      const csrf = await api<{ csrf_token: string }>('/auth/csrf')
      setCsrfToken(csrf.csrf_token)
      setUser(current)
    } catch {
      setCsrfToken('')
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  const login = async (email: string, password: string) => {
    const result = await api<{ user: User; csrf_token: string }>('/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }), headers: { 'Content-Type': 'application/json' },
    })
    setCsrfToken(result.csrf_token)
    setUser(result.user)
    return result.user
  }

  const logout = async () => {
    await api<void>('/auth/logout', { method: 'POST' })
    setCsrfToken('')
    setUser(null)
  }

  const value = useMemo<AuthContextValue>(() => ({
    user, loading, login, logout, refresh, isAdmin: Boolean(user?.roles.includes('system_admin')),
  }), [user, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider fehlt')
  return value
}

