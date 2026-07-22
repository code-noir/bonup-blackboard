import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api/client'
import WorkflowTimeline from '@/components/workflow/WorkflowTimeline'
import NegotiationCommentsPanel from '@/components/workflow/NegotiationCommentsPanel'
import WorkflowSharePanel from '@/components/workflow/WorkflowSharePanel'

type ReviewType = 'analysis_only' | 'analysis_plus_counter'

type AnalysisResult = {
  conversation_id: string
  workflow_id?: string
  summary: string
  key_terms: Record<string, unknown>
  red_flags: string[]
  questions: string[]
}

type CounterResult = {
  id?: string
  conversation_id: string
  workflow_id?: string
  status?: string
  created_version_id?: string | null
  summary: string
  concerning_clauses: Array<{
    clause_reference?: string
    concern?: string
    counter_language?: string
  }>
  negotiation_strategy: {
    push_on?: string[]
    concede?: string[]
  }
  question_answers?: Array<{
    question?: string
    answer?: string
  }>
  revised_contract: string
}

type SavedContractReview = {
  id: string
  title: string
  review_type: ReviewType
  workflow_state: string
  completed_states: string[]
  pending_states: string[]
  state_timestamps: Record<string, string>
  contract_id?: string | null
  created_version_id?: string | null
  sent_to_counterparty_email?: string
  counterparty_email?: string
  counterparty_requested_changes?: Array<unknown>
  last_activity?: {
    activity_type: string
    description: string
    created_at: string
  } | null
  source_label: string
  original_contract_text?: string
  analysis_result?: AnalysisResult
  counter_result?: CounterResult
  saved_at: string
}

type WorkflowRecord = {
  id: string
  current_state: string
  completed_states: string[]
  pending_states: string[]
  state_timestamps: Record<string, string>
  source_label: string
  contract_id?: string | null
  created_version_id?: string | null
  sent_to_counterparty_email?: string
  counterparty_email?: string
  counterparty_requested_changes?: Array<unknown>
  last_activity?: {
    activity_type: string
    description: string
    created_at: string
  } | null
  created_at: string
  updated_at: string
  review_result?: {
    id: string
    conversation_id?: string
    summary: string
    key_terms: Record<string, unknown>
    risks?: string[]
    red_flags?: string[]
    identified_risks?: string[]
    questions: string[]
  } | null
  counter_drafts?: Array<{
    id: string
    conversation_id?: string
    summary: string
    concerning_clauses?: CounterResult['concerning_clauses']
    negotiation_strategy?: CounterResult['negotiation_strategy']
    question_answers?: CounterResult['question_answers']
    revised_contract: string
    status?: string
    created_version_id?: string | null
    created_at: string
  }>
}

function renderValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ')
  if (value && typeof value === 'object') return JSON.stringify(value)
  return String(value ?? '-')
}

function reviewFromWorkflow(workflow: WorkflowRecord): SavedContractReview {
  const review = workflow.review_result
  const counterDraft = workflow.counter_drafts?.[0]

  return {
    id: workflow.id,
    title: counterDraft ? 'Contract Review + Counter' : 'Contract Workflow',
    workflow_state: workflow.current_state,
    completed_states: workflow.completed_states || [],
    pending_states: workflow.pending_states || [],
    state_timestamps: workflow.state_timestamps || {},
    review_type: counterDraft ? 'analysis_plus_counter' : 'analysis_only',
    contract_id: workflow.contract_id || null,
    created_version_id: workflow.created_version_id || null,
    sent_to_counterparty_email: workflow.sent_to_counterparty_email || '',
    counterparty_email: workflow.counterparty_email || '',
    counterparty_requested_changes: workflow.counterparty_requested_changes || [],
    last_activity: workflow.last_activity || null,
    source_label: workflow.source_label || 'Saved workflow',
    analysis_result: review ? {
      conversation_id: review.conversation_id || '',
      summary: review.summary,
      key_terms: review.key_terms || {},
      red_flags: review.identified_risks || review.risks || review.red_flags || [],
      questions: review.questions || [],
    } : undefined,
    counter_result: counterDraft ? {
      id: counterDraft.id,
      conversation_id: counterDraft.conversation_id || '',
      summary: counterDraft.summary,
      concerning_clauses: counterDraft.concerning_clauses || [],
      negotiation_strategy: counterDraft.negotiation_strategy || {},
      question_answers: counterDraft.question_answers || [],
      revised_contract: counterDraft.revised_contract,
      status: counterDraft.status,
      created_version_id: counterDraft.created_version_id || null,
    } : undefined,
    saved_at: workflow.updated_at || workflow.created_at,
  }
}

