import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import AgreementExchangeRequestBuilder, { type AgreementExchangeSavedRequest } from '@/components/agreementExchange/AgreementExchangeRequestBuilder'

type ExchangeRole = 'initiator' | 'counterparty' | 'unknown'
type Actor = 'initiator' | 'counterparty' | 'none'

type ExchangeSummary = {
  id: string
  contract_id: string
  current_contract_version_id: string
  source_contract_version_id?: string | null
  restarted_from_exchange_id?: string | null
  status: string
  current_actor: Actor
  counterparty_email: string
  initiator?: { id: string; email: string; name?: string } | null
  counterparty_user?: { id: string; email: string; name?: string } | null
  created_at: string
  updated_at: string
}

type ContractSection = {
  id: string
  number: number
  name: string
  title?: string
  content_html?: string
}

type CurrentContract = {
  id: string
  contract_id: string
  title: string
  version_label: string
  version_number: number
  source_version_number?: number
  status: string
  content_html: string
  sections: ContractSection[]
}

type ExchangeRequest = AgreementExchangeSavedRequest & {
  requested_by_email?: string
  initiator_response?: string | null
  pending_next_version_text?: string | null
  created_at?: string
  updated_at?: string
}

type ExchangeEvent = {
  id: string
  actor_role: ExchangeRole | 'system'
  event_type: string
  message: string
  metadata?: Record<string, unknown>
  created_at: string
}

type ExchangeSignature = {
  id: string
  signer_email: string
  signer_role: ExchangeRole
  typed_name?: string | null
  signature_text?: string | null
  signed_at: string
}

type AgreementExchangeDetail = {
  exchange: ExchangeSummary
  viewer_role: ExchangeRole
  screen_state: string
  current_contract: CurrentContract
  requests: ExchangeRequest[]
  events: ExchangeEvent[]
  signatures: ExchangeSignature[]
  available_actions: string[]
}

type RestartResponse = {
  exchange_id: string
  redirect_path: string
  status: string
  current_contract: CurrentContract
}

