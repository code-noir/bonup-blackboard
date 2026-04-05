import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import type { ReactNode } from 'react'
import api, { tokenStorage } from '@/api/client'
import type { AuthUser } from '@/types/auth'

interface AuthContextValue {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await api.get<AuthUser>('/users/me/')
      setUser(data)
    } catch {
      setUser(null)
      tokenStorage.clear()
    }
  }, [])

  useEffect(() => {
    if (tokenStorage.getAccess()) {
      fetchMe().finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [fetchMe])

  const login = async (username: string, password: string) => {
    const { data } = await api.post<{ access: string; refresh: string }>(
      '/auth/token/',
      { username, password },
    )
    tokenStorage.set(data.access, data.refresh)
    await fetchMe()
  }

  const logout = async () => {
    try {
      const refresh = tokenStorage.getRefresh()
      if (refresh) await api.post('/users/logout/', { refresh })
    } finally {
      tokenStorage.clear()
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: !!user, isLoading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
