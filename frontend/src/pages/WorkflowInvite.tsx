import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '@/api/client'
import { useAuth } from '@/context/AuthContext'

type InviteContext = {
  token: string
  workflow_id: string
  source_label: string
  current_state: string
  counterparty_email: string
  initiator_name: string
  active_version?: {
    version_number: number
    status: string
  } | null
}

export default function WorkflowInvite() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuth()
  const [invite, setInvite] = useState<InviteContext | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isAccepting, setIsAccepting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    if (!token) return
    api.get<InviteContext>(`/ai/workflow-shares/${token}/`)
      .then(({ data }) => {
        if (!cancelled) setInvite(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.error || 'Invite could not be loaded.')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function acceptInvite() {
    if (!token) return
    setIsAccepting(true)
    setError('')
    try {
      const { data } = await api.post<{ workflow_id: string }>(`/ai/workflow-shares/${token}/accept/`, {})
      navigate(`/shared/workflows/${data.workflow_id}`)
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Invite could not be accepted.')
    } finally {
      setIsAccepting(false)
    }
  }

  if (isLoading) return <div style={{ maxWidth: 720, margin: '64px auto', color: '#6B7280' }}>Loading invite...</div>

  return (
    <div style={{ maxWidth: 720, margin: '64px auto', background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 8, padding: 24 }}>
      <h1 style={{ fontSize: 24, color: '#0F1F3D', margin: '0 0 8px' }}>Agreement Invite</h1>
      {invite && <p style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.6, margin: '0 0 18px' }}>{invite.initiator_name || 'A bonUP user'} invited you to review a structured agreement.</p>}
      {error && <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#B91C1C', marginBottom: 16 }}>{error}</div>}
      {invite && (
        <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14, marginBottom: 18 }}>
          <Info label="Workflow" value={invite.source_label || invite.workflow_id} />
          <Info label="Status" value={invite.current_state.replaceAll('_', ' ')} />
          <Info label="Version" value={invite.active_version ? `v${invite.active_version.version_number} · ${invite.active_version.status}` : 'Not available'} />
          <Info label="Invited email" value={invite.counterparty_email || 'Not specified'} />
        </div>
      )}
      {isAuthenticated ? (
        <button onClick={acceptInvite} disabled={isAccepting} style={{ height: 38, padding: '0 16px', background: isAccepting ? '#9CA3AF' : '#243447', color: 'white', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: isAccepting ? 'default' : 'pointer' }}>
          {isAccepting ? 'Opening...' : user?.email === invite?.counterparty_email || !invite?.counterparty_email ? 'Open Agreement' : 'Accept Invite'}
        </button>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          <button onClick={() => navigate('/login')} style={{ height: 38, padding: '0 16px', background: '#243447', color: 'white', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>Log in</button>
          <button onClick={() => navigate('/register')} style={{ height: 38, padding: '0 16px', background: 'white', color: '#243447', border: '1px solid #E5E7EB', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>Create account</button>
        </div>
      )}
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ fontSize: 10, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700, margin: '0 0 2px' }}>{label}</p>
      <p style={{ fontSize: 13, color: '#374151', margin: 0 }}>{value}</p>
    </div>
  )
}
