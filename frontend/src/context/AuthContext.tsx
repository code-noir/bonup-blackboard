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
  isOnTrial: () => boolean
  trialDaysRemaining: () => number
  hasTrialExpired: () => boolean
  canCreateContract: () => boolean
}

function daysUntil(dateStr: string | null | undefined): number {
  if (!dateStr) return 0
  const end = new Date(dateStr)
  const now = new Date()
  return Math.max(0, Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)))
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

  function isOnTrial(): boolean {
    if (user?.subscription_tier !== 'trial') return false
    if (user.trial_expired) return false
    return daysUntil(user.trial_ends_at) > 0
  }

  function trialDaysRemaining(): number {
    if (user?.subscription_tier !== 'trial') return 0
    return daysUntil(user.trial_ends_at)
  }

  function hasTrialExpired(): boolean {
    if (user?.subscription_tier !== 'trial') return false
    return user.trial_expired === true || daysUntil(user.trial_ends_at) === 0
  }

  function canCreateContract(): boolean {
    if (!user) return false
    const tier = user.subscription_tier
    if (!tier) return false
    if (tier === 'trial') return isOnTrial()
    return true
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        isOnTrial,
        trialDaysRemaining,
        hasTrialExpired,
        canCreateContract,
      }}
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
