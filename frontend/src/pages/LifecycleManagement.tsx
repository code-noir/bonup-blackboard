import { useEffect, useMemo, useState } from 'react'
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

type PaymentRecord = {
  id: string
  contract?: string | null
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

export default function LifecycleManagement() {
  const [obligationSummary, setObligationSummary] = useState<ObligationSummary | null>(null)
  const [paymentSummary, setPaymentSummary] = useState<PaymentSummary | null>(null)
  const [obligations, setObligations] = useState<ObligationRecord[]>([])
  const [payments, setPayments] = useState<PaymentRecord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errors, setErrors] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setErrors([])

    Promise.allSettled([
      api.get<ObligationSummary>('/obligations/dashboard-summary/'),
      api.get<Paginated<ObligationRecord>>('/obligations/'),
      api.get<PaymentSummary>('/payments/dashboard-summary/'),
      api.get<Paginated<PaymentRecord>>('/payments/'),
    ]).then((results) => {
      if (cancelled) return
      const nextErrors: string[] = []

      const [obSummary, obList, paySummary, payList] = results
      if (obSummary.status === 'fulfilled') setObligationSummary(obSummary.value.data)
      else nextErrors.push(obSummary.reason?.response?.data?.error || 'Unable to load obligation summary.')

      if (obList.status === 'fulfilled') setObligations(obList.value.data.results || [])
      else nextErrors.push(obList.reason?.response?.data?.error || 'Unable to load obligations.')

      if (paySummary.status === 'fulfilled') setPaymentSummary(paySummary.value.data)
      else nextErrors.push(paySummary.reason?.response?.data?.error || 'Unable to load payment summary.')

      if (payList.status === 'fulfilled') setPayments(payList.value.data.results || [])
      else nextErrors.push(payList.reason?.response?.data?.error || 'Unable to load payments.')

      setErrors(Array.from(new Set(nextErrors)))
      setIsLoading(false)
    })

    return () => { cancelled = true }
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

      {errors.length > 0 && (
        <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '12px 14px' }}>
          {errors.map((error) => <p key={error} style={{ fontSize: 13, color: '#B91C1C', margin: '3px 0' }}>{error}</p>)}
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
                </tr>
              </thead>
              <tbody>
                {serviceObligations.map((obligation) => {
                  const label = serviceStatusLabel(obligation.state)
                  const notes = obligation.proof_url || obligation.proof || obligation.notes || (obligation.completed_at ? `Completed ${formatDate(obligation.completed_at)}` : '—')
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
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
