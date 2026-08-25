// frontend/src/components/admin/RequireAdmin.tsx
//
// Guards admin routes. Requires an operator-scoped session, not a normal staff login.

import { Navigate, useLocation } from 'react-router-dom'
import { useOperator } from '@/context/OperatorContext'

export default function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { isOperatorAuthenticated, isLoading } = useOperator()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-4 border-amber-500 border-t-transparent" />
      </div>
    )
  }

  if (!isOperatorAuthenticated) {
    return <Navigate to="/operator/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
