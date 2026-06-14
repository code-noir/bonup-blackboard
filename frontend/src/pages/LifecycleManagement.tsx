import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '@/api/client'

type SummaryCounts = Record<string, number>

type ObligationSummary = {
  counts?: { total?: number; payment?: number; service?: number }
  by_state?: { payment?: SummaryCounts; service?: SummaryCounts }
  attention?: { total_requiring_attention?: number }
}

type PaymentSummary = {
  count?: number
  total_amount?: string
  confirmed_amount?: string
  by_status?: SummaryCounts
}

type ObligationRecord = {
  id: string
  type: 'payment' | 'service'
  contract_id: string
  state?: string
  due_date?: string | null
  obligor_id?: number | string | null
  obligee_id?: number | string | null
  amount_due?: string
  amount_paid?: string
  installment_number?: number
  description?: string
  completed_at?: string | null
  notes?: string
  proof?: string
  proof_url?: string
  counterparty_email?: string
  counterparty_name?: string
}

type ObligationDetailResponse = {
  obligation?: {
    id?: string
    type?: 'payment' | 'service'
    contract_id?: string
    state?: string
    due_date?: string | null
    description?: string
    obligor_id?: number | string | null
    obligee_id?: number | string | null
    amount_due?: string
    amount_paid?: string
    installment_number?: number
    completed_at?: string | null
  }
  execution_summary?: { session_count?: number; event_count?: number }
  approval_summary?: { pending?: number; approved?: number; rejected?: number }
  adjustment_summary?: { total_adjustments?: number }
  promotion_summary?: { promoted_count?: number }
}

type PaymentRecord = {
  id: string
  contract?: string | null
  version?: string | null
  source_clause?: string | null
  source_clause_id?: string | null
  source_clause_title?: string | null
  source_clause_number?: string | null
  payment_obligation?: string | null
  payer?: number | string | null
  payee?: number | string | null
  amount?: string
  currency?: string
  status?: string
  payment_method?: string
  created_at?: string
  updated_at?: string
}

type Paginated<T> = {
  count: number
  results: T[]
}

type ExecutionEventRecord = {
  id: string
  event_type?: string
  task?: string | null
  observation?: string | null
  summary?: string
  estimated_duration_minutes?: number | null
  estimated_cost_amount?: string | null
  estimated_cost_currency?: string | null
  planned_execution_time?: string | null
  metadata?: Record<string, unknown>
  created_at?: string
}

type ApprovalRequestRecord = {
  id: string
  approval_type?: string
  status?: string
  summary?: string
}

type PaymentDetailResponse = PaymentRecord & {
  contract?: string | null
  version?: string | null
  source_clause?: string | null
}

type ActionFeedback = { kind: 'success' | 'error'; message: string } | null

type ServiceEventForm = {
  task: string
  observation: string
  summary: string
  estimated_duration_minutes: string
  estimated_cost_amount: string
  estimated_cost_currency: string
}

const DEFAULT_EVENT_FORM: ServiceEventForm = {
  task: '',
  observation: '',
  summary: '',
  estimated_duration_minutes: '30',
  estimated_cost_amount: '0',
  estimated_cost_currency: 'USD',
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString()
}