async function loadSavedReviews(): Promise<SavedContractReview[]> {
  const { data } = await api.get<{ results: WorkflowRecord[] }>('/ai/workflows/')
  return (data.results || []).map(reviewFromWorkflow)
}


export default function ContractReview() {
  const navigate = useNavigate()

  const [savedReviews, setSavedReviews] = useState<SavedContractReview[]>([])
  const [openReviewId, setOpenReviewId] = useState('')
  const [activeWorkflowId, setActiveWorkflowId] = useState('')
  const [contractText, setContractText] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [reviewType, setReviewType] = useState<ReviewType>('analysis_plus_counter')
  const [counterTerms, setCounterTerms] = useState('')
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [counterResult, setCounterResult] = useState<CounterResult | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isCountering, setIsCountering] = useState(false)
  const [approvingWorkflowId, setApprovingWorkflowId] = useState('')
  const [sendingWorkflowId, setSendingWorkflowId] = useState('')
  const [counterpartyEmail, setCounterpartyEmail] = useState('')
  const [error, setError] = useState('')
  const [savedMessage, setSavedMessage] = useState('')

  const hasSource = Boolean(selectedFile || contractText.trim())
  const openReview = savedReviews.find((review) => review.id === openReviewId) ?? null
  const canSaveReview = reviewType === 'analysis_only'
    ? Boolean(analysisResult)
    : Boolean(analysisResult && counterResult)

  useEffect(() => {
    let cancelled = false

    loadSavedReviews()
      .then((reviews) => {
        if (!cancelled) setSavedReviews(reviews)
      })
      .catch(() => {
        if (!cancelled) setSavedReviews([])
      })

    return () => {
      cancelled = true
    }
  }, [])

  async function refreshWorkflows(openId?: string) {
    const reviews = await loadSavedReviews()
    setSavedReviews(reviews)
    if (openId) setOpenReviewId(openId)
    return reviews
  }

  async function createWorkflow() {
    const { data } = await api.post<WorkflowRecord>('/ai/workflows/', {
      source_label: selectedFile?.name || 'Pasted contract text',
    })
    setActiveWorkflowId(data.id)
    await refreshWorkflows(data.id)
    return data.id
  }

  async function handleAnalyze() {
    if (!hasSource) return
    setIsAnalyzing(true)
    setAnalysisResult(null)
    setCounterResult(null)
    setSavedMessage('')
    setError('')
    let workflowId = activeWorkflowId
    try {
      if (!workflowId) workflowId = await createWorkflow()

      if (selectedFile) {
        const formData = new FormData()
        formData.append('file', selectedFile)
        formData.append('workflow_id', workflowId)
        const { data } = await api.post<AnalysisResult>('/ai/analyze-contract/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        setAnalysisResult(data)
      } else {
        const { data } = await api.post<AnalysisResult>('/ai/analyze-contract/', {
          contract_text: contractText,
          workflow_id: workflowId,
        })
        setAnalysisResult(data)
      }

      await refreshWorkflows(workflowId)
      setOpenReviewId(workflowId)
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Contract review failed. Please try again.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  async function handleGenerateCounter() {
    if (!hasSource || !counterTerms.trim()) return
    if (!activeWorkflowId) {
      setError('Analyze the contract before generating a counter draft.')
      return
    }
    setIsCountering(true)
    setCounterResult(null)
    setSavedMessage('')
    setError('')
    try {
      if (selectedFile) {
        const formData = new FormData()
        formData.append('file', selectedFile)
        formData.append('counter_terms', counterTerms)
        formData.append('workflow_id', activeWorkflowId)
        const { data } = await api.post<CounterResult>('/ai/counter-contract/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        setCounterResult(data)
      } else {
        const { data } = await api.post<CounterResult>('/ai/counter-contract/', {
          contract_text: contractText,
          counter_terms: counterTerms,
          workflow_id: activeWorkflowId,
        })
        setCounterResult(data)
      }

      await refreshWorkflows(activeWorkflowId)
      setOpenReviewId(activeWorkflowId)
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Counter generation failed. Please try again.')
    } finally {
      setIsCountering(false)
    }
  }

  async function handleSaveReview() {
    if (!canSaveReview) {
      setError(reviewType === 'analysis_plus_counter'
        ? 'Generate the counter-contract before saving this review.'
        : 'Analyze the contract before saving this review.')
      return
    }

    try {
      const reviews = await loadSavedReviews()
      setSavedReviews(reviews)
      if (activeWorkflowId) setOpenReviewId(activeWorkflowId)
      setSavedMessage('Review saved.')
    } catch {
      setError('Saved review could not be refreshed. Please try again.')
    }
  }

  async function handleApproveCounterDraft(review: SavedContractReview) {
    const draftId = review.counter_result?.id
    if (!draftId) return
    setApprovingWorkflowId(review.id)
    setSavedMessage('')
    setError('')
    try {
      await api.post(`/ai/counter-drafts/${draftId}/approve/`, {})
      await refreshWorkflows(review.id)
      setSavedMessage('Counter draft approved into a contract version.')
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Counter draft approval failed. Please try again.')
    } finally {
      setApprovingWorkflowId('')
    }
  }

  async function handleSendWorkflow(review: SavedContractReview) {
    setSendingWorkflowId(review.id)
    setSavedMessage('')
    setError('')
    try {
      await api.post(`/ai/workflows/${review.id}/send/`, {
        counterparty_email: counterpartyEmail.trim(),
      })
      await refreshWorkflows(review.id)
      setCounterpartyEmail('')
      setSavedMessage('Workflow sent to counterparty.')
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Send progression failed. Please try again.')
    } finally {
      setSendingWorkflowId('')
    }
  }


  function resetNewReview() {
    setContractText('')
    setSelectedFile(null)
    setCounterTerms('')
    setAnalysisResult(null)
    setCounterResult(null)
    setActiveWorkflowId('')
    setSavedMessage('')
    setError('')
  }

  return (
    <div style={{ maxWidth: 980, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#0F1F3D', marginBottom: 6 }}>
          Contract Review
        </h1>
        <p style={{ fontSize: 13, color: '#6B7280', margin: 0 }}>
          Analyze a contract and optionally generate a counter-contract under one review.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.1fr) minmax(300px, 0.9fr)', gap: 18 }}>
        <div>
          <div style={{ background: 'white', borderRadius: 11, border: '1px solid rgba(0,0,0,0.08)', padding: 20, marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
              <div>
                <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>Start New Review</p>
                <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0' }}>
                  Choose analysis only or include a counter-contract.
                </p>
              </div>
              <button
                onClick={resetNewReview}
                style={{ border: '1px solid #E5E7EB', background: 'white', color: '#6B7280', borderRadius: 8, height: 34, padding: '0 12px', fontSize: 12, cursor: 'pointer' }}
              >
                New
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
              {[
                ['analysis_only', 'Analyze only', 'Review summary, key terms, red flags, and questions.'],
                ['analysis_plus_counter', 'Analyze + Counter', 'Review the contract, then generate revised counter language.'],
              ].map(([value, label, description]) => (
                <button
                  key={value}
                  onClick={() => setReviewType(value as ReviewType)}
                  style={{
                    textAlign: 'left',
                    padding: 14,
                    borderRadius: 8,
                    border: reviewType === value ? '1px solid #243447' : '1px solid #E5E7EB',
                    background: reviewType === value ? '#F8FAFC' : 'white',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ display: 'block', fontSize: 13, fontWeight: 700, color: '#0F1F3D', marginBottom: 4 }}>{label}</span>
                  <span style={{ display: 'block', fontSize: 12, color: '#6B7280', lineHeight: 1.5 }}>{description}</span>
                </button>
              ))}
            </div>

            <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: '10px 12px', fontSize: 12, color: '#6B7280', marginBottom: 16 }}>
              Review analysis runs inside the workflow workspace and saves directly into backend workflow state.
            </div>

            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>
              Contract PDF
            </label>
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              style={{ width: '100%', border: '1px solid #E5E7EB', borderRadius: 8, padding: 10, fontSize: 13, color: '#374151', boxSizing: 'border-box', marginBottom: 16 }}
            />

            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>
              Contract Text
            </label>
            <textarea
              value={contractText}
              onChange={(event) => setContractText(event.target.value)}
              placeholder="Paste your contract text here..."
              style={{ width: '100%', minHeight: 220, border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, fontSize: 13, color: '#374151', lineHeight: 1.6, resize: 'vertical', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box', marginBottom: 16 }}
            />

            <button
              onClick={handleAnalyze}
              disabled={isAnalyzing || !hasSource}
              style={{ height: 40, padding: '0 18px', background: isAnalyzing || !hasSource ? '#9CA3AF' : '#243447', color: 'white', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: isAnalyzing || !hasSource ? 'default' : 'pointer' }}
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze Contract'}
            </button>
          </div>

          {reviewType === 'analysis_plus_counter' && analysisResult && (
            <div style={{ background: 'white', borderRadius: 11, border: '1px solid rgba(0,0,0,0.08)', padding: 20, marginBottom: 16 }}>
              <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: '0 0 10px' }}>Counter-Contract</p>
              <p style={{ fontSize: 12, color: '#6B7280', margin: '0 0 12px', lineHeight: 1.5 }}>
                Required before saving an Analysis + Counter review.
              </p>
              <textarea
                value={counterTerms}
                onChange={(event) => setCounterTerms(event.target.value)}
                placeholder="Describe your counter terms or proposed changes..."
                style={{ width: '100%', minHeight: 120, border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, fontSize: 13, color: '#374151', lineHeight: 1.6, resize: 'vertical', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box', marginBottom: 12 }}
              />
              <button
                onClick={handleGenerateCounter}
                disabled={isCountering || !counterTerms.trim()}
                style={{ height: 38, padding: '0 16px', background: isCountering || !counterTerms.trim() ? '#9CA3AF' : '#243447', color: 'white', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: isCountering || !counterTerms.trim() ? 'default' : 'pointer' }}
              >
                {isCountering ? 'Generating...' : 'Generate Counter'}
              </button>
            </div>
          )}

          {error && (
            <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#B91C1C', marginBottom: 16 }}>
              {error}
            </div>
          )}

          {(analysisResult || counterResult) && (
            <div style={{ background: 'white', borderRadius: 11, border: '1px solid rgba(0,0,0,0.08)', padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 18 }}>
                <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>Current Review</p>
                <button
                  onClick={handleSaveReview}
                  disabled={!canSaveReview}
                  style={{ height: 36, padding: '0 14px', background: canSaveReview ? '#243447' : '#9CA3AF', color: 'white', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: canSaveReview ? 'pointer' : 'default' }}
                >
                  Save Review Draft
                </button>
              </div>
              {reviewType === 'analysis_plus_counter' && analysisResult && !counterResult && (
                <p style={{ fontSize: 12, color: '#9CA3AF', margin: '0 0 12px' }}>
                  Generate the counter-contract to save clauses, negotiation strategy, and revised contract.
                </p>
              )}
              {savedMessage && <p style={{ fontSize: 12, color: '#065F46', margin: '0 0 12px' }}>{savedMessage}</p>}
              {analysisResult && <ReviewAnalysis result={analysisResult} />}
              {counterResult && <ReviewCounter result={counterResult} />}
            </div>
          )}
        </div>

        <div>
          <div style={{ background: 'white', borderRadius: 11, border: '1px solid rgba(0,0,0,0.08)', padding: 20, marginBottom: 16 }}>
            <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: '0 0 12px' }}>Saved Reviews</p>
            {savedReviews.length ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {savedReviews.map((review) => (
                  <button
                    key={review.id}
                    onClick={() => setOpenReviewId(review.id)}
                    style={{ textAlign: 'left', border: '1px solid #E5E7EB', background: openReviewId === review.id ? '#F8FAFC' : 'white', borderRadius: 8, padding: 12, cursor: 'pointer' }}
                  >
                    <span style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F1F3D' }}>{review.title || 'Contract Review'}</span>
                      <span style={{ fontSize: 11, color: '#D4900A', fontWeight: 700 }}>
                        {review.workflow_state.replaceAll('_', ' ')}
                      </span>
                    </span>
                    <span style={{ display: 'block', fontSize: 12, color: '#6B7280', marginBottom: 4 }}>{review.source_label}</span>
                    <span style={{ display: 'block', fontSize: 11, color: '#9CA3AF' }}>{new Date(review.saved_at).toLocaleString()}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>Saved reviews will appear here.</p>
            )}
          </div>

          {openReview && (
            <div style={{ background: 'white', borderRadius: 11, border: '1px solid rgba(0,0,0,0.08)', padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
                <div>
                  <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>{openReview.title}</p>
                  <p style={{ fontSize: 11, color: '#9CA3AF', margin: '4px 0 0' }}>{openReview.id}</p>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {openReview.workflow_state && (
                    <button
                      onClick={() => navigate(`/workflows/${openReview.id}`)}
                      style={{ height: 30, border: '1px solid #243447', background: 'white', color: '#243447', borderRadius: 8, padding: '0 10px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                    >
                      Open workspace
                    </button>
                  )}
                  <button
                    onClick={() => setOpenReviewId('')}
                    style={{ height: 30, border: '1px solid #E5E7EB', background: 'white', color: '#6B7280', borderRadius: 8, padding: '0 10px', fontSize: 12, cursor: 'pointer' }}
                  >
                    Close
                  </button>
                </div>
              </div>
              <div style={{ marginBottom: 14 }}>
                <WorkflowTimeline
                  compact
                  workflow={{
                    id: openReview.id,
                    current_state: openReview.workflow_state,
                    completed_states: openReview.completed_states,
                    pending_states: openReview.pending_states,
                    state_timestamps: openReview.state_timestamps,
                    created_version_id: openReview.created_version_id,
                    counterparty_email: openReview.counterparty_email,
                    sent_to_counterparty_email: openReview.sent_to_counterparty_email,
                    last_activity: openReview.last_activity,
                  }}
                />
              </div>
              {openReview.workflow_state === 'counter_draft_ready' && openReview.counter_result?.id && (
                <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginBottom: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                  <span style={{ fontSize: 12, color: '#6B7280' }}>Draft ready for approval</span>
                  <button
                    onClick={() => handleApproveCounterDraft(openReview)}
                    disabled={approvingWorkflowId === openReview.id}
                    style={{ height: 32, border: 'none', background: approvingWorkflowId === openReview.id ? '#9CA3AF' : '#243447', color: 'white', borderRadius: 8, padding: '0 12px', fontSize: 12, fontWeight: 600, cursor: approvingWorkflowId === openReview.id ? 'default' : 'pointer' }}
                  >
                    {approvingWorkflowId === openReview.id ? 'Approving...' : 'Approve Draft'}
                  </button>
                </div>
              )}
              {openReview.workflow_state === 'version_created' && (
                <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginBottom: 14, display: 'grid', gap: 10 }}>
                  <input
                    value={counterpartyEmail}
                    onChange={(event) => setCounterpartyEmail(event.target.value)}
                    placeholder="Counterparty email"
                    style={{ height: 34, border: '1px solid #E5E7EB', borderRadius: 8, padding: '0 10px', fontSize: 12, color: '#374151', outline: 'none' }}
                  />
                  <button
                    onClick={() => handleSendWorkflow(openReview)}
                    disabled={sendingWorkflowId === openReview.id}
                    style={{ height: 32, border: 'none', background: sendingWorkflowId === openReview.id ? '#9CA3AF' : '#243447', color: 'white', borderRadius: 8, padding: '0 12px', fontSize: 12, fontWeight: 600, cursor: sendingWorkflowId === openReview.id ? 'default' : 'pointer' }}
                  >
                    {sendingWorkflowId === openReview.id ? 'Sending...' : 'Send to Counterparty'}
                  </button>
                </div>
              )}
              {openReview.workflow_state === 'sent_to_counterparty' && openReview.sent_to_counterparty_email && (
                <p style={{ fontSize: 12, color: '#065F46', margin: '0 0 14px' }}>Sent to {openReview.sent_to_counterparty_email}</p>
              )}
              <div style={{ marginBottom: 14 }}>
                <WorkflowSharePanel workflowId={openReview.id} defaultCounterpartyEmail={openReview.counterparty_email || openReview.sent_to_counterparty_email || counterpartyEmail} compact />
              </div>
              <div style={{ marginBottom: 14 }}>
                <NegotiationCommentsPanel workflowId={openReview.id} compact />
              </div>
              {openReview.analysis_result ? <ReviewAnalysis result={openReview.analysis_result} compact /> : (
                <p style={{ fontSize: 13, color: '#9CA3AF' }}>No analysis was saved with this review.</p>
              )}
              {openReview.counter_result ? <ReviewCounter result={openReview.counter_result} compact /> : (
                openReview.review_type === 'analysis_plus_counter' && (
                  <p style={{ fontSize: 13, color: '#9CA3AF' }}>No counter-contract was saved with this review.</p>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ReviewAnalysis({ result, compact = false }: { result: AnalysisResult; compact?: boolean }) {
  return (
    <div style={{ marginBottom: compact ? 18 : 24 }}>
      <p style={{ fontWeight: 700, margin: '0 0 8px', color: '#0F1F3D' }}>Analysis Summary</p>
      <p style={{ margin: '0 0 14px', fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{result.summary || '-'}</p>

      <p style={{ fontWeight: 700, margin: '0 0 8px', color: '#0F1F3D' }}>Key Terms</p>
      {Object.keys(result.key_terms || {}).length ? (
        <ul style={{ margin: '0 0 14px', paddingLeft: 18, fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
          {Object.entries(result.key_terms).map(([key, value]) => (
            <li key={key}><strong>{key}:</strong> {renderValue(value)}</li>
          ))}
        </ul>
      ) : (
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#9CA3AF' }}>-</p>
      )}

      <p style={{ fontWeight: 700, margin: '0 0 8px', color: '#0F1F3D' }}>Red Flags</p>
      {result.red_flags.length ? (
        <ul style={{ margin: '0 0 14px', paddingLeft: 18, fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
          {result.red_flags.map((item, index) => <li key={index}>{item}</li>)}
        </ul>
      ) : (
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#9CA3AF' }}>-</p>
      )}

      <p style={{ fontWeight: 700, margin: '0 0 8px', color: '#0F1F3D' }}>Questions</p>
      {result.questions.length ? (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
          {result.questions.map((item, index) => <li key={index}>{item}</li>)}
        </ul>
      ) : (
        <p style={{ margin: 0, fontSize: 13, color: '#9CA3AF' }}>-</p>
      )}
    </div>
  )
}

function ReviewCounter({ result, compact = false }: { result: CounterResult; compact?: boolean }) {
  return (
    <div style={{ borderTop: '1px solid #E5E7EB', paddingTop: compact ? 14 : 18 }}>
      <CollapsibleResultSection title="Counter Summary">
        <p style={{ margin: 0, fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{result.summary || '-'}</p>
      </CollapsibleResultSection>

      <CollapsibleResultSection title="Concerning Clauses">
        {result.concerning_clauses.length ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
            {result.concerning_clauses.map((clause, index) => (
              <li key={index}>
                <strong>{clause.clause_reference || 'Clause'}:</strong> {clause.concern || '-'}
                {clause.counter_language && <div>Counter language: {clause.counter_language}</div>}
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ margin: 0, fontSize: 13, color: '#9CA3AF' }}>-</p>
        )}
      </CollapsibleResultSection>

      <CollapsibleResultSection title="Negotiation Strategy">
        <p style={{ margin: '0 0 6px', fontSize: 13, color: '#374151' }}>
          <strong>Push on:</strong> {(result.negotiation_strategy.push_on || []).join(', ') || '-'}
        </p>
        <p style={{ margin: 0, fontSize: 13, color: '#374151' }}>
          <strong>Concede:</strong> {(result.negotiation_strategy.concede || []).join(', ') || '-'}
        </p>
      </CollapsibleResultSection>

      <CollapsibleResultSection title="Revised Contract">
        <div style={{ maxHeight: compact ? 300 : 520, overflow: 'auto', background: '#F8FAFC', borderRadius: 8, padding: 12, fontSize: 12, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
          {result.revised_contract || '-'}
        </div>
      </CollapsibleResultSection>

      <CollapsibleResultSection title="Important Questions About This Contract" last>
        {result.question_answers?.length ? (
          <div style={{ display: 'grid', gap: 10 }}>
            {result.question_answers.map((item, index) => (
              <QuestionAnswerItem
                key={index}
                question={item.question || 'Question'}
                answer={item.answer || '-'}
              />
            ))}
          </div>
        ) : (
          <p style={{ margin: 0, fontSize: 13, color: '#9CA3AF' }}>-</p>
        )}
      </CollapsibleResultSection>
    </div>
  )
}

function QuestionAnswerItem({ question, answer }: { question: string; answer: string }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden' }}>
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          background: 'transparent',
          border: 'none',
          padding: 12,
          cursor: 'pointer',
          textAlign: 'left',
          font: 'inherit',
          color: '#0F1F3D',
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 700 }}>{question}</span>
        <span style={{ fontSize: 12, color: '#6B7280', flexShrink: 0 }}>{isOpen ? 'Hide' : 'Show'}</span>
      </button>
      {isOpen && (
        <p style={{ margin: 0, padding: '0 12px 12px', fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
          {answer}
        </p>
      )}
    </div>
  )
}

function CollapsibleResultSection({
  title,
  children,
  last = false,
}: {
  title: string
  children: React.ReactNode
  last?: boolean
}) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <section style={{ borderBottom: last ? 'none' : '1px solid #E5E7EB', paddingBottom: 14, marginBottom: last ? 0 : 14 }}>
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          background: 'transparent',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          font: 'inherit',
          color: '#0F1F3D',
        }}
      >
        <span style={{ fontWeight: 700 }}>{title}</span>
        <span style={{ fontSize: 12, color: '#6B7280' }}>{isOpen ? 'Hide' : 'Show'}</span>
      </button>
      {isOpen && <div style={{ marginTop: 8 }}>{children}</div>}
    </section>
  )
}
