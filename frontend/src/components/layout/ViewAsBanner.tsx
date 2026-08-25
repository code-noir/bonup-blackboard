import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOperator } from '@/context/OperatorContext'

export default function ViewAsBanner() {
  const { impersonatedUser, exitViewAs } = useOperator()
  const navigate = useNavigate()
  const [exiting, setExiting] = useState(false)

  if (!impersonatedUser) return null

  const displayName = [impersonatedUser.first_name, impersonatedUser.last_name].filter(Boolean).join(' ') || impersonatedUser.email

  const handleExit = async () => {
    setExiting(true)
    try {
      await exitViewAs()
      navigate('/operator', { replace: true })
    } finally {
      setExiting(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 'var(--sidebar-w, 216px)',
        right: 0,
        zIndex: 55,
        minHeight: 40,
        background: '#7F1D1D',
        color: '#fff',
        borderBottom: '1px solid rgba(255,255,255,0.18)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '7px 20px',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: '0.14em', textTransform: 'uppercase' }}>Viewing as</span>
        <span style={{ marginLeft: 10, fontSize: 13, fontWeight: 750 }}>{displayName}</span>
        <span style={{ marginLeft: 8, fontSize: 12, color: 'rgba(255,255,255,0.78)' }}>{impersonatedUser.email}</span>
      </div>
      <button
        type="button"
        onClick={handleExit}
        disabled={exiting}
        style={{
          border: '1px solid rgba(255,255,255,0.55)',
          borderRadius: 6,
          background: '#fff',
          color: '#7F1D1D',
          cursor: exiting ? 'default' : 'pointer',
          fontSize: 12,
          fontWeight: 850,
          padding: '5px 12px',
          whiteSpace: 'nowrap',
          opacity: exiting ? 0.75 : 1,
        }}
      >
        {exiting ? 'Exiting...' : 'Exit User View'}
      </button>
    </div>
  )
}