function formatMoney(amount?: string, currency = 'USD') {
  if (!amount) return '—'
  const parsed = Number(amount)
  if (Number.isNaN(parsed)) return `${amount} ${currency}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(parsed)
}

function humanize(value?: string) {
  if (!value) return '—'
  return value.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function serviceStatusLabel(status?: string) {
  switch ((status || '').toLowerCase()) {
    case 'active': return 'In Progress'
    case 'due': return 'Due'
    case 'overdue': return 'Missed'
    case 'resolved': return 'Performed'
    case 'fulfilled': return 'Performed'
    case 'pending': return 'Planned'
    case 'cancelled': return 'Missed'
    default: return 'Planned'
  }
}

function paymentStatusLabel(status?: string, paid?: string, owed?: string) {
  const paidAmount = Number(paid || '0')
  const owedAmount = Number(owed || '0')
  if (owedAmount > 0 && paidAmount >= owedAmount) return 'Paid'

  switch ((status || '').toLowerCase()) {
    case 'active': return 'Planned'
    case 'draft': return 'Planned'
    case 'pending': return 'Due'
    case 'due': return 'Due'
    case 'grace': return 'Due'
    case 'overdue': return 'Late'
    case 'defaulted': return 'Missed'
    case 'failed': return 'Missed'
    case 'resolved': return 'Paid'
    case 'confirmed': return 'Paid'
    case 'cancelled': return 'Missed'
    case 'refunded': return 'Paid'
    case 'reversed': return 'Missed'
    default: return 'Planned'
  }
}

function statusStyle(label: string) {
  if (label === 'In Progress') return { background: '#E0F2FE', color: '#0369A1' }
  if (label === 'Due') return { background: '#FEF3C7', color: '#B45309' }
  if (label === 'Late' || label === 'Missed') return { background: '#FEF2F2', color: '#B91C1C' }
  if (label === 'Paid' || label === 'Performed') return { background: '#ECFDF5', color: '#047857' }
  return { background: '#F8FAFC', color: '#475569' }
}

function contractLabel(contractId?: string | null) {
  if (!contractId) return 'No contract'
  return `Contract ${contractId.slice(0, 8)}`
}

function partyLabel(prefix: string, value?: number | string | null) {
  if (!value) return '—'
  return `${prefix} ${value}`
}

function getErrorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { error?: string; detail?: string } } })?.response
  return response?.data?.error || response?.data?.detail || fallback
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 18 }}>
      <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 26, lineHeight: 1.1, fontWeight: 800, color: '#0F1F3D', margin: '8px 0 0' }}>{value}</p>
      {sub && <p style={{ fontSize: 12, color: '#6B7280', margin: '6px 0 0' }}>{sub}</p>}
    </div>
  )
}

function EmptyStates() {
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {[
        'No lifecycle obligations found yet.',
        'Prepare a contract to generate service and payment obligations.',
        'Lifecycle records remain planned until the contract becomes Active.',
      ].map((message) => (
        <div key={message} style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#F8FAFC' }}>
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>{message}</p>
        </div>
      ))}
    </div>
  )
}

function ModalShell({
  title,
  onClose,
  children,
  width = 760,
}: {
  title: string
  onClose: () => void
  children: ReactNode
  width?: number
}) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.45)',
        zIndex: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: width,
          maxHeight: '90vh',
          overflow: 'auto',
          background: '#FFFFFF',
          borderRadius: 12,
          boxShadow: '0 20px 60px rgba(15, 23, 42, 0.3)',
          border: '1px solid rgba(15, 23, 42, 0.08)',
          padding: 20,
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div>
            <p style={{ margin: 0, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#94A3B8', fontWeight: 700 }}>Lifecycle action</p>
            <h3 style={{ margin: '4px 0 0', fontSize: 20, fontWeight: 800, color: '#0F1F3D' }}>{title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: '1px solid #CBD5E1', background: '#FFFFFF', color: '#334155', borderRadius: 8, padding: '8px 12px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
          >
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}


type LifecycleItemGroup = 'obligations' | 'payments' | 'deadlines' | 'services' | 'risks' | 'notes'

type ContractScopedLifecycleResponse = {
  contract: { id: string; title: string; status: string; state?: string; counterparty_email?: string; counterparty_name?: string }
  signed_version: { id: string; label: string; status: string; content_snapshot?: string }
  lifecycle_agreement: { id: string; status: string; started_at?: string; source_exchange_id?: string | null }
  parties?: { initiator?: { email?: string; name?: string } | null; counterparty?: { email?: string; name?: string } | null }
  items: Record<LifecycleItemGroup, Array<Record<string, string | null | undefined>>>
  events: Array<{ id: string; event_type: string; title: string; description?: string; occurred_at?: string }>
}

const LIFECYCLE_TABS: Array<{ key: LifecycleItemGroup | 'overview' | 'events' | 'documents'; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'obligations', label: 'Obligations' },
  { key: 'payments', label: 'Payments' },
  { key: 'deadlines', label: 'Deadlines' },
  { key: 'services', label: 'Services' },
  { key: 'events', label: 'Events' },
  { key: 'documents', label: 'Documents / Signed Version' },
]

const EMPTY_COPY: Record<LifecycleItemGroup, string> = {
  obligations: 'No obligations added yet.',
  payments: 'No payment obligations added yet.',
  deadlines: 'No deadlines tracked yet.',
  services: 'No service duties added yet.',
  risks: 'No risks tracked yet.',
  notes: 'No notes added yet.',
}

function ContractScopedLifecycle({ contractId }: { contractId: string }) {
  const [data, setData] = useState<ContractScopedLifecycleResponse | null>(null)
  const [activeTab, setActiveTab] = useState<(typeof LIFECYCLE_TABS)[number]['key']>('overview')
  const [isLoading, setIsLoading] = useState(true)
  const [feedback, setFeedback] = useState<ActionFeedback>(null)
  const [draftType, setDraftType] = useState<LifecycleItemGroup>('obligations')
  const [draftTitle, setDraftTitle] = useState('')

  const loadLifecycle = async () => {
    setIsLoading(true)
    try {
      const response = await api.get<ContractScopedLifecycleResponse>('/lifecycle/', { params: { contract: contractId } })
      setData(response.data)
      setFeedback(null)
    } catch (error) {
      setFeedback({ kind: 'error', message: getErrorMessage(error, 'Unable to load lifecycle data for this contract.') })
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
    const itemType = draftType === 'obligations' ? 'obligation' : draftType === 'payments' ? 'payment' : draftType === 'deadlines' ? 'deadline' : draftType === 'services' ? 'service' : draftType.slice(0, -1)
    try {
      await api.post(`/lifecycle/${data.lifecycle_agreement.id}/items/`, { item_type: itemType, title: draftTitle.trim() })
      setDraftTitle('')
      await loadLifecycle()
    } catch (error) {
      setFeedback({ kind: 'error', message: getErrorMessage(error, 'Unable to add lifecycle item.') })
    }
  }

  if (isLoading) return <p style={{ fontSize: 13, color: '#64748B' }}>Loading lifecycle...</p>

  if (!data) {
    return (
      <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 14 }}>
        <p style={{ fontSize: 13, color: '#B91C1C', margin: 0 }}>{feedback?.message || 'Lifecycle data is unavailable.'}</p>
      </div>
    )
  }

  const activeItems = activeTab in data.items ? data.items[activeTab as LifecycleItemGroup] : []

  return (
    <div className="space-y-6">
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
        <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>Signed contract lifecycle</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{data.contract.title}</h1>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '8px 0 0' }}>
              Signed version {data.signed_version.label} · Lifecycle {humanize(data.lifecycle_agreement.status)}
            </p>
          </div>
          <span style={{ alignSelf: 'flex-start', borderRadius: 999, padding: '5px 10px', fontSize: 11, fontWeight: 800, ...statusStyle('Paid') }}>Signed</span>
        </div>
      </section>

      {feedback && (
        <div style={{ background: feedback.kind === 'success' ? '#ECFDF5' : '#FEF2F2', border: `1px solid ${feedback.kind === 'success' ? '#A7F3D0' : '#FECACA'}`, borderRadius: 8, padding: '12px 14px' }}>
          <p style={{ fontSize: 13, color: feedback.kind === 'success' ? '#047857' : '#B91C1C', margin: 0 }}>{feedback.message}</p>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {LIFECYCLE_TABS.map((tab) => (
          <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} style={{ border: '1px solid #CBD5E1', borderRadius: 8, background: activeTab === tab.key ? '#0F1F3D' : '#FFFFFF', color: activeTab === tab.key ? '#FFFFFF' : '#334155', padding: '8px 11px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <StatCard label="Lifecycle Status" value={humanize(data.lifecycle_agreement.status)} sub={`Started ${formatDate(data.lifecycle_agreement.started_at)}`} />
          <StatCard label="Counterparty" value={data.contract.counterparty_name || data.contract.counterparty_email || '—'} sub="Signed agreement party" />
          <StatCard label="Tracked Items" value={Object.values(data.items).reduce((sum, items) => sum + items.length, 0)} sub="Manual and existing lifecycle records" />
        </div>
      )}

      {activeTab in data.items && (
        <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{LIFECYCLE_TABS.find((tab) => tab.key === activeTab)?.label}</h2>
              <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0' }}>Contract-scoped lifecycle records for this signed agreement.</p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select value={draftType} onChange={(event) => setDraftType(event.target.value as LifecycleItemGroup)} style={{ height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 8px', fontSize: 12 }}>
                {(['obligations', 'payments', 'deadlines', 'services', 'risks', 'notes'] as LifecycleItemGroup[]).map((key) => <option key={key} value={key}>{humanize(key)}</option>)}
              </select>
              <input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} placeholder="Add item" style={{ height: 34, border: '1px solid #CBD5E1', borderRadius: 8, padding: '0 10px', fontSize: 12 }} />
              <button type="button" onClick={() => void addItem()} disabled={!draftTitle.trim()} style={{ height: 34, border: 'none', borderRadius: 8, background: draftTitle.trim() ? '#0F1F3D' : '#E5E7EB', color: draftTitle.trim() ? '#FFFFFF' : '#64748B', padding: '0 12px', fontSize: 12, fontWeight: 700, cursor: draftTitle.trim() ? 'pointer' : 'default' }}>Add Item</button>
            </div>
          </div>
          {activeItems.length === 0 ? (
            <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#F8FAFC' }}>
              <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>{EMPTY_COPY[activeTab as LifecycleItemGroup]}</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {activeItems.map((item) => (
                <div key={`${item.source}-${item.id}`} style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                    <p style={{ fontSize: 14, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{item.title}</p>
                    <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 700, ...statusStyle(item.status === 'completed' ? 'Paid' : 'Due') }}>{humanize(item.status || 'pending')}</span>
                  </div>
                  {item.description && <p style={{ fontSize: 12, color: '#475569', margin: '8px 0 0' }}>{item.description}</p>}
                  <p style={{ fontSize: 11, color: '#94A3B8', margin: '8px 0 0' }}>{item.due_date ? `Due ${formatDate(item.due_date)}` : 'No due date'}{item.amount ? ` · ${formatMoney(item.amount)}` : ''}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {activeTab === 'events' && (
        <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: '0 0 12px' }}>Events</h2>
          {data.events.length === 0 ? <p style={{ fontSize: 13, color: '#64748B' }}>No lifecycle events recorded yet.</p> : data.events.map((event) => (
            <div key={event.id} style={{ borderBottom: '1px solid #E5E7EB', padding: '10px 0' }}>
              <p style={{ fontSize: 13, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>{event.title}</p>
              <p style={{ fontSize: 12, color: '#64748B', margin: '4px 0 0' }}>{event.description || humanize(event.event_type)}</p>
              <p style={{ fontSize: 11, color: '#94A3B8', margin: '4px 0 0' }}>{formatDate(event.occurred_at)}</p>
            </div>
          ))}
        </section>
      )}

      {activeTab === 'documents' && (
        <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Signed Version</h2>
          <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 14px' }}>Immutable signed contract snapshot retained from {data.signed_version.label}.</p>
          <pre style={{ maxHeight: 360, overflow: 'auto', whiteSpace: 'pre-wrap', background: '#F8FAFC', border: '1px solid #E5E7EB', borderRadius: 8, padding: 14, fontSize: 12, color: '#334155' }}>{data.signed_version.content_snapshot || 'No signed version snapshot returned.'}</pre>
        </section>
      )}
    </div>
  )
}

function GlobalLifecycleManagement() {
  const [obligationSummary, setObligationSummary] = useState<ObligationSummary | null>(null)
  const [paymentSummary, setPaymentSummary] = useState<PaymentSummary | null>(null)
  const [obligations, setObligations] = useState<ObligationRecord[]>([])
  const [payments, setPayments] = useState<PaymentRecord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [feedback, setFeedback] = useState<ActionFeedback>(null)
  const [busyAction, setBusyAction] = useState<string | null>(null)

  const [serviceDetail, setServiceDetail] = useState<{ obligation: ObligationRecord; detail: ObligationDetailResponse } | null>(null)
  const [paymentDetail, setPaymentDetail] = useState<{ payment: PaymentRecord; detail: PaymentDetailResponse } | null>(null)
  const [serviceEventFormOpen, setServiceEventFormOpen] = useState(false)
  const [serviceEventDraft, setServiceEventDraft] = useState<ServiceEventForm>(DEFAULT_EVENT_FORM)
  const [lastRecordedEvent, setLastRecordedEvent] = useState<ExecutionEventRecord | null>(null)
  const [lastApprovalRequest, setLastApprovalRequest] = useState<ApprovalRequestRecord | null>(null)
  const [approvalSummary, setApprovalSummary] = useState('Request approval for this execution event')
  const [detailError, setDetailError] = useState<string | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadData = async () => {
    setIsLoading(true)
    const results = await Promise.allSettled([
      api.get<ObligationSummary>('/obligations/dashboard-summary/'),
      api.get<Paginated<ObligationRecord>>('/obligations/'),
      api.get<PaymentSummary>('/payments/dashboard-summary/'),
      api.get<Paginated<PaymentRecord>>('/payments/'),
    ])

    const nextErrors: string[] = []
    const [obSummary, obList, paySummary, payList] = results

    if (obSummary.status === 'fulfilled') setObligationSummary(obSummary.value.data)
    else nextErrors.push(getErrorMessage(obSummary.reason, 'Unable to load obligation summary.'))

    if (obList.status === 'fulfilled') setObligations(obList.value.data.results || [])
    else nextErrors.push(getErrorMessage(obList.reason, 'Unable to load obligations.'))

    if (paySummary.status === 'fulfilled') setPaymentSummary(paySummary.value.data)
    else nextErrors.push(getErrorMessage(paySummary.reason, 'Unable to load payment summary.'))

    if (payList.status === 'fulfilled') setPayments(payList.value.data.results || [])
    else nextErrors.push(getErrorMessage(payList.reason, 'Unable to load payments.'))

    setFeedback(nextErrors.length > 0 ? { kind: 'error', message: nextErrors[0] } : null)
    setIsLoading(false)
  }

  useEffect(() => {
    void loadData()
  }, [])

  const serviceObligations = useMemo(() => obligations.filter((obligation) => obligation.type === 'service'), [obligations])
  const paymentObligations = useMemo(() => obligations.filter((obligation) => obligation.type === 'payment'), [obligations])

  const paymentsByObligation = useMemo(() => {
    const map = new Map<string, PaymentRecord[]>()
    payments.forEach((payment) => {
      if (!payment.payment_obligation) return
      const current = map.get(payment.payment_obligation) || []
      current.push(payment)
      map.set(payment.payment_obligation, current)
    })
    return map
  }, [payments])

  const serviceCount = obligationSummary?.counts?.service ?? serviceObligations.length
  const paymentObligationCount = obligationSummary?.counts?.payment ?? paymentObligations.length
  const serviceAttention = (obligationSummary?.by_state?.service?.due ?? 0) + (obligationSummary?.by_state?.service?.overdue ?? 0)
  const paymentAttention = (obligationSummary?.by_state?.payment?.due ?? 0)
    + (obligationSummary?.by_state?.payment?.grace ?? 0)
    + (obligationSummary?.by_state?.payment?.overdue ?? 0)
    + (obligationSummary?.by_state?.payment?.defaulted ?? 0)
  const dueAttentionCount = serviceAttention + paymentAttention
  const paymentsDueCount = (paymentSummary?.by_status?.pending ?? 0) + paymentAttention

  const closeServiceDetail = () => {
    setServiceDetail(null)
    setServiceEventFormOpen(false)
    setLastRecordedEvent(null)
    setLastApprovalRequest(null)
    setDetailError(null)
    setApprovalSummary('Request approval for this execution event')
    setServiceEventDraft(DEFAULT_EVENT_FORM)
  }

  const closePaymentDetail = () => {
    setPaymentDetail(null)
    setDetailError(null)
  }

  const openServiceDetail = async (obligation: ObligationRecord): Promise<boolean> => {
    setDetailError(null)
    setDetailLoading(true)
    try {
      const response = await api.get<ObligationDetailResponse>(`/obligations/${obligation.type}/${obligation.id}/`)
      setServiceDetail({ obligation, detail: response.data })
      setServiceEventFormOpen(false)
      setLastRecordedEvent(null)
      setLastApprovalRequest(null)
      setApprovalSummary('Request approval for this execution event')
      return true
    } catch (error) {
      setFeedback({ kind: 'error', message: getErrorMessage(error, 'Unable to load service obligation details.') })
      return false
    } finally {
      setDetailLoading(false)
    }
  }

  const openPaymentDetail = async (payment: PaymentRecord) => {
    setDetailError(null)
    setDetailLoading(true)
    try {
      const response = await api.get<PaymentDetailResponse>(`/payments/${payment.id}/`)
      setPaymentDetail({ payment, detail: response.data })
    } catch (error) {
      setFeedback({ kind: 'error', message: getErrorMessage(error, 'Unable to load payment details.') })
    } finally {
      setDetailLoading(false)
    }
  }

  const runAction = async (actionKey: string, runner: () => Promise<void>) => {
    setBusyAction(actionKey)
    try {
      await runner()
      await loadData()
    } catch (error) {
      setFeedback({ kind: 'error', message: getErrorMessage(error, 'Action failed.') })
    } finally {
      setBusyAction(null)
    }
  }

  const resolveService = (obligation: ObligationRecord) => runAction(`service-resolve-${obligation.id}`, async () => {
    await api.post(`/contracts/obligations/${obligation.type}/${obligation.id}/resolve/`)
    setFeedback({ kind: 'success', message: 'Service obligation marked performed.' })
    closeServiceDetail()
  })

  const resolvePaymentObligation = (obligation: ObligationRecord) => runAction(`payment-obligation-resolve-${obligation.id}`, async () => {
    await api.post(`/contracts/obligations/payment/${obligation.id}/resolve/`)
    setFeedback({ kind: 'success', message: 'Payment obligation resolved.' })
    closeServiceDetail()
  })

  const confirmPayment = (payment: PaymentRecord) => runAction(`payment-confirm-${payment.id}`, async () => {
    await api.post(`/payments/${payment.id}/confirm/`)
    setFeedback({ kind: 'success', message: 'Payment confirmed.' })
    closePaymentDetail()
  })

  const markPaymentPending = (payment: PaymentRecord) => runAction(`payment-pending-${payment.id}`, async () => {
    await api.post(`/payments/${payment.id}/pending/`)
    setFeedback({ kind: 'success', message: 'Payment marked pending.' })
    closePaymentDetail()
  })

  const markPaymentFailed = (payment: PaymentRecord) => runAction(`payment-failed-${payment.id}`, async () => {
    await api.post(`/payments/${payment.id}/fail/`)
    setFeedback({ kind: 'success', message: 'Payment marked failed.' })
    closePaymentDetail()
  })

  const submitServiceEvent = async () => {
    if (!serviceDetail) return
    const obligation = serviceDetail.obligation
    setBusyAction(`service-event-${obligation.id}`)
    setDetailError(null)

    try {
      const sessionResponse = await api.post(`/contracts/obligations/${obligation.type}/${obligation.id}/execution-sessions/`, {})
      const sessionId = sessionResponse.data?.id || sessionResponse.data?.session_id
      if (!sessionId) throw new Error('Execution session was not created.')

      const eventResponse = await api.post(`/contracts/execution-sessions/${sessionId}/execution-items/`, {
        task: serviceEventDraft.task,
        observation: serviceEventDraft.observation,
        summary: serviceEventDraft.summary,
        estimated_duration_minutes: Number(serviceEventDraft.estimated_duration_minutes),
        estimated_cost_amount: serviceEventDraft.estimated_cost_amount,
        estimated_cost_currency: serviceEventDraft.estimated_cost_currency,
        metadata: { source: 'lifecycle-management' },
      })

      const event = eventResponse.data?.event as ExecutionEventRecord | undefined
      const approvalRequest = eventResponse.data?.approval_request as ApprovalRequestRecord | undefined
      if (!event) throw new Error('Execution event was not created.')

      setLastRecordedEvent(event)
      setLastApprovalRequest(approvalRequest || null)
      setApprovalSummary(serviceEventDraft.summary || event.summary || 'Request approval for this execution event')
      setFeedback({ kind: 'success', message: 'Execution event recorded.' })
      await loadData()
    } catch (error) {
      setDetailError(getErrorMessage(error, 'Unable to record execution event.'))
    } finally {
      setBusyAction(null)
    }
  }

  const requestApprovalForEvent = async () => {
    if (!serviceDetail || !lastRecordedEvent) return
    const obligation = serviceDetail.obligation
    setBusyAction(`service-approval-${obligation.id}`)
    setDetailError(null)

    try {
      const response = await api.post(`/contracts/obligations/${obligation.type}/${obligation.id}/approval-requests/`, {
        execution_event_id: lastRecordedEvent.id,
        summary: approvalSummary || lastRecordedEvent.summary || 'Request approval',
        metadata: { source: 'lifecycle-management' },
      })
      setLastApprovalRequest(response.data as ApprovalRequestRecord)
      setFeedback({ kind: 'success', message: 'Approval requested.' })
      await loadData()
    } catch (error) {
      setDetailError(getErrorMessage(error, 'Unable to request approval.'))
    } finally {
      setBusyAction(null)
    }
  }

  const isServiceResolved = (state?: string) => (state || '').toLowerCase() === 'resolved'
  const canConfirmPayment = (status?: string) => (status || '').toLowerCase() === 'pending'
  const canMarkPaymentPending = (status?: string) => (status || '').toLowerCase() === 'draft'
  const canMarkPaymentFailed = (status?: string) => (status || '').toLowerCase() === 'pending'

  return (
    <div className="space-y-6">
      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
        <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#9CA3AF', fontWeight: 700, margin: '0 0 6px' }}>
          Blackboard lifecycle
        </p>
        <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Lifecycle Management</h1>
        <p style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.6, margin: '8px 0 0', maxWidth: 820 }}>
          Track service obligations, payment obligations, and payment records returned by the current lifecycle APIs.
        </p>
      </section>

      {feedback && (
        <div style={{ background: feedback.kind === 'success' ? '#ECFDF5' : '#FEF2F2', border: `1px solid ${feedback.kind === 'success' ? '#A7F3D0' : '#FECACA'}`, borderRadius: 8, padding: '12px 14px' }}>
          <p style={{ fontSize: 13, color: feedback.kind === 'success' ? '#047857' : '#B91C1C', margin: 0 }}>{feedback.message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Service Obligations" value={isLoading ? '—' : serviceCount} sub="Service and delivery duties" />
        <StatCard label="Due / Needs Attention" value={isLoading ? '—' : dueAttentionCount} sub={`${obligationSummary?.attention?.total_requiring_attention ?? 0} flagged by backend`} />
        <StatCard label="Payments Due" value={isLoading ? '—' : paymentsDueCount} sub={`${paymentObligationCount} payment obligation(s)`} />
        <StatCard label="Confirmed / Paid" value={isLoading ? '—' : formatMoney(paymentSummary?.confirmed_amount || '0')} sub={`${paymentSummary?.count ?? payments.length} payment record(s)`} />
      </div>

      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
        <div style={{ marginBottom: 14 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Service Obligations</h2>
          <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0' }}>Operational service, delivery, and performance obligations from existing lifecycle records.</p>
        </div>
        {isLoading ? (
          <p style={{ fontSize: 13, color: '#64748B' }}>Loading service obligations...</p>
        ) : serviceObligations.length === 0 ? (
          <EmptyStates />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #E5E7EB', color: '#64748B', textAlign: 'left' }}>
                  <th style={{ padding: '10px 8px' }}>Contract</th>
                  <th style={{ padding: '10px 8px' }}>Service Description</th>
                  <th style={{ padding: '10px 8px' }}>Responsible Party</th>
                  <th style={{ padding: '10px 8px' }}>Counterparty</th>
                  <th style={{ padding: '10px 8px' }}>Due Date</th>
                  <th style={{ padding: '10px 8px' }}>Status</th>
                  <th style={{ padding: '10px 8px' }}>Notes / Proof</th>
                  <th style={{ padding: '10px 8px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {serviceObligations.map((obligation) => {
                  const label = serviceStatusLabel(obligation.state)
                  const notes = obligation.proof_url || obligation.proof || obligation.notes || (obligation.completed_at ? `Completed ${formatDate(obligation.completed_at)}` : '—')
                  const resolved = isServiceResolved(obligation.state)
                  return (
                    <tr key={obligation.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '11px 8px', color: '#0F1F3D', fontWeight: 700 }}>{contractLabel(obligation.contract_id)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569', minWidth: 240 }}>{obligation.description || 'Service obligation'}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{partyLabel('Obligor', obligation.obligor_id)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{obligation.counterparty_name || obligation.counterparty_email || partyLabel('Obligee', obligation.obligee_id)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{formatDate(obligation.due_date)}</td>
                      <td style={{ padding: '11px 8px' }}>
                        <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 700, ...statusStyle(label) }}>{label}</span>
                      </td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{notes}</td>
                      <td style={{ padding: '11px 8px' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => void openServiceDetail(obligation)}
                            style={tableButtonStyle('ghost')}
                          >
                            View Details
                          </button>
                          <button
                            type="button"
                            onClick={() => void resolveService(obligation)}
                            disabled={resolved || busyAction === `service-resolve-${obligation.id}`}
                            style={tableButtonStyle('primary', resolved || busyAction === `service-resolve-${obligation.id}`)}
                          >
                            {busyAction === `service-resolve-${obligation.id}` ? 'Saving...' : 'Mark Performed'}
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              if (await openServiceDetail(obligation)) {
                                setServiceEventFormOpen(true)
                              }
                            }}
                            disabled={resolved || busyAction === `service-event-${obligation.id}`}
                            style={tableButtonStyle('secondary', resolved || busyAction === `service-event-${obligation.id}`)}
                          >
                            Add Event
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
        <div style={{ marginBottom: 14 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Payment Obligations</h2>
          <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0' }}>Amounts owed, payer/payee references, due dates, and paid status from obligation and payment APIs.</p>
        </div>
        {isLoading ? (
          <p style={{ fontSize: 13, color: '#64748B' }}>Loading payment obligations...</p>
        ) : paymentObligations.length === 0 ? (
          <EmptyStates />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #E5E7EB', color: '#64748B', textAlign: 'left' }}>
                  <th style={{ padding: '10px 8px' }}>Contract</th>
                  <th style={{ padding: '10px 8px' }}>Amount Owed</th>
                  <th style={{ padding: '10px 8px' }}>Payer</th>
                  <th style={{ padding: '10px 8px' }}>Payee</th>
                  <th style={{ padding: '10px 8px' }}>Due Date</th>
                  <th style={{ padding: '10px 8px' }}>Status</th>
                  <th style={{ padding: '10px 8px' }}>Paid / Confirmed</th>
                  <th style={{ padding: '10px 8px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {paymentObligations.map((obligation) => {
                  const linkedPayments = paymentsByObligation.get(obligation.id) || []
                  const confirmed = linkedPayments.filter((payment) => payment.status === 'confirmed')
                  const confirmedTotal = confirmed.reduce((sum, payment) => sum + Number(payment.amount || 0), 0)
                  const label = paymentStatusLabel(obligation.state, obligation.amount_paid, obligation.amount_due)
                  const paidLabel = confirmed.length > 0
                    ? `${formatMoney(String(confirmedTotal))} confirmed (${confirmed.length})`
                    : obligation.amount_paid && Number(obligation.amount_paid) > 0
                      ? `${formatMoney(obligation.amount_paid)} paid`
                      : 'Not paid'
                  const resolved = (obligation.state || '').toLowerCase() === 'resolved'
                  return (
                    <tr key={obligation.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '11px 8px', color: '#0F1F3D', fontWeight: 700 }}>{contractLabel(obligation.contract_id)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{formatMoney(obligation.amount_due)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{partyLabel('Payer', obligation.obligor_id)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{partyLabel('Payee', obligation.obligee_id)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{formatDate(obligation.due_date)}</td>
                      <td style={{ padding: '11px 8px' }}>
                        <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 700, ...statusStyle(label) }}>{label}</span>
                      </td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{paidLabel}</td>
                      <td style={{ padding: '11px 8px' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => void openServiceDetail({ ...obligation, type: 'payment' })}
                            style={tableButtonStyle('ghost')}
                          >
                            View Details
                          </button>
                          <button
                            type="button"
                            onClick={() => void resolvePaymentObligation(obligation)}
                            disabled={resolved || busyAction === `payment-obligation-resolve-${obligation.id}`}
                            style={tableButtonStyle('primary', resolved || busyAction === `payment-obligation-resolve-${obligation.id}`)}
                          >
                            {busyAction === `payment-obligation-resolve-${obligation.id}` ? 'Saving...' : 'Resolve Obligation'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 20 }}>
        <div style={{ marginBottom: 14 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>Payments</h2>
          <p style={{ fontSize: 12, color: '#6B7280', margin: '4px 0 0' }}>Payment records attached to the current user’s contracts and obligations.</p>
        </div>
        {isLoading ? (
          <p style={{ fontSize: 13, color: '#64748B' }}>Loading payments...</p>
        ) : payments.length === 0 ? (
          <EmptyStates />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #E5E7EB', color: '#64748B', textAlign: 'left' }}>
                  <th style={{ padding: '10px 8px' }}>Contract</th>
                  <th style={{ padding: '10px 8px' }}>Obligation</th>
                  <th style={{ padding: '10px 8px' }}>Amount</th>
                  <th style={{ padding: '10px 8px' }}>Status</th>
                  <th style={{ padding: '10px 8px' }}>Method</th>
                  <th style={{ padding: '10px 8px' }}>Recorded</th>
                  <th style={{ padding: '10px 8px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((payment) => {
                  const label = paymentStatusLabel(payment.status, payment.amount, payment.amount)
                  const canConfirm = canConfirmPayment(payment.status)
                  const canPending = canMarkPaymentPending(payment.status)
                  const canFail = canMarkPaymentFailed(payment.status)
                  return (
                    <tr key={payment.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '11px 8px', color: '#0F1F3D', fontWeight: 700 }}>{contractLabel(payment.contract)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{payment.payment_obligation ? `Obligation ${payment.payment_obligation.slice(0, 8)}` : '—'}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{formatMoney(payment.amount, payment.currency || 'USD')}</td>
                      <td style={{ padding: '11px 8px' }}>
                        <span style={{ borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 700, ...statusStyle(label) }}>{label}</span>
                      </td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{humanize(payment.payment_method)}</td>
                      <td style={{ padding: '11px 8px', color: '#475569' }}>{formatDate(payment.created_at)}</td>
                      <td style={{ padding: '11px 8px' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => void openPaymentDetail(payment)}
                            style={tableButtonStyle('ghost')}
                          >
                            View Details
                          </button>
                          <button
                            type="button"
                            onClick={() => void confirmPayment(payment)}
                            disabled={!canConfirm || busyAction === `payment-confirm-${payment.id}`}
                            style={tableButtonStyle('primary', !canConfirm || busyAction === `payment-confirm-${payment.id}`)}
                          >
                            {busyAction === `payment-confirm-${payment.id}` ? 'Saving...' : 'Confirm / Mark Paid'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void markPaymentPending(payment)}
                            disabled={!canPending || busyAction === `payment-pending-${payment.id}`}
                            style={tableButtonStyle('secondary', !canPending || busyAction === `payment-pending-${payment.id}`)}
                          >
                            {busyAction === `payment-pending-${payment.id}` ? 'Saving...' : 'Mark Pending'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void markPaymentFailed(payment)}
                            disabled={!canFail || busyAction === `payment-failed-${payment.id}`}
                            style={tableButtonStyle('danger', !canFail || busyAction === `payment-failed-${payment.id}`)}
                          >
                            {busyAction === `payment-failed-${payment.id}` ? 'Saving...' : 'Mark Failed'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {serviceDetail && (
        <ModalShell title={`${serviceDetail.obligation.type === 'service' ? 'Service' : 'Payment'} obligation details`} onClose={closeServiceDetail} width={860}>
          {detailLoading ? (
            <p style={{ margin: 0, color: '#64748B' }}>Loading obligation details...</p>
          ) : (
            <div style={{ display: 'grid', gap: 16 }}>
              {detailError && (
                <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 12px' }}>
                  <p style={{ margin: 0, color: '#B91C1C', fontSize: 13 }}>{detailError}</p>
                </div>
              )}
              <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                <InfoPill label="Contract" value={contractLabel(serviceDetail.obligation.contract_id)} />
                <InfoPill label="Status" value={humanize(serviceDetail.detail.obligation?.state || serviceDetail.obligation.state)} />
                <InfoPill label="Due Date" value={formatDate(serviceDetail.detail.obligation?.due_date || serviceDetail.obligation.due_date)} />
                <InfoPill label="Obligor" value={partyLabel('User', serviceDetail.detail.obligation?.obligor_id || serviceDetail.obligation.obligor_id)} />
                <InfoPill label="Obligee" value={partyLabel('User', serviceDetail.detail.obligation?.obligee_id || serviceDetail.obligation.obligee_id)} />
              </div>
              {serviceDetail.obligation.type === 'service' && (
                <>
                  <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: 14 }}>
                    <p style={{ margin: '0 0 6px', fontSize: 12, fontWeight: 700, color: '#0F1F3D' }}>Execution summary</p>
                    <p style={{ margin: 0, fontSize: 13, color: '#475569' }}>
                      Sessions: {serviceDetail.detail.execution_summary?.session_count ?? 0} • Events: {serviceDetail.detail.execution_summary?.event_count ?? 0} • Approvals pending: {serviceDetail.detail.approval_summary?.pending ?? 0}
                    </p>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    <button type="button" onClick={() => void resolveService(serviceDetail.obligation)} disabled={busyAction === `service-resolve-${serviceDetail.obligation.id}` || isServiceResolved(serviceDetail.obligation.state)} style={tableButtonStyle('primary', busyAction === `service-resolve-${serviceDetail.obligation.id}` || isServiceResolved(serviceDetail.obligation.state))}>
                      {busyAction === `service-resolve-${serviceDetail.obligation.id}` ? 'Saving...' : 'Mark Performed / Resolve'}
                    </button>
                    <button type="button" onClick={() => setServiceEventFormOpen((current) => !current)} disabled={busyAction === `service-event-${serviceDetail.obligation.id}` || isServiceResolved(serviceDetail.obligation.state)} style={tableButtonStyle('secondary', busyAction === `service-event-${serviceDetail.obligation.id}` || isServiceResolved(serviceDetail.obligation.state))}>
                      Add Event
                    </button>
                  </div>
                  {serviceEventFormOpen && (
                    <div style={{ display: 'grid', gap: 10, border: '1px solid #E2E8F0', borderRadius: 8, padding: 14, background: '#F8FAFC' }}>
                      <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: '#0F1F3D' }}>Record execution item</p>
                      <div style={gridFormStyle}>
                        <FormField label="Task" value={serviceEventDraft.task} onChange={(value) => setServiceEventDraft((current) => ({ ...current, task: value }))} />
                        <FormField label="Observation" value={serviceEventDraft.observation} onChange={(value) => setServiceEventDraft((current) => ({ ...current, observation: value }))} />
                        <FormField label="Summary" value={serviceEventDraft.summary} onChange={(value) => setServiceEventDraft((current) => ({ ...current, summary: value }))} />
                        <FormField label="Duration (minutes)" value={serviceEventDraft.estimated_duration_minutes} type="number" onChange={(value) => setServiceEventDraft((current) => ({ ...current, estimated_duration_minutes: value }))} />
                        <FormField label="Estimated cost amount" value={serviceEventDraft.estimated_cost_amount} type="number" onChange={(value) => setServiceEventDraft((current) => ({ ...current, estimated_cost_amount: value }))} />
                        <FormField label="Currency" value={serviceEventDraft.estimated_cost_currency} onChange={(value) => setServiceEventDraft((current) => ({ ...current, estimated_cost_currency: value }))} />
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        <button type="button" onClick={() => void submitServiceEvent()} disabled={busyAction === `service-event-${serviceDetail.obligation.id}`} style={tableButtonStyle('primary', busyAction === `service-event-${serviceDetail.obligation.id}`)}>
                          {busyAction === `service-event-${serviceDetail.obligation.id}` ? 'Saving...' : 'Save Event'}
                        </button>
                        <button type="button" onClick={() => setServiceEventFormOpen(false)} style={tableButtonStyle('ghost')}>
                          Cancel
                        </button>
                      </div>
                      {lastRecordedEvent && (
                        <div style={{ background: '#FFFFFF', border: '1px solid #D1FAE5', borderRadius: 8, padding: 12 }}>
                          <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 700, color: '#047857' }}>Latest event recorded</p>
                          <p style={{ margin: 0, fontSize: 13, color: '#475569' }}>{lastRecordedEvent.summary}</p>
                          <div style={{ marginTop: 10, display: 'grid', gap: 8 }}>
                            <FormField label="Approval summary" value={approvalSummary} onChange={(value) => setApprovalSummary(value)} />
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                              <button type="button" onClick={() => void requestApprovalForEvent()} disabled={busyAction === `service-approval-${serviceDetail.obligation.id}`} style={tableButtonStyle('primary', busyAction === `service-approval-${serviceDetail.obligation.id}`)}>
                                {busyAction === `service-approval-${serviceDetail.obligation.id}` ? 'Saving...' : 'Request Approval'}
                              </button>
                              {lastApprovalRequest && (
                                <span style={{ fontSize: 12, color: '#047857', alignSelf: 'center' }}>Approval request {lastApprovalRequest.status || 'created'}.</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
              {serviceDetail.obligation.type === 'payment' && (
                <>
                  <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: 14 }}>
                    <p style={{ margin: '0 0 6px', fontSize: 12, fontWeight: 700, color: '#0F1F3D' }}>Payment obligation</p>
                    <p style={{ margin: 0, fontSize: 13, color: '#475569' }}>
                      Amount due: {formatMoney(serviceDetail.detail.obligation?.amount_due || serviceDetail.obligation.amount_due)} • Paid: {formatMoney(serviceDetail.detail.obligation?.amount_paid || serviceDetail.obligation.amount_paid)}
                    </p>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    <button type="button" onClick={() => void resolvePaymentObligation(serviceDetail.obligation)} disabled={busyAction === `payment-obligation-resolve-${serviceDetail.obligation.id}` || isServiceResolved(serviceDetail.obligation.state)} style={tableButtonStyle('primary', busyAction === `payment-obligation-resolve-${serviceDetail.obligation.id}` || isServiceResolved(serviceDetail.obligation.state))}>
                      {busyAction === `payment-obligation-resolve-${serviceDetail.obligation.id}` ? 'Saving...' : 'Resolve Obligation'}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </ModalShell>
      )}

      {paymentDetail && (
        <ModalShell title="Payment details" onClose={closePaymentDetail} width={760}>
          {detailLoading ? (
            <p style={{ margin: 0, color: '#64748B' }}>Loading payment details...</p>
          ) : (
            <div style={{ display: 'grid', gap: 14 }}>
              {detailError && (
                <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 12px' }}>
                  <p style={{ margin: 0, color: '#B91C1C', fontSize: 13 }}>{detailError}</p>
                </div>
              )}
              <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                <InfoPill label="Contract" value={contractLabel(paymentDetail.detail.contract || paymentDetail.payment.contract)} />
                <InfoPill label="Status" value={humanize(paymentDetail.detail.status || paymentDetail.payment.status)} />
                <InfoPill label="Amount" value={formatMoney(paymentDetail.detail.amount || paymentDetail.payment.amount, paymentDetail.detail.currency || paymentDetail.payment.currency || 'USD')} />
                <InfoPill label="Method" value={humanize(paymentDetail.detail.payment_method || paymentDetail.payment.payment_method)} />
                <InfoPill label="Recorded" value={formatDate(paymentDetail.detail.created_at || paymentDetail.payment.created_at)} />
              </div>
              <div style={{ display: 'grid', gap: 8, background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: 14 }}>
                <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: '#0F1F3D' }}>Linked obligation</p>
                <p style={{ margin: 0, fontSize: 13, color: '#475569' }}>{paymentDetail.detail.payment_obligation || paymentDetail.payment.payment_obligation || '—'}</p>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                <button type="button" onClick={() => void confirmPayment(paymentDetail.payment)} disabled={!canConfirmPayment(paymentDetail.payment.status) || busyAction === `payment-confirm-${paymentDetail.payment.id}`} style={tableButtonStyle('primary', !canConfirmPayment(paymentDetail.payment.status) || busyAction === `payment-confirm-${paymentDetail.payment.id}`)}>
                  {busyAction === `payment-confirm-${paymentDetail.payment.id}` ? 'Saving...' : 'Confirm / Mark Paid'}
                </button>
                <button type="button" onClick={() => void markPaymentPending(paymentDetail.payment)} disabled={!canMarkPaymentPending(paymentDetail.payment.status) || busyAction === `payment-pending-${paymentDetail.payment.id}`} style={tableButtonStyle('secondary', !canMarkPaymentPending(paymentDetail.payment.status) || busyAction === `payment-pending-${paymentDetail.payment.id}`)}>
                  {busyAction === `payment-pending-${paymentDetail.payment.id}` ? 'Saving...' : 'Mark Pending'}
                </button>
                <button type="button" onClick={() => void markPaymentFailed(paymentDetail.payment)} disabled={!canMarkPaymentFailed(paymentDetail.payment.status) || busyAction === `payment-failed-${paymentDetail.payment.id}`} style={tableButtonStyle('danger', !canMarkPaymentFailed(paymentDetail.payment.status) || busyAction === `payment-failed-${paymentDetail.payment.id}`)}>
                  {busyAction === `payment-failed-${paymentDetail.payment.id}` ? 'Saving...' : 'Mark Failed'}
                </button>
              </div>
            </div>
          )}
        </ModalShell>
      )}
    </div>
  )
}

function tableButtonStyle(kind: 'ghost' | 'primary' | 'secondary' | 'danger', disabled = false) {
  const base = {
    borderRadius: 8,
    border: '1px solid transparent',
    padding: '7px 10px',
    fontSize: 12,
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.65 : 1,
    transition: 'background-color 120ms ease, border-color 120ms ease, color 120ms ease',
  } as const

  switch (kind) {
    case 'primary':
      return {
        ...base,
        background: '#0F1F3D',
        color: '#FFFFFF',
        borderColor: '#0F1F3D',
      }
    case 'secondary':
      return {
        ...base,
        background: '#EFF6FF',
        color: '#1D4ED8',
        borderColor: '#BFDBFE',
      }
    case 'danger':
      return {
        ...base,
        background: '#FEF2F2',
        color: '#B91C1C',
        borderColor: '#FECACA',
      }
    case 'ghost':
    default:
      return {
        ...base,
        background: '#FFFFFF',
        color: '#334155',
        borderColor: '#CBD5E1',
      }
  }
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: 12 }}>
      <p style={{ margin: 0, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8', fontWeight: 700 }}>{label}</p>
      <p style={{ margin: '6px 0 0', fontSize: 13, fontWeight: 700, color: '#0F1F3D' }}>{value}</p>
    </div>
  )
}

function FormField({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'number'
}) {
  return (
    <label style={{ display: 'grid', gap: 5 }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        style={{
          border: '1px solid #CBD5E1',
          borderRadius: 8,
          padding: '9px 10px',
          fontSize: 13,
          color: '#0F1F3D',
          background: '#FFFFFF',
        }}
      />
    </label>
  )
}


export default function LifecycleManagement() {
  const [searchParams] = useSearchParams()
  const contractId = searchParams.get('contract')

  if (contractId) return <ContractScopedLifecycle contractId={contractId} />

  return <GlobalLifecycleManagement />
}
