import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useOperator } from '@/context/OperatorContext'
import { impersonationTokenStorage } from '@/api/client'

export default function CustomerSignOutButton() {
  const { logout } = useAuth()
  const { impersonatedUser, exitViewAs } = useOperator()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const handleClick = async () => {
    setBusy(true)
    setError('')
    try {
      if (impersonationTokenStorage.getAccess()) {
        await exitViewAs()
        navigate('/operator', { replace: true })
      } else {
        await logout()
        navigate('/login', { replace: true })
      }
    } catch {
      setError('Sign-out could not be confirmed. Please try again.')
    } finally {
      setBusy(false)
    }
  }
  return <>
    <button type="button" disabled={busy} onClick={handleClick} className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 disabled:opacity-50">
      {busy ? 'Please wait...' : impersonatedUser ? 'Exit User View' : 'Sign out'}
    </button>
    {error && <p role="alert" className="px-4 py-2 text-sm text-red-600">{error}</p>}
  </>
}