const PAGE: React.CSSProperties = { display: 'grid', gap: 12, paddingBottom: 36 }
const HEADER: React.CSSProperties = { background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 10, padding: '12px 14px', boxShadow: '0 10px 24px rgba(15, 31, 61, 0.06)' }
const FRAME: React.CSSProperties = {
  borderRadius: 16,
  padding: 18,
  border: '1px solid rgba(148, 163, 184, 0.28)',
  background: 'radial-gradient(circle at 20% 12%, rgba(59, 130, 246, 0.22), transparent 28%), radial-gradient(circle at 84% 18%, rgba(245, 166, 35, 0.18), transparent 24%), linear-gradient(135deg, #07111F 0%, #0B1730 46%, #030712 100%)',
  boxShadow: '0 24px 60px rgba(2, 6, 23, 0.24), inset 0 1px 0 rgba(255,255,255,0.12)',
}
const CARD: React.CSSProperties = { background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 10, padding: 14, boxShadow: '0 16px 36px rgba(15, 31, 61, 0.12)' }
const LABEL: React.CSSProperties = { fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#94A3B8', fontWeight: 800, margin: '0 0 8px' }
const BUTTON: React.CSSProperties = { height: 36, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 13px', background: '#FFFFFF', color: '#0F1F3D', fontSize: 12, fontWeight: 800, cursor: 'pointer' }
const PRIMARY_BUTTON: React.CSSProperties = { ...BUTTON, border: 'none', background: '#0F1F3D', color: '#FFFFFF' }
const DANGER_BUTTON: React.CSSProperties = { ...BUTTON, border: '1px solid #FCA5A5', color: '#991B1B' }
const TEXTAREA: React.CSSProperties = { width: '100%', minHeight: 96, border: '1px solid #CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, lineHeight: 1.5, fontFamily: 'inherit', boxSizing: 'border-box', resize: 'vertical' }

function formatDate(value?: string) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not recorded'
  return date.toLocaleString()
}

function prettify(value?: string | null) {
  if (!value) return 'Not set'
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    const media = window.matchMedia(query)
    const update = () => setMatches(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [query])

  return matches
}

function latestRequest(requests: ExchangeRequest[]) {
  return [...requests].reverse().find((request) => request.status === 'pending') || requests[requests.length - 1]
}


function getExchangeStateCopy(detail: AgreementExchangeDetail) {
  const role = detail.viewer_role
  const actor = detail.exchange.current_actor
  const status = detail.exchange.status
  const state = detail.screen_state

  if (state === 'initiator_send_initial_version') {
    return { mode: 'Ready to send', actor: role === 'initiator' ? 'You / Initiator' : 'Waiting on initiator', next: 'Send Version 1 to the counterparty.' }
  }
  if (state === 'counterparty_not_sent') {
    return { mode: 'Not sent yet', actor: 'Waiting on initiator', next: 'The initiator has not sent Version 1 yet.' }
  }
  if (state === 'signed' || status === 'signed') {
    return { mode: 'Signed', actor: 'No action required', next: 'The exchange is complete and visible to both parties.' }
  }
  if (state === 'rejected' || status === 'rejected') {
    return { mode: 'Rejected', actor: 'No action required', next: 'The exchange has ended.' }
  }
  if (state === 'initiator_review_requested_change') {
    return {
      mode: 'Initiator review',
      actor: role === 'initiator' ? 'Your turn' : 'Waiting on initiator',
      next: 'Review the requested change and accept, edit, or reject it.',
    }
  }
  if (state === 'counterparty_review_updated_version') {
    return {
      mode: 'Updated version sent',
      actor: role === 'counterparty' ? 'Your turn' : 'Waiting on counterparty',
      next: 'Counterparty should review the update and sign, reject, or request another change.',
    }
  }
  if (state === 'ready_to_sign') {
    return {
      mode: 'Ready to sign',
      actor: actor === role ? 'Your turn' : actor === 'none' ? 'No action required' : `Waiting on ${actor}`,
      next: 'Review the current version and sign when ready.',
    }
  }
  if (state === 'counterparty_review') {
    return {
      mode: status === 'sent' || status === 'viewed' ? 'Sent to counterparty' : 'Counterparty review',
      actor: role === 'counterparty' ? 'Your turn' : 'Waiting on counterparty',
      next: 'Counterparty can sign, reject, or request a change.',
    }
  }
  if (state === 'counterparty_waiting') {
    return {
      mode: 'Waiting on initiator',
      actor: role === 'initiator' ? 'Your turn' : 'Waiting on initiator',
      next: 'Initiator should review the requested change.',
    }
  }
  if (state === 'initiator_waiting') {
    return {
      mode: actor === 'counterparty' ? 'Waiting on counterparty' : 'Preparing to send',
      actor: actor === role ? 'Your turn' : actor === 'none' ? 'No action required' : `Waiting on ${actor}`,
      next: actor === 'counterparty' ? 'Counterparty can sign, reject, or request a change.' : 'Send the agreement to the counterparty.',
    }
  }

  return {
    mode: prettify(status),
    actor: actor === role ? 'Your turn' : actor === 'none' ? 'No action required' : `Waiting on ${actor}`,
    next: detail.available_actions.length ? `Available actions: ${detail.available_actions.map(prettify).join(', ')}` : 'No action is available right now.',
  }
}

function StateBanner({ detail }: { detail: AgreementExchangeDetail }) {
  const copy = getExchangeStateCopy(detail)
  return (
    <div style={{ marginTop: 12, border: '1px solid #BFDBFE', borderRadius: 10, background: 'linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 100%)', padding: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
      <Info label="Mode" value={copy.mode} />
      <Info label="Current actor" value={copy.actor} />
      <Info label="Next action" value={copy.next} />
    </div>
  )
}

function StatusBadge({ children }: { children: string }) {
  return <span style={{ display: 'inline-flex', alignItems: 'center', height: 24, padding: '0 9px', borderRadius: 999, background: '#EEF2FF', color: '#3730A3', fontSize: 11, fontWeight: 800 }}>{children}</span>
}

function Timeline({ events }: { events: ExchangeEvent[] }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', fontSize: 11, color: '#475569' }}>
      <strong style={{ color: '#0F1F3D' }}>Timeline</strong>
      {events.length ? events.map((event) => (
        <span key={event.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', maxWidth: '100%' }}>
          <span style={{ width: 7, height: 7, borderRadius: 999, background: event.actor_role === 'counterparty' ? '#2563EB' : event.actor_role === 'initiator' ? '#059669' : '#94A3B8' }} />
          {prettify(event.event_type)}
          <span style={{ color: '#94A3B8' }}>{formatDate(event.created_at)}</span>
        </span>
      )) : <span style={{ color: '#94A3B8' }}>No events yet.</span>}
    </div>
  )
}



function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function plainTextToHtml(value: string) {
  return value
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => `<p style="margin:0 0 10px;line-height:1.65;">${escapeHtml(block).replace(/\n/g, '<br />')}</p>`)
    .join('')
}

function resolveContractBodyHtml(contract: CurrentContract) {
  const raw = contract.content_html || ''
  if (!raw.trim()) {
    const sectionHtml = contract.sections.map((section) => section.content_html || '').filter(Boolean).join('')
    return sectionHtml
  }
  const trimmed = raw.trim()
  if (trimmed.startsWith('{')) {
    try {
      const parsed = JSON.parse(trimmed) as { editor_html?: string; final_editor_html?: string; content_html?: string; html?: string; clauses?: Array<{ body?: string }>; sections?: Array<{ content_html?: string; body?: string; text?: string }> }
      const html = parsed.editor_html || parsed.final_editor_html || parsed.content_html || parsed.html
      if (html) return html
      const sectionHtml = Array.isArray(parsed.sections) ? parsed.sections.map((section) => section.content_html || section.body || section.text || '').filter(Boolean).join('\n\n') : ''
      if (sectionHtml) return sectionHtml.includes('<') ? sectionHtml : plainTextToHtml(sectionHtml)
      const clauseText = Array.isArray(parsed.clauses) ? parsed.clauses.map((clause) => clause.body || '').filter(Boolean).join('\n\n') : ''
      if (clauseText) return plainTextToHtml(clauseText)
    } catch {
      return plainTextToHtml(raw)
    }
  }
  return trimmed.includes('<') ? raw : plainTextToHtml(raw)
}

function normalizeAnchorText(value: string) {
  return value.replace(/\s+/g, ' ').trim().toLowerCase()
}

function annotateContractBodyHtml(html: string, sections: ContractSection[]) {
  if (!html || !sections.length || typeof document === 'undefined') return html
  const container = document.createElement('div')
  container.innerHTML = html
  const candidates = Array.from(container.querySelectorAll<HTMLElement>('h1,h2,h3,h4,p,div,li'))
  const used = new Set<string>()

  sections.forEach((section) => {
    const title = normalizeAnchorText(section.name || section.title || '')
    const numberedTitle = normalizeAnchorText(`${section.number}. ${section.name || section.title || ''}`)
    if (!title || container.querySelector(`#ae-section-${section.id}`)) return
    const match = candidates.find((element) => {
      const text = normalizeAnchorText(element.textContent || '')
      return !used.has(text) && (text === title || text === numberedTitle || text.startsWith(numberedTitle) || text.startsWith(title))
    })
    if (match) {
      match.id = `ae-section-${section.id}`
      used.add(normalizeAnchorText(match.textContent || ''))
    }
  })

  return container.innerHTML
}

function ContractViewer({ contract }: { contract: CurrentContract }) {
  const previewRef = useRef<HTMLDivElement | null>(null)
  const stackContractLayout = useMediaQuery('(max-width: 900px)')

  function scrollToSection(sectionId: string) {
    const container = previewRef.current
    const target = container?.querySelector<HTMLElement>(`#ae-section-${sectionId}`)
    if (!container || !target) return
    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    container.scrollTo({ top: container.scrollTop + targetRect.top - containerRect.top - 12, behavior: 'smooth' })
  }

  const bodyHtml = useMemo(() => resolveContractBodyHtml(contract), [contract])
  const hasBody = Boolean(bodyHtml && bodyHtml.trim())
  const annotatedBodyHtml = useMemo(() => annotateContractBodyHtml(bodyHtml, contract.sections), [bodyHtml, contract.sections])

  return (
    <div style={CARD}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start', marginBottom: 10 }}>
        <div>
          <p style={LABEL}>Current Contract</p>
          <h2 style={{ margin: 0, fontSize: 19, color: '#0F1F3D' }}>{contract.title}</h2>
        </div>
        <StatusBadge>{contract.version_label}</StatusBadge>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: contract.sections.length && !stackContractLayout ? '180px minmax(0, 1fr)' : '1fr', gap: 14, alignItems: 'start' }}>
        {contract.sections.length > 0 && (
          <aside style={{ border: '1px solid #E5E7EB', borderRadius: 8, background: '#F8FAFC', padding: 10, maxHeight: 620, overflow: 'auto' }}>
            <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748B', fontWeight: 800, margin: '0 0 8px' }}>Sections</p>
            <div style={{ display: 'grid', gap: 6 }}>
              {contract.sections.map((section) => (
                <button key={section.id} type="button" onClick={() => scrollToSection(section.id)} style={{ minHeight: 30, border: '1px solid #CBD5E1', borderRadius: 7, background: '#FFFFFF', color: '#0F1F3D', padding: '6px 8px', fontSize: 11, fontWeight: 750, cursor: 'pointer', textAlign: 'left', lineHeight: 1.3 }}>
                  <span style={{ color: '#64748B', marginRight: 5 }}>{section.number}.</span>{section.name || section.title}
                </button>
              ))}
            </div>
          </aside>
        )}
        <div ref={previewRef} style={{ maxHeight: stackContractLayout ? 560 : 680, minHeight: stackContractLayout ? 360 : 520, overflow: 'auto', border: '1px solid #CBD5E1', borderRadius: 8, padding: 22, background: '#FFFFFF', color: '#0F172A', lineHeight: 1.65, fontSize: 14, boxShadow: 'inset 0 1px 0 rgba(15,23,42,0.04)' }}>
          {hasBody ? (
            <div className="agreement-exchange-contract-body" dangerouslySetInnerHTML={{ __html: annotatedBodyHtml }} />
          ) : (
            <div style={{ minHeight: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', border: '1px dashed #CBD5E1', borderRadius: 8, background: '#F8FAFC', color: '#64748B', fontSize: 13, fontWeight: 700 }}>
              No contract body was returned for this version.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function RequestSummary({ request }: { request?: ExchangeRequest }) {
  if (!request) return <p style={{ margin: 0, color: '#64748B', fontSize: 13 }}>No requested changes have been submitted.</p>
  return (
    <div style={{ display: 'grid', gap: 8, fontSize: 13, color: '#0F172A' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
        <Info label="Counterparty" value={request.requested_by_email || 'Counterparty'} />
        <Info label="Target section" value={request.target_section_title || 'General'} />
        <Info label="Category" value={prettify(request.request_category)} />
        <Info label="Action" value={prettify(request.action_type)} />
      </div>
      <Block label="Proposed text" value={request.proposed_text || ''} />
      {request.pending_next_version_text && <Block label="Update sent" value={request.pending_next_version_text} />}
      {request.reason && <Block label="Reason" value={request.reason} />}
      {request.initiator_response && <Block label="Initiator response" value={request.initiator_response} />}
      <StatusBadge>{prettify(request.status)}</StatusBadge>
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return <div><p style={{ margin: '0 0 3px', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#94A3B8', fontWeight: 800 }}>{label}</p><p style={{ margin: 0, fontWeight: 700, color: '#0F1F3D' }}>{value}</p></div>
}

function Block({ label, value }: { label: string; value: string }) {
  return <div><p style={{ ...LABEL, color: '#64748B', marginBottom: 4 }}>{label}</p><div style={{ border: '1px solid #E5E7EB', borderRadius: 8, background: '#F8FAFC', padding: 10, whiteSpace: 'pre-wrap' }}>{value || 'Not provided.'}</div></div>
}

function decisionStatusCopy(detail: AgreementExchangeDetail) {
  const actor = detail.exchange.current_actor
  const isViewerTurn = detail.viewer_role === actor
  const copy = getExchangeStateCopy(detail)

  if (isViewerTurn) {
    return {
      title: copy.mode,
      body: copy.next,
    }
  }

  return {
    title: copy.actor,
    body: copy.next,
  }
}

function DecisionPanel({ detail, onRefresh, smallScreen }: { detail: AgreementExchangeDetail; onRefresh: () => void; smallScreen: boolean }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'idle' | 'request' | 'reject' | 'sign' | 'edit'>('idle')
  const [reason, setReason] = useState('')
  const [typedName, setTypedName] = useState(user ? `${user.first_name || ''} ${user.last_name || ''}`.trim() : '')
  const [signatureText, setSignatureText] = useState('')
  const [responseText, setResponseText] = useState('')
  const [finalText, setFinalText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const request = useMemo(() => latestRequest(detail.requests), [detail.requests])
  const canCounterpartyAct = detail.viewer_role === 'counterparty' && detail.exchange.current_actor === 'counterparty'
  const canInitiatorAct = detail.viewer_role === 'initiator' && detail.exchange.current_actor === 'initiator'

  useEffect(() => {
    if (request?.proposed_text) setFinalText(request.proposed_text)
  }, [request?.id])

  async function submit(path: string, payload: Record<string, unknown>) {
    setIsSubmitting(true)
    setError('')
    try {
      await api.post(path, payload)
      await onRefresh()
      setMode('idle')
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.response?.data?.non_field_errors?.[0] || 'Action could not be completed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function respond(decision: 'accept' | 'edit' | 'reject') {
    if (!request?.id) return
    await submit(`/agreement-exchange/${detail.exchange.id}/requests/${request.id}/respond/`, {
      decision,
      final_text: decision === 'reject' ? '' : finalText,
      initiator_response: responseText,
    })
  }

  async function restartFromCurrentVersion() {
    setIsSubmitting(true)
    setError('')
    try {
      const { data } = await api.post<RestartResponse>(`/agreement-exchange/${detail.exchange.id}/restart/`, {
        source_version_id: detail.current_contract.id,
      })
      navigate(data.redirect_path || `/agreement-exchange/${data.exchange_id}`)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Agreement Exchange could not be restarted.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (detail.screen_state === 'initiator_send_initial_version') {
    return (
      <div style={CARD}>
        <p style={LABEL}>Review Version 1</p>
        <div style={{ display: 'grid', gap: 8 }}>
          <p style={{ margin: 0, color: '#0F1F3D', fontSize: 14, fontWeight: 800 }}>Version {detail.current_contract.version_number} is ready for initiator review.</p>
          <p style={{ margin: 0, color: '#64748B', fontSize: 13 }}>Send the initial version to {detail.exchange.counterparty_email} when it is ready for counterparty review.</p>
          {detail.viewer_role === 'initiator' && detail.available_actions.includes('send_initial_version') ? (
            <button type="button" style={{ ...PRIMARY_BUTTON, justifySelf: 'start', marginTop: 4 }} onClick={() => submit(`/agreement-exchange/${detail.exchange.id}/send-initial/`, {})} disabled={isSubmitting}>
              {isSubmitting ? 'Sending...' : 'Send Initial Version'}
            </button>
          ) : (
            <p style={{ margin: 0, color: '#64748B', fontSize: 13 }}>Waiting for the initiator to send Version 1.</p>
          )}
        </div>
        {error && <p style={{ margin: '10px 0 0', color: '#B91C1C', fontSize: 12 }}>{error}</p>}
      </div>
    )
  }

  if (detail.screen_state === 'counterparty_not_sent') {
    return (
      <div style={CARD}>
        <p style={LABEL}>Not Sent Yet</p>
        <p style={{ margin: 0, color: '#64748B', fontSize: 13 }}>The initiator has not sent Version 1 for counterparty review yet.</p>
      </div>
    )
  }

  if (detail.screen_state === 'signed') {
    return <div style={CARD}><p style={LABEL}>Signed</p><RequestSummary request={request} />{detail.signatures.map((signature) => <p key={signature.id} style={{ margin: '10px 0 0', fontSize: 13, color: '#047857', fontWeight: 800 }}>{signature.signer_email} signed as {signature.signer_role} on {formatDate(signature.signed_at)}</p>)}</div>
  }

  if (detail.screen_state === 'rejected') {
    const rejected = detail.events.find((event) => event.event_type === 'exchange_rejected')
    return (
      <div style={CARD}>
        <p style={LABEL}>Rejected</p>
        <div style={{ display: 'grid', gap: 10 }}>
          <p style={{ margin: 0, color: '#991B1B', fontWeight: 800 }}>{rejected?.message || 'This Agreement Exchange was rejected.'}</p>
          {detail.viewer_role === 'initiator' && (
            <button type="button" style={{ ...PRIMARY_BUTTON, justifySelf: 'start' }} onClick={restartFromCurrentVersion} disabled={isSubmitting}>
              {isSubmitting ? 'Starting...' : 'Start New Exchange From This Version'}
            </button>
          )}
          {error && <p style={{ margin: 0, color: '#B91C1C', fontSize: 12 }}>{error}</p>}
        </div>
      </div>
    )
  }

  if (detail.screen_state === 'counterparty_waiting') {
    return <div style={CARD}><p style={LABEL}>Waiting for initiator review</p><RequestSummary request={request} /></div>
  }

  if (detail.screen_state === 'counterparty_review_updated_version') {
    return (
      <div style={CARD}>
        <p style={LABEL}>Updated Version</p>
        <RequestSummary request={request} />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          <button type="button" style={PRIMARY_BUTTON} onClick={() => setMode('sign')}>Sign Contract</button>
          <button type="button" style={BUTTON} onClick={() => setMode('request')}>Request Another Change</button>
          <button type="button" style={DANGER_BUTTON} onClick={() => setMode('reject')}>Reject</button>
        </div>
        {mode === 'request' && <Builder detail={detail} onRefresh={onRefresh} />}
        {mode === 'sign' && <SignForm typedName={typedName} signatureText={signatureText} setTypedName={setTypedName} setSignatureText={setSignatureText} onSubmit={() => submit(`/agreement-exchange/${detail.exchange.id}/sign/`, { typed_name: typedName, signature_text: signatureText })} isSubmitting={isSubmitting} />}
        {mode === 'reject' && <RejectForm reason={reason} setReason={setReason} onSubmit={() => submit(`/agreement-exchange/${detail.exchange.id}/reject/`, { reason })} isSubmitting={isSubmitting} />}
        {error && <p style={{ margin: '10px 0 0', color: '#B91C1C', fontSize: 12 }}>{error}</p>}
      </div>
    )
  }

  if (canInitiatorAct) {
    return (
      <div style={CARD}>
        <p style={LABEL}>Counterparty Request</p>
        <RequestSummary request={request} />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          <button type="button" style={PRIMARY_BUTTON} onClick={() => respond('accept')} disabled={!request?.id || isSubmitting}>Accept and Send Updated Version</button>
          <button type="button" style={BUTTON} onClick={() => setMode(mode === 'edit' ? 'idle' : 'edit')} disabled={!request?.id}>Edit First</button>
          <button type="button" style={DANGER_BUTTON} onClick={() => respond('reject')} disabled={!request?.id || isSubmitting}>Reject</button>
        </div>
        {mode === 'edit' && (
          <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
            <textarea value={finalText} onChange={(event) => setFinalText(event.target.value)} style={TEXTAREA} />
            <textarea value={responseText} onChange={(event) => setResponseText(event.target.value)} placeholder="Message to counterparty" style={{ ...TEXTAREA, minHeight: 70 }} />
            <button type="button" style={{ ...PRIMARY_BUTTON, justifySelf: 'start' }} onClick={() => respond('edit')} disabled={isSubmitting || !finalText.trim()}>{isSubmitting ? 'Sending...' : 'Send Edited Version'}</button>
          </div>
        )}
        {error && <p style={{ margin: '10px 0 0', color: '#B91C1C', fontSize: 12 }}>{error}</p>}
      </div>
    )
  }

  const statusCopy = decisionStatusCopy(detail)

  return (
    <div style={CARD}>
      <p style={LABEL}>{canCounterpartyAct ? 'Decision Panel' : 'Status'}</p>
      {canCounterpartyAct ? (
        <>
          <p style={{ margin: '0 0 12px', color: '#475569', fontSize: 13 }}>Review the contract, then sign, request a structured change, or reject.</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', width: smallScreen ? '100%' : undefined }}>
            <button type="button" style={{ ...PRIMARY_BUTTON, minWidth: 130 }} onClick={() => setMode('sign')}>Sign Contract</button>
            <button type="button" style={BUTTON} onClick={() => setMode(mode === 'request' ? 'idle' : 'request')}>Request Change</button>
            <button type="button" style={DANGER_BUTTON} onClick={() => setMode('reject')}>Reject</button>
          </div>
          {mode === 'request' && <Builder detail={detail} onRefresh={onRefresh} />}
          {mode === 'sign' && <SignForm typedName={typedName} signatureText={signatureText} setTypedName={setTypedName} setSignatureText={setSignatureText} onSubmit={() => submit(`/agreement-exchange/${detail.exchange.id}/sign/`, { typed_name: typedName, signature_text: signatureText })} isSubmitting={isSubmitting} />}
          {mode === 'reject' && <RejectForm reason={reason} setReason={setReason} onSubmit={() => submit(`/agreement-exchange/${detail.exchange.id}/reject/`, { reason })} isSubmitting={isSubmitting} />}
        </>
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          <p style={{ margin: 0, color: '#0F1F3D', fontSize: 14, fontWeight: 800 }}>{statusCopy.title}</p>
          <p style={{ margin: 0, color: '#64748B', fontSize: 13 }}>{statusCopy.body}</p>
        </div>
      )}
      {error && <p style={{ margin: '10px 0 0', color: '#B91C1C', fontSize: 12 }}>{error}</p>}
    </div>
  )
}

function Builder({ detail, onRefresh }: { detail: AgreementExchangeDetail; onRefresh: () => void }) {
  return (
    <div style={{ marginTop: 14, borderTop: '1px solid #E5E7EB', paddingTop: 14 }}>
      <AgreementExchangeRequestBuilder exchangeId={detail.exchange.id} sections={detail.current_contract.sections} onSaved={() => onRefresh()} />
    </div>
  )
}

function SignForm({ typedName, signatureText, setTypedName, setSignatureText, onSubmit, isSubmitting }: { typedName: string; signatureText: string; setTypedName: (value: string) => void; setSignatureText: (value: string) => void; onSubmit: () => void; isSubmitting: boolean }) {
  return (
    <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
      <input value={typedName} onChange={(event) => setTypedName(event.target.value)} placeholder="Typed name" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 10px', fontSize: 13 }} />
      <input value={signatureText} onChange={(event) => setSignatureText(event.target.value)} placeholder="Signature text" style={{ height: 36, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 10px', fontSize: 13 }} />
      <button type="button" style={{ ...PRIMARY_BUTTON, justifySelf: 'start' }} onClick={onSubmit} disabled={isSubmitting || (!typedName.trim() && !signatureText.trim())}>{isSubmitting ? 'Signing...' : 'Confirm Signature'}</button>
    </div>
  )
}

function RejectForm({ reason, setReason, onSubmit, isSubmitting }: { reason: string; setReason: (value: string) => void; onSubmit: () => void; isSubmitting: boolean }) {
  return (
    <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
      <textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason for rejecting" style={{ ...TEXTAREA, minHeight: 76 }} />
      <button type="button" style={{ ...DANGER_BUTTON, justifySelf: 'start' }} onClick={onSubmit} disabled={isSubmitting}>{isSubmitting ? 'Rejecting...' : 'Reject Exchange'}</button>
    </div>
  )
}

export default function AgreementExchange() {
  const { exchangeId } = useParams()
  const stackPanels = useMediaQuery('(max-width: 1100px)')
  const smallScreen = useMediaQuery('(max-width: 640px)')
  const [detail, setDetail] = useState<AgreementExchangeDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const viewedRef = useRef(false)

  async function loadDetail() {
    if (!exchangeId) return
    const { data } = await api.get<AgreementExchangeDetail>(`/agreement-exchange/${exchangeId}/`)
    setDetail(data)
  }

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError('')
    if (!exchangeId) {
      setError('Agreement Exchange id is missing.')
      setIsLoading(false)
      return () => { cancelled = true }
    }
    api.get<AgreementExchangeDetail>(`/agreement-exchange/${exchangeId}/`)
      .then(({ data }) => {
        if (!cancelled) setDetail(data)
      })
      .catch(() => {
        if (!cancelled) setError('Agreement Exchange could not be loaded.')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => { cancelled = true }
  }, [exchangeId])

  useEffect(() => {
    if (!detail || viewedRef.current) return
    if (detail.viewer_role !== 'counterparty' || detail.exchange.current_actor !== 'counterparty') return
    viewedRef.current = true
    api.post<AgreementExchangeDetail>(`/agreement-exchange/${detail.exchange.id}/viewed/`, {})
      .then(({ data }) => setDetail(data))
      .catch(() => {})
  }, [detail])

  if (isLoading) return <div style={PAGE}><div style={HEADER}>Loading Agreement Exchange...</div></div>
  if (error || !detail) return <div style={PAGE}><div style={HEADER}><p style={{ color: '#B91C1C', margin: 0 }}>{error || 'Agreement Exchange unavailable.'}</p></div></div>

  const request = latestRequest(detail.requests)

  return (
    <div style={PAGE}>
      <div style={HEADER}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'start' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, color: '#0F1F3D' }}>Agreement Exchange</h1>
            <p style={{ margin: '4px 0 0', color: '#475569', fontSize: 13 }}>
              {detail.current_contract.title} <span style={{ color: '#CBD5E1' }}>•</span> Exchange ID {detail.exchange.id}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Link to="/dashboard" style={{ ...BUTTON, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none', width: smallScreen ? '100%' : undefined }}>Back to Dashboard</Link>
            <Link to="/workflows" style={{ ...BUTTON, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none', width: smallScreen ? '100%' : undefined }}>Back to Workflows</Link>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 10, alignItems: 'center' }}>
          <Info label="Counterparty" value={detail.exchange.counterparty_email} />
          <Info label="Pending action" value={prettify(detail.exchange.current_actor)} />
          <Info label="Screen state" value={prettify(detail.screen_state)} />
          <Info label="Last activity" value={formatDate(detail.exchange.updated_at)} />
          <StatusBadge>{prettify(detail.exchange.status)}</StatusBadge>
          <StatusBadge>{detail.current_contract.version_label}</StatusBadge>
        </div>
        <StateBanner detail={detail} />
        <div style={{ marginTop: 10 }}><Timeline events={detail.events} /></div>
      </div>

      <div style={FRAME}>
        <div style={{ display: 'grid', gridTemplateColumns: stackPanels ? '1fr' : 'minmax(0, 1.45fr) minmax(320px, 0.75fr)', gap: 16, alignItems: 'start', minWidth: 0 }}>
          <div style={{ minWidth: 0 }}>
            <p style={LABEL}>Initiator Panel</p>
            <ContractViewer contract={detail.current_contract} />
          </div>
          <div style={{ minWidth: 0 }}>
            <p style={LABEL}>Counterparty Panel</p>
            <DecisionPanel detail={detail} onRefresh={loadDetail} smallScreen={smallScreen} />
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: stackPanels ? '1fr' : 'minmax(0, 1fr) minmax(280px, 0.55fr)', gap: 12, minWidth: 0 }}>
        <div style={CARD}>
          <p style={LABEL}>Events / Review Activity</p>
          <div style={{ display: 'grid', gap: 8 }}>
            {detail.events.map((event) => (
              <div key={event.id} style={{ borderBottom: '1px solid #E5E7EB', paddingBottom: 8 }}>
                <p style={{ margin: 0, fontSize: 13, color: '#0F1F3D', fontWeight: 800 }}>{prettify(event.event_type)}</p>
                <p style={{ margin: '3px 0', fontSize: 12, color: '#475569' }}>{event.message}</p>
                <p style={{ margin: 0, fontSize: 11, color: '#94A3B8' }}>{prettify(event.actor_role)} • {formatDate(event.created_at)}</p>
              </div>
            ))}
          </div>
        </div>
        <div style={CARD}>
          <p style={LABEL}>Latest Request</p>
          <RequestSummary request={request} />
        </div>
      </div>
    </div>
  )
}
