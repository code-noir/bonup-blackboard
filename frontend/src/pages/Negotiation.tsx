import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '@/api/client'

type WorkflowForContractResponse = {
  workflow_id?: string
  exchange_id?: string
  redirect_url?: string
}

export default function Negotiation() {
  const { contractId } = useParams()
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    if (!contractId) {
      navigate('/workflows', { replace: true })
      return () => {
        cancelled = true
      }
    }

    setIsLoading(true)
    setError('')
    api.post<WorkflowForContractResponse>('/ai/workflows/for-contract/', { contract_id: contractId })
      .then(({ data }) => {
        if (cancelled) return
        const redirectUrl = data.redirect_url || (data.workflow_id ? `/workflows/${data.workflow_id}` : '/workflows')
        navigate(redirectUrl, { replace: true })
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.error || 'Negotiation workflow could not be opened.')
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [contractId, navigate])

  if (isLoading) {
    return <div style={{ color: '#6B7280' }}>Opening workflow workspace...</div>
  }

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

  return null
}
