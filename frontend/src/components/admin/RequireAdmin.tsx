// frontend/src/components/admin/RequireAdmin.tsx
//
// Guards admin routes. Requires is_staff=true on the authenticated user.
// Structure: add role check here when a formal admin-role system is introduced.

import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-4 border-amber-500 border-t-transparent" />
      </div>
    )
  }

  if (!user?.is_staff) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}
