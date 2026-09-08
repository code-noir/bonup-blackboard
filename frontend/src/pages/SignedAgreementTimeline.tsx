import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { useNotification } from '@/context/NotificationContext'
import {
  formatDate,
  formatMoney,
  fromDateInputValue,
  getErrorMessage,
  humanize,
  ModalShell,
  StatCard,
  statusStyle,
  timelineDateLabel,
  toDateInputValue,
} from './LifecycleShared'

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
      const sectionText = sections
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
      if (sectionText.trim()) return sectionText
    }
  } catch {
    return htmlToReadableText(contentSnapshot)
  }
  return htmlToReadableText(contentSnapshot)
}

function looksLikeWholeContractText(value?: string | null) {
  if (!value) return false
  const normalized = value.toLowerCase().replace(/\s+/g, ' ').trim()
  if (normalized.length < 500) return false
  const markers = ['agreement is made between', 'personal repayment agreement', 'governing law', 'signatures', 'borrower', 'lender', 'provider', 'client']
  return normalized.includes('agreement') && markers.filter((marker) => normalized.includes(marker)).length >= 2
}

function isSignedContractDocument(item: TimelineItem) {
  return item.item_type === 'document' && (item.source_type || item.source) === 'original_contract'
}

function isWholeContractTimelineItem(item: TimelineItem) {
  return looksLikeWholeContractText(item.title) || looksLikeWholeContractText(item.description)
}

function timelineRecordItems(items: TimelineItem[]) {
  return items.filter((item) => !isSignedContractDocument(item) && !isWholeContractTimelineItem(item))
}

function isOpenTimelineStatus(item: TimelineItem) {
  return !['completed', 'confirmed', 'cancelled', 'rejected'].includes(item.status || '')
}

function itemTypeLabel(item: TimelineItem) {
  if (item.item_type === 'service_work') return 'Work / Service'
  if (item.item_type === 'due_date') return 'Due Date'
  if (item.item_type === 'change_order') return 'Change Order'
  if (item.item_type === 'add_on') return 'Add-on'
  return humanize(item.item_type || item.source || 'Timeline item')
}

function itemSourceLabel(item: TimelineItem) {
  if (item.source_label) return item.source_label
  if (item.source === 'contract_payment_obligation') return 'Signed agreement payment term'
  if (item.source === 'contract_service_obligation') return 'Signed agreement work term'
  if (item.source === 'payment_record') return 'Payment record'
  if (item.source === 'manual') return 'Manual timeline item'
  return item.source ? humanize(item.source) : ''
}

function itemSourceText(item: TimelineItem) {
  return itemSourceLabel(item) || humanize(item.source_type || item.source || 'Timeline item')
}

function sourceMetadataList(item: TimelineItem) {
  const metadata = item.metadata || {}
  const entries: Array<{ label: string; value: string }> = []
  if (item.source_version_id) entries.push({ label: 'Source version', value: item.source_version_id })
  if (item.source_exchange_id) entries.push({ label: 'Source exchange', value: item.source_exchange_id })
  if (item.source_clause) entries.push({ label: 'Source clause', value: item.source_clause })
  if (item.payment_method) entries.push({ label: 'Payment method', value: item.payment_method })
  if (item.is_contract_derived) entries.push({ label: 'Origin', value: 'Signed agreement' })
  if (item.locked_fields && item.locked_fields.length) entries.push({ label: 'Locked fields', value: item.locked_fields.join(', ') })
  if (metadata.original_values && typeof metadata.original_values === 'object') {
    const original = metadata.original_values as Record<string, unknown>
    const originalText = Object.entries(original)
      .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
      .join(' · ')
    if (originalText) entries.push({ label: 'Original values', value: originalText })
  }
  if (metadata.corrections && Array.isArray(metadata.corrections) && metadata.corrections.length) {
    entries.push({ label: 'Corrections', value: `${metadata.corrections.length} recorded` })
  }
  return entries
}

