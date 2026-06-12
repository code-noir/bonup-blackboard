import { useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import WorkflowTimeline from '@/components/workflow/WorkflowTimeline'
import AgreementExchangeRequestBuilder, { type AgreementExchangeSavedRequest } from '@/components/agreementExchange/AgreementExchangeRequestBuilder'
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


type ContractSection = {
  id: string
  number: number
  name: string
}

type WorkflowVersionSnapshot = {
  content_snapshot?: string | null
  status?: string
  version_number?: number
}

type PersistedContractSnapshot = {
  editor_html?: string
  final_editor_html?: string
  sections?: ContractSection[]
  clauses?: { body?: string }[]
}

export type WorkflowActivity = {
  id?: string
  activity_type: string
  description: string
  created_at: string
}

export type WorkflowRecord = {
  id: string
  agreement_exchange_id?: string | null
  exchange_id?: string | null
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
  content_snapshot?: string | null
  active_version?: WorkflowVersionSnapshot | null
  latest_version?: WorkflowVersionSnapshot | null
  current_version?: WorkflowVersionSnapshot | null
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

type CounterpartyRequestView = {
  requestType: string
  text: string
  message: string
}

function getRecordValue(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function getRequestType(value: unknown) {
  const text = String(value || '').toLowerCase()
  if (text.includes('payment')) return 'Payment'
  if (text.includes('service')) return 'Service'
  if (text.includes('termination')) return 'Termination'
  return 'General'
}

function getCounterpartyRequestView(requests?: Array<unknown>): CounterpartyRequestView | null {
  const request = requests?.[0]
  if (!request) return null

  if (typeof request === 'string') {
    return { requestType: 'General', text: request, message: '' }
  }

  if (typeof request === 'object') {
    const record = request as Record<string, unknown>
    const requestType = getRequestType(record.request_type || record.type || record.category || record.change_type || record.obligation_type)
    const text = getRecordValue(record, ['proposed_text', 'requested_change', 'change', 'text', 'body', 'summary', 'description', 'request']) || JSON.stringify(request)
    const message = getRecordValue(record, ['reason', 'message', 'note', 'comment', 'comments'])
    return { requestType, text, message }
  }

  return { requestType: 'General', text: String(request), message: '' }
}

function normalizeSectionHeadingText(value: string) {
  return value.replace(/\s+/g, ' ').trim().toLowerCase()
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function toTitleCase(value: string) {
  return value.toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase())
}

function isAddressLikeSectionTitle(value: string) {
  const title = value.trim()
  return /^\d+\s+[\w\s.'-]+,\s*[A-Z]{2}\b/.test(title) || /\b(street|st\.|avenue|ave\.|road|rd\.|boulevard|blvd\.|suite|unit|zip)\b/i.test(title)
}

function isSignatureOnlySectionTitle(value: string) {
  return /^(provider|client|party|signature|signed|date)\s*:?\s*_*$/i.test(value.trim())
}

function isManualSectionHeading(line: string) {
  const trimmed = line.trim()
  if (trimmed.length < 4 || trimmed.length > 80) return false
  if (/[.!?]$/.test(trimmed)) return false
  if (/^[-_*\s]+$/.test(trimmed)) return false
  if (isAddressLikeSectionTitle(trimmed) || isSignatureOnlySectionTitle(trimmed)) return false
  const words = trimmed.split(/\s+/).filter(Boolean)
  if (words.length < 2 || words.length > 8) return false
  const hasContractKeyword = /\b(service|services|obligation|obligations|clause|payment|payments|terms|termination|warranty|liability|damages|insurance|confidentiality|notice|notices|governing|law|dispute|resolution|change|order|scope|deliverable|deliverables|schedule|workmanship)\b/i.test(trimmed)
  if (!hasContractKeyword) return false
  return words.every((word) => /^[A-Z][a-zA-Z0-9/&().-]*$/.test(word) || /^(and|or|of|the|to|for|in)$/i.test(word))
}

function sectionHeadingMatch(line: string) {
  const trimmed = line.trim()
  const match = trimmed.match(/^(?:(\d+)\.\s+([A-Z][A-Z0-9\s/&,().-]+|[A-Z][a-zA-Z0-9\s/&,().-]{2,80})|SECTION\s+(\d+)\s*[-:]\s*([A-Z][A-Z0-9\s/&,().-]+|[A-Z][a-zA-Z0-9\s/&,().-]{2,80})|([A-Z][A-Z0-9\s/&,().-]{3,80}))$/)
  if (match) return match
  if (!isManualSectionHeading(trimmed)) return null
  const manualMatch = [trimmed, undefined, undefined, undefined, undefined, trimmed] as unknown as RegExpMatchArray
  manualMatch.index = 0
  manualMatch.input = line
  return manualMatch
}

function sectionMatchTitle(match: RegExpMatchArray) {
  return (match[2] || match[4] || match[5] || '').trim()
}

function sectionMatchNumber(match: RegExpMatchArray, fallback: number) {
  return parseInt(match[1] || match[3] || String(fallback), 10)
}

function normalizePersistedSections(value: unknown): ContractSection[] | null {
  if (!Array.isArray(value)) return null
  const parsed = value
    .map((item, index) => {
      if (!item || typeof item !== 'object') return null
      const section = item as Partial<ContractSection>
      if (typeof section.name !== 'string') return null
      return {
        id: typeof section.id === 'string' ? section.id : `ps${index + 1}`,
        number: typeof section.number === 'number' ? section.number : index + 1,
        name: section.name,
      }
    })
    .filter((section): section is ContractSection => section !== null)
  return parsed.length > 0 ? parsed : null
}

function parsedSectionsFromMatches(matches: RegExpMatchArray[], prefix = 'exs'): ContractSection[] {
  return matches.map((match, index) => ({
    id: `${prefix}${index + 1}`,
    number: sectionMatchNumber(match, index + 1),
    name: toTitleCase(sectionMatchTitle(match)),
  }))
}

function parseCompatibleSections(content: string): ContractSection[] | null {
  const matches = content.split(/\r?\n/)
    .map((line) => sectionHeadingMatch(line))
    .filter((match): match is RegExpMatchArray => Boolean(match))
    .filter((match) => {
      const title = sectionMatchTitle(match)
      return Boolean(title) && !isAddressLikeSectionTitle(title) && !isSignatureOnlySectionTitle(title)
    })

  if (matches.length < 2) return null
  return parsedSectionsFromMatches(matches)
}

function textFromHtml(html: string) {
  if (typeof document === 'undefined') return html.replace(/<[^>]+>/g, '\n')
  const container = document.createElement('div')
  container.innerHTML = html
  return Array.from(container.querySelectorAll<HTMLElement>('h1,h2,h3,h4,p,div,li'))
    .map((el) => (el.textContent || '').trim())
    .filter(Boolean)
    .join('\n') || (container.textContent || '')
}

function buildHtmlFromText(content: string, sections: ContractSection[]) {
  const byNum = new Map(sections.map((section) => [section.number, section]))
  const byName = new Map(sections.map((section) => [normalizeSectionHeadingText(section.name), section]))
  const usedAnchors = new Set<string>()
  return content.split('\n').map((line) => {
    const match = sectionHeadingMatch(line)
    if (match) {
      const title = sectionMatchTitle(match)
      const num = sectionMatchNumber(match, 0)
      const section = (num ? byNum.get(num) : null) || byName.get(normalizeSectionHeadingText(title))
      if (section && !usedAnchors.has(section.id)) {
        usedAnchors.add(section.id)
        return `<h2 id="section-${section.id}" style="margin:20px 0 6px;font-size:15px;font-weight:800;color:#0F1F3D;">${escapeHtml(line)}</h2>`
      }
    }
    if (line.trim() === '') return '<div style="height:8px"></div>'
    return `<p style="font-size:13px;line-height:1.65;color:#374151;margin:0 0 8px;">${escapeHtml(line)}</p>`
  }).join('')
}

function annotateHtmlAnchors(html: string, sections: ContractSection[]) {
  if (!sections.length || typeof document === 'undefined') return html
  const container = document.createElement('div')
  container.innerHTML = html
  const candidates = Array.from(container.querySelectorAll<HTMLElement>('h1,h2,h3,h4,p,div,li'))
  const used = new Set<string>()

  sections.forEach((section) => {
    const expectedTitle = normalizeSectionHeadingText(section.name)
    const expectedNumbered = normalizeSectionHeadingText(`${section.number}. ${section.name}`)
    const existing = container.querySelector<HTMLElement>(`#section-${section.id}`)
    if (existing) {
      used.add(section.id)
      return
    }

    const match = candidates.find((el) => {
      if (used.has(el.dataset.sectionAnchorCandidate || '')) return false
      const text = normalizeSectionHeadingText(el.textContent || '')
      const heading = sectionHeadingMatch(el.textContent || '')
      if (heading) {
        const headingNumber = sectionMatchNumber(heading, section.number)
        const headingName = normalizeSectionHeadingText(sectionMatchTitle(heading))
        if (headingNumber === section.number && headingName === expectedTitle) return true
      }
      return text === expectedTitle || text === expectedNumbered || text.startsWith(`${section.number}. ${expectedTitle}`)
    })

    if (match) {
      match.id = `section-${section.id}`
      match.dataset.sectionAnchorCandidate = section.id
      used.add(section.id)
    }
  })

  return container.innerHTML
}

function parseSnapshot(content: string): PersistedContractSnapshot | null {
  try {
    const parsed = JSON.parse(content) as PersistedContractSnapshot
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

function getWorkflowContentSnapshot(workflow: WorkflowRecord) {
  return workflow.active_version?.content_snapshot
    || workflow.current_version?.content_snapshot
    || workflow.latest_version?.content_snapshot
    || workflow.content_snapshot
    || ''
}

function getCurrentContractDocument(workflow: WorkflowRecord) {
  const contentSnapshot = getWorkflowContentSnapshot(workflow)
  const snapshot = contentSnapshot ? parseSnapshot(contentSnapshot) : null
  const persistedSections = normalizePersistedSections(snapshot?.sections)
  const snapshotHtml = snapshot?.editor_html || snapshot?.final_editor_html || ''
  const clauseText = Array.isArray(snapshot?.clauses) ? snapshot.clauses.map((clause) => clause.body || '').join('\n\n') : ''
  const fallbackText = workflow.counter_drafts?.[0]?.generated_revised_contract || ''
  const rawContent = snapshotHtml || clauseText || (!snapshot && contentSnapshot ? contentSnapshot : '') || fallbackText

  if (!rawContent) return { html: '', sections: [] as ContractSection[], usedPersistedSections: Boolean(persistedSections), usedFallbackParsing: false }

  const textForParsing = snapshotHtml ? textFromHtml(snapshotHtml) : rawContent
  const parsedSections = persistedSections || parseCompatibleSections(textForParsing) || []
  const html = snapshotHtml
    ? annotateHtmlAnchors(snapshotHtml, parsedSections)
    : buildHtmlFromText(rawContent, parsedSections)

  return {
    html,
    sections: parsedSections,
    usedPersistedSections: Boolean(persistedSections),
    usedFallbackParsing: !persistedSections && parsedSections.length > 0,
  }
}


function DisabledExchangeButton({ children }: { children: ReactNode }) {
  return (
    <button
      type="button"
      disabled
      title="Coming soon"
      style={{ height: 34, padding: '0 12px', borderRadius: 8, border: '1px solid #CBD5E1', background: '#F8FAFC', color: '#94A3B8', fontSize: 12, fontWeight: 700, cursor: 'not-allowed' }}
    >
      {children}
    </button>
  )
}

export default function WorkflowWorkspace({ workflow }: WorkflowWorkspaceProps) {
  const navigate = useNavigate()
  const versionStatus = getDerivedVersionStatus(workflow)
  const nextAction = getNextAction(workflow.current_state)
  const counterparty = workflow.counterparty_email || workflow.sent_to_counterparty_email || 'Not shared yet'
  const agreementExchangeId = workflow.agreement_exchange_id || workflow.exchange_id || workflow.id
  const progress = Math.max(1, getProgressIndex(workflow.current_state) + 1)
  const [activeContractSection, setActiveContractSection] = useState<string | null>(null)
  const [showRequestBuilder, setShowRequestBuilder] = useState(false)
  const [savedExchangeRequest, setSavedExchangeRequest] = useState<AgreementExchangeSavedRequest | null>(null)
  const contractPreviewRef = useRef<HTMLDivElement | null>(null)
  const contractDocument = useMemo(() => getCurrentContractDocument(workflow), [workflow])
  const counterpartyRequest = getCounterpartyRequestView(savedExchangeRequest ? [savedExchangeRequest] : workflow.counterparty_requested_changes)

  function scrollToContractSection(sectionId: string) {
    const container = contractPreviewRef.current
    const target = container?.querySelector<HTMLElement>(`#section-${sectionId}`)
    if (!container || !target) {
      setActiveContractSection(null)
      return
    }

    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const nextTop = container.scrollTop + targetRect.top - containerRect.top - 14
    container.scrollTo({ top: Math.max(nextTop, 0), behavior: 'smooth' })
    setActiveContractSection(sectionId)
  }

  return (
    <div className="space-y-3">
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: '10px 14px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', alignItems: 'start', gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
              <h1 style={{ fontSize: 23, fontWeight: 800, color: '#0F1F3D', margin: 0, lineHeight: 1.12 }}>
                Agreement Exchange
              </h1>
              <button type="button" onClick={() => navigate('/dashboard')} style={{ height: 28, padding: '0 10px', border: '1px solid #CBD5E1', borderRadius: 7, background: '#F8FAFC', color: '#334155', fontSize: 11, fontWeight: 750, cursor: 'pointer' }}>
                Back to Dashboard
              </button>
              <button type="button" onClick={() => navigate('/workflows')} style={{ height: 28, padding: '0 10px', border: '1px solid #CBD5E1', borderRadius: 7, background: 'white', color: '#334155', fontSize: 11, fontWeight: 750, cursor: 'pointer' }}>
                Back to Workflows
              </button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '5px 9px', marginTop: 4 }}>
              <p style={{ margin: 0, fontSize: 13, color: '#4B5563', lineHeight: 1.3, fontWeight: 650 }}>
                {workflow.source_label || 'Agreement workflow'}
              </p>
              <span style={{ width: 4, height: 4, borderRadius: 999, background: '#CBD5E1' }} />
              <p style={{ margin: 0, fontSize: 12, color: '#6B7280', lineHeight: 1.3 }}>
                Exchange ID {agreementExchangeId}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center', justifyContent: 'flex-end' }}>
            <span style={{ borderRadius: 999, background: '#FEF3C7', color: '#9A6700', fontSize: 11, fontWeight: 700, padding: '4px 8px' }}>
              {humanize(workflow.current_state)}
            </span>
            <span style={{ borderRadius: 999, background: '#EEF2FF', color: '#4338CA', fontSize: 11, fontWeight: 700, padding: '4px 8px' }}>
              Version {versionStatus}
            </span>
            <span style={{ borderRadius: 999, background: '#ECFDF5', color: '#065F46', fontSize: 11, fontWeight: 700, padding: '4px 8px' }}>
              Step {progress} of {FLOW_STEPS.length}
            </span>
          </div>
        </div>

        <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 6 }}>
          <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: '6px 9px' }}><MetaRow label="Counterparty" value={counterparty} /></div>
          <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: '6px 9px' }}><MetaRow label="Pending action" value={nextAction} /></div>
          <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: '6px 9px' }}><MetaRow label="Last activity" value={workflow.last_activity?.description || 'No activity yet'} /></div>
          <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: '6px 9px' }}><MetaRow label="Activity time" value={formatDate(workflow.last_activity?.created_at || workflow.updated_at)} /></div>
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
        compact
        hideContext
        variant="horizontal"
      />

      <div
          className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,1fr)]"
          style={{
            minHeight: 560,
            alignItems: "stretch",
            border: "1px solid rgba(226,232,240,0.24)",
            borderRadius: 18,
            padding: 20,
            backgroundColor: "#020617",
            backgroundImage: [
              "radial-gradient(circle at 18% 22%, rgba(16,185,129,0.22) 0, rgba(16,185,129,0.08) 9%, transparent 24%)",
              "radial-gradient(circle at 78% 18%, rgba(96,165,250,0.18) 0, rgba(96,165,250,0.06) 12%, transparent 28%)",
              "radial-gradient(circle at 64% 72%, rgba(255,255,255,0.11) 0, transparent 22%)",
              "radial-gradient(circle, rgba(255,255,255,0.86) 0 1px, transparent 1.8px)",
              "radial-gradient(circle, rgba(125,211,252,0.75) 0 1px, transparent 1.6px)",
              "linear-gradient(180deg, rgba(255,255,255,0.07), transparent 32%, rgba(2,6,23,0.34))",
              "linear-gradient(135deg, #020617 0%, #07111F 48%, #020617 100%)",
            ].join(", "),
            backgroundSize: "100% 100%, 100% 100%, 100% 100%, 68px 68px, 118px 118px, 100% 100%, 100% 100%",
            backgroundPosition: "center, center, center, 8px 10px, 28px 32px, center, center, center",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.12), inset 0 0 86px rgba(15,23,42,0.76), 0 20px 46px rgba(15,23,42,0.16)",
          }}
        >
          <div style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
            <p style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.12em", color: "#E2E8F0", fontWeight: 800, margin: "0 0 8px", textShadow: "0 1px 10px rgba(15,23,42,0.65)" }}>Initiator Panel</p>
            <section style={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(255,255,255,0.72)', borderRadius: 12, padding: 20, minHeight: 500, flex: 1, boxShadow: '0 18px 38px rgba(2,6,23,0.24), inset 0 1px 0 rgba(255,255,255,0.82)' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Current Contract</h2>
                <p style={{ fontSize: 13, color: '#6B7280', margin: '6px 0 0', lineHeight: 1.5 }}>{workflow.source_label || 'Agreement workflow'}</p>
              </div>
              <span style={{ borderRadius: 999, background: '#EEF2FF', color: '#4338CA', fontSize: 11, fontWeight: 700, padding: '5px 9px' }}>
                Version {versionStatus}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[180px_minmax(0,1fr)]">
              <aside style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 10, padding: 12, alignSelf: 'start' }}>
                <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 10px' }}>Contract Sections</p>
                {contractDocument.sections.length ? (
                  <div style={{ display: 'grid', gap: 6 }}>
                    {contractDocument.sections.map((section) => {
                      const isActive = activeContractSection === section.id
                      return (
                        <button
                          key={section.id}
                          type="button"
                          onClick={() => scrollToContractSection(section.id)}
                          style={{ width: '100%', textAlign: 'left', border: `1px solid ${isActive ? '#F5A623' : '#E5E7EB'}`, borderRadius: 8, background: isActive ? '#FFFBF0' : '#FFFFFF', color: isActive ? '#0F1F3D' : '#475569', padding: '8px 9px', fontSize: 12, fontWeight: isActive ? 800 : 600, cursor: 'pointer', lineHeight: 1.35 }}
                        >
                          <span style={{ color: '#94A3B8', marginRight: 6 }}>{section.number}.</span>{section.name}
                        </button>
                      )
                    })}
                  </div>
                ) : (
                  <p style={{ fontSize: 12, color: '#9CA3AF', lineHeight: 1.5, margin: 0 }}>No contract sections available yet.</p>
                )}
              </aside>

              {contractDocument.html ? (
                <div
                  ref={contractPreviewRef}
                  style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 10, padding: 14, maxHeight: 560, minHeight: 420, overflowY: 'auto' }}
                  dangerouslySetInnerHTML={{ __html: contractDocument.html }}
                />
              ) : (
                <div style={{ minHeight: 420, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFC', border: '1px dashed #CBD5E1', borderRadius: 10, padding: 18, textAlign: 'center' }}>
                  <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>Current contract version will appear here.</p>
                </div>
              )}
            </div>
            </section>
          </div>

          <div style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
            <p style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.12em", color: "#E2E8F0", fontWeight: 800, margin: "0 0 8px", textShadow: "0 1px 10px rgba(15,23,42,0.65)" }}>Counterparty Panel</p>
            <section style={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(255,255,255,0.72)', borderRadius: 12, padding: 20, minHeight: 500, flex: 1, boxShadow: '0 18px 38px rgba(2,6,23,0.24), inset 0 1px 0 rgba(255,255,255,0.82)' }}>
            <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Counterparty Event</h2>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '6px 0 14px', lineHeight: 1.5 }}>{counterparty}</p>

            {counterpartyRequest ? (
              <div style={{ display: 'grid', gap: 12 }}>
                <span style={{ justifySelf: 'start', borderRadius: 999, background: '#FEF3C7', color: '#9A6700', fontSize: 11, fontWeight: 800, padding: '5px 9px' }}>
                  {counterpartyRequest.requestType}
                </span>
                <div>
                  <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>Requested change</p>
                  <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>{counterpartyRequest.text}</p>
                </div>
                {counterpartyRequest.message && (
                  <div>
                    <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>Message</p>
                    <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>{counterpartyRequest.message}</p>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ minHeight: 320, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFC', border: '1px dashed #CBD5E1', borderRadius: 10, padding: 16, textAlign: 'center' }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>No counterparty change request yet.</p>
              </div>
            )}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
              <DisabledExchangeButton>Sign Contract</DisabledExchangeButton>
              <button type="button" onClick={() => setShowRequestBuilder((value) => !value)} style={{ height: 34, padding: '0 12px', borderRadius: 8, border: '1px solid #0F1F3D', background: showRequestBuilder ? '#0F1F3D' : 'white', color: showRequestBuilder ? 'white' : '#0F1F3D', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
                Request Change
              </button>
              <DisabledExchangeButton>Reject</DisabledExchangeButton>
            </div>
            <p style={{ fontSize: 11, color: '#9CA3AF', margin: '8px 0 0' }}>Sign and reject are coming soon. Request Change saves a structured request only.</p>

            {showRequestBuilder && (
              <div style={{ marginTop: 16, background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 10, padding: 14 }}>
                <AgreementExchangeRequestBuilder
                  exchangeId={agreementExchangeId}
                  sections={contractDocument.sections}
                  onSaved={(request) => {
                    setSavedExchangeRequest(request)
                    setShowRequestBuilder(false)
                  }}
                />
              </div>
            )}

            <div style={{ height: 1, background: 'linear-gradient(90deg, transparent, #CBD5E1, transparent)', margin: '18px 0 16px' }} />
            <div>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 4px' }}>Participants</p>
              <h3 style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '0 0 12px' }}>Counterparty Status</h3>
              <MetaRow label="Counterparty email" value={counterparty} />
              <MetaRow label="Counterparty user" value={workflow.counterparty_user_id ? workflow.counterparty_user_id : 'Not attached'} />
              <MetaRow label="Requested changes" value={workflow.counterparty_requested_changes?.length ? `${workflow.counterparty_requested_changes.length} request bundle(s)` : 'No requests yet'} />
              <MetaRow label="Sent to" value={workflow.sent_to_counterparty_email || 'Not sent yet'} />
              <MetaRow label="Active version status" value={versionStatus} />
            </div>
          </section>
        </div>
      </div>

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
