import { type CSSProperties, type ReactNode, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { WorkflowRecord } from '@/components/workflow/WorkflowWorkspace'

const DASHBOARD_STATES = [
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

type WorkflowListResponse = { results: WorkflowRecord[] }

type ContractRecord = {
  id: string
  title?: string
  contract_type?: string
  counterparty_name?: string
  counterparty_email?: string
  status?: string
  state?: string
  created_at?: string
}

type ContractListResponse = ContractRecord[] | { results: ContractRecord[] }

const AI_CLAUSE_OPTIONS = [
  'Payment',
  'Service obligations',
  'Termination',
  'Dispute resolution',
  'Confidentiality',
  'Notices',
  'Change orders',
] as const

const OBLIGATION_FILTERS = ['All', 'Due Soon', 'Needs Review', 'Payments', 'Services', 'Completed'] as const

const OBLIGATION_SUMMARY_ITEMS = [
  ['Due Soon', '0'],
  ['Needs Review', '0'],
  ['Payments', '0'],
  ['Services', '0'],
] as const

const CONTRACT_STUFF_ITEMS = [
  ['Amendments', 'Track formal changes to signed agreement terms.'],
  ['Addenda', 'Organize supplemental documents connected to the agreement.'],
  ['Attachments / Exhibits', 'Keep supporting files, exhibits, and schedules together.'],
  ['Renewals', 'Prepare renewal actions and renewal records.'],
  ['Extensions', 'Track time extensions and extended performance periods.'],
  ['Waivers', 'Record waived rights, exceptions, or enforcement decisions.'],
  ['Approvals / Consents', 'Capture required approvals and consent records.'],
  ['Assignments', 'Track assignment requests and transfer records.'],
  ['Subcontracting', 'Manage subcontracting notices and support records.'],
  ['Suspension', 'Record pauses, holds, and suspended obligations.'],
  ['Termination', 'Track termination notices and closeout records.'],
  ['Force Majeure', 'Capture force majeure notices, events, and impacts.'],
  ['Notices', 'Organize formal notice activity and delivery records.'],
] as const

const GET_STARTED_VIDEOS = [
  'How to create a contract',
  'Begin negotiating in Blackboard',
  'Lifecycle management',
  'Understand contracting',
]

type SectionConfig = {
  title: string
  description: string
  empty: string
  workflows: WorkflowRecord[]
}

function formatDate(value?: string) {
  if (!value) return 'No activity yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No activity yet'
  return date.toLocaleString()
}

function formatContractDate(value?: string) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not recorded'
  return date.toLocaleDateString()
}

function contractStatusLabel(contract: ContractRecord) {
  if (contract.state === 'created') return 'Created'
  if (contract.state === 'prepared') return 'Prepared'
  if (contract.state === 'ready_to_send') return 'Ready to Send'
  if (contract.status === 'draft') return 'Drafting'
  if (contract.status === 'sent') return 'Sent'
  if (contract.status === 'active') return 'Active'
  if (contract.status === 'completed') return 'Completed'
  if (contract.status === 'archived') return 'Archived'
  return contract.status || contract.state || 'Created'
}

function contractStatusStyle(label: string): CSSProperties {
  if (label === 'Active') return { background: '#ECFDF5', color: '#047857' }
  if (label === 'Prepared' || label === 'Ready to Send') return { background: '#E0F2FE', color: '#0369A1' }
  if (label === 'Sent') return { background: '#FEF3C7', color: '#B45309' }
  if (label === 'Completed') return { background: '#EEF2FF', color: '#4F46E5' }
  if (label === 'Archived') return { background: '#F3F4F6', color: '#6B7280' }
  return { background: '#F8FAFC', color: '#475569' }
}

function contractPartyLabel(contract: ContractRecord) {
  return contract.counterparty_name || contract.counterparty_email || 'Counterparty not attached'
}

function humanize(value: string) {
  return value.replaceAll('_', ' ')
}

function getNextAction(state: string) {
  switch (state) {
    case 'uploaded': return 'Run AI review'
    case 'analyzing': return 'Await review completion'
    case 'review_ready': return 'Generate a counter draft'
    case 'counter_draft_ready': return 'Approve the draft'
    case 'version_created': return 'Send to counterparty'
    case 'sent_to_counterparty': return 'Waiting on counterparty'
    case 'counterparty_viewed': return 'Review response'
    case 'counterparty_requested_changes': return 'Review requested changes'
    case 'accepted': return 'Counterparty can sign'
    case 'rejected': return 'Negotiation closed'
    case 'signed': return 'Agreement completed'
    default: return 'Continue activity'
  }
}

function getVersionStatus(workflow: WorkflowRecord) {
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

function getStageIndex(state: string) {
  const index = DASHBOARD_STATES.indexOf(state as (typeof DASHBOARD_STATES)[number])
  return index >= 0 ? index : 0
}

function stateTone(state: string) {
  if (['analyzing', 'review_ready', 'counter_draft_ready'].includes(state)) return 'review'
  if (['sent_to_counterparty', 'counterparty_viewed', 'counterparty_requested_changes', 'accepted'].includes(state)) return 'negotiation'
  if (state === 'signed') return 'signed'
  if (state === 'rejected') return 'rejected'
  return 'active'
}

function ProgressStrip({ workflow }: { workflow: WorkflowRecord }) {
  const index = getStageIndex(workflow.current_state)
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${DASHBOARD_STATES.length}, minmax(0, 1fr))`, gap: 4 }}>
        {DASHBOARD_STATES.map((state, i) => {
          const isDone = i < index
          const isCurrent = i === index
          return (
            <div
              key={state}
              title={humanize(state)}
              style={{
                height: 8,
                borderRadius: 999,
                background: isDone ? '#6EE7B7' : isCurrent ? '#F5A623' : '#E5E7EB',
                border: isCurrent ? '1px solid #D4900A' : '1px solid transparent',
              }}
            />
          )
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 11, color: '#9CA3AF' }}>
        <span>{humanize(DASHBOARD_STATES[0])}</span>
        <span>{humanize(DASHBOARD_STATES[DASHBOARD_STATES.length - 1])}</span>
      </div>
    </div>
  )
}

function WorkflowCard({ workflow, onOpen }: { workflow: WorkflowRecord; onOpen: (id: string) => void }) {
  const tone = stateTone(workflow.current_state)
  const versionStatus = getVersionStatus(workflow)
  const borderColor = tone === 'review' ? '#F59E0B' : tone === 'negotiation' ? '#0EA5E9' : tone === 'signed' ? '#10B981' : tone === 'rejected' ? '#EF4444' : '#E5E7EB'
  const bg = tone === 'review' ? '#FFFBEB' : tone === 'negotiation' ? '#F0F9FF' : tone === 'signed' ? '#ECFDF5' : tone === 'rejected' ? '#FEF2F2' : 'white'

  return (
    <button
      onClick={() => onOpen(workflow.id)}
      style={{ textAlign: 'left', width: '100%', border: `1px solid ${borderColor}`, background: bg, borderRadius: 12, padding: 14, boxShadow: '0 1px 0 rgba(15,23,42,0.02)', cursor: 'pointer' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: 14, fontWeight: 800, color: '#0F1F3D', margin: 0, lineHeight: 1.3 }}>{workflow.source_label || 'Agreement activity'}</p>
          <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {workflow.counterparty_email || workflow.sent_to_counterparty_email || 'Counterparty not attached'}
          </p>
        </div>
        <span style={{ borderRadius: 999, background: '#243447', color: 'white', fontSize: 11, fontWeight: 700, padding: '5px 10px', whiteSpace: 'nowrap' }}>
          {humanize(workflow.current_state)}
        </span>
      </div>
      <div style={{ marginBottom: 10 }}>
        <ProgressStrip workflow={workflow} />
      </div>
      <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, color: '#374151' }}>
          <span>Pending action</span>
          <strong style={{ fontWeight: 700 }}>{getNextAction(workflow.current_state)}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, color: '#374151' }}>
          <span>Last activity</span>
          <strong style={{ fontWeight: 700, textAlign: 'right' }}>{workflow.last_activity?.description || 'No activity yet'}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, color: '#374151' }}>
          <span>Active version</span>
          <strong style={{ fontWeight: 700 }}>{versionStatus}</strong>
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
        <p style={{ fontSize: 11, color: '#9CA3AF', margin: 0 }}>{formatDate(workflow.last_activity?.created_at || workflow.updated_at)}</p>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D' }}>Open workspace</span>
      </div>
    </button>
  )
}

function Section({ title, description, empty, workflows, onOpen }: SectionConfig & { onOpen: (id: string) => void }) {
  return (
    <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 18 }}>
      <div style={{ marginBottom: 14 }}>
        <h3 style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{title}</h3>
        <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0', lineHeight: 1.5 }}>{description}</p>
      </div>
      {workflows.length ? (
        <div style={{ display: 'grid', gap: 12 }}>
          {workflows.map((workflow) => <WorkflowCard key={workflow.id} workflow={workflow} onOpen={onOpen} />)}
        </div>
      ) : (
        <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>{empty}</p>
      )}
    </section>
  )
}

function RailButton({ label, active = false, disabled = false, onClick }: { label: string; active?: boolean; disabled?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={disabled ? 'Coming soon' : undefined}
      onClick={onClick}
      style={{
        width: '100%', height: 32, textAlign: 'left', border: active ? '1px solid #243447' : disabled ? '1px solid #E5E7EB' : '1px solid #CBD5E1',
        borderRadius: 8, background: active ? '#243447' : disabled ? '#F8FAFC' : 'white', padding: '0 10px', cursor: disabled ? 'default' : 'pointer',
        color: active ? 'white' : disabled ? '#94A3B8' : '#243447', fontSize: 12, fontWeight: 800,
      }}
    >
      {label}
    </button>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 10, padding: 10, boxShadow: '0 1px 2px rgba(15,23,42,0.03)' }}>
      <p style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#9CA3AF', fontWeight: 800, margin: '0 0 7px' }}>{title}</p>
      <div style={{ display: 'grid', gap: 6 }}>{children}</div>
    </section>
  )
}

function TopActionTab({ label, disabled = false, onClick }: { label: string; disabled?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={disabled ? 'Coming soon' : undefined}
      onClick={onClick}
      style={{
        height: 32,
        padding: '0 12px',
        border: disabled ? '1px solid #E5E7EB' : '1px solid #CBD5E1',
        borderRadius: 999,
        background: disabled ? '#F8FAFC' : 'white',
        color: disabled ? '#94A3B8' : '#243447',
        fontSize: 12,
        fontWeight: 800,
        cursor: disabled ? 'default' : 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )
}

function PanelQuickAction({ label, tone, disabled = false, onClick }: { label: string; tone: 'green' | 'neutral' | 'warm' | 'light'; disabled?: boolean; onClick?: () => void }) {
  const styles: Record<typeof tone, CSSProperties> = {
    green: { background: '#10B981', border: '1px solid #10B981', color: 'white' },
    neutral: { background: 'rgba(226,232,240,0.12)', border: '1px solid rgba(226,232,240,0.28)', color: '#E2E8F0' },
    warm: { background: 'rgba(245,166,35,0.92)', border: '1px solid rgba(245,166,35,0.92)', color: '#111827' },
    light: { background: 'rgba(255,255,255,0.9)', border: '1px solid rgba(255,255,255,0.9)', color: '#243447' },
  }

  return (
    <button
      type="button"
      disabled={disabled}
      title={disabled ? 'Coming soon' : undefined}
      onClick={onClick}
      style={{
        ...styles[tone],
        minHeight: 36,
        borderRadius: 10,
        padding: '0 12px',
        fontSize: 12,
        fontWeight: 850,
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.72 : 1,
        boxShadow: tone === 'green' ? '0 10px 22px rgba(16,185,129,0.18)' : 'none',
      }}
    >
      {label}
    </button>
  )
}

function EditorToolButton({ label, onClick, disabled = false, minWidth }: { label: string; onClick?: () => void; disabled?: boolean; minWidth?: number }) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={disabled ? 'Coming soon' : undefined}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      style={{
        height: 30,
        minWidth: minWidth || 34,
        padding: '0 10px',
        border: disabled ? '1px solid #E5E7EB' : '1px solid #CBD5E1',
        borderRadius: 8,
        background: disabled ? '#F8FAFC' : 'white',
        color: disabled ? '#94A3B8' : '#243447',
        fontSize: 12,
        fontWeight: 850,
        cursor: disabled ? 'default' : 'pointer',
        boxShadow: disabled ? 'none' : '0 1px 2px rgba(15,23,42,0.04)',
      }}
    >
      {label}
    </button>
  )
}

function UtilityCard({ title, detail }: { title: string; detail: string }) {
  return (
    <div style={{ border: '1px solid #E5E7EB', borderRadius: 12, background: '#FFFFFF', padding: 12 }}>
      <p style={{ margin: 0, fontSize: 12, fontWeight: 850, color: '#0F1F3D' }}>{title}</p>
      <p style={{ margin: '5px 0 0', fontSize: 11, lineHeight: 1.45, color: '#64748B' }}>{detail}</p>
    </div>
  )
}

function WorkspaceEditorPanel({ onClose }: { onClose: () => void }) {
  const [isEmpty, setIsEmpty] = useState(true)
  const [wordCount, setWordCount] = useState(0)

  const runCommand = (command: string, value?: string) => {
    document.execCommand(command, false, value)
  }

  const updateWordCount = (text: string) => {
    const words = text.trim().split(/\s+/).filter(Boolean)
    setWordCount(words.length)
    setIsEmpty(words.length === 0)
  }

  const addLink = () => {
    const url = window.prompt('Paste a link')
    if (url) runCommand('createLink', url)
  }

  const addTable = () => {
    runCommand('insertHTML', '<table style="width:100%;border-collapse:collapse;margin:12px 0"><tbody><tr><td style="border:1px solid #CBD5E1;padding:8px"> </td><td style="border:1px solid #CBD5E1;padding:8px"> </td></tr><tr><td style="border:1px solid #CBD5E1;padding:8px"> </td><td style="border:1px solid #CBD5E1;padding:8px"> </td></tr></tbody></table>')
  }

  const addChecklist = () => {
    runCommand('insertHTML', '<ul style="list-style:none;padding-left:0"><li><input type="checkbox" /> Task item</li></ul>')
  }

  return (
    <section style={{ background: '#F8FAFC', border: '1px solid rgba(15,31,61,0.12)', borderRadius: 18, minHeight: 560, overflow: 'hidden', boxShadow: '0 18px 42px rgba(15,23,42,0.08)' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', borderBottom: '1px solid #E5E7EB', padding: '14px 16px', background: 'linear-gradient(180deg, #FFFFFF, #F8FAFC)' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 5 }}>
            <span style={{ borderRadius: 999, background: '#DCFCE7', color: '#047857', fontSize: 10, fontWeight: 900, padding: '4px 8px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>General editor</span>
            <span style={{ color: '#94A3B8', fontSize: 12, fontWeight: 800 }}>Local draft</span>
          </div>
          <h2 style={{ fontSize: 19, fontWeight: 900, color: '#0F1F3D', margin: 0, lineHeight: 1.2 }}>Workspace Editor</h2>
        </div>
        <button type="button" onClick={onClose} style={{ height: 32, padding: '0 12px', border: '1px solid #CBD5E1', borderRadius: 8, background: 'white', color: '#334155', fontSize: 12, fontWeight: 850, cursor: 'pointer' }}>Close</button>
      </header>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, borderBottom: '1px solid #E5E7EB', padding: '10px 16px', background: 'white' }}>
        <EditorToolButton label="Undo" onClick={() => runCommand('undo')} minWidth={50} />
        <EditorToolButton label="Redo" onClick={() => runCommand('redo')} minWidth={50} />
        <EditorToolButton label="B" onClick={() => runCommand('bold')} />
        <EditorToolButton label="I" onClick={() => runCommand('italic')} />
        <EditorToolButton label="U" onClick={() => runCommand('underline')} />
        <EditorToolButton label="H1" onClick={() => runCommand('formatBlock', 'H1')} />
        <EditorToolButton label="H2" onClick={() => runCommand('formatBlock', 'H2')} />
        <EditorToolButton label="Bullets" onClick={() => runCommand('insertUnorderedList')} minWidth={64} />
        <EditorToolButton label="Numbered" onClick={() => runCommand('insertOrderedList')} minWidth={76} />
        <EditorToolButton label="Quote" onClick={() => runCommand('formatBlock', 'BLOCKQUOTE')} minWidth={56} />
        <EditorToolButton label="Link" onClick={addLink} minWidth={48} />
        <EditorToolButton label="Table" onClick={addTable} minWidth={54} />
        <EditorToolButton label="Attachment" disabled minWidth={84} />
        <EditorToolButton label="Checklist" onClick={addChecklist} minWidth={78} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(150px,190px)', gap: 14, padding: 16 }}>
        <div style={{ minWidth: 0, display: 'flex', justifyContent: 'center' }}>
          <div style={{ position: 'relative', width: '100%', maxWidth: 760, minHeight: 420, border: '1px solid #E2E8F0', borderRadius: 14, background: '#FFFFFF', boxShadow: '0 16px 40px rgba(15,23,42,0.10)' }}>
            {isEmpty && (
              <p style={{ position: 'absolute', top: 30, left: 34, right: 34, margin: 0, color: '#94A3B8', fontSize: 15, lineHeight: 1.65, pointerEvents: 'none' }}>
                Start writing workspace notes, plans, tasks, meeting notes, or drafting material...
              </p>
            )}
            <div
              contentEditable
              suppressContentEditableWarning
              onInput={(event) => updateWordCount(event.currentTarget.textContent || '')}
              style={{ minHeight: 420, padding: '30px 34px', outline: 'none', color: '#0F172A', fontSize: 15, lineHeight: 1.75 }}
            />
          </div>
        </div>

        <aside style={{ display: 'grid', gap: 10, alignContent: 'start' }}>
          <UtilityCard title="Outline" detail="Headings from this workspace draft will appear here." />
          <UtilityCard title="Notes" detail="Keep side notes for planning and follow-up." />
          <UtilityCard title="Attachments" detail="Attach supporting workspace files later." />
          <UtilityCard title="Tasks" detail="Track draft work and next actions." />
        </aside>
      </div>

      <footer style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12, borderTop: '1px solid #E5E7EB', background: 'white', padding: '10px 16px', color: '#64748B', fontSize: 12, fontWeight: 750 }}>
        <span>Words: {wordCount}</span>
        <span>Last edited: Local</span>
        <span>Workspace draft</span>
      </footer>
    </section>
  )
}

type AskAIResponse = {
  draft_text?: string
  title?: string
  warnings?: string[]
  missing_fields?: string[]
  error?: string
}

type CreatedContractResponse = { id: string }

function AskAIContractPanel() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')
  const [contractType, setContractType] = useState('')
  const [jurisdiction, setJurisdiction] = useState('')
  const [parties, setParties] = useState('')
  const [keyTerms, setKeyTerms] = useState('')
  const [paymentTerms, setPaymentTerms] = useState('')
  const [serviceObligations, setServiceObligations] = useState('')
  const [deadlines, setDeadlines] = useState('')
  const [terminationTerms, setTerminationTerms] = useState('')
  const [disputeTerms, setDisputeTerms] = useState('')
  const [specialClauses, setSpecialClauses] = useState('')
  const [selectedClauses, setSelectedClauses] = useState<string[]>(['Payment', 'Service obligations', 'Termination', 'Dispute resolution'])
  const [generatedDraft, setGeneratedDraft] = useState('')
  const [generatedTitle, setGeneratedTitle] = useState('')
  const [generationWarnings, setGenerationWarnings] = useState<string[]>([])
  const [missingFields, setMissingFields] = useState<string[]>([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationError, setGenerationError] = useState('')
  const [isCreatingContract, setIsCreatingContract] = useState(false)
  const [createError, setCreateError] = useState('')

  const toggleClause = (clause: string) => {
    setSelectedClauses((current) => current.includes(clause) ? current.filter((item) => item !== clause) : [...current, clause])
  }

  const canGenerate = Boolean(prompt.trim() || contractType.trim() || keyTerms.trim())

  const generateDraft = async () => {
    if (!canGenerate || isGenerating) return
    setIsGenerating(true)
    setGenerationError('')
    setCreateError('')
    setGeneratedDraft('')
    setGeneratedTitle('')
    setGenerationWarnings([])
    setMissingFields([])
    try {
      const { data } = await api.post<AskAIResponse>('/ai/contracts/generate-draft/', {
        prompt,
        contract_type: contractType,
        jurisdiction,
        parties,
        key_terms: keyTerms,
        payment_terms: paymentTerms,
        service_obligations: serviceObligations,
        deadlines,
        termination_terms: terminationTerms,
        dispute_terms: disputeTerms,
        special_clauses: specialClauses,
        include_clauses: selectedClauses.map((clause) => clause.toLowerCase().replaceAll(' ', '_')),
      })
      setGeneratedDraft(data.draft_text || '')
      setGeneratedTitle(data.title || 'AI Generated Contract Draft')
      setGenerationWarnings(data.warnings || [])
      setMissingFields(data.missing_fields || [])
      if (!data.draft_text) setGenerationError('AI returned no draft text.')
    } catch (err: unknown) {
      const responseError = (err as { response?: { data?: { error?: string } } })?.response?.data?.error
      setGenerationError(responseError || 'AI generation failed. Please try again.')
    } finally {
      setIsGenerating(false)
    }
  }

  const copyDraft = async () => {
    if (!generatedDraft) return
    await navigator.clipboard?.writeText(generatedDraft)
  }


  const createContractFromDraft = async () => {
    if (!generatedDraft || isCreatingContract) return
    setIsCreatingContract(true)
    setCreateError('')
    try {
      const title = generatedTitle || contractType || 'AI Generated Contract Draft'
      const { data: created } = await api.post<CreatedContractResponse>('/contracts/', {
        title,
        contract_type: contractType || 'AI Generated Contract',
        description: keyTerms || prompt || 'Generated by Ask AI in Workspace.',
        jurisdiction,
        governing_law: jurisdiction,
        counterparty_name: parties,
        counterparty_email: 'pending@bonup.placeholder',
        structure_type: 'ONE_TIME',
        entity_type: 'personal',
        status: 'draft',
        state: 'created',
      })
      const editorHtml = generatedDraft
        .split(/\n{2,}/)
        .map((block) => `<p>${block.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br />')}</p>`)
        .join('')
      await api.patch(`/contracts/${created.id}/draft/`, {
        content_snapshot: {
          editor_html: editorHtml,
          text: generatedDraft,
          source: 'workspace_ask_ai',
          generated_title: title,
          missing_fields: missingFields,
          warnings: generationWarnings,
        },
      })
      navigate(`/contracts/create?id=${created.id}`)
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: unknown } })?.response?.data
      const msg = errData && typeof errData === 'object'
        ? Object.values(errData as Record<string, unknown>).flat().join(' ')
        : 'Could not create a contract from this draft.'
      setCreateError(String(msg))
    } finally {
      setIsCreatingContract(false)
    }
  }

  return (
    <section style={{ background: '#F8FAFC', border: '1px solid rgba(15,31,61,0.12)', borderRadius: 18, overflow: 'hidden', boxShadow: '0 18px 42px rgba(15,23,42,0.08)' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', borderBottom: '1px solid #E5E7EB', padding: '16px 18px', background: 'linear-gradient(180deg, #FFFFFF, #F8FAFC)' }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ margin: '0 0 5px', color: '#10B981', fontSize: 10, fontWeight: 900, letterSpacing: '0.14em', textTransform: 'uppercase' }}>Ask AI</p>
          <h2 style={{ margin: 0, color: '#0F1F3D', fontSize: 20, fontWeight: 900, lineHeight: 1.2 }}>Ask AI</h2>
          <p style={{ margin: '7px 0 0', color: '#64748B', fontSize: 13, lineHeight: 1.5 }}>Generate contract drafts from plain-language instructions.</p>
        </div>
        <span style={{ flexShrink: 0, borderRadius: 999, background: '#ECFDF5', color: '#047857', fontSize: 11, fontWeight: 850, padding: '6px 10px' }}>Draft text only</span>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,0.92fr) minmax(260px,1.08fr)', gap: 14, padding: 16 }}>
        <section style={{ display: 'grid', gap: 10, minWidth: 0 }}>
          <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>
            Freeform request
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="I need a lawn service agreement in Florida with monthly payment, weekly service, 10-day termination, and mediation before arbitration." style={{ minHeight: 118, resize: 'vertical', border: '1px solid #CBD5E1', borderRadius: 10, padding: 11, color: '#0F172A', fontSize: 13, lineHeight: 1.5, outline: 'none' }} />
          </label>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Contract type<input value={contractType} onChange={(event) => setContractType(event.target.value)} placeholder="Service agreement" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
            <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Jurisdiction<input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} placeholder="Florida" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
          </div>

          <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Parties<input value={parties} onChange={(event) => setParties(event.target.value)} placeholder="Provider and client names, emails, or roles" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
          <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Key terms<input value={keyTerms} onChange={(event) => setKeyTerms(event.target.value)} placeholder="Purpose, scope, deliverables, constraints" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Payment terms<input value={paymentTerms} onChange={(event) => setPaymentTerms(event.target.value)} placeholder="$500/month, due first of month" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
            <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Deadlines<input value={deadlines} onChange={(event) => setDeadlines(event.target.value)} placeholder="Start date, renewal, milestones" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
          </div>
          <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Service obligations<input value={serviceObligations} onChange={(event) => setServiceObligations(event.target.value)} placeholder="Weekly mowing, edging, cleanup" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Termination terms<input value={terminationTerms} onChange={(event) => setTerminationTerms(event.target.value)} placeholder="10-day written notice" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
            <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Dispute / resolution<input value={disputeTerms} onChange={(event) => setDisputeTerms(event.target.value)} placeholder="Mediation before arbitration" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>
          </div>
          <label style={{ display: 'grid', gap: 5, color: '#334155', fontSize: 12, fontWeight: 800 }}>Special clauses<input value={specialClauses} onChange={(event) => setSpecialClauses(event.target.value)} placeholder="Insurance, confidentiality, access, warranties" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 9, padding: '0 10px', fontSize: 13 }} /></label>

          <div style={{ display: 'grid', gap: 8 }}>
            <p style={{ margin: 0, color: '#334155', fontSize: 12, fontWeight: 850 }}>Include clauses</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {AI_CLAUSE_OPTIONS.map((clause) => (
                <label key={clause} style={{ display: 'flex', alignItems: 'center', gap: 6, border: '1px solid #CBD5E1', borderRadius: 999, background: selectedClauses.includes(clause) ? '#ECFDF5' : 'white', color: '#243447', padding: '7px 9px', fontSize: 12, fontWeight: 750 }}>
                  <input type="checkbox" checked={selectedClauses.includes(clause)} onChange={() => toggleClause(clause)} />
                  {clause}
                </label>
              ))}
            </div>
          </div>

          <button type="button" disabled={!canGenerate || isGenerating} onClick={generateDraft} style={{ justifySelf: 'start', height: 38, padding: '0 14px', border: 'none', borderRadius: 10, background: !canGenerate || isGenerating ? '#CBD5E1' : '#10B981', color: 'white', fontSize: 13, fontWeight: 900, cursor: !canGenerate || isGenerating ? 'default' : 'pointer' }}>
            {isGenerating ? 'Generating...' : 'Generate Contract'}
          </button>
          {generationError && <p style={{ margin: 0, color: '#B91C1C', fontSize: 12, fontWeight: 750 }}>{generationError}</p>}
        </section>

        <section style={{ display: 'grid', gap: 10, minWidth: 0 }}>
          <div style={{ background: 'white', border: '1px solid #E5E7EB', borderRadius: 14, overflow: 'hidden', minHeight: 520, display: 'grid', gridTemplateRows: 'auto minmax(0,1fr) auto' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', borderBottom: '1px solid #E5E7EB', padding: '11px 13px', background: '#F8FAFC' }}>
              <p style={{ margin: 0, color: '#0F1F3D', fontSize: 13, fontWeight: 900 }}>Generated draft preview</p>
              <span style={{ color: '#64748B', fontSize: 11, fontWeight: 750 }}>Draft text</span>
            </header>
            <div style={{ padding: 16, overflow: 'auto' }}>
              {generatedDraft ? (
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: '#0F172A', fontSize: 13, lineHeight: 1.65, fontFamily: 'inherit' }}>{generatedDraft}</pre>
              ) : (
                <div style={{ height: '100%', minHeight: 360, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: '#94A3B8', fontSize: 13, lineHeight: 1.5, padding: 24 }}>
                  Generated contract text will appear here after a real AI response.
                </div>
              )}
            </div>
            <footer style={{ display: 'flex', flexWrap: 'wrap', gap: 8, borderTop: '1px solid #E5E7EB', padding: 11, background: '#F8FAFC' }}>
              <button type="button" disabled={!generatedDraft} onClick={copyDraft} style={{ height: 32, padding: '0 11px', border: '1px solid #CBD5E1', borderRadius: 8, background: generatedDraft ? 'white' : '#F1F5F9', color: generatedDraft ? '#243447' : '#94A3B8', fontSize: 12, fontWeight: 850, cursor: generatedDraft ? 'pointer' : 'default' }}>Copy</button>
              <button type="button" disabled={!generatedDraft || isCreatingContract} onClick={createContractFromDraft} style={{ height: 32, padding: '0 11px', border: generatedDraft ? '1px solid #10B981' : '1px solid #E5E7EB', borderRadius: 8, background: generatedDraft ? '#10B981' : '#F1F5F9', color: generatedDraft ? 'white' : '#94A3B8', fontSize: 12, fontWeight: 850, cursor: generatedDraft && !isCreatingContract ? 'pointer' : 'default' }}>{isCreatingContract ? 'Creating...' : 'Create Contract from Draft'}</button>
            </footer>
            {(generationWarnings.length > 0 || missingFields.length > 0 || createError) && (
              <div style={{ borderTop: '1px solid #E5E7EB', padding: 11, background: '#FFFBEB', color: '#92400E', fontSize: 12, lineHeight: 1.45 }}>
                {generationWarnings.map((warning) => <p key={warning} style={{ margin: '0 0 5px' }}>{warning}</p>)}
                {missingFields.length > 0 && <p style={{ margin: '0 0 5px' }}>Missing fields: {missingFields.join(', ')}</p>}
                {createError && <p style={{ margin: 0, color: '#B91C1C' }}>{createError}</p>}
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  )
}

