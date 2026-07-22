import { useEffect, useState } from 'react'
import api from '@/api/client'

type NegotiationComment = {
  id: string
  author_email: string
  author_name: string
  comment_type: string
  clause_reference: string
  body: string
  created_at: string
}

type NegotiationCommentsPanelProps = {
  workflowId: string
  compact?: boolean
}

const COMMENT_TYPES = [
  ['general', 'General'],
  ['clarification_request', 'Clarification'],
  ['change_request', 'Change request'],
  ['risk_note', 'Risk note'],
  ['acceptance_note', 'Acceptance note'],
] as const

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString()
}

function typeLabel(value: string) {
  return COMMENT_TYPES.find(([key]) => key === value)?.[1] || value.replaceAll('_', ' ')
}

export default function NegotiationCommentsPanel({ workflowId, compact = false }: NegotiationCommentsPanelProps) {
  const [comments, setComments] = useState<NegotiationComment[]>([])
  const [commentType, setCommentType] = useState('general')
  const [clauseReference, setClauseReference] = useState('')
  const [body, setBody] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function loadComments() {
    const { data } = await api.get<{ results: NegotiationComment[] }>(`/ai/workflows/${workflowId}/comments/`)
    setComments(data.results || [])
  }

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    loadComments()
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.error || 'Negotiation comments could not be loaded.')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [workflowId])

  async function submitComment() {
    if (!body.trim()) return
    setIsSubmitting(true)
    setError('')
    try {
      const { data } = await api.post<NegotiationComment>(`/ai/workflows/${workflowId}/comments/`, {
        comment_type: commentType,
        clause_reference: clauseReference,
        body,
      })
      setComments((items) => [...items, data])
      setBody('')
      setClauseReference('')
      setCommentType('general')
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Comment could not be added.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ background: 'white', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)', padding: compact ? 12 : 16 }}>
      <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: '0 0 12px' }}>Negotiation Comments</p>
      {error && <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: '#B91C1C', marginBottom: 12 }}>{error}</div>}

      <div style={{ display: 'grid', gap: 10, marginBottom: 14 }}>
        {isLoading ? (
          <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>Loading comments...</p>
        ) : comments.length ? comments.map((comment) => (
          <div key={comment.id} style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 10, background: '#F8FAFC' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D' }}>{comment.author_name || comment.author_email}</span>
              <span style={{ fontSize: 11, color: '#D4900A', fontWeight: 700, background: '#FEF3C7', borderRadius: 999, padding: '2px 7px' }}>{typeLabel(comment.comment_type)}</span>
              <span style={{ fontSize: 11, color: '#9CA3AF' }}>{formatDate(comment.created_at)}</span>
            </div>
            {comment.clause_reference && <p style={{ fontSize: 11, color: '#6B7280', margin: '0 0 6px' }}>Clause: {comment.clause_reference}</p>}
            <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.5, whiteSpace: 'pre-wrap', margin: 0 }}>{comment.body}</p>
          </div>
        )) : (
          <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>No structured comments yet.</p>
        )}
      </div>

      <div style={{ display: 'grid', gap: 9 }}>
        <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'minmax(0, 180px) minmax(0, 1fr)', gap: 9 }}>
          <select value={commentType} onChange={(event) => setCommentType(event.target.value)} style={{ height: 34, border: '1px solid #E5E7EB', borderRadius: 8, padding: '0 9px', fontSize: 12, color: '#374151', background: 'white' }}>
            {COMMENT_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <input value={clauseReference} onChange={(event) => setClauseReference(event.target.value)} placeholder="Clause reference" style={{ height: 34, border: '1px solid #E5E7EB', borderRadius: 8, padding: '0 10px', fontSize: 12, color: '#374151', outline: 'none' }} />
        </div>
        <textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Add a structured negotiation note..." style={{ minHeight: 90, border: '1px solid #E5E7EB', borderRadius: 8, padding: 10, fontSize: 13, color: '#374151', lineHeight: 1.5, resize: 'vertical', outline: 'none', fontFamily: 'inherit' }} />
        <button onClick={submitComment} disabled={isSubmitting || !body.trim()} style={{ justifySelf: 'start', height: 34, padding: '0 13px', border: 'none', borderRadius: 8, background: isSubmitting || !body.trim() ? '#9CA3AF' : '#243447', color: 'white', fontSize: 12, fontWeight: 700, cursor: isSubmitting || !body.trim() ? 'default' : 'pointer' }}>
          {isSubmitting ? 'Adding...' : 'Add Comment'}
        </button>
      </div>
    </div>
  )
}
