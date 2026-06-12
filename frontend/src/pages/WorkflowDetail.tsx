import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '@/api/client'

type AgreementExchangeFromWorkflowResponse = {
  exchange_id: string
  redirect_url: string
}

type AgreementExchangeErrorResponse = {
  code?: string
  detail?: string
  error?: string
}

export default function WorkflowDetail() {
  const { workflowId } = useParams()
  const navigate = useNavigate()
  const [error, setError] = useState('')

  useEffect(() => {
    if (!workflowId) {
      setError('Workflow id is missing.')
      return
    }

    let cancelled = false
    setError('')
    api.post<AgreementExchangeFromWorkflowResponse>('/agreement-exchange/from-workflow/', { workflow_id: workflowId })
      .then(({ data }) => {
        if (!cancelled) navigate(data.redirect_url || `/agreement-exchange/${data.exchange_id}`, { replace: true })
      })
      .catch((err) => {
        if (!cancelled) {
          const data = err?.response?.data as AgreementExchangeErrorResponse | undefined
          const message = data?.detail || data?.error || 'Agreement Exchange could not be opened.'
          setError(data?.code ? `${data.code}: ${message}` : message)
        }
      })

    return () => { cancelled = true }
  }, [navigate, workflowId])

  if (error) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/workflows')}
          style={{ height: 34, padding: '0 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: 'white', color: '#374151', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
        >
          Back to Workflows
        </button>
        <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 12, padding: '12px 14px', fontSize: 13, color: '#B91C1C' }}>
          {error}
        </div>
      </div>
    )
  }

  return <div style={{ color: '#6B7280' }}>Opening Agreement Exchange...</div>
}
