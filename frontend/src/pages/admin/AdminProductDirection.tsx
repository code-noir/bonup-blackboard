import { FormEvent, useEffect, useMemo, useState } from 'react'
import api from '@/api/client'
import { AdminBadge, AdminTable, formatDateTime, useAdminFetch } from './adminShared'

interface ProductDirectionTask {
  task_id: string
  agent_control_task_id: string | null
  agent_id: 'PROD-01'
  objective: string
  status: string
  proposal_artifact_id: string | null
  proposal_id: string | null
  proposal_digest: string | null
  review_id: string | null
  review_digest: string | null
  runtime_failure_reason: string | null
  created_by: { id: number; email: string; display_name: string }
  created_at: string
  updated_at: string
}

interface ProductDirectionTaskPage {
  count: number
  page: number
  page_size: number
  results: ProductDirectionTask[]
}

interface EvidenceReference {
  reference_type: string
  reference_id: string
  digest: string
  knowledge_state: string
}

interface ProductProposal {
  application_task_id: string
  agent_control_task_id: string
  agent_id: string
  proposal_id: string
  proposal_digest: string
  knowledge_state: string
  title: string
  problem_user_need: string
  objective: string
  proposed_requirement: string
  acceptance_intent: string[]
  dependencies: string[]
  assumptions: string[]
  risks_open_questions: string[]
  priority_recommendation: string
  evidence_references: EvidenceReference[]
}

interface ReviewAvailability {
  available: boolean
  reason: string | null
}

const PROPOSAL_READABLE_STATUSES = new Set([
  'WORKING_PROPOSAL',
  'AWAITING_FOUNDER_REVIEW',
  'APPROVED_INTERNAL',
  'REJECTED',
  'CHANGES_REQUESTED',
])

const STATUS_STYLE: Record<string, 'green' | 'yellow' | 'blue' | 'gray' | 'red' | 'sky' | 'navy'> = {
  SUBMITTED: 'blue',
  RUNNING: 'sky',
  WORKING_PROPOSAL: 'yellow',
  AWAITING_FOUNDER_REVIEW: 'yellow',
  APPROVED_INTERNAL: 'green',
  REJECTED: 'red',
  CHANGES_REQUESTED: 'navy',
  BLOCKED: 'red',
}

function statusLabel(value: string) {
  return value.replace(/_/g, ' ')
}

function requestMessage(error: unknown, fallback: string) {
  const status = (error as { response?: { status?: number } })?.response?.status
  if (status === 401) return 'Your operator session has expired. Sign in again to continue.'
  if (status === 403) return 'This operator account cannot access Product Direction.'
  return fallback
}

function runtimeMessage(reason: unknown) {
  if (reason === 'RUNTIME_UNAVAILABLE') return 'The trusted PROD-01 runtime is currently unavailable.'
  if (reason === 'PROPOSAL_ARTIFACT_PERSISTENCE_FAILED') return 'PROD-01 completed without a durable proposal result. The task is blocked.'
  return 'PROD-01 could not complete this task. No proposal is available.'
}

function reviewMessage(reason: unknown) {
  if (reason === 'FOUNDER_RUNTIME_UNAVAILABLE') return 'Founder authentication is not available on this installation.'
  if (reason === 'FOUNDER_REVIEW_PENDING') return 'Founder review is still pending in the trusted external channel.'
  if (reason === 'FOUNDER_EXTERNAL_ONLY') return 'Founder authorization must be completed through the trusted external Founder channel.'
  if (reason === 'REVIEW_ALREADY_RECORDED') return 'This proposal already has a durable Founder review result.'
  if (reason === 'REVIEW_NOT_AVAILABLE') return 'This proposal is not currently available for Founder review.'
  if (reason === 'REVIEW_BINDING_MISMATCH' || reason === 'ARTIFACT_BINDING_MISMATCH' || reason === 'TASK_BINDING_MISMATCH' || reason === 'PROPOSAL_BINDING_MISMATCH' || reason === 'PROPOSAL_DIGEST_MISMATCH') return 'The exact proposal binding could not be verified. No review was applied.'
  return 'Founder review could not be completed. No application status was changed.'
}

