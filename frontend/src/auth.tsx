import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setCsrfToken } from './api'
import type { User } from './types'
import { useQueryClient } from '@tanstack/react-query'

type AuthContextValue = {
  user: User | null
  loading: boolean
  login: (identifier: string, password: string) => Promise<User>
  loginDemo: (role: string) => Promise<User>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  syncProfile: (profile: Pick<User,'id'> & Partial<Pick<User,'display_name'|'profile_color'|'avatar_version'>>) => void
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient=useQueryClient()
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

  const login = async (identifier: string, password: string) => {
    const result = await api<{ user: User; csrf_token: string }>('/auth/login', {
      method: 'POST', body: JSON.stringify({ identifier, password }), headers: { 'Content-Type': 'application/json' },
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

  const loginDemo = async (role:string) => {
    const result=await api<{user:User;csrf_token:string}>('/demo/login',{method:'POST',body:JSON.stringify({role})})
    queryClient.removeQueries({predicate:query=>query.queryKey[0]!=='runtime-config'})
    setCsrfToken(result.csrf_token)
    setUser(result.user)
    return result.user
  }

  const value = useMemo<AuthContextValue>(() => ({
    user, loading, login, loginDemo, logout, refresh,
    syncProfile: profile=>setUser(current=>current?.id===profile.id?{...current,...profile}:current),
    isAdmin: Boolean(user?.roles.includes('system_admin')),
  }), [user, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider fehlt')
  return value
}