function toDateInputValue(value?: string | null) {
  return dateOnlyInputValue(value)
}

function fromDateInputValue(value: string) {
  return dateOnlyPayloadValue(value)
}

function tabItems(items: TimelineItem[], tab: TimelineViewKey) {
  const records = timelineRecordItems(items)
  switch (tab) {
    case 'payments':
      return records.filter((item) => item.item_type === 'payment')
    case 'due_dates':
      return records
        .filter((item) => item.due_date && ['payment', 'service', 'service_work', 'responsibility', 'obligation', 'due_date', 'deadline'].includes(item.item_type || ''))
        .sort((left, right) => String(left.due_date || '').localeCompare(String(right.due_date || '')))
    case 'work_services':
      return records.filter((item) => ['service', 'service_work'].includes(item.item_type || ''))
    default:
      return records
  }
}

function timelineStatusLabel(status?: string) {
  switch ((status || '').toLowerCase()) {
    case 'setup': return 'Ready for setup'
    case 'active': return 'Active'
    case 'completed': return 'Completed'
    case 'archived': return 'Archived'
    default: return 'Ready for setup'
  }
}

function timelineSubtitleStatus(status?: string) {
  return (status || '').toLowerCase() === 'active' ? 'Timeline Active' : 'Timeline Setup'
}

type LifecycleItemGroup = 'obligations' | 'payments' | 'deadlines' | 'services' | 'notices' | 'documents' | 'risks' | 'changes' | 'notes'
type TimelineViewKey = 'overview' | 'payments' | 'due_dates' | 'work_services' | 'source_agreement'

type TimelineItem = {
  id: string
  [key: string]: unknown
  item_type?: string
  title?: string
  status?: string
  source?: string
  source_type?: string
  description?: string | null
  responsible_party?: string | null
  beneficiary_party?: string | null
  due_date?: string | null
  amount?: string | null
  recurrence?: string | null
  source_label?: string | null
  source_version_id?: string | null
  source_exchange_id?: string | null
  source_clause?: string | null
  payment_method?: string | null
  notes?: string | null
  reminder_at?: string | null
  visibility?: string | null
  metadata?: Record<string, unknown>
  baseline_values?: Partial<Record<'title' | 'description' | 'due_date' | 'amount' | 'responsible_party' | 'payment_method' | 'status', string | null>>
  has_personal_overrides?: boolean
  locked_fields?: string[]
  is_contract_derived?: boolean
}

type TimelineItemDraft = {
  title: string
  description: string
  responsible_party: string
  beneficiary_party: string
  due_date: string
  amount: string
  status: string
  recurrence: string
  payment_method: string
  source_clause: string
  visibility: string
  notes: string
}

const EMPTY_TIMELINE_ITEM_DRAFT: TimelineItemDraft = {
  title: '',
  description: '',
  responsible_party: '',
  beneficiary_party: '',
  due_date: '',
  amount: '',
  status: '',
  recurrence: '',
  payment_method: '',
  source_clause: '',
  visibility: '',
  notes: '',
}

type TimelineEvent = { id: string; event_type: string; title: string; description?: string; occurred_at?: string }

type LifecycleAgreementSummary = {
  id: string
  status?: string
  started_at?: string
  source_exchange_id?: string | null
  performance_ready?: boolean
  performance_ready_at?: string | null
  performance_ready_by?: string | null
}

type ContractScopedLifecycleResponse = {
  contract?: { id: string; title?: string; status?: string; state?: string; counterparty_email?: string; counterparty_name?: string }
  signed_version?: { id: string; label?: string; status?: string; content_snapshot?: string }
  lifecycle_agreement?: LifecycleAgreementSummary
  timeline?: LifecycleAgreementSummary
  parties?: { initiator?: { email?: string; name?: string } | null; counterparty?: { email?: string; name?: string } | null }
  items?: Partial<Record<LifecycleItemGroup, TimelineItem[]>>
  views?: Partial<Record<TimelineViewKey | 'upcoming' | 'to_dos' | 'changes_add_ons' | 'activity' | 'documents', TimelineItem[] | TimelineEvent[]>>
  counts?: Record<string, number>
  events?: TimelineEvent[]
}

