import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '@/api/client'
import WorkflowWorkspace, { WorkflowRecord } from '@/components/workflow/WorkflowWorkspace'

type WorkflowDetailResponse = WorkflowRecord

export default function WorkflowDetail() {
  const { workflowId } = useParams()
  const navigate = useNavigate()
  const [workflow, setWorkflow] = useState<WorkflowRecord | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!workflowId) return

    let cancelled = false
    setIsLoading(true)
    api.get<WorkflowDetailResponse>(`/ai/workflows/${workflowId}/`)
      .then(({ data }) => {
        if (!cancelled) setWorkflow(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.error || 'Workflow could not be loaded.')
          setWorkflow(null)
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => { cancelled = true }
  }, [workflowId])

  if (isLoading) {
    return <div style={{ color: '#6B7280' }}>Loading workflow workspace...</div>
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/workflows')}
          style={{ height: 34, padding: '0 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: 'white', color: '#374151', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
        >
          ← Back to Workflows
        </button>
        <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 12, padding: '12px 14px', fontSize: 13, color: '#B91C1C' }}>
          {error}
        </div>
      </div>
    )
  }

  if (!workflow) {
    return null
  }

  return (
    <div className="space-y-4">
      <button
        onClick={() => navigate('/workflows')}
        style={{ height: 34, padding: '0 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: 'white', color: '#374151', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
      >
        ← Back to Workflows
      </button>
      <WorkflowWorkspace workflow={workflow} />
    </div>
  )
}
