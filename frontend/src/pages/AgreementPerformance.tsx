import { useEffect, useMemo, useState, type ReactNode } from 'react'
import api from '@/api/client'

type BoardTab = 'payments' | 'work' | 'due_dates' | 'activity' | 'changes'

type PerformanceAgreement = {
  id: string
  contract_id?: string
  lifecycle_id?: string
  title?: string
  contract: { id: string; title?: string; counterparty_name?: string | null; counterparty_email?: string | null }
  counterparty?: { name?: string | null; email?: string | null }
  status: string
  performance_ready?: boolean
  payment_count?: number
  work_count?: number
  work_item_count?: number
  due_date_count?: number
  activity_count?: number
  lifecycle_agreement?: { performance_ready_at?: string | null }
}

type PerformanceListResponse = { results: PerformanceAgreement[] }

type TimelineItem = {
  id: string
  item_type?: string
  title?: string
  description?: string | null
  responsible_party?: string | null
  beneficiary_party?: string | null
  due_date?: string | null
  amount?: string | null
  currency?: string | null
  status?: string
  source?: string
  source_type?: string
  source_label?: string | null
  source_clause?: string | null
  payment_method?: string | null
  lifecycle_state?: string
  metadata?: Record<string, unknown>
}

type TimelineEvent = {
  id: string
  event_type?: string
  title?: string
  description?: string
  occurred_at?: string
}

type LifecycleBoardResponse = {
  contract?: { id: string; title?: string; counterparty_name?: string | null; counterparty_email?: string | null; status?: string }
  signed_version?: { label?: string; content_snapshot?: string }
  lifecycle_agreement?: { id: string; status?: string; performance_ready?: boolean }
  views?: Partial<Record<'payments' | 'work_services' | 'due_dates' | 'activity' | 'changes_add_ons', TimelineItem[] | TimelineEvent[]>>
  events?: TimelineEvent[]
}

const BOARD_TABS: Array<{ key: BoardTab; label: string }> = [
  { key: 'payments', label: 'Payments' },
  { key: 'work', label: 'Work / Services' },
  { key: 'due_dates', label: 'Due Dates' },
  { key: 'activity', label: 'Activity' },
  { key: 'changes', label: 'Changes / Add-ons' },
]

function formatDate(value?: string | null) {
  if (!value) return 'Ready for tracking'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Ready for tracking'
  return date.toLocaleDateString()
}

function dueDateLabel(value?: string | null) {
  if (!value) return 'No date set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No date set'
  return date.toLocaleDateString()
}

