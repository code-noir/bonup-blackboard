import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { isCancel } from 'axios'
import api, { impersonationTokenStorage, operatorTokenStorage } from '@/api/client'
import type { ImpersonationUser } from '@/api/client'
import type { OperatorUser } from '@/types/auth'

interface OperatorContextValue {
  operator: OperatorUser | null
  isOperatorAuthenticated: boolean
  sessionNotice: string
  isLoading: boolean
  impersonatedUser: ImpersonationUser | null
  loginOperator: (email: string, password: string) => Promise<void>
  logoutOperator: () => Promise<void>
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
  const [sessionNotice, setSessionNotice] = useState('')
  const [isLoading, setIsLoading] = useState(true)

  const refreshOperator = useCallback(async () => {
    const identity = operatorTokenStorage.getRefresh() || operatorTokenStorage.getAccess()
    try {
      const { data } = await api.get<{ operator: OperatorUser }>('/operator/me/')
      setOperator(data.operator)
    } catch (error) {
      const current = operatorTokenStorage.getRefresh() || operatorTokenStorage.getAccess()
      if (isCancel(error) || (current && current !== identity)) return
      operatorTokenStorage.clear()
      setOperator(null)
    }
  }, [])

  useEffect(() => {
    const clearViewAs = () => setImpersonatedUser(null)
    window.addEventListener('view-as-exited', clearViewAs)
    if (operatorTokenStorage.getAccess()) {
      refreshOperator().finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
    return () => window.removeEventListener('view-as-exited', clearViewAs)
  }, [refreshOperator])

  const loginOperator = async (email: string, password: string) => {
    const { data } = await api.post<OperatorTokenResponse>('/operator/auth/token/', { email, password })
    operatorTokenStorage.set(data.access, data.refresh)
    setOperator(data.operator)
    setSessionNotice('')
  }

  const logoutOperator = async () => {
    try {
      const refresh = operatorTokenStorage.getRefresh()
      if (!refresh) throw new Error('Operator refresh unavailable.')
      await api.post('/operator/auth/logout/', { refresh })
      setSessionNotice('')
    } catch {
      setSessionNotice('Signed out on this browser. Server sign-out could not be confirmed; the previous session may remain active until it expires.')
    } finally {
      operatorTokenStorage.clear()
      impersonationTokenStorage.clear()
      setOperator(null)
      setImpersonatedUser(null)
    }
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
      setSessionNotice('')
    } catch {
      setSessionNotice('User View closed on this browser. Server exit could not be confirmed; the previous View-As session may remain active until it expires.')
    } finally {
      impersonationTokenStorage.clear()
      setImpersonatedUser(null)
    }
  }

  return (
    <OperatorContext.Provider
      value={{
        operator,
        sessionNotice,
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