function proposalMessage(error: unknown) {
  const reason = (error as { response?: { data?: { reason?: unknown } } })?.response?.data?.reason
  if (reason === 'PROPOSAL_NOT_AVAILABLE') return null
  if (reason === 'ARTIFACT_MISSING') return 'The validated proposal artifact is unavailable.'
  if (reason === 'ARTIFACT_INVALID') return 'The validated proposal artifact could not be verified.'
  if (reason === 'ARTIFACT_BINDING_MISMATCH' || reason === 'TASK_BINDING_MISMATCH' || reason === 'PROPOSAL_BINDING_MISMATCH' || reason === 'PROPOSAL_DIGEST_MISMATCH') {
    return 'The proposal binding could not be verified.'
  }
  return requestMessage(error, 'The validated proposal could not be loaded.')
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ border: '1px solid #E5E7EB', borderRadius: 12, background: '#fff', padding: 16 }}>
      <h3 style={{ margin: '0 0 10px', color: '#64748B', fontSize: 11, fontWeight: 850, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        {title}
      </h3>
      {children}
    </section>
  )
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(118px, 0.35fr) minmax(0, 1fr)', gap: 12, padding: '9px 0', borderBottom: '1px solid #F1F5F9' }}>
      <span style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700 }}>{label}</span>
      <span style={{ color: '#0F172A', fontSize: 13, minWidth: 0, overflowWrap: 'anywhere' }}>{value}</span>
    </div>
  )
}

function BoundedList({ values, empty = 'None recorded.' }: { values: string[]; empty?: string }) {
  if (values.length === 0) return <p style={{ margin: 0, color: '#94A3B8', fontSize: 13 }}>{empty}</p>
  return (
    <ul style={{ margin: 0, paddingLeft: 20, color: '#334155', fontSize: 13, lineHeight: 1.6 }}>
      {values.map((value, index) => <li key={`${value}-${index}`}>{value}</li>)}
    </ul>
  )
}

function TaskStateMessage({ task }: { task: ProductDirectionTask }) {
  const messages: Record<string, string> = {
    SUBMITTED: 'Ready to submit to PROD-01.',
    RUNNING: 'PROD-01 is processing this task.',
    WORKING_PROPOSAL: 'A validated WORKING proposal is available below.',
    AWAITING_FOUNDER_REVIEW: 'Founder review is required before this product direction can be approved.',
    APPROVED_INTERNAL: 'This product direction has an internal approval state recorded by a later Founder workflow.',
    REJECTED: 'This product direction was rejected by a later Founder workflow.',
    CHANGES_REQUESTED: 'Changes were requested by a later Founder workflow.',
    BLOCKED: 'This task could not complete. No proposal is available.',
  }
  return <p style={{ margin: 0, color: '#475569', fontSize: 13 }}>{messages[task.status] || 'No proposal is available.'}</p>
}