function formatMoney(amount?: string | null, currency = 'USD') {
  if (!amount) return 'No amount set'
  const parsed = Number(amount)
  if (Number.isNaN(parsed)) return `${amount} ${currency}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(parsed)
}

function humanize(value?: string) {
  if (!value) return 'Planned'
  return value.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function htmlToReadableText(value: string) {
  return value
    .replace(/<\/?(p|div|h[1-6]|li|br|section|article|tr)[^>]*>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function signedAgreementText(contentSnapshot?: string) {
  if (!contentSnapshot) return 'No signed agreement snapshot returned.'
  try {
    const parsed = JSON.parse(contentSnapshot) as Record<string, unknown>
    const candidate = parsed.final_editor_html || parsed.editor_html || parsed.content_html || parsed.html || parsed.body || parsed.text
    if (typeof candidate === 'string' && candidate.trim()) return htmlToReadableText(candidate)
    const sections = parsed.sections
    if (Array.isArray(sections)) {
      const text = sections
        .map((section) => {
          if (!section || typeof section !== 'object') return ''
          const record = section as Record<string, unknown>
          const title = typeof record.title === 'string' ? record.title : ''
          const body = [record.body, record.text, record.content, record.html, record.content_html, record.editor_html]
            .find((value) => typeof value === 'string' && value.trim())
          return [title, typeof body === 'string' ? htmlToReadableText(body) : ''].filter(Boolean).join('\n')
        })
        .filter(Boolean)
        .join('\n\n')
      if (text.trim()) return text
    }
  } catch {
    return htmlToReadableText(contentSnapshot)
  }
  return htmlToReadableText(contentSnapshot)
}

function getErrorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { error?: string; detail?: string } } })?.response
  return response?.data?.error || response?.data?.detail || fallback
}

function statusStyle(status?: string) {
  const normalized = (status || '').toLowerCase()
  if (['completed', 'confirmed', 'resolved'].includes(normalized)) return { background: '#ECFDF5', color: '#047857' }
  if (['overdue', 'defaulted', 'failed', 'rejected'].includes(normalized)) return { background: '#FEF2F2', color: '#B91C1C' }
  if (['pending', 'due', 'grace'].includes(normalized)) return { background: '#FEF3C7', color: '#B45309' }
  return { background: '#F8FAFC', color: '#475569' }
}

function itemAction(item: TimelineItem): { action: string; label: string } | null {
  const source = item.source || item.source_type
  if (source === 'contract_payment_obligation' || source === 'payment_record') return null
  if ((item.status || '').toLowerCase() === 'completed') return null
  if (item.item_type === 'payment') return { action: 'mark_paid', label: 'Mark Paid' }
  if (['service', 'service_work'].includes(item.item_type || '')) return { action: 'mark_work_performed', label: 'Mark Performed' }
  if (['responsibility', 'obligation', 'due_date', 'deadline'].includes(item.item_type || '')) return { action: 'mark_completed', label: 'Mark Completed' }
  return null
}

function isDisplayableItem(item: TimelineItem) {
  const text = `${item.title || ''} ${item.description || ''}`.toLowerCase().replace(/\s+/g, ' ')
  if (text.length < 500) return true
  const markers = ['agreement is made between', 'governing law', 'signatures', 'borrower', 'lender', 'provider', 'client']
  return !(text.includes('agreement') && markers.filter((marker) => text.includes(marker)).length >= 2)
}

function sourceLabel(item: TimelineItem) {
  if (item.source_label) return item.source_label
  if (item.source === 'contract_payment_obligation') return 'Signed agreement payment term'
  if (item.source === 'contract_service_obligation') return 'Signed agreement work term'
  if (item.source === 'payment_record') return 'Payment record'
  if (item.source_type === 'original_contract') return 'Signed agreement source'
  return humanize(item.source_type || item.source || 'Performance item')
}

export default function AgreementPerformance() {
  const [agreements, setAgreements] = useState<PerformanceAgreement[]>([])
  const [selectedAgreement, setSelectedAgreement] = useState<PerformanceAgreement | null>(null)
  const [boardData, setBoardData] = useState<LifecycleBoardResponse | null>(null)
  const [activeTab, setActiveTab] = useState<BoardTab>('payments')
  const [selectedItem, setSelectedItem] = useState<TimelineItem | null>(null)
  const [showSource, setShowSource] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [boardLoading, setBoardLoading] = useState(false)
  const [actionBusy, setActionBusy] = useState('')
  const [error, setError] = useState('')
  const [boardError, setBoardError] = useState('')
  const [feedback, setFeedback] = useState('')

  async function loadPerformanceAgreements() {
    setIsLoading(true)
    setError('')
    try {
      const response = await api.get<PerformanceListResponse>('/lifecycle/performance/')
      setAgreements(response.data.results || [])
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to load Agreement Performance records.'))
    } finally {
      setIsLoading(false)
    }
  }

  async function openBoard(agreement: PerformanceAgreement) {
    const contractId = agreement.contract_id || agreement.contract.id
    setSelectedAgreement(agreement)
    setBoardLoading(true)
    setBoardError('')
    setFeedback('')
    setActiveTab('payments')
    setSelectedItem(null)
    try {
      const response = await api.get<LifecycleBoardResponse>('/lifecycle/', { params: { contract: contractId } })
      setBoardData(response.data)
    } catch (err) {
      setBoardError(getErrorMessage(err, 'Unable to open Agreement Performance board.'))
      setBoardData(null)
    } finally {
      setBoardLoading(false)
    }
  }

  async function refreshBoard() {
    if (!selectedAgreement) return
    await openBoard(selectedAgreement)
    await loadPerformanceAgreements()
  }

  async function runAction(item: TimelineItem, action: string) {
    setActionBusy(`${item.id}:${action}`)
    setFeedback('')
    try {
      await api.post(`/lifecycle/items/${item.id}/actions/`, { action })
      setFeedback('Performance action recorded.')
      setSelectedItem(null)
      await refreshBoard()
    } catch (err) {
      setBoardError(getErrorMessage(err, 'Unable to record performance action.'))
    } finally {
      setActionBusy('')
    }
  }

  useEffect(() => {
    void loadPerformanceAgreements()
  }, [])

  const payments = useMemo(() => ((boardData?.views?.payments || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const workItems = useMemo(() => ((boardData?.views?.work_services || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const dueDates = useMemo(() => ((boardData?.views?.due_dates || []) as TimelineItem[]).filter(isDisplayableItem), [boardData])
  const events = useMemo(() => ((boardData?.views?.activity || boardData?.events || []) as TimelineEvent[]), [boardData])

  const activeItems = activeTab === 'payments' ? payments : activeTab === 'work' ? workItems : activeTab === 'due_dates' ? dueDates : []
  const sourceText = signedAgreementText(boardData?.signed_version?.content_snapshot)

  return (
    <div style={{ padding: '32px 0' }}>
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 22, marginBottom: 18 }}>
        <p style={{ margin: '0 0 8px', fontSize: 11, fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#047857' }}>
          Performance
        </p>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#0F1F3D', margin: 0, letterSpacing: 0 }}>
          Agreement Performance
        </h1>
        <p style={{ fontSize: 14, color: '#64748B', margin: '9px 0 0', maxWidth: 780, lineHeight: 1.55 }}>
          Track performed obligations, payments, delivery, confirmations, and records.
        </p>
      </section>

      {error && <section style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 16, marginBottom: 18 }}><p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>{error}</p></section>}

      {isLoading ? (
        <section style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 20 }}>
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>Loading Agreement Performance records...</p>
        </section>
      ) : agreements.length === 0 ? (
        <section style={{ background: '#F8FAFC', border: '1px solid #D1FAE5', borderRadius: 8, padding: 20, marginBottom: 18 }}>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>No agreements are ready for performance yet.</h2>
          <p style={{ fontSize: 13, color: '#475569', margin: '8px 0 0', maxWidth: 760, lineHeight: 1.6 }}>
            Performance starts when a party checks off the first performed obligation. Before that, a signed agreement appears here only after someone marks the Signed Agreement Timeline ready for Agreement Performance.
          </p>
        </section>
      ) : (
        <div style={{ display: 'grid', gap: 14, marginBottom: 18 }}>
          {agreements.map((agreement) => {
            const counterparty = agreement.counterparty?.name || agreement.counterparty?.email || agreement.contract.counterparty_name || agreement.contract.counterparty_email || 'Counterparty not set'
            const selected = selectedAgreement?.id === agreement.id
            return (
              <section key={agreement.id} style={{ background: selected ? '#F0FDF4' : 'white', border: `1px solid ${selected ? '#86EFAC' : '#E5E7EB'}`, borderRadius: 8, padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
                  <div style={{ minWidth: 0 }}>
                    <p style={{ fontSize: 11, fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>Ready for tracking</p>
                    <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{agreement.title || agreement.contract.title || 'Untitled contract'}</h2>
                    <p style={{ fontSize: 13, color: '#64748B', margin: '7px 0 0' }}>{counterparty}</p>
                  </div>
                  <button type="button" onClick={() => void openBoard(agreement)} style={{ height: 34, border: '1px solid #047857', borderRadius: 8, background: '#047857', color: '#FFFFFF', padding: '0 12px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
                    {selected ? 'Refresh Performance' : 'Open Performance'}
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginTop: 16 }}>
                  <SummaryCell label="Status" value={agreement.status} />
                  <SummaryCell label="Payments" value={`${agreement.payment_count || 0} payment item(s)`} />
                  <SummaryCell label="Work" value={`${agreement.work_count ?? agreement.work_item_count ?? 0} work item(s)`} />
                  <SummaryCell label="Due Dates" value={`${agreement.due_date_count || 0} due date(s)`} />
                  <SummaryCell label="Activity" value={`${agreement.activity_count || 0} event(s)`} />
                  <SummaryCell label="Ready Since" value={formatDate(agreement.lifecycle_agreement?.performance_ready_at)} />
                </div>
              </section>
            )
          })}
        </div>
      )}

      <section style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 18, minHeight: 260 }}>
        {!selectedAgreement ? (
          <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}>
            <p style={{ fontSize: 14, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Select a signed agreement to view performance records.</p>
            <p style={{ fontSize: 13, color: '#64748B', margin: '7px 0 0' }}>Open Performance loads the board for payments, work, due dates, activity, and future changes.</p>
          </div>
        ) : boardLoading ? (
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>Opening Agreement Performance board...</p>
        ) : boardError ? (
          <p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>{boardError}</p>
        ) : boardData ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 5px' }}>Performance board</p>
                <h2 style={{ fontSize: 20, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{boardData.contract?.title || selectedAgreement.contract.title || 'Untitled contract'}</h2>
                <p style={{ fontSize: 12, color: '#64748B', margin: '6px 0 0' }}>Status: Waiting for first performed obligation</p>
              </div>
              <button type="button" onClick={() => setShowSource(true)} style={secondaryButtonStyle}>View Signed Source</button>
            </div>

            {feedback && <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: 8, padding: 12, marginBottom: 12 }}><p style={{ fontSize: 13, color: '#047857', margin: 0 }}>{feedback}</p></div>}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
              {BOARD_TABS.map((tab) => (
                <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} style={{ border: '1px solid #CBD5E1', borderRadius: 8, background: activeTab === tab.key ? '#047857' : '#FFFFFF', color: activeTab === tab.key ? '#FFFFFF' : '#334155', padding: '8px 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'activity' ? (
              <ActivityPanel events={events} />
            ) : activeTab === 'changes' ? (
              <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}>
                <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>Changes and add-ons will be managed here.</p>
              </div>
            ) : activeItems.length === 0 ? (
              <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}>
                <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No records found for this panel.</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {activeItems.map((item) => <PerformanceCard key={`${item.source || item.source_type}-${item.id}`} item={item} onOpen={() => setSelectedItem(item)} onViewSource={() => setShowSource(true)} />)}
              </div>
            )}
          </div>
        ) : null}
      </section>

      {selectedItem && (
        <ItemDetail
          item={selectedItem}
          busy={actionBusy}
          onClose={() => setSelectedItem(null)}
          onViewSource={() => setShowSource(true)}
          onAction={(action) => void runAction(selectedItem, action)}
        />
      )}

      {showSource && (
        <Modal title="Signed agreement source" onClose={() => setShowSource(false)}>
          <pre style={{ maxHeight: '70vh', overflow: 'auto', whiteSpace: 'pre-wrap', background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, color: '#334155', fontFamily: 'inherit' }}>{sourceText}</pre>
        </Modal>
      )}
    </div>
  )
}

function SummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
      <p style={{ fontSize: 11, color: '#94A3B8', margin: 0, fontWeight: 800, textTransform: 'uppercase' }}>{label}</p>
      <p style={{ fontSize: 13, color: '#0F1F3D', margin: '5px 0 0', fontWeight: 800 }}>{value}</p>
    </div>
  )
}

function PerformanceCard({ item, onOpen, onViewSource }: { item: TimelineItem; onOpen: () => void; onViewSource: () => void }) {
  const action = itemAction(item)
  return (
    <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{item.title || humanize(item.item_type)}</p>
          <p style={{ fontSize: 11, color: '#94A3B8', margin: '5px 0 0' }}>{sourceLabel(item)}</p>
        </div>
        <span style={{ alignSelf: 'flex-start', borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 800, ...statusStyle(item.status || item.lifecycle_state) }}>{humanize(item.status || item.lifecycle_state)}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 12 }}>
        <SmallFact label="Amount" value={formatMoney(item.amount, item.currency || 'USD')} />
        <SmallFact label="Due / Delivery" value={dueDateLabel(item.due_date)} />
        <SmallFact label="Responsible" value={item.responsible_party || 'Not set'} />
      </div>
      {item.description && <p style={{ fontSize: 12, color: '#475569', lineHeight: 1.5, margin: '10px 0 0' }}>{item.description}</p>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
        <button type="button" onClick={onOpen} style={primaryButtonStyle}>Open Detail</button>
        <button type="button" onClick={onViewSource} style={secondaryButtonStyle}>View Source</button>
        {!action && <span style={{ fontSize: 11, color: '#64748B', alignSelf: 'center' }}>Action unavailable for this generated record.</span>}
      </div>
    </div>
  )
}

function SmallFact({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 10 }}>
      <p style={{ fontSize: 10, color: '#94A3B8', fontWeight: 800, textTransform: 'uppercase', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 12, color: '#0F1F3D', fontWeight: 800, margin: '4px 0 0' }}>{value}</p>
    </div>
  )
}

function ActivityPanel({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#FFFFFF' }}><p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>No performance activity recorded yet.</p></div>
  }
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {events.map((event) => (
        <div key={event.id} style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
          <p style={{ fontSize: 13, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{event.title || humanize(event.event_type)}</p>
          <p style={{ fontSize: 12, color: '#64748B', margin: '5px 0 0' }}>{event.description || humanize(event.event_type)}</p>
          <p style={{ fontSize: 11, color: '#94A3B8', margin: '5px 0 0' }}>{formatDate(event.occurred_at)}</p>
        </div>
      ))}
    </div>
  )
}

function ItemDetail({ item, busy, onClose, onViewSource, onAction }: { item: TimelineItem; busy: string; onClose: () => void; onViewSource: () => void; onAction: (action: string) => void }) {
  const action = itemAction(item)
  const actionBusy = action ? busy === `${item.id}:${action.action}` : false
  return (
    <Modal title={item.title || humanize(item.item_type)} onClose={onClose}>
      <div style={{ display: 'grid', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
          <SmallFact label="Status" value={humanize(item.status || item.lifecycle_state)} />
          <SmallFact label="Amount" value={formatMoney(item.amount, item.currency || 'USD')} />
          <SmallFact label="Due / Delivery" value={dueDateLabel(item.due_date)} />
          <SmallFact label="Responsible" value={item.responsible_party || 'Not set'} />
        </div>
        <section style={{ background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
          <p style={{ fontSize: 11, color: '#94A3B8', margin: 0, fontWeight: 800, textTransform: 'uppercase' }}>Performance detail</p>
          <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.55, margin: '6px 0 0' }}>{item.description || 'No additional detail recorded for this performance item.'}</p>
        </section>
        <section style={{ background: '#F8FAFC', border: '1px dashed #CBD5E1', borderRadius: 8, padding: 12 }}>
          <p style={{ fontSize: 12, color: '#64748B', margin: 0 }}>Notes, reminders, receipts, and confirmations will be managed here later.</p>
        </section>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={onViewSource} style={secondaryButtonStyle}>View Source</button>
          {action ? (
            <button type="button" onClick={() => onAction(action.action)} disabled={actionBusy} style={{ ...primaryButtonStyle, opacity: actionBusy ? 0.7 : 1, cursor: actionBusy ? 'default' : 'pointer' }}>
              {actionBusy ? 'Recording...' : action.label}
            </button>
          ) : (
            <span style={{ fontSize: 12, color: '#64748B', alignSelf: 'center' }}>No direct performance action is available for this generated record yet.</span>
          )}
        </div>
      </div>
    </Modal>
  )
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', zIndex: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} onClick={onClose}>
      <div style={{ width: '100%', maxWidth: 820, maxHeight: '90vh', overflow: 'auto', background: '#FFFFFF', borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', boxShadow: '0 20px 60px rgba(15,23,42,0.3)', padding: 20 }} onClick={(event) => event.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: '#0F1F3D' }}>{title}</h3>
          <button type="button" onClick={onClose} style={secondaryButtonStyle}>Close</button>
        </div>
        {children}
      </div>
    </div>
  )
}

const primaryButtonStyle = {
  border: '1px solid #047857',
  borderRadius: 8,
  background: '#047857',
  color: '#FFFFFF',
  padding: '8px 12px',
  fontSize: 12,
  fontWeight: 800,
  cursor: 'pointer',
}

const secondaryButtonStyle = {
  border: '1px solid #CBD5E1',
  borderRadius: 8,
  background: '#FFFFFF',
  color: '#334155',
  padding: '8px 12px',
  fontSize: 12,
  fontWeight: 800,
  cursor: 'pointer',
}