const EMPTY_LIFECYCLE_GROUPS: Record<LifecycleItemGroup, TimelineItem[]> = {
  obligations: [],
  payments: [],
  deadlines: [],
  services: [],
  notices: [],
  documents: [],
  risks: [],
  changes: [],
  notes: [],
}

const LIFECYCLE_TABS: Array<{ key: TimelineViewKey; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'payments', label: 'Payments' },
  { key: 'due_dates', label: 'Due Dates' },
  { key: 'work_services', label: 'Work / Services' },
  { key: 'source_agreement', label: 'Source / Signed Agreement' },
]

const EMPTY_COPY: Record<TimelineViewKey, string> = {
  overview: '',
  payments: 'No payment obligations were extracted from this signed agreement.',
  due_dates: 'No dated or scheduled obligations were extracted from this signed agreement.',
  work_services: 'No work or service obligations were extracted from this signed agreement.',
  source_agreement: 'No signed agreement source is available for this Timeline.',
}

const TIMELINE_ITEM_TYPES = [
  { value: 'responsibility', label: 'Responsibility' },
  { value: 'payment', label: 'Payment' },
  { value: 'due_date', label: 'Due Date' },
  { value: 'service_work', label: 'Work / Service' },
  { value: 'notice', label: 'Notice' },
  { value: 'document', label: 'Document' },
  { value: 'risk', label: 'Risk' },
  { value: 'change_order', label: 'Change Order' },
  { value: 'add_on', label: 'Add-on' },
  { value: 'note', label: 'Note' },
]

const BUTTON = {
  border: '1px solid #CBD5E1',
  borderRadius: 8,
  background: '#FFFFFF',
  color: '#334155',
  padding: '7px 10px',
  fontSize: 12,
  fontWeight: 700,
  cursor: 'pointer',
}