function ProposalView({ proposal }: { proposal: ProductProposal }) {
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <Panel title="Proposal provenance">
        <DetailRow label="Produced by" value={<><strong>PROD-01</strong> · Product Agent</>} />
        <DetailRow label="Knowledge state" value={<AdminBadge label="WORKING — not approved" style="yellow" />} />
        <DetailRow label="Proposal ID" value={<code style={{ fontSize: 12 }}>{proposal.proposal_id}</code>} />
        <DetailRow label="Proposal digest" value={<code style={{ fontSize: 12 }}>{proposal.proposal_digest}</code>} />
      </Panel>

      <Panel title="Product direction">
        <h3 style={{ margin: '0 0 10px', color: '#0F1F3D', fontSize: 21, fontWeight: 850 }}>{proposal.title}</h3>
        <DetailRow label="Problem / user need" value={proposal.problem_user_need} />
        <DetailRow label="Objective" value={proposal.objective} />
        <DetailRow label="Proposed requirement" value={proposal.proposed_requirement} />
      </Panel>

      <Panel title="Acceptance intent">
        <BoundedList values={proposal.acceptance_intent} />
      </Panel>

      <Panel title="Dependencies and assumptions">
        <DetailRow label="Dependencies" value={<BoundedList values={proposal.dependencies} />} />
        <DetailRow label="Assumptions" value={<BoundedList values={proposal.assumptions} />} />
      </Panel>

      <Panel title="Risks / open questions">
        <BoundedList values={proposal.risks_open_questions} />
        <p style={{ margin: '12px 0 0', color: '#64748B', fontSize: 12 }}>Priority recommendation: <strong>{proposal.priority_recommendation}</strong></p>
      </Panel>

      <Panel title="Evidence references">
        {proposal.evidence_references.length === 0 ? (
          <p style={{ margin: 0, color: '#94A3B8', fontSize: 13 }}>No evidence references.</p>
        ) : (
          <div style={{ display: 'grid', gap: 8 }}>
            {proposal.evidence_references.map((reference) => (
              <div key={`${reference.reference_type}-${reference.reference_id}`} style={{ border: '1px solid #E2E8F0', borderRadius: 8, padding: 10, background: '#F8FAFC' }}>
                <div style={{ color: '#334155', fontSize: 12, fontWeight: 750 }}>{reference.reference_type} · {reference.reference_id}</div>
                <code style={{ display: 'block', marginTop: 4, color: '#64748B', fontSize: 11, overflowWrap: 'anywhere' }}>{reference.digest}</code>
                <div style={{ marginTop: 4, color: '#64748B', fontSize: 11 }}>Knowledge state: {reference.knowledge_state}</div>
              </div>
            ))}
          </div>
        )}
        <p style={{ margin: '10px 0 0', color: '#94A3B8', fontSize: 11 }}>References are displayed as validated metadata only.</p>
      </Panel>
    </div>
  )
}

function ReviewProvenance({ task }: { task: ProductDirectionTask }) {
  if (!task.review_id || !task.review_digest) return null
  return (
    <Panel title="Founder review provenance">
      <DetailRow label="Review ID" value={<code style={{ fontSize: 12 }}>{task.review_id}</code>} />
      <DetailRow label="Review digest" value={<code style={{ fontSize: 12 }}>{task.review_digest}</code>} />
      <p style={{ margin: '10px 0 0', color: '#64748B', fontSize: 12 }}>The cryptographic review record remains authoritative in Agent Control. Blackboard stores only this bounded provenance.</p>
    </Panel>
  )
}

