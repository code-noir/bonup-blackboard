import type { ReactNode } from 'react'
import WorkflowTimeline from '@/components/workflow/WorkflowTimeline'
import WorkflowSharePanel from '@/components/workflow/WorkflowSharePanel'
import NegotiationCommentsPanel from '@/components/workflow/NegotiationCommentsPanel'

export type WorkflowReviewResult = {
  id?: string
  summary?: string
  identified_risks?: string[]
  unclear_clauses?: string[]
  negotiation_opportunities?: string[]
  suggested_changes?: string[]
  ai_metadata?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export type WorkflowCounterDraft = {
  id: string
  status?: string
  generated_revised_contract?: string
  selected_requested_changes?: Array<unknown>
  user_negotiation_instructions?: string
  summary?: string
  concerning_clauses?: Array<unknown>
  negotiation_strategy?: Record<string, unknown>
  ai_metadata?: Record<string, unknown>
  approved_at?: string | null
  created_version_id?: string | null
  created_at?: string
  updated_at?: string
}

export type WorkflowActivity = {
  id?: string
  activity_type: string
  description: string
  created_at: string
}

export type WorkflowRecord = {
  id: string
  contract_id?: string | null
  source_label: string
  current_state: string
  completed_states: string[]
  pending_states: string[]
  state_timestamps: Record<string, string>
  created_version_id?: string | null
  sent_to_counterparty_email?: string | null
  counterparty_email?: string | null
  counterparty_user_id?: string | null
  counterparty_requested_changes?: Array<unknown>
  last_activity?: WorkflowActivity | null
  created_at: string
  updated_at: string
  review_result?: WorkflowReviewResult | null
  counter_drafts?: WorkflowCounterDraft[]
}

type WorkflowWorkspaceProps = {
  workflow: WorkflowRecord
}

const FLOW_STEPS = [
  'uploaded',
  'analyzing',
  'review_ready',
  'counter_draft_ready',
  'version_created',
  'sent_to_counterparty',
  'counterparty_viewed',
  'counterparty_requested_changes',
  'accepted',
  'rejected',
  'signed',
] as const

function formatDate(value?: string) {
  if (!value) return 'Not yet recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not yet recorded'
  return date.toLocaleString()
}

function humanize(value: string) {
  return value.replaceAll('_', ' ')
}

function getDerivedVersionStatus(workflow: WorkflowRecord) {
  if (!workflow.created_version_id) return 'not created'

  switch (workflow.current_state) {
    case 'version_created':
      return 'draft'
    case 'sent_to_counterparty':
    case 'counterparty_viewed':
      return 'sent'
    case 'counterparty_requested_changes':
      return 'negotiating'
    case 'accepted':
      return 'accepted'
    case 'rejected':
      return 'rejected'
    case 'signed':
      return 'signed'
    default:
      return 'created'
  }
}

function getNextAction(state: string) {
  switch (state) {
    case 'uploaded': return 'Run AI review'
    case 'analyzing': return 'Wait for analysis to complete'
    case 'review_ready': return 'Generate a counter draft'
    case 'counter_draft_ready': return 'Approve the counter draft'
    case 'version_created': return 'Send the agreement to the counterparty'
    case 'sent_to_counterparty': return 'Wait for counterparty review'
    case 'counterparty_viewed': return 'Wait for a response or reply'
    case 'counterparty_requested_changes': return 'Review requested changes'
    case 'accepted': return 'Counterparty can sign now'
    case 'rejected': return 'Negotiation ended'
    case 'signed': return 'Agreement completed'
    default: return 'Continue workflow'
  }
}

function getProgressIndex(state: string) {
  const index = FLOW_STEPS.indexOf(state as (typeof FLOW_STEPS)[number])
  return index >= 0 ? index : 0
}

function renderList(items?: Array<unknown>) {
  if (!items || !items.length) {
    return <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>None recorded.</p>
  }

  return (
    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
      {items.map((item, index) => {
        if (typeof item === 'string') {
          return <li key={index}>{item}</li>
        }
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>
          const parts = [record.text, record.clause_reference, record.concern, record.counter_language, record.answer]
            .filter(Boolean)
            .map((part) => String(part))
          return <li key={index}>{parts.length ? parts.join(' • ') : JSON.stringify(item)}</li>
        }
        return <li key={index}>{String(item)}</li>
      })}
    </ul>
  )
}