function MyObligationsPanel() {
  return (
    <section style={{ background: '#F8FAFC', border: '1px solid rgba(15,31,61,0.12)', borderRadius: 18, overflow: 'hidden', boxShadow: '0 18px 42px rgba(15,23,42,0.08)' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', borderBottom: '1px solid #E5E7EB', padding: '16px 18px', background: 'linear-gradient(180deg, #FFFFFF, #F8FAFC)' }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ margin: '0 0 5px', color: '#10B981', fontSize: 10, fontWeight: 900, letterSpacing: '0.14em', textTransform: 'uppercase' }}>Lifecycle workspace</p>
          <h2 style={{ margin: 0, color: '#0F1F3D', fontSize: 20, fontWeight: 900, lineHeight: 1.2 }}>My Obligations</h2>
          <p style={{ margin: '7px 0 0', color: '#64748B', fontSize: 13, lineHeight: 1.5 }}>Track what you owe, what others owe you, and what needs action.</p>
        </div>
        <span style={{ flexShrink: 0, borderRadius: 999, background: '#E0F2FE', color: '#0369A1', fontSize: 11, fontWeight: 850, padding: '6px 10px' }}>Workspace view</span>
      </header>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, borderBottom: '1px solid #E5E7EB', padding: '10px 16px', background: 'white' }}>
        {OBLIGATION_FILTERS.map((filter, index) => (
          <button key={filter} type="button" style={{ height: 30, padding: '0 11px', border: index === 0 ? '1px solid #243447' : '1px solid #CBD5E1', borderRadius: 999, background: index === 0 ? '#243447' : 'white', color: index === 0 ? 'white' : '#243447', fontSize: 12, fontWeight: 850, cursor: 'default' }}>
            {filter}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(150px,190px)', gap: 14, padding: 16 }}>
        <main style={{ minWidth: 0, display: 'grid', gap: 12 }}>
          <section style={{ minHeight: 250, border: '1px dashed #CBD5E1', borderRadius: 14, background: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
            <div style={{ textAlign: 'center', maxWidth: 360 }}>
              <p style={{ margin: 0, color: '#0F1F3D', fontSize: 15, fontWeight: 850 }}>No obligations loaded yet.</p>
              <p style={{ margin: '8px 0 0', color: '#64748B', fontSize: 12, lineHeight: 1.5 }}>Signed-contract obligations will appear here when lifecycle data is available in Workspace.</p>
            </div>
          </section>
        </main>

        <aside style={{ display: 'grid', gap: 10, alignContent: 'start' }}>
          {OBLIGATION_SUMMARY_ITEMS.map(([label, value]) => (
            <div key={label} style={{ border: '1px solid #E5E7EB', borderRadius: 12, background: 'white', padding: 12 }}>
              <p style={{ margin: 0, color: '#64748B', fontSize: 11, fontWeight: 800 }}>{label}</p>
              <p style={{ margin: '6px 0 0', color: '#0F1F3D', fontSize: 24, fontWeight: 900 }}>{value}</p>
            </div>
          ))}
        </aside>
      </div>
    </section>
  )
}

function ContractStuffPanel() {
  return (
    <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 16, padding: 18, boxShadow: '0 12px 30px rgba(15,23,42,0.05)' }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 20, fontWeight: 900, color: '#0F1F3D', margin: 0 }}>Contract Stuff</h2>
        <p style={{ fontSize: 13, color: '#64748B', margin: '7px 0 0', lineHeight: 1.55 }}>Manage supporting contract actions, documents, and operational records.</p>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {CONTRACT_STUFF_ITEMS.map(([label, description]) => (
          <article key={label} style={{ border: '1px solid #E5E7EB', borderRadius: 12, background: '#F8FAFC', padding: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
              <div style={{ minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 850, color: '#0F1F3D' }}>{label}</p>
                <p style={{ margin: '6px 0 0', fontSize: 12, lineHeight: 1.45, color: '#64748B' }}>{description}</p>
              </div>
              <span style={{ flexShrink: 0, borderRadius: 999, background: '#FEF3C7', color: '#92400E', fontSize: 10, fontWeight: 850, padding: '4px 7px' }}>Coming soon</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

export default function WorkflowDashboard() {
  const navigate = useNavigate()
  const [showActivity, setShowActivity] = useState(false)
  const [showContracts, setShowContracts] = useState(false)
  const [showWorkspaceEditor, setShowWorkspaceEditor] = useState(false)
  const [showContractStuff, setShowContractStuff] = useState(false)
  const [showMyObligations, setShowMyObligations] = useState(false)
  const [showAskAI, setShowAskAI] = useState(false)
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [contracts, setContracts] = useState<ContractRecord[]>([])
  const [contractsLoading, setContractsLoading] = useState(true)
  const [contractsError, setContractsError] = useState('')

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    api.get<WorkflowListResponse>('/ai/workflows/')
      .then(({ data }) => {
        if (!cancelled) setWorkflows(data.results || [])
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.error || 'Activity could not be loaded.')
          setWorkflows([])
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setContractsLoading(true)
    api.get<ContractListResponse>('/contracts/')
      .then(({ data }) => {
        if (cancelled) return
        setContracts(Array.isArray(data) ? data : data.results || [])
      })
      .catch((err) => {
        if (!cancelled) {
          setContractsError(err?.response?.data?.error || 'Contracts could not be loaded.')
          setContracts([])
        }
      })
      .finally(() => {
        if (!cancelled) setContractsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const sections = useMemo(() => {
    const active = workflows.filter((workflow) => !['signed', 'rejected'].includes(workflow.current_state))
    const awaiting = workflows.filter((workflow) => ['sent_to_counterparty', 'counterparty_viewed', 'counterparty_requested_changes'].includes(workflow.current_state))
    const needsReview = workflows.filter((workflow) => ['uploaded', 'analyzing', 'review_ready', 'counter_draft_ready', 'version_created'].includes(workflow.current_state))
    const sent = workflows.filter((workflow) => ['sent_to_counterparty', 'counterparty_viewed', 'counterparty_requested_changes', 'accepted'].includes(workflow.current_state))
    const signed = workflows.filter((workflow) => workflow.current_state === 'signed')
    const recent = workflows
      .filter((workflow) => workflow.last_activity)
      .slice()
      .sort((a, b) => new Date(b.last_activity!.created_at).getTime() - new Date(a.last_activity!.created_at).getTime())
    return { active, awaiting, needsReview, sent, signed, recent }
  }, [workflows])

  const toggleWorkspaceEditor = () => {
    setShowWorkspaceEditor((value) => {
      const nextValue = !value
      if (nextValue) {
        setShowActivity(false)
        setShowContracts(false)
        setShowContractStuff(false)
        setShowMyObligations(false)
        setShowAskAI(false)
      }
      return nextValue
    })
  }

  const toggleActivity = () => {
    setShowActivity((value) => {
      const nextValue = !value
      if (nextValue) {
        setShowWorkspaceEditor(false)
        setShowContracts(false)
        setShowContractStuff(false)
        setShowMyObligations(false)
        setShowAskAI(false)
      }
      return nextValue
    })
  }

  const toggleContracts = () => {
    setShowContracts((value) => {
      const nextValue = !value
      if (nextValue) {
        setShowWorkspaceEditor(false)
        setShowActivity(false)
        setShowContractStuff(false)
        setShowMyObligations(false)
        setShowAskAI(false)
      }
      return nextValue
    })
  }

  const toggleContractStuff = () => {
    setShowContractStuff((value) => {
      const nextValue = !value
      if (nextValue) {
        setShowWorkspaceEditor(false)
        setShowActivity(false)
        setShowContracts(false)
        setShowMyObligations(false)
        setShowAskAI(false)
      }
      return nextValue
    })
  }

  const toggleMyObligations = () => {
    setShowMyObligations((value) => {
      const nextValue = !value
      if (nextValue) {
        setShowWorkspaceEditor(false)
        setShowActivity(false)
        setShowContracts(false)
        setShowContractStuff(false)
        setShowAskAI(false)
      }
      return nextValue
    })
  }

  const toggleAskAI = () => {
    setShowAskAI((value) => {
      const nextValue = !value
      if (nextValue) {
        setShowWorkspaceEditor(false)
        setShowActivity(false)
        setShowContracts(false)
        setShowContractStuff(false)
        setShowMyObligations(false)
      }
      return nextValue
    })
  }

  const stats = [
    { label: 'Active Activity', value: sections.active.length },
    { label: 'Awaiting Response', value: sections.awaiting.length },
    { label: 'Needs Your Review', value: sections.needsReview.length },
    { label: 'Sent To Counterparty', value: sections.sent.length },
    { label: 'Signed Agreements', value: sections.signed.length },
    { label: 'Recent Activity', value: sections.recent.length },
  ]

  return (
    <div className="space-y-6">
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 20 }}>
        <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.16em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>
          Blackboard operating center
        </p>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#0F1F3D', margin: 0, lineHeight: 1.15 }}>Workspace</h1>
        <p style={{ fontSize: 13, color: '#6B7280', margin: '10px 0 0', maxWidth: 760, lineHeight: 1.6 }}>
          Activity across agreements, pending actions, counterparties, and negotiation continuity is tracked here.
        </p>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(190px,220px)_minmax(0,1fr)_minmax(280px,340px)]" style={{ alignItems: 'start' }}>
        <aside style={{ display: 'grid', gap: 10, alignContent: 'start' }}>
          <Group title="Create">
            <RailButton label="Workspace Editor" active={showWorkspaceEditor} onClick={toggleWorkspaceEditor} />
          </Group>
          <Group title="Agreement Records">
            <RailButton label="Activity" active={showActivity} onClick={toggleActivity} />
            <RailButton label="Contract" active={showContracts} onClick={toggleContracts} />
          </Group>
          <Group title="Post-Signature">
            <RailButton label="My Obligations" active={showMyObligations} onClick={toggleMyObligations} />
            <RailButton label="Lifecycle" onClick={() => navigate('/lifecycle')} />
            <RailButton label="Change Orders" disabled />
            <RailButton label="Resolution" disabled />
            <RailButton label="Contract Stuff" active={showContractStuff} onClick={toggleContractStuff} />
          </Group>
        </aside>

        <main style={{ minHeight: 360, maxHeight: 'calc(100vh - 220px)', overflowY: 'auto', paddingRight: 4 }}>
          <div style={{ display: 'grid', gap: 14 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
              <TopActionTab label="Workspace Editor" onClick={toggleWorkspaceEditor} />
              <TopActionTab label="Analyze Contract" onClick={() => navigate('/analysis')} />
              <TopActionTab label="Contract Counter" onClick={() => navigate('/counter')} />
              <TopActionTab label="Calendar" disabled />
              <TopActionTab label="Ask AI" onClick={toggleAskAI} />
              <TopActionTab label="Messages" disabled />
              <TopActionTab label="Live Messages" disabled />
              <TopActionTab label="Notes" disabled />
            </div>

            {showWorkspaceEditor && !showActivity && !showContracts && !showContractStuff && !showMyObligations && !showAskAI && <WorkspaceEditorPanel onClose={() => setShowWorkspaceEditor(false)} />}

            {showAskAI && !showWorkspaceEditor && !showActivity && !showContracts && !showContractStuff && !showMyObligations && <AskAIContractPanel />}

            {showMyObligations && !showWorkspaceEditor && !showActivity && !showContracts && !showContractStuff && !showAskAI && <MyObligationsPanel />}

            {showContractStuff && !showWorkspaceEditor && !showActivity && !showContracts && !showMyObligations && !showAskAI && <ContractStuffPanel />}

            {!showWorkspaceEditor && !showActivity && !showContracts && !showContractStuff && !showMyObligations && !showAskAI && (
              <section
                aria-label="Workspace empty state"
                style={{
                  minHeight: 320,
                  border: '1px solid rgba(148,163,184,0.18)',
                  borderRadius: 16,
                  backgroundColor: '#020617',
                  backgroundImage: [
                    'radial-gradient(circle at 18% 22%, rgba(16,185,129,0.22) 0, rgba(16,185,129,0.08) 9%, transparent 24%)',
                    'radial-gradient(circle at 78% 18%, rgba(96,165,250,0.18) 0, rgba(96,165,250,0.06) 12%, transparent 28%)',
                    'radial-gradient(circle at 64% 72%, rgba(255,255,255,0.11) 0, transparent 22%)',
                    'radial-gradient(circle, rgba(255,255,255,0.86) 0 1px, transparent 1.8px)',
                    'radial-gradient(circle, rgba(125,211,252,0.75) 0 1px, transparent 1.6px)',
                    'linear-gradient(135deg, #020617 0%, #07111F 48%, #020617 100%)',
                  ].join(', '),
                  backgroundSize: '100% 100%, 100% 100%, 100% 100%, 68px 68px, 118px 118px, 100% 100%',
                  backgroundPosition: 'center, center, center, 8px 10px, 28px 32px, center',
                  boxShadow: 'inset 0 0 70px rgba(15,23,42,0.72), 0 12px 32px rgba(15,23,42,0.08)',
                  overflow: 'hidden',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'linear-gradient(180deg, rgba(255,255,255,0.05), transparent 28%, rgba(2,6,23,0.32))',
                    pointerEvents: 'none',
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    left: '50%',
                    top: '50%',
                    width: 180,
                    height: 180,
                    transform: 'translate(-50%, -50%)',
                    borderRadius: '50%',
                    background: 'radial-gradient(circle, rgba(16,185,129,0.12), transparent 64%)',
                    filter: 'blur(6px)',
                    pointerEvents: 'none',
                  }}
                />
                <div
                  aria-hidden="true"
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    pointerEvents: 'none',
                    userSelect: 'none',
                  }}
                >
                  <div style={{ textAlign: 'center', transform: 'translateY(-12%)' }}>
                    <p style={{ margin: 0, color: 'rgba(255,255,255,0.085)', fontSize: 'clamp(48px, 8vw, 104px)', fontWeight: 900, lineHeight: 0.95, letterSpacing: 0 }}>
                      Blackboard
                    </p>
                    <p style={{ margin: '14px 0 0', color: 'rgba(209,250,229,0.34)', fontSize: 13, fontWeight: 800, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
                      Agreement operations start here
                    </p>
                  </div>
                </div>
                <div style={{ position: 'absolute', left: 24, right: 24, bottom: 24, display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', zIndex: 1 }}>
                  <PanelQuickAction label="Start New Contract" tone="green" onClick={() => navigate('/contracts/new')} />
                  <PanelQuickAction label="Analyze Contract" tone="neutral" onClick={() => navigate('/analysis')} />
                  <PanelQuickAction label="Contract Counter" tone="warm" onClick={() => navigate('/counter')} />
                  <PanelQuickAction label="Invite a Friend" tone="light" disabled />
                </div>
              </section>
            )}

            {showContracts && (
              <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 18 }}>
                <div style={{ marginBottom: 14 }}>
                  <h3 style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Contract</h3>
                  <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0', lineHeight: 1.5 }}>Your current contract records from Blackboard.</p>
                </div>
                {contractsLoading ? (
                  <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>Loading contracts...</p>
                ) : contractsError ? (
                  <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 10, padding: '10px 12px', fontSize: 13, color: '#B91C1C' }}>{contractsError}</div>
                ) : contracts.length === 0 ? (
                  <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>No contract records yet.</p>
                ) : (
                  <div style={{ display: 'grid', gap: 10 }}>
                    {contracts.map((contract) => {
                      const label = contractStatusLabel(contract)
                      return (
                        <article key={contract.id} style={{ border: '1px solid #E5E7EB', background: '#F8FAFC', borderRadius: 10, padding: 12 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                            <div style={{ minWidth: 0 }}>
                              <p style={{ fontSize: 13, fontWeight: 800, color: '#0F1F3D', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{contract.title || 'Untitled Contract'}</p>
                              <p style={{ fontSize: 12, color: '#64748B', margin: '5px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {contract.contract_type || 'Contract'} - {contractPartyLabel(contract)} - Created {formatContractDate(contract.created_at)}
                              </p>
                            </div>
                            <span style={{ flexShrink: 0, borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 700, ...contractStatusStyle(label) }}>{label}</span>
                          </div>
                          <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                            <button type="button" onClick={() => navigate(`/contracts/${contract.id}`)} style={{ height: 30, padding: '0 11px', borderRadius: 7, border: '1px solid #CBD5E1', background: 'white', color: '#334155', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>Open Contract</button>
                          </div>
                        </article>
                      )
                    })}
                  </div>
                )}
              </section>
            )}

            {showActivity && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {stats.map((stat) => (
                    <div key={stat.label} style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 18 }}>
                      <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#9CA3AF', fontWeight: 700, margin: 0 }}>{stat.label}</p>
                      <p style={{ fontSize: 28, fontWeight: 800, color: '#0F1F3D', margin: '8px 0 0' }}>{isLoading ? '-' : stat.value}</p>
                    </div>
                  ))}
                </div>
                {error && <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 12, padding: '12px 14px', fontSize: 13, color: '#B91C1C' }}>{error}</div>}
                <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                  <Section title="Active Activity" description="Open agreements that still require movement or a decision." empty="No active activity items are in motion right now." workflows={sections.active} onOpen={(id) => navigate(`/workflows/${id}`)} />
                  <Section title="Needs Your Review" description="Review, counter, or approve the next operational step." empty="Nothing is waiting for your review." workflows={sections.needsReview} onOpen={(id) => navigate(`/workflows/${id}`)} />
                  <Section title="Awaiting Response" description="Agreements that are with the counterparty or waiting on a reply." empty="No activity item is awaiting a counterparty response." workflows={sections.awaiting} onOpen={(id) => navigate(`/workflows/${id}`)} />
                  <Section title="Sent To Counterparty" description="Agreements that have left the initiator-side workspace." empty="No agreements have been sent yet." workflows={sections.sent} onOpen={(id) => navigate(`/workflows/${id}`)} />
                  <Section title="Signed Agreements" description="Completed agreements that are now canonical records." empty="No agreements are signed yet." workflows={sections.signed} onOpen={(id) => navigate(`/workflows/${id}`)} />
                  <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 18 }}>
                    <div style={{ marginBottom: 14 }}>
                      <h3 style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Recent Negotiation Activity</h3>
                      <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0', lineHeight: 1.5 }}>Most recent operational events across your agreements.</p>
                    </div>
                    {sections.recent.length ? (
                      <div style={{ display: 'grid', gap: 10 }}>
                        {sections.recent.map((workflow) => (
                          <button key={workflow.id} onClick={() => navigate(`/workflows/${workflow.id}`)} style={{ textAlign: 'left', border: '1px solid #E5E7EB', background: '#F8FAFC', borderRadius: 10, padding: 12, cursor: 'pointer' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                              <p style={{ fontSize: 13, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>{workflow.source_label || 'Agreement activity'}</p>
                              <span style={{ fontSize: 11, color: '#9CA3AF' }}>{formatDate(workflow.last_activity?.created_at)}</span>
                            </div>
                            <p style={{ fontSize: 12, color: '#374151', margin: 0, lineHeight: 1.5 }}>{workflow.last_activity?.description || 'No activity recorded.'}</p>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>No negotiation activity has been recorded yet.</p>
                    )}
                  </section>
                </div>
              </>
            )}
          </div>
        </main>

        <aside style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end' }}>
          <section style={{ width: '100%', maxWidth: 340, background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 16, padding: 14, boxShadow: '0 12px 28px rgba(15,23,42,0.06)' }}>
            <div style={{ borderRadius: 12, background: '#243447', height: 112, padding: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden', marginBottom: 14 }}>
              <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, rgba(16,185,129,0.24), rgba(15,31,61,0) 52%)' }} />
              <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'rgba(255,255,255,0.14)', border: '1px solid rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                <span style={{ marginLeft: 3, width: 0, height: 0, borderTop: '7px solid transparent', borderBottom: '7px solid transparent', borderLeft: '11px solid white' }} />
              </div>
              <div style={{ position: 'absolute', left: 14, right: 14, bottom: 12, height: 4, borderRadius: 999, background: 'rgba(255,255,255,0.18)' }}>
                <div style={{ width: '34%', height: '100%', borderRadius: 999, background: '#10B981' }} />
              </div>
            </div>
            <div style={{ display: 'grid', gap: 7, marginBottom: 14 }}>
              {GET_STARTED_VIDEOS.map((title) => (
                <div key={title} style={{ display: 'flex', alignItems: 'center', gap: 8, border: '1px solid #E5E7EB', borderRadius: 9, background: '#F8FAFC', padding: '8px 9px' }}>
                  <span style={{ width: 6, height: 6, borderRadius: 999, background: '#10B981', flexShrink: 0 }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#334155', lineHeight: 1.35 }}>{title}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gap: 12 }}>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 850, color: '#0F1F3D', margin: 0 }}>Get Started</h2>
                <p style={{ fontSize: 12, color: '#64748B', margin: '7px 0 0', lineHeight: 1.5 }}>Create, review, negotiate, and track agreements from one workspace.</p>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}
