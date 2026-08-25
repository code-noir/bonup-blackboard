import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import api, { impersonationTokenStorage, operatorTokenStorage } from '@/api/client'
import type { ImpersonationUser } from '@/api/client'
import type { OperatorUser } from '@/types/auth'

interface OperatorContextValue {
  operator: OperatorUser | null
  isOperatorAuthenticated: boolean
  isLoading: boolean
  impersonatedUser: ImpersonationUser | null
  loginOperator: (email: string, password: string) => Promise<void>
  logoutOperator: () => void
  refreshOperator: () => Promise<void>
  startViewAs: (userId: number) => Promise<void>
  exitViewAs: () => Promise<void>
}

interface OperatorTokenResponse {
  access: string
  refresh: string
  operator: OperatorUser
}

interface ViewAsResponse {
  access: string
  view_as_session_id: string
  effective_user: ImpersonationUser
  operator: OperatorUser
}

const OperatorContext = createContext<OperatorContextValue | null>(null)

export function OperatorProvider({ children }: { children: ReactNode }) {
  const [operator, setOperator] = useState<OperatorUser | null>(null)
  const [impersonatedUser, setImpersonatedUser] = useState<ImpersonationUser | null>(() => impersonationTokenStorage.getUser())
  const [isLoading, setIsLoading] = useState(true)

  const refreshOperator = useCallback(async () => {
    try {
      const { data } = await api.get<{ operator: OperatorUser }>('/operator/me/')
      setOperator(data.operator)
    } catch {
      operatorTokenStorage.clear()
      setOperator(null)
    }
  }, [])

  useEffect(() => {
    if (operatorTokenStorage.getAccess()) {
      refreshOperator().finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [refreshOperator])

  const loginOperator = async (email: string, password: string) => {
    const { data } = await api.post<OperatorTokenResponse>('/operator/auth/token/', { email, password })
    operatorTokenStorage.set(data.access, data.refresh)
    setOperator(data.operator)
  }

  const logoutOperator = () => {
    operatorTokenStorage.clear()
    impersonationTokenStorage.clear()
    setOperator(null)
    setImpersonatedUser(null)
  }

  const startViewAs = async (userId: number) => {
    const { data } = await api.post<ViewAsResponse>(`/operator/view-as/${userId}/`, {})
    impersonationTokenStorage.set(data.access, data.view_as_session_id, data.effective_user)
    setOperator(data.operator)
    setImpersonatedUser(data.effective_user)
    window.dispatchEvent(new Event('view-as-started'))
  }

  const exitViewAs = async () => {
    const sessionId = impersonationTokenStorage.getSessionId()
    try {
      if (sessionId) await api.post('/operator/view-as/exit/', { view_as_session_id: sessionId })
    } finally {
      impersonationTokenStorage.clear()
      setImpersonatedUser(null)
      window.dispatchEvent(new Event('view-as-exited'))
    }
  }

  return (
    <OperatorContext.Provider
      value={{
        operator,
        isOperatorAuthenticated: !!operator,
        isLoading,
        impersonatedUser,
        loginOperator,
        logoutOperator,
        refreshOperator,
        startViewAs,
        exitViewAs,
      }}
    >
      {children}
    </OperatorContext.Provider>
  )
}

export function useOperator() {
  const ctx = useContext(OperatorContext)
  if (!ctx) throw new Error('useOperator must be used inside OperatorProvider')
  return ctx
}
