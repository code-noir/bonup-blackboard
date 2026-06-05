import { useState } from 'react'
import api from '@/api/client'

type WorkflowSharePanelProps = {
  workflowId: string
  defaultCounterpartyEmail?: string
  compact?: boolean
}

type ShareLink = {
  invite_url: string
  counterparty_email: string
  shared_workflow_url: string
  email_sent?: boolean
  invite_email?: string
  invite_subject?: string
}

export default function WorkflowSharePanel({ workflowId, defaultCounterpartyEmail = '', compact = false }: WorkflowSharePanelProps) {
  const [counterpartyEmail, setCounterpartyEmail] = useState(defaultCounterpartyEmail)
  const [shareLink, setShareLink] = useState<ShareLink | null>(null)
  const [success, setSuccess] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState('')

  async function createLink() {
    setIsCreating(true)
    setError('')
    setSuccess('')
    try {
      const { data } = await api.post<ShareLink>(`/ai/workflows/${workflowId}/share-link/`, {
        counterparty_email: counterpartyEmail,
      })
      setShareLink(data)
      setCounterpartyEmail(data.counterparty_email)
      setSuccess(data.email_sent ? `Invite email sent to ${data.invite_email || data.counterparty_email}.` : 'Invite link created.')
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Invite link could not be created.')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div style={{ background: 'white', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)', padding: compact ? 12 : 16 }}>
      <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: '0 0 10px' }}>Invite Counterparty</p>
      {error && <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: '#B91C1C', marginBottom: 10 }}>{error}</div>}
      {success && <div style={{ background: '#ECFDF5', border: '1px solid #6EE7B7', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: '#065F46', marginBottom: 10 }}>{success}</div>}
      <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'minmax(0, 1fr) auto', gap: 9 }}>
        <input value={counterpartyEmail} onChange={(event) => setCounterpartyEmail(event.target.value)} placeholder="Counterparty email" style={{ height: 34, border: '1px solid #E5E7EB', borderRadius: 8, padding: '0 10px', fontSize: 12, color: '#374151', outline: 'none' }} />
        <button onClick={createLink} disabled={isCreating || !counterpartyEmail.trim()} style={{ height: 34, padding: '0 13px', border: 'none', borderRadius: 8, background: isCreating || !counterpartyEmail.trim() ? '#9CA3AF' : '#0F1F3D', color: 'white', fontSize: 12, fontWeight: 700, cursor: isCreating || !counterpartyEmail.trim() ? 'default' : 'pointer' }}>
          {isCreating ? 'Sending...' : 'Send Invite Email'}
        </button>
      </div>
      {shareLink && (
        <div style={{ marginTop: 10, background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 10 }}>
          <p style={{ fontSize: 11, color: '#6B7280', margin: '0 0 5px' }}>Invite link:</p>
          <p style={{ fontSize: 12, color: '#0F1F3D', margin: 0, wordBreak: 'break-all' }}>{shareLink.invite_url}</p>
        </div>
      )}
    </div>
  )
}
