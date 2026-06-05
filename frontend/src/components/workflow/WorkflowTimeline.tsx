export type WorkflowTimelineState = {
  id: string
  current_state: string
  completed_states?: string[]
  pending_states?: string[]
  state_timestamps?: Record<string, string>
  counterparty_email?: string
  sent_to_counterparty_email?: string
  created_version_id?: string | null
  last_activity?: {
    activity_type: string
    description: string
    created_at: string
  } | null
}

type ActiveVersionSummary = {
  id?: string
  version_number?: number
  status?: string
}

type WorkflowTimelineProps = {
  workflow: WorkflowTimelineState | null
  activeVersion?: ActiveVersionSummary | null
  compact?: boolean
}

const WORKFLOW_STATES = [
  ['uploaded', 'Uploaded'],
  ['analyzing', 'Analyzing'],
  ['review_ready', 'Review ready'],
  ['counter_draft_ready', 'Counter draft ready'],
  ['version_created', 'Version created'],
  ['sent_to_counterparty', 'Sent'],
  ['counterparty_viewed', 'Viewed'],
  ['counterparty_requested_changes', 'Changes requested'],
  ['accepted', 'Accepted'],
  ['rejected', 'Rejected'],
  ['signed', 'Signed'],
] as const

function formatDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString()
}

function getNextAction(state?: string) {
  switch (state) {
    case 'uploaded': return 'Run AI review'
    case 'analyzing': return 'Wait for review completion'
    case 'review_ready': return 'Generate counter draft'
    case 'counter_draft_ready': return 'Approve draft into a version'
    case 'version_created': return 'Send to counterparty'
    case 'sent_to_counterparty': return 'Counterparty review'
    case 'counterparty_viewed': return 'Counterparty response'
    case 'counterparty_requested_changes': return 'Initiator review of requested changes'
    case 'accepted': return 'Counterparty signing'
    case 'rejected': return 'Negotiation stopped'
    case 'signed': return 'Agreement signed'
    default: return 'Continue workflow'
  }
}

function getStateStatus(workflow: WorkflowTimelineState, state: string) {
  if (workflow.current_state === state) return 'current'
  if ((workflow.completed_states || []).includes(state)) return 'completed'
  return 'pending'
}

export default function WorkflowTimeline({ workflow, activeVersion, compact = false }: WorkflowTimelineProps) {
  if (!workflow) return null
  const counterparty = workflow.counterparty_email || workflow.sent_to_counterparty_email || ''
  const visibleStates = WORKFLOW_STATES.filter(([state]) => {
    if (state === 'rejected') return workflow.current_state === 'rejected' || (workflow.completed_states || []).includes('rejected')
    if (state === 'signed') return workflow.current_state === 'signed' || (workflow.completed_states || []).includes('signed')
    if (state === 'accepted') return workflow.current_state === 'accepted' || workflow.current_state === 'signed' || (workflow.completed_states || []).includes('accepted')
    return true
  })

  return (
    <div style={{ background: 'white', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)', padding: compact ? 12 : 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'minmax(0, 1.4fr) minmax(220px, 0.8fr)', gap: 16 }}>
        <div>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: '0 0 12px' }}>Workflow Timeline</p>
          <div style={{ display: 'grid', gap: 0 }}>
            {visibleStates.map(([state, label], index) => {
              const status = getStateStatus(workflow, state)
              const isCompleted = status === 'completed'
              const isCurrent = status === 'current'
              const color = isCurrent ? '#0F1F3D' : isCompleted ? '#065F46' : '#9CA3AF'
              const bg = isCurrent ? '#F5A623' : isCompleted ? '#D1FAE5' : '#F3F4F6'
              return (
                <div key={state} style={{ display: 'grid', gridTemplateColumns: '26px minmax(0, 1fr)', gap: 10 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div style={{ width: 22, height: 22, borderRadius: 999, background: bg, color, border: `1px solid ${isCurrent ? '#D4900A' : isCompleted ? '#6EE7B7' : '#E5E7EB'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>
                      {isCompleted ? '✓' : isCurrent ? '•' : ''}
                    </div>
                    {index < visibleStates.length - 1 && <div style={{ width: 1, minHeight: 24, background: isCompleted ? '#A7F3D0' : '#E5E7EB' }} />}
                  </div>
                  <div style={{ paddingBottom: index < visibleStates.length - 1 ? 10 : 0 }}>
                    <p style={{ fontSize: 13, fontWeight: isCurrent ? 700 : 600, color, margin: 0 }}>{label}</p>
                    <p style={{ fontSize: 11, color: '#9CA3AF', margin: '3px 0 0' }}>{formatDate(workflow.state_timestamps?.[state]) || (status === 'pending' ? 'Pending' : '')}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div style={{ background: '#F8FAFC', borderRadius: 8, border: '1px solid #E5E7EB', padding: 12, alignSelf: 'start' }}>
          <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: '0 0 10px' }}>Workflow Context</p>
          <ContextRow label="Current" value={workflow.current_state.replaceAll('_', ' ')} />
          <ContextRow label="Next" value={getNextAction(workflow.current_state)} />
          <ContextRow label="Version" value={activeVersion?.version_number ? `v${activeVersion.version_number} · ${activeVersion.status || 'unknown'}` : activeVersion?.status ? activeVersion.status.replaceAll('_', ' ') : workflow.created_version_id ? 'Created' : 'Not created'} />
          <ContextRow label="Counterparty" value={counterparty || 'Not sent'} />
          <ContextRow label="Last activity" value={workflow.last_activity?.description || 'No activity yet'} muted />
        </div>
      </div>
    </div>
  )
}

function ContextRow({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div style={{ marginBottom: 9 }}>
      <p style={{ fontSize: 10, textTransform: 'uppercase', color: '#9CA3AF', fontWeight: 700, margin: '0 0 2px' }}>{label}</p>
      <p style={{ fontSize: 12, color: muted ? '#6B7280' : '#374151', margin: 0, lineHeight: 1.4 }}>{value}</p>
    </div>
  )
}