export default function SignedAgreementTimeline({ contractId }: { contractId: string }) {
  const navigate = useNavigate()
  const notify = useNotification()
  const [data, setData] = useState<ContractScopedLifecycleResponse | null>(null)
  const [activeTab, setActiveTab] = useState<TimelineViewKey>('overview')
  const [isLoading, setIsLoading] = useState(true)
  const [draftType, setDraftType] = useState('responsibility')
  const [draftTitle, setDraftTitle] = useState('')
  const [showSignedAgreement, setShowSignedAgreement] = useState(false)
  const [selectedTimelineItem, setSelectedTimelineItem] = useState<TimelineItem | null>(null)
  const [timelineItemDraft, setTimelineItemDraft] = useState<TimelineItemDraft>(EMPTY_TIMELINE_ITEM_DRAFT)
  const [timelineItemEditMode, setTimelineItemEditMode] = useState(false)
  const [timelineItemSaving, setTimelineItemSaving] = useState(false)
  const [timelineItemError, setTimelineItemError] = useState<string | null>(null)
  const [performancePreparing, setPerformancePreparing] = useState(false)

  const loadLifecycle = async () => {
    setIsLoading(true)
    try {
      const response = await api.get<ContractScopedLifecycleResponse>('/lifecycle/', { params: { contract: contractId } })
      setData(response.data)
    } catch (error) {
      notify.error(getErrorMessage(error, 'Unable to load Agreement Timeline data for this contract.'))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadLifecycle()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contractId])

  const addItem = async () => {
    if (!data || !draftTitle.trim()) return
    try {
      await api.post(`/lifecycle/${data.lifecycle_agreement.id}/items/`, { item_type: draftType, title: draftTitle.trim() })
      setDraftTitle('')
      await loadLifecycle()
    } catch (error) {
      notify.error(getErrorMessage(error, 'Unable to add timeline item.'))
    }
  }

  const openTimelineItemDetail = (item: TimelineItem) => {
    setSelectedTimelineItem(item)
    setTimelineItemEditMode(false)
    setTimelineItemError(null)
    setTimelineItemDraft({
      title: item.title || '',
      description: item.description || '',
      responsible_party: item.responsible_party || '',
      beneficiary_party: item.beneficiary_party || '',
      due_date: toDateInputValue(item.due_date),
      amount: item.amount || '',
      status: item.status || '',
      recurrence: item.recurrence || '',
      payment_method: item.payment_method || '',
      source_clause: item.source_clause || '',
      visibility: item.visibility || '',
      notes: item.notes || '',
    })
  }

  const closeTimelineItemDetail = () => {
    setSelectedTimelineItem(null)
    setTimelineItemDraft(EMPTY_TIMELINE_ITEM_DRAFT)
    setTimelineItemEditMode(false)
    setTimelineItemSaving(false)
    setTimelineItemError(null)
  }

  const saveTimelineItemDetail = async () => {
    if (!selectedTimelineItem) return
    setTimelineItemSaving(true)
    setTimelineItemError(null)
    try {
      await api.patch(`/lifecycle/items/${selectedTimelineItem.id}/`, {
        title: timelineItemDraft.title,
        description: timelineItemDraft.description,
        responsible_party: timelineItemDraft.responsible_party,
        due_date: timelineItemDraft.due_date ? fromDateInputValue(timelineItemDraft.due_date) : '',
        amount: timelineItemDraft.amount,
        status: timelineItemDraft.status,
        payment_method: timelineItemDraft.payment_method,
        notes: timelineItemDraft.notes,
      })
      notify.success('Timeline item updated.')
      await loadLifecycle()
      closeTimelineItemDetail()
    } catch (error) {
      setTimelineItemError(getErrorMessage(error, 'Unable to save Timeline details.'))
    } finally {
      setTimelineItemSaving(false)
    }
  }

  const prepareAgreementPerformance = async () => {
    if (!data?.lifecycle_agreement?.id) return
    setPerformancePreparing(true)
    try {
      const response = await api.post<ContractScopedLifecycleResponse>(`/lifecycle/${data.lifecycle_agreement.id}/ready-for-performance/`, {})
      setData(response.data)
      notify.success('Agreement Performance is ready.')
    } catch (error) {
      notify.error(getErrorMessage(error, 'Unable to prepare Agreement Performance.'))
    } finally {
      setPerformancePreparing(false)
    }
  }

  if (isLoading) return <p style={{ fontSize: 13, color: '#64748B' }}>Loading Agreement Timeline...</p>

  if (!data) {
    return (
      <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 14 }}>
        <p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>Agreement Timeline data is unavailable.</p>
      </div>
    )
  }

  const groupedItems = Object.fromEntries(
    Object.entries({ ...EMPTY_LIFECYCLE_GROUPS, ...(data.items || {}) })
      .map(([key, items]) => [key, timelineRecordItems(items || [])])
  ) as Record<LifecycleItemGroup, TimelineItem[]>
  const agreement = data.lifecycle_agreement || data.timeline
  if (!data.contract || !data.signed_version || !agreement) {
    return (
      <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 14 }}>
        <p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>Agreement Timeline data is incomplete. Please refresh or try another signed agreement.</p>
      </div>
    )
  }

  const allTimelineItems = Object.values(groupedItems).flat()
  const fallbackViews: Record<TimelineViewKey, TimelineItem[]> = {
    overview: [],
    payments: tabItems(groupedItems.payments, 'payments'),
    due_dates: tabItems(allTimelineItems, 'due_dates'),
    work_services: tabItems(groupedItems.services, 'work_services'),
    source_agreement: [],
  }
  const serverViews = data.views || {}
  const views: Record<TimelineViewKey, TimelineItem[]> = {
    ...fallbackViews,
    payments: tabItems((serverViews.payments as TimelineItem[] | undefined) || fallbackViews.payments, 'payments'),
    due_dates: tabItems((serverViews.due_dates as TimelineItem[] | undefined) || fallbackViews.due_dates, 'due_dates'),
    work_services: tabItems((serverViews.work_services as TimelineItem[] | undefined) || fallbackViews.work_services, 'work_services'),
  }
  const activeItems = (views[activeTab] || []) as TimelineItem[]
  const nextDueItem = views.due_dates[0]
  const signedAgreementLabel = `Signed Agreement ${data.signed_version.label || ''}`.trim()
  const signedAgreementReadableText = signedAgreementText(data.signed_version.content_snapshot)

  return (
    <div className="space-y-6">
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
        <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>Signed agreement timeline</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{data.contract.title || 'Untitled contract'}</h1>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '8px 0 0' }}>
              Signed version {data.signed_version.label || 'signed'} · {timelineSubtitleStatus(agreement.status)}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <button type="button" onClick={() => setShowSignedAgreement(true)} style={{ border: '1px solid #243447', borderRadius: 8, background: '#243447', color: '#FFFFFF', padding: '7px 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
              View Signed Agreement
            </button>
            {agreement.performance_ready ? (
              <button type="button" onClick={() => navigate('/agreement-performance')} style={{ border: '1px solid #243447', borderRadius: 8, background: '#243447', color: '#FFFFFF', padding: '7px 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
                Open Agreement Performance
              </button>
            ) : (
              <button type="button" onClick={() => void prepareAgreementPerformance()} disabled={performancePreparing} style={{ border: '1px solid #B45309', borderRadius: 8, background: performancePreparing ? '#FEF3C7' : '#B45309', color: performancePreparing ? '#92400E' : '#FFFFFF', padding: '7px 11px', fontSize: 12, fontWeight: 800, cursor: performancePreparing ? 'default' : 'pointer' }}>
                {performancePreparing ? 'Preparing Agreement Performance...' : 'Ready for Agreement Performance'}
              </button>
            )}
            <span style={{ borderRadius: 999, padding: '5px 10px', fontSize: 11, fontWeight: 800, ...statusStyle('Paid') }}>Signed</span>
          </div>
        </div>
      </section>

      {performancePreparing && (
        <section style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 8, padding: 16 }}>
          <p style={{ fontSize: 13, fontWeight: 800, color: '#92400E', margin: '0 0 8px' }}>Preparing Agreement Performance...</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['Checking obligations...', 'Preparing performance records...', 'Opening Agreement Performance...'].map((step) => (
              <span key={step} style={{ borderRadius: 999, background: '#FFFFFF', border: '1px solid #FDE68A', color: '#92400E', padding: '5px 9px', fontSize: 11, fontWeight: 800 }}>{step}</span>
            ))}
          </div>
        </section>
      )}

      {agreement.performance_ready && !performancePreparing && (
        <section style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 8, padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: 13, fontWeight: 800, color: '#78350F', margin: 0 }}>Agreement Performance is ready.</p>
              <p style={{ fontSize: 12, color: '#475569', margin: '5px 0 0' }}>This signed agreement is now available in Agreement Performance while the Signed Agreement Timeline remains available here.</p>
            </div>
          </div>
        </section>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {LIFECYCLE_TABS.map((tab) => (
          <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} style={{ border: '1px solid #CBD5E1', borderRadius: 8, background: activeTab === tab.key ? '#243447' : '#FFFFFF', color: activeTab === tab.key ? '#FFFFFF' : '#334155', padding: '8px 11px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
          <StatCard label="Timeline Status" value={timelineStatusLabel(agreement.status)} sub={`Available since ${formatDate(agreement.started_at)}`} />
          <StatCard label="Counterparty" value={data.contract.counterparty_name || data.contract.counterparty_email || '—'} sub="Signed agreement party" />
          <StatCard label="Extracted Items" value={data.counts?.total ?? Object.values(groupedItems).reduce((sum, items) => sum + items.length, 0)} sub="Setup records from the signed agreement" />
          <StatCard label="Next Due Date" value={nextDueItem?.title || '—'} sub={nextDueItem?.due_date ? timelineDateLabel(nextDueItem.due_date) : 'No extracted dated item'} />
          <StatCard label="Source" value={signedAgreementLabel} sub="Signed agreement source is attached" />
        </div>
      )}

      {!['overview', 'source_agreement'].includes(activeTab) && (
        <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{LIFECYCLE_TABS.find((tab) => tab.key === activeTab)?.label}</h2>
              <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0' }}>Review extracted obligations before Agreement Performance. Source clauses remain attached to each item.</p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select value={draftType} onChange={(event) => setDraftType(event.target.value)} style={{ height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 8px', fontSize: 12 }}>
                {TIMELINE_ITEM_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
              </select>
              <input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} placeholder="Add item" style={{ height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 10px', fontSize: 12 }} />
              <button type="button" onClick={() => void addItem()} disabled={!draftTitle.trim()} style={{ height: 34, border: 'none', borderRadius: 8, background: draftTitle.trim() ? '#243447' : '#E5E7EB', color: draftTitle.trim() ? '#FFFFFF' : '#64748B', padding: '0 12px', fontSize: 12, fontWeight: 700, cursor: draftTitle.trim() ? 'pointer' : 'default' }}>Add Item</button>
            </div>
          </div>
          {activeItems.length === 0 ? (
            <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#F8FAFC' }}>
              <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>{EMPTY_COPY[activeTab]}</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {activeItems.map((item) => {
                const sourceLabel = itemSourceText(item)
                const statusLabel = humanize(item.status || 'pending')
                const dueLabel = item.due_date ? timelineDateLabel(item.due_date) : 'No due date'
                const amountLabel = item.amount ? formatMoney(item.amount) : 'No amount set'
                return (
                  <div
                    key={`${item.source}-${item.id}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => openTimelineItemDetail(item)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        openTimelineItemDetail(item)
                      }
                    }}
                    style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 14, cursor: 'pointer', background: '#FFFFFF' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                      <div style={{ minWidth: 0 }}>
                        <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{item.title || itemTypeLabel(item)}</p>
                        <p style={{ fontSize: 11, color: '#94A3B8', margin: '5px 0 0' }}>{itemTypeLabel(item)}{sourceLabel ? ` · ${sourceLabel}` : ''}</p>
                      </div>
                      <span style={{ alignSelf: 'flex-start', borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 700, ...statusStyle(item.status === 'completed' || item.status === 'confirmed' ? 'Paid' : 'Due') }}>{statusLabel}</span>
                    </div>
                    <div style={{ display: 'grid', gap: 4, marginTop: 10 }}>
                      <p style={{ fontSize: 13, color: '#334155', margin: 0, fontWeight: 700 }}>{dueLabel}</p>
                      <p style={{ fontSize: 13, color: '#334155', margin: 0, fontWeight: 700 }}>{amountLabel}</p>
                      {item.responsible_party && <p style={{ fontSize: 12, color: '#64748B', margin: 0 }}>Responsible: {item.responsible_party}</p>}
                      {item.payment_method && <p style={{ fontSize: 12, color: '#64748B', margin: 0 }}>Payment method: {item.payment_method}</p>}
                    </div>
                    {item.description && !looksLikeWholeContractText(item.description) && <p style={{ fontSize: 12, color: '#475569', margin: '8px 0 0' }}>{item.description}</p>}
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
                      <button type="button" style={BUTTON} onClick={(event) => { event.stopPropagation(); setShowSignedAgreement(true) }}>View Source</button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      )}

      {activeTab === 'source_agreement' && (
        <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Source / Signed Agreement</h2>
              <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0' }}>Signed agreement source used for this Timeline setup.</p>
            </div>
            <button type="button" onClick={() => setShowSignedAgreement(true)} style={BUTTON}>Open Source</button>
          </div>
          {signedAgreementReadableText ? (
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 13, lineHeight: 1.6, color: '#334155', background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14, maxHeight: 520, overflow: 'auto', margin: 0 }}>{signedAgreementReadableText}</pre>
          ) : (
            <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#F8FAFC' }}>
              <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>{EMPTY_COPY.source_agreement}</p>
            </div>
          )}
        </section>
      )}

      {selectedTimelineItem && (
        <ModalShell
          title={selectedTimelineItem.title || itemTypeLabel(selectedTimelineItem)}
          onClose={closeTimelineItemDetail}
          width={980}
          eyebrow={itemSourceText(selectedTimelineItem)}
        >
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
            <button type="button" onClick={() => setShowSignedAgreement(true)} style={{ border: '1px solid #243447', borderRadius: 8, background: '#243447', color: '#FFFFFF', padding: '7px 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
              View Source / View Signed Agreement
            </button>
            <button type="button" onClick={() => setTimelineItemEditMode((current) => !current)} style={{ border: '1px solid #CBD5E1', borderRadius: 8, background: '#FFFFFF', color: '#334155', padding: '7px 11px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
              {timelineItemEditMode ? 'View Details' : 'Edit Timeline Details'}
            </button>
          </div>

          {selectedTimelineItem.has_personal_overrides && (
            <div style={{ background: '#FEFCE8', border: '1px solid #FDE68A', borderRadius: 8, padding: 12, marginBottom: 14 }}>
              <p style={{ fontSize: 12, color: '#92400E', margin: 0, fontWeight: 800 }}>This is your Timeline view. Editing this item does not change the signed agreement or the other party's Timeline view.</p>
            </div>
          )}
          {selectedTimelineItem.is_contract_derived && (
            <div style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: 12, marginBottom: 14 }}>
              <p style={{ fontSize: 12, color: '#1D4ED8', margin: 0 }}>This Timeline item was created from the signed agreement. Editing it updates the Timeline record only, not the signed agreement.</p>
            </div>
          )}

          {timelineItemError && (
            <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 12, marginBottom: 14 }}>
              <p style={{ fontSize: 12, color: '#B91C1C', margin: 0 }}>{timelineItemError}</p>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Title</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{selectedTimelineItem.title || '—'}</p>
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Type</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{itemTypeLabel(selectedTimelineItem)}</p>
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Status</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{humanize(selectedTimelineItem.status || 'pending')}</p>
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Amount</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{selectedTimelineItem.amount ? formatMoney(selectedTimelineItem.amount) : '—'}</p>
              {selectedTimelineItem.baseline_values?.amount && selectedTimelineItem.baseline_values.amount !== selectedTimelineItem.amount && (
                <p style={{ fontSize: 12, color: '#64748B', margin: '6px 0 0' }}>Original from signed agreement: {formatMoney(selectedTimelineItem.baseline_values.amount)}</p>
              )}
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Due date</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{selectedTimelineItem.due_date ? timelineDateLabel(selectedTimelineItem.due_date) : '—'}</p>
              {selectedTimelineItem.baseline_values?.due_date && selectedTimelineItem.baseline_values.due_date !== selectedTimelineItem.due_date && (
                <p style={{ fontSize: 12, color: '#64748B', margin: '6px 0 0' }}>Original from signed agreement: {timelineDateLabel(selectedTimelineItem.baseline_values.due_date)}</p>
              )}
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Responsible party</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{selectedTimelineItem.responsible_party || '—'}</p>
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Beneficiary</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{selectedTimelineItem.beneficiary_party || '—'}</p>
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Payment method</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{selectedTimelineItem.payment_method || '—'}</p>
              {selectedTimelineItem.baseline_values?.payment_method && selectedTimelineItem.baseline_values.payment_method !== selectedTimelineItem.payment_method && (
                <p style={{ fontSize: 12, color: '#64748B', margin: '6px 0 0' }}>Original from signed agreement: {selectedTimelineItem.baseline_values.payment_method}</p>
              )}
            </div>
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Source</p>
              <p style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: '6px 0 0' }}>{itemSourceText(selectedTimelineItem) || '—'}</p>
            </div>
          </div>
          {selectedTimelineItem.description && (
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginTop: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Notes / description</p>
              <p style={{ fontSize: 13, lineHeight: 1.6, color: '#334155', margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>{selectedTimelineItem.description}</p>
            </div>
          )}

          {sourceMetadataList(selectedTimelineItem).length > 0 && (
            <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginTop: 12 }}>
              <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', margin: 0 }}>Source / origin metadata</p>
              <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
                {sourceMetadataList(selectedTimelineItem).map((entry) => (
                  <div key={`${entry.label}-${entry.value}`}>
                    <p style={{ fontSize: 12, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>{entry.label}</p>
                    <p style={{ fontSize: 12, color: '#475569', margin: '2px 0 0', wordBreak: 'break-word' }}>{entry.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {timelineItemEditMode && (
            <div style={{ borderTop: '1px solid #E5E7EB', marginTop: 16, paddingTop: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Title</span>
                  <input value={timelineItemDraft.title} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, title: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '8px 10px', fontSize: 13 }} />
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Status</span>
                  <select value={timelineItemDraft.status} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, status: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '8px 10px', fontSize: 13 }}>
                    <option value="">—</option>
                    <option value="pending">Pending</option>
                    <option value="proposed">Proposed</option>
                    <option value="due">Due</option>
                    <option value="active">Active</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Due date</span>
                  <input type="date" value={timelineItemDraft.due_date} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, due_date: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '8px 10px', fontSize: 13 }} />
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Amount</span>
                  <input value={timelineItemDraft.amount} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, amount: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '8px 10px', fontSize: 13 }} />
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Responsible party</span>
                  <input value={timelineItemDraft.responsible_party} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, responsible_party: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '8px 10px', fontSize: 13 }} />
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Payment method</span>
                  <input value={timelineItemDraft.payment_method} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, payment_method: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '8px 10px', fontSize: 13 }} />
                </label>
              </div>
              <label style={{ display: 'grid', gap: 6, marginTop: 12 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Notes</span>
                <textarea rows={4} value={timelineItemDraft.notes} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, notes: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '10px 12px', fontSize: 13, resize: 'vertical' }} />
              </label>
              <label style={{ display: 'grid', gap: 6, marginTop: 12 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Description</span>
                <textarea rows={4} value={timelineItemDraft.description} onChange={(event) => setTimelineItemDraft((current) => ({ ...current, description: event.target.value }))} style={{ border: '1px solid #CBD5E1', borderRadius: 8, padding: '10px 12px', fontSize: 13, resize: 'vertical' }} />
              </label>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
                <button type="button" onClick={() => void saveTimelineItemDetail()} disabled={timelineItemSaving} style={{ border: 'none', borderRadius: 8, background: timelineItemSaving ? '#94A3B8' : '#243447', color: '#FFFFFF', padding: '8px 12px', fontSize: 12, fontWeight: 800, cursor: timelineItemSaving ? 'default' : 'pointer' }}>
                  {timelineItemSaving ? 'Saving...' : 'Save Changes'}
                </button>
                <button type="button" onClick={() => { if (selectedTimelineItem) openTimelineItemDetail(selectedTimelineItem) }} style={{ border: '1px solid #CBD5E1', borderRadius: 8, background: '#FFFFFF', color: '#334155', padding: '8px 12px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                  Reset
                </button>
              </div>
            </div>
          )}
        </ModalShell>
      )}

      {showSignedAgreement && (
        <ModalShell title={signedAgreementLabel} onClose={() => setShowSignedAgreement(false)} width={920} eyebrow="Signed agreement">
          <pre style={{ maxHeight: '70vh', overflow: 'auto', whiteSpace: 'pre-wrap', background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, color: '#334155', fontFamily: 'inherit' }}>{signedAgreementReadableText}</pre>
        </ModalShell>
      )}
    </div>
  )
}