export default function AdminProductDirection() {
  const [refreshToken, setRefreshToken] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [objective, setObjective] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [proposal, setProposal] = useState<ProductProposal | null>(null)
  const [proposalError, setProposalError] = useState<string | null>(null)
  const [reviewAvailability, setReviewAvailability] = useState<ReviewAvailability | null>(null)
  const [reviewDecision, setReviewDecision] = useState<'ACCEPT' | 'REJECT' | 'REQUEST_CHANGES'>('ACCEPT')
  const [reviewReason, setReviewReason] = useState('')
  const [challengeRequested, setChallengeRequested] = useState(false)
  const [reviewAction, setReviewAction] = useState<'challenge' | 'observe' | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewNotice, setReviewNotice] = useState<string | null>(null)

  const { data, loading, error } = useAdminFetch<ProductDirectionTaskPage>(`/product-direction/tasks/?page=1&page_size=100&refresh=${refreshToken}`)
  const selectedTask = useMemo(
    () => data?.results.find((task) => task.task_id === selectedId) || data?.results[0] || null,
    [data, selectedId],
  )

  useEffect(() => {
    if (selectedTask && selectedTask.task_id !== selectedId) setSelectedId(selectedTask.task_id)
  }, [selectedTask, selectedId])

  useEffect(() => {
    setChallengeRequested(false)
  }, [selectedTask?.task_id])

  useEffect(() => {
    let cancelled = false
    setProposal(null)
    setProposalError(null)
    setReviewAvailability(null)
    setReviewError(null)
    setReviewNotice(null)
    if (!selectedTask || !PROPOSAL_READABLE_STATUSES.has(selectedTask.status)) return () => { cancelled = true }
    api.get<ProductProposal>(`/product-direction/tasks/${selectedTask.task_id}/proposal/`)
      .then((response) => { if (!cancelled) setProposal(response.data) })
      .catch((requestError: unknown) => { if (!cancelled) setProposalError(proposalMessage(requestError)) })
    api.get<ReviewAvailability>(`/product-direction/tasks/${selectedTask.task_id}/review/availability/`)
      .then((response) => { if (!cancelled) setReviewAvailability(response.data) })
      .catch(() => { if (!cancelled) setReviewAvailability({ available: false, reason: 'FOUNDER_RUNTIME_UNAVAILABLE' }) })
    return () => { cancelled = true }
  }, [selectedTask?.task_id, selectedTask?.status])

  const createTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = objective.trim()
    if (!value) {
      setFormError('Objective is required.')
      return
    }
    if (value.length > 4096) {
      setFormError('Objective must be 4096 characters or fewer.')
      return
    }
    setIsCreating(true)
    setFormError(null)
    setActionError(null)
    try {
      const response = await api.post<ProductDirectionTask>('/product-direction/tasks/', { objective: value })
      setObjective('')
      setSelectedId(response.data.task_id)
      setRefreshToken((current) => current + 1)
    } catch (requestError: unknown) {
      setFormError(requestMessage(requestError, 'The product-direction task could not be created.'))
    } finally {
      setIsCreating(false)
    }
  }

  const submitTask = async () => {
    if (!selectedTask || selectedTask.status !== 'SUBMITTED' || submittingId) return
    setSubmittingId(selectedTask.task_id)
    setActionError(null)
    try {
      await api.post(`/product-direction/tasks/${selectedTask.task_id}/submit/`, {})
      setRefreshToken((current) => current + 1)
    } catch (requestError: unknown) {
      const reason = (requestError as { response?: { data?: { reason?: unknown } } })?.response?.data?.reason
      setActionError(runtimeMessage(reason))
      setRefreshToken((current) => current + 1)
    } finally {
      setSubmittingId(null)
    }
  }

  const requestReviewChallenge = async () => {
    if (!selectedTask || !proposal || !reviewAvailability?.available || reviewAction) return
    const reason = reviewReason.trim()
    if (!reason) {
      setReviewError('A bounded reason is required by the Founder review contract.')
      return
    }
    if (reason.length > 2048) {
      setReviewError('Reason must be 2048 characters or fewer.')
      return
    }
    setReviewAction('challenge')
    setReviewError(null)
    setReviewNotice(null)
    try {
      await api.post(`/product-direction/tasks/${selectedTask.task_id}/review/challenge/`, { decision: reviewDecision, reason })
      setChallengeRequested(true)
      setReviewNotice('Founder review requested through trusted Agent Control. Complete authorization in the external Founder channel; Operator access cannot decide this review.')
    } catch (requestError: unknown) {
      const reasonCode = (requestError as { response?: { data?: { reason?: unknown } } })?.response?.data?.reason
      setReviewError(reviewMessage(reasonCode))
    } finally {
      setReviewAction(null)
    }
  }

  const observeReview = async () => {
    if (!selectedTask || selectedTask.status !== 'AWAITING_FOUNDER_REVIEW' || reviewAction) return
    setReviewAction('observe')
    setReviewError(null)
    setReviewNotice(null)
    try {
      const response = await api.get(`/product-direction/tasks/${selectedTask.task_id}/review/status/`)
      if (response.data.status === 'PENDING' || response.data.status === 'REVIEW_PENDING_PROJECTION') {
        setReviewNotice(response.data.status === 'PENDING'
          ? 'Founder review is still pending in the trusted external Founder channel.'
          : 'Founder review is committed and waiting for the trusted durable projection worker.')
      } else {
        setChallengeRequested(false)
        setReviewNotice(`Founder review recorded: ${response.data.decision}. Application status is now ${response.data.resulting_knowledge_state}.`)
      }
      setRefreshToken((current) => current + 1)
    } catch (requestError: unknown) {
      const reasonCode = (requestError as { response?: { data?: { reason?: unknown } } })?.response?.data?.reason
      setReviewError(reviewMessage(reasonCode))
    } finally {
      setReviewAction(null)
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <p style={{ margin: 0, color: '#38BDF8', fontSize: 10, fontWeight: 850, letterSpacing: '0.14em', textTransform: 'uppercase' }}>Blackboard · Product Direction</p>
        <h1 style={{ margin: '5px 0 0', color: '#0F1F3D', fontSize: 24, fontWeight: 900 }}>Product Direction</h1>
        <p style={{ margin: '5px 0 0', color: '#64748B', fontSize: 13 }}>Create bounded product work and inspect validated PROD-01 proposals.</p>
      </header>

      {(formError || actionError) && (
        <div role="alert" style={{ border: '1px solid #FECACA', borderRadius: 9, background: '#FEF2F2', color: '#B91C1C', padding: '11px 14px', fontSize: 13 }}>
          {formError || actionError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.6fr)]">
        <div style={{ display: 'grid', alignContent: 'start', gap: 14 }}>
          <Panel title="Create product-direction task">
            <form onSubmit={createTask}>
              <label htmlFor="product-direction-objective" style={{ display: 'block', color: '#334155', fontSize: 13, fontWeight: 750 }}>Objective</label>
              <textarea
                id="product-direction-objective"
                value={objective}
                onChange={(event) => setObjective(event.target.value)}
                maxLength={4096}
                rows={5}
                placeholder="Describe the product direction PROD-01 should propose."
                aria-describedby="product-direction-objective-help"
                style={{ display: 'block', width: '100%', marginTop: 7, border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, color: '#0F172A', fontSize: 13, resize: 'vertical' }}
              />
              <p id="product-direction-objective-help" style={{ margin: '6px 0 0', color: '#94A3B8', fontSize: 11 }}>Only the objective is editable. Agent, model, tools, and credentials are controlled by bonUP.</p>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 12 }}>
                <span style={{ color: '#94A3B8', fontSize: 11 }}>{objective.length}/4096</span>
                <button type="submit" disabled={isCreating} style={{ border: 0, borderRadius: 8, background: isCreating ? '#94A3B8' : '#0F1F3D', color: '#fff', cursor: isCreating ? 'wait' : 'pointer', padding: '9px 14px', fontSize: 12, fontWeight: 800 }}>
                  {isCreating ? 'Creating…' : 'Create task'}
                </button>
              </div>
            </form>
          </Panel>

          <Panel title="Product agent">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div aria-hidden="true" style={{ width: 34, height: 34, display: 'grid', placeItems: 'center', borderRadius: 9, background: '#F0F9FF', color: '#0369A1', fontSize: 17 }}>✦</div>
              <div>
                <p style={{ margin: 0, color: '#0F1F3D', fontSize: 14, fontWeight: 850 }}>PROD-01</p>
                <p style={{ margin: '2px 0 0', color: '#64748B', fontSize: 12 }}>Product Agent · proposal-only</p>
              </div>
            </div>
          </Panel>

          <section aria-labelledby="product-direction-history-title">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
              <h2 id="product-direction-history-title" style={{ margin: 0, color: '#0F1F3D', fontSize: 15, fontWeight: 850 }}>Task history</h2>
              {data && <span style={{ color: '#94A3B8', fontSize: 11 }}>{data.count} task{data.count === 1 ? '' : 's'}</span>}
            </div>
            {error && <div role="alert" style={{ marginBottom: 8, border: '1px solid #FECACA', borderRadius: 8, background: '#FEF2F2', color: '#B91C1C', padding: '10px 12px', fontSize: 12 }}>Product Direction history could not be loaded.</div>}
            <AdminTable loading={loading} empty={!loading && !error && data?.results.length === 0} headers={['Objective', 'Status']}>
              {data?.results.map((task) => (
                <tr key={task.task_id} style={{ background: selectedTask?.task_id === task.task_id ? '#F0F9FF' : '#fff' }}>
                  <td style={{ padding: 0 }}>
                    <button type="button" onClick={() => setSelectedId(task.task_id)} aria-pressed={selectedTask?.task_id === task.task_id} style={{ width: '100%', border: 0, background: 'transparent', cursor: 'pointer', padding: '11px 12px', textAlign: 'left' }}>
                      <span style={{ display: 'block', color: '#0F1F3D', fontSize: 12, fontWeight: 750, overflowWrap: 'anywhere' }}>{task.objective}</span>
                      <span style={{ display: 'block', marginTop: 4, color: '#94A3B8', fontSize: 10 }}>{formatDateTime(task.created_at)}</span>
                    </button>
                  </td>
                  <td style={{ padding: '11px 12px', whiteSpace: 'nowrap', verticalAlign: 'top' }}><AdminBadge label={statusLabel(task.status)} style={STATUS_STYLE[task.status] || 'gray'} /></td>
                </tr>
              ))}
            </AdminTable>
          </section>
        </div>

        <main aria-live="polite" style={{ minWidth: 0 }}>
          {!selectedTask ? (
            <Panel title="Task detail"><p style={{ margin: 0, color: '#64748B', fontSize: 13 }}>Create or select a Product Direction task to inspect it.</p></Panel>
          ) : (
            <div style={{ display: 'grid', gap: 14 }}>
              <Panel title="Task detail">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ minWidth: 0 }}>
                    <p style={{ margin: 0, color: '#0F1F3D', fontSize: 18, fontWeight: 850, overflowWrap: 'anywhere' }}>{selectedTask.objective}</p>
                    <p style={{ margin: '6px 0 0', color: '#64748B', fontSize: 12 }}>Application task {selectedTask.task_id}</p>
                  </div>
                  <AdminBadge label={statusLabel(selectedTask.status)} style={STATUS_STYLE[selectedTask.status] || 'gray'} />
                </div>
                <div style={{ marginTop: 12 }}>
                  <DetailRow label="Agent" value="PROD-01 · Product Agent" />
                  <DetailRow label="Agent Control task" value={selectedTask.agent_control_task_id || 'Not assigned yet'} />
                  <DetailRow label="Created" value={formatDateTime(selectedTask.created_at)} />
                  <DetailRow label="Updated" value={formatDateTime(selectedTask.updated_at)} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 14, flexWrap: 'wrap' }}>
                  <TaskStateMessage task={selectedTask} />
                  {selectedTask.status === 'SUBMITTED' && (
                    <button type="button" onClick={submitTask} disabled={submittingId === selectedTask.task_id} style={{ border: 0, borderRadius: 8, background: submittingId ? '#94A3B8' : '#0369A1', color: '#fff', cursor: submittingId ? 'wait' : 'pointer', padding: '9px 14px', fontSize: 12, fontWeight: 800 }}>
                      {submittingId ? 'Submitting…' : 'Submit to PROD-01'}
                    </button>
                  )}
                </div>
              </Panel>

              {proposalError && <div role="alert" style={{ border: '1px solid #FDE68A', borderRadius: 9, background: '#FFFBEB', color: '#92400E', padding: '11px 14px', fontSize: 13 }}>{proposalError}</div>}
              {proposal && <ProposalView proposal={proposal} />}
              <ReviewProvenance task={selectedTask} />
              {selectedTask.status === 'WORKING_PROPOSAL' && !proposal && !proposalError && <Panel title="Proposal"><p style={{ margin: 0, color: '#64748B', fontSize: 13 }}>Loading the validated proposal…</p></Panel>}
              {proposal && (selectedTask.status === 'WORKING_PROPOSAL' || selectedTask.status === 'AWAITING_FOUNDER_REVIEW') && (
                <Panel title="Founder review">
                  <div style={{ border: '1px solid #BAE6FD', borderRadius: 10, background: '#F0F9FF', color: '#075985', padding: '12px 14px', fontSize: 13 }}>
                    Founder review required. Operator access is separate from Founder authorization and cannot approve this proposal by itself.
                  </div>
                  {reviewAvailability && !reviewAvailability.available && (
                    <p role="status" style={{ margin: '12px 0 0', border: '1px solid #FDE68A', borderRadius: 9, background: '#FFFBEB', color: '#92400E', padding: '11px 14px', fontSize: 13 }}>
                      Founder authentication is not available on this installation.
                    </p>
                  )}
                  <fieldset disabled={!reviewAvailability?.available || !!reviewAction || selectedTask.status === 'AWAITING_FOUNDER_REVIEW'} style={{ margin: '14px 0 0', border: 0, padding: 0 }}>
                    <legend style={{ color: '#334155', fontSize: 13, fontWeight: 800 }}>Decision</legend>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                      {(['ACCEPT', 'REJECT', 'REQUEST_CHANGES'] as const).map((decision) => (
                        <label key={decision} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid #CBD5E1', borderRadius: 8, padding: '8px 10px', color: '#334155', fontSize: 12, fontWeight: 750 }}>
                          <input type="radio" name="founder-review-decision" checked={reviewDecision === decision} onChange={() => setReviewDecision(decision)} />
                          {decision}
                        </label>
                      ))}
                    </div>
                    <label htmlFor="founder-review-reason" style={{ display: 'block', marginTop: 12, color: '#334155', fontSize: 13, fontWeight: 750 }}>Bounded reason</label>
                    <textarea id="founder-review-reason" value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} maxLength={2048} rows={3} placeholder="Explain the Founder decision." style={{ display: 'block', width: '100%', marginTop: 7, border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, color: '#0F172A', fontSize: 13, resize: 'vertical' }} />
                    {reviewDecision === 'ACCEPT' && <p style={{ margin: '8px 0 0', color: '#475569', fontSize: 12 }}>Confirmation: <strong>{proposal.title}</strong> · proposal {proposal.proposal_id} · digest <code>{proposal.proposal_digest}</code> · resulting state <strong>APPROVED_INTERNAL</strong>.</p>}
                    {reviewDecision !== 'ACCEPT' && <p style={{ margin: '8px 0 0', color: '#475569', fontSize: 12 }}>The proposal remains immutable historical evidence. This decision will not create publication or execution authority.</p>}
                    <button type="button" onClick={requestReviewChallenge} style={{ marginTop: 12, border: 0, borderRadius: 8, background: reviewAvailability?.available ? '#0369A1' : '#94A3B8', color: '#fff', cursor: reviewAvailability?.available ? 'pointer' : 'not-allowed', padding: '9px 14px', fontSize: 12, fontWeight: 800 }}>
                      {reviewAction === 'challenge' ? 'Requesting Founder review…' : `Request Founder ${reviewDecision} review`}
                    </button>
                  </fieldset>
                  {(challengeRequested || selectedTask.status === 'AWAITING_FOUNDER_REVIEW') && (
                    <div style={{ marginTop: 14, borderTop: '1px solid #E2E8F0', paddingTop: 14 }}>
                      <p style={{ margin: 0, color: '#64748B', fontSize: 12 }}>Founder authorization is completed outside Blackboard through the trusted Founder transport. No signature, challenge, session, or Founder identity is entered here.</p>
                      <button type="button" onClick={observeReview} disabled={!!reviewAction} style={{ marginTop: 10, border: 0, borderRadius: 8, background: !reviewAction ? '#0F1F3D' : '#94A3B8', color: '#fff', cursor: !reviewAction ? 'pointer' : 'not-allowed', padding: '9px 14px', fontSize: 12, fontWeight: 800 }}>
                        {reviewAction === 'observe' ? 'Checking Founder result…' : 'Check Founder review result'}
                      </button>
                    </div>
                  )}
                  {reviewNotice && <p role="status" style={{ margin: '12px 0 0', color: '#166534', fontSize: 13 }}>{reviewNotice}</p>}
                  {reviewError && <p role="alert" style={{ margin: '12px 0 0', color: '#B91C1C', fontSize: 13 }}>{reviewError}</p>}
                </Panel>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