function SectionCard({
  title,
  eyebrow,
  children,
}: {
  title: string
  eyebrow?: string
  children: ReactNode
}) {
  return (
    <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 18 }}>
      {eyebrow && (
        <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.16em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>
          {eyebrow}
        </p>
      )}
      <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: '0 0 12px' }}>{title}</h3>
      {children}
    </section>
  )
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 2px' }}>{label}</p>
      <p style={{ fontSize: 13, color: '#374151', margin: 0, lineHeight: 1.5 }}>{value}</p>
    </div>
  )
}

export default function WorkflowWorkspace({ workflow }: WorkflowWorkspaceProps) {
  const versionStatus = getDerivedVersionStatus(workflow)
  const nextAction = getNextAction(workflow.current_state)
  const counterparty = workflow.counterparty_email || workflow.sent_to_counterparty_email || 'Not shared yet'
  const progress = Math.max(1, getProgressIndex(workflow.current_state) + 1)

  return (
    <div className="space-y-6">
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 20 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.16em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>
              Workflow workspace
            </p>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0F1F3D', margin: 0, lineHeight: 1.2 }}>
              {workflow.source_label || 'Agreement workflow'}
            </h1>
            <p style={{ margin: '8px 0 0', fontSize: 13, color: '#6B7280' }}>
              Workflow ID {workflow.id}
            </p>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <span style={{ borderRadius: 999, background: '#FEF3C7', color: '#9A6700', fontSize: 11, fontWeight: 700, padding: '6px 10px' }}>
              {humanize(workflow.current_state)}
            </span>
            <span style={{ borderRadius: 999, background: '#EEF2FF', color: '#4338CA', fontSize: 11, fontWeight: 700, padding: '6px 10px' }}>
              Version {versionStatus}
            </span>
            <span style={{ borderRadius: 999, background: '#ECFDF5', color: '#065F46', fontSize: 11, fontWeight: 700, padding: '6px 10px' }}>
              Step {progress} of {FLOW_STEPS.length}
            </span>
          </div>
        </div>

        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <MetaRow label="Counterparty" value={counterparty} />
          <MetaRow label="Pending action" value={nextAction} />
          <MetaRow label="Last activity" value={workflow.last_activity?.description || 'No activity yet'} />
          <MetaRow label="Activity time" value={formatDate(workflow.last_activity?.created_at || workflow.updated_at)} />
        </div>
      </section>

      <WorkflowTimeline
        workflow={{
          id: workflow.id,
          current_state: workflow.current_state,
          completed_states: workflow.completed_states,
          pending_states: workflow.pending_states,
          state_timestamps: workflow.state_timestamps,
          counterparty_email: workflow.counterparty_email || undefined,
          sent_to_counterparty_email: workflow.sent_to_counterparty_email || undefined,
          created_version_id: workflow.created_version_id,
          last_activity: workflow.last_activity,
        }}
        activeVersion={{ status: versionStatus }}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(320px,0.82fr)]">
        <div className="space-y-6">
          <SectionCard title="Review Results" eyebrow="Analysis">
            {workflow.review_result ? (
              <div className="space-y-4">
                <div>
                  <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Summary</p>
                  <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>{workflow.review_result.summary || 'No summary recorded.'}</p>
                </div>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Identified risks</p>
                  {renderList(workflow.review_result.identified_risks)}
                </div>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Unclear clauses</p>
                  {renderList(workflow.review_result.unclear_clauses)}
                </div>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Negotiation opportunities</p>
                  {renderList(workflow.review_result.negotiation_opportunities)}
                </div>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Suggested changes</p>
                  {renderList(workflow.review_result.suggested_changes)}
                </div>
              </div>
            ) : (
              <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>No review result has been saved yet.</p>
            )}
          </SectionCard>

          <SectionCard title="Counter Drafts" eyebrow="Negotiation">
            {workflow.counter_drafts?.length ? (
              <div className="space-y-4">
                {workflow.counter_drafts.map((draft) => (
                  <div key={draft.id} style={{ border: '1px solid #E5E7EB', borderRadius: 10, background: '#F8FAFC', padding: 14 }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                      <p style={{ fontSize: 13, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>Draft {draft.id.slice(0, 8)}</p>
                      <span style={{ borderRadius: 999, background: '#FEF3C7', color: '#9A6700', fontSize: 11, fontWeight: 700, padding: '4px 8px' }}>
                        {humanize(draft.status || 'draft')}
                      </span>
                    </div>
                    <MetaRow label="Approved" value={draft.approved_at ? formatDate(draft.approved_at) : 'Not approved'} />
                    <MetaRow label="Linked version" value={draft.created_version_id ? draft.created_version_id : 'No canonical version created'} />
                    <div style={{ marginBottom: 10 }}>
                      <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Summary</p>
                      <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>{draft.summary || 'No summary recorded.'}</p>
                    </div>
                    <div style={{ marginBottom: 10 }}>
                      <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Selected requested changes</p>
                      {renderList(draft.selected_requested_changes)}
                    </div>
                    <div style={{ marginBottom: 10 }}>
                      <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Negotiation instructions</p>
                      <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>{draft.user_negotiation_instructions || 'None recorded.'}</p>
                    </div>
                    <div>
                      <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>Revised contract</p>
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 13, color: '#374151', lineHeight: 1.6, background: 'white', border: '1px solid #E5E7EB', borderRadius: 8, padding: 10, maxHeight: 220, overflow: 'auto' }}>
                        {draft.generated_revised_contract || 'No revised contract text recorded.'}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>No counter drafts have been generated yet.</p>
            )}
          </SectionCard>

          <SectionCard title="Negotiation Comments" eyebrow="Conversation">
            <NegotiationCommentsPanel workflowId={workflow.id} />
          </SectionCard>
        </div>

        <div className="space-y-6">
          <SectionCard title="Pending Actions" eyebrow="Operations">
            <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 10, padding: 14 }}>
              <p style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>Next step</p>
              <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: 0, lineHeight: 1.5 }}>{nextAction}</p>
            </div>
            <div style={{ marginTop: 12 }}>
              <MetaRow label="Current state" value={humanize(workflow.current_state)} />
              <MetaRow label="Completed" value={workflow.completed_states.length ? workflow.completed_states.map(humanize).join(' • ') : 'None yet'} />
              <MetaRow label="Pending" value={workflow.pending_states.length ? workflow.pending_states.map(humanize).join(' • ') : 'None remaining'} />
            </div>
          </SectionCard>

          <SectionCard title="Counterparty Status" eyebrow="Participants">
            <MetaRow label="Counterparty email" value={counterparty} />
            <MetaRow label="Counterparty user" value={workflow.counterparty_user_id ? workflow.counterparty_user_id : 'Not attached'} />
            <MetaRow label="Requested changes" value={workflow.counterparty_requested_changes?.length ? `${workflow.counterparty_requested_changes.length} request bundle(s)` : 'No requests yet'} />
            <MetaRow label="Sent to" value={workflow.sent_to_counterparty_email || 'Not sent yet'} />
            <MetaRow label="Active version status" value={versionStatus} />
          </SectionCard>

          <SectionCard title="Invite & Share" eyebrow="Access">
            <WorkflowSharePanel workflowId={workflow.id} defaultCounterpartyEmail={workflow.counterparty_email || workflow.sent_to_counterparty_email || ''} />
          </SectionCard>

          <SectionCard title="Recent Activity" eyebrow="Timeline">
            {workflow.last_activity ? (
              <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 10, padding: 14 }}>
                <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 6px' }}>{workflow.last_activity.activity_type.replaceAll('_', ' ')}</p>
                <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, margin: '0 0 8px' }}>{workflow.last_activity.description}</p>
                <p style={{ fontSize: 11, color: '#9CA3AF', margin: 0 }}>{formatDate(workflow.last_activity.created_at)}</p>
              </div>
            ) : (
              <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>No activity has been recorded yet.</p>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  )
}
