import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

/**
 * The API's /users/me/ response is the only source used for this gate.
 * A missing entitlement is treated as no access until the server says otherwise.
 */
export default function RequireBlackboardAccess({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) return null
  if (user?.has_blackbod_access !== true) return <Navigate to="/hub" replace />
  return children
}
