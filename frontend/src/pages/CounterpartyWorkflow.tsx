import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '@/api/client'
import WorkflowTimeline from '@/components/workflow/WorkflowTimeline'
import NegotiationCommentsPanel from '@/components/workflow/NegotiationCommentsPanel'

type SharedWorkflow = {
  id: string
  current_state: string
  completed_states: string[]
  pending_states: string[]
  state_timestamps: Record<string, string>
  counterparty_email?: string
  sent_to_counterparty_email?: string
  created_version_id?: string | null
  counterparty_requested_changes?: Array<unknown>
  last_activity?: {
    activity_type: string
    description: string
    created_at: string
  } | null
}

type ActiveVersion = {
  id: string
  contract_id: string
  version_number: number
  status: string
  content_snapshot: string
  created_at: string
}

type SharedWorkflowResponse = {
  workflow: SharedWorkflow
  active_version: ActiveVersion | null
}

export default function CounterpartyWorkflow() {
  const { workflowId } = useParams()
  const [workflow, setWorkflow] = useState<SharedWorkflow | null>(null)
  const [activeVersion, setActiveVersion] = useState<ActiveVersion | null>(null)
  const [requestedChanges, setRequestedChanges] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function loadWorkflow() {
    if (!workflowId) return
    const { data } = await api.get<SharedWorkflowResponse>(`/ai/counterparty/workflows/${workflowId}/`)
    setWorkflow(data.workflow)
    setActiveVersion(data.active_version)
  }

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    loadWorkflow()
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.error || 'Shared workflow could not be loaded.')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [workflowId])

  async function submitAction(path: string, payload: Record<string, unknown> = {}, success: string) {
    if (!workflowId) return
    setIsSubmitting(true)
    setError('')
    setMessage('')
    try {
      const { data } = await api.post<SharedWorkflowResponse>(`/ai/counterparty/workflows/${workflowId}/${path}/`, payload)
      setWorkflow(data.workflow)
      setActiveVersion(data.active_version)
      setRequestedChanges('')
      setMessage(success)
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Action failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const state = workflow?.current_state || ''
  const canRespond = state === 'counterparty_viewed' || state === 'counterparty_counter_generated'
  const canSign = state === 'counterparty_viewed' || state === 'accepted'

  if (isLoading) return <div style={{ maxWidth: 900, margin: '0 auto', color: '#6B7280' }}>Loading shared agreement...</div>

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#0F1F3D', marginBottom: 6 }}>Shared Agreement</h1>
        <p style={{ fontSize: 13, color: '#6B7280', margin: 0 }}>{state.replaceAll('_', ' ')}</p>
      </div>

      {error && <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#B91C1C', marginBottom: 16 }}>{error}</div>}
      {message && <div style={{ background: '#ECFDF5', border: '1px solid #6EE7B7', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#065F46', marginBottom: 16 }}>{message}</div>}

      <div style={{ marginBottom: 16 }}>
        <WorkflowTimeline workflow={workflow} activeVersion={activeVersion} />
      </div>

      {workflow && (
        <div style={{ marginBottom: 16 }}>
          <NegotiationCommentsPanel workflowId={workflow.id} />
        </div>
      )}

      <div style={{ background: 'white', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)', padding: 18, marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>Version {activeVersion?.version_number || '-'}</p>
          <p style={{ fontSize: 12, fontWeight: 700, color: '#D4900A', margin: 0 }}>{activeVersion?.status || 'unavailable'}</p>
        </div>
        <div style={{ maxHeight: 520, overflow: 'auto', background: '#F8FAFC', borderRadius: 8, padding: 12, fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
          {activeVersion?.content_snapshot || 'No active version is available.'}
        </div>
      </div>

      {canRespond && (
        <div style={{ background: 'white', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)', padding: 18 }}>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: '0 0 10px' }}>Respond</p>
          <textarea
            value={requestedChanges}
            onChange={(event) => setRequestedChanges(event.target.value)}
            placeholder="Request specific changes..."
            style={{ width: '100%', minHeight: 110, border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, fontSize: 13, color: '#374151', lineHeight: 1.6, resize: 'vertical', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box', marginBottom: 12 }}
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <button onClick={() => submitAction('request-changes', { requested_changes: requestedChanges }, 'Changes requested.')} disabled={isSubmitting || !requestedChanges.trim()} style={{ height: 36, padding: '0 14px', border: 'none', borderRadius: 8, background: isSubmitting || !requestedChanges.trim() ? '#9CA3AF' : '#243447', color: 'white', fontSize: 13, fontWeight: 600, cursor: isSubmitting || !requestedChanges.trim() ? 'default' : 'pointer' }}>Request Changes</button>
            <button onClick={() => submitAction('accept', {}, 'Agreement accepted.')} disabled={isSubmitting} style={{ height: 36, padding: '0 14px', border: 'none', borderRadius: 8, background: isSubmitting ? '#9CA3AF' : '#065F46', color: 'white', fontSize: 13, fontWeight: 600, cursor: isSubmitting ? 'default' : 'pointer' }}>Accept</button>
            <button onClick={() => submitAction('reject', {}, 'Agreement rejected.')} disabled={isSubmitting} style={{ height: 36, padding: '0 14px', border: '1px solid #FECACA', borderRadius: 8, background: 'white', color: '#B91C1C', fontSize: 13, fontWeight: 600, cursor: isSubmitting ? 'default' : 'pointer' }}>Reject</button>
          </div>
        </div>
      )}

      {canSign && (
        <div style={{ background: 'white', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)', padding: 18, marginTop: 16 }}>
          <button onClick={() => submitAction('sign', {}, 'Agreement signed.')} disabled={isSubmitting} style={{ height: 38, padding: '0 16px', border: 'none', borderRadius: 8, background: isSubmitting ? '#9CA3AF' : '#243447', color: 'white', fontSize: 13, fontWeight: 600, cursor: isSubmitting ? 'default' : 'pointer' }}>Sign Agreement</button>
        </div>
      )}
    </div>
  )
}
