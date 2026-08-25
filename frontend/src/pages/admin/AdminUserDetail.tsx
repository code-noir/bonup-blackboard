// frontend/src/pages/admin/AdminUserDetail.tsx
// bonID-first identity record for a single bonUP user.
// Real data from GET /api/admin/users/<id>/
// Behaves as an identity record / bonID record, not a generic profile.

import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useOperator } from '@/context/OperatorContext'
import { AdminBadge, AdminMetricCard, AdminTable, formatDate, formatDateTime, useAdminFetch, planDisplay } from './adminShared'

interface AgreementRow {
  id: string
  title: string
  role: string
  status: string
  obligation_count: number
  last_activity_at: string | null
}

interface ObligationRow {
  id: string
  agreement_title: string
  agreement_status: string
  counterparty: string
  obligation: string
  type: string
  assigned_user: string
  assigned_user_email: string | null
  due_date: string | null
  completion_date: string | null
  status: string
  created_at: string | null
  last_updated: string | null
  internal_reference: string | null
}

interface UserDetail {
  id: number
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  date_joined: string
  bon_id: string | null
  plan: string | null
  plan_display: string | null
  subscription_status: string | null
  is_trialing: boolean
  trial_remaining: number | null
  business_count: number
  contract_count: number
  agreements_created: number
  agreements_participating: number
  agreements_accessible: number
  signed_agreements: number
  draft_agreements: number
  archived_agreements: number
  open_obligations: number
  resolved_obligations: number
  completed_obligations: number
  assigned_open_obligations: number
  payment_obligations: number
  service_obligations: number
  overdue_obligations: number
  agreements: AgreementRow[]
  obligations: ObligationRow[]
}

const STATUS_LABELS: Record<string, string> = {
  active:           'Active',
  trialing:         'Trialing',
  per_contract:     'Pay As You Go',
  past_due:         'Past Due',
  cancelled:        'Cancelled',
  no_subscription:  'None',
}

const STATUS_STYLE: Record<string, 'green' | 'yellow' | 'blue' | 'gray' | 'red'> = {
  draft: 'yellow',
  sent: 'blue',
  pending: 'blue',
  active: 'green',
  signed: 'green',
  completed: 'gray',
  archived: 'gray',
  resolved: 'green',
  overdue: 'red',
  defaulted: 'red',
  cancelled: 'red',
  rejected: 'red',
}

const SUBSCRIPTION_STYLE: Record<string, 'green' | 'yellow' | 'blue' | 'gray' | 'red' | 'sky'> = {
  active: 'green',
  trialing: 'sky',
  per_contract: 'green',
  past_due: 'yellow',
  cancelled: 'red',
  no_subscription: 'gray',
}

function labelize(value: string | null | undefined) {
  return value ? value.replace(/_/g, ' ') : 'unknown'
}

function concise(value: string | null | undefined, maxLength = 96) {
  const text = (value || '').replace(/\s+/g, ' ').trim()
  if (text.length <= maxLength) return text || '—'
  return `${text.slice(0, maxLength - 1).trim()}…`
}

function ActionButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        border: '1px solid #D1D5DB',
        borderRadius: 8,
        background: '#fff',
        color: '#0F1F3D',
        cursor: 'pointer',
        fontSize: 12,
        fontWeight: 750,
        padding: '6px 12px',
      }}
    >
      {children}
    </button>
  )
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '132px minmax(0, 1fr)', gap: 12, padding: '9px 0', borderBottom: '1px solid #F1F5F9' }}>
      <span style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700 }}>{label}</span>
      <span style={{ color: '#0F172A', fontSize: 13, fontWeight: 600, minWidth: 0, overflowWrap: 'anywhere' }}>{value}</span>
    </div>
  )
}

function PanelSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ border: '1px solid #E5E7EB', borderRadius: 12, background: '#fff', padding: 14 }}>
      <p style={{ margin: '0 0 6px', color: '#64748B', fontSize: 11, fontWeight: 850, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{title}</p>
      {children}
    </section>
  )
}

function UserObligationInspectionPanel({ obligation, onClose }: { obligation: ObligationRow; onClose: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="user-obligation-inspection-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 60,
        background: 'rgba(15,23,42,0.38)',
        display: 'flex',
        justifyContent: 'flex-end',
      }}
      onClick={onClose}
    >
      <aside
        style={{
          width: 'min(560px, 100%)',
          minHeight: '100%',
          background: '#F8FAFC',
          boxShadow: '-18px 0 40px rgba(15,23,42,0.18)',
          padding: 22,
          overflowY: 'auto',
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <p style={{ margin: 0, color: '#64748B', fontSize: 11, fontWeight: 850, textTransform: 'uppercase', letterSpacing: '0.12em' }}>Obligation Inspection</p>
            <h2 id="user-obligation-inspection-title" style={{ margin: '6px 0 0', color: '#0F1F3D', fontSize: 22, fontWeight: 900 }}>{concise(obligation.obligation, 72)}</h2>
            <p style={{ margin: '6px 0 0', color: '#64748B', fontSize: 13 }}>Operator support inspection.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close obligation inspection"
            style={{
              border: '1px solid #D1D5DB',
              borderRadius: 8,
              background: '#fff',
              color: '#475569',
              cursor: 'pointer',
              fontSize: 18,
              lineHeight: 1,
              padding: '6px 10px',
            }}
          >
            x
          </button>
        </div>

        <div style={{ display: 'grid', gap: 12 }}>
          <PanelSection title="Agreement">
            <DetailRow label="Title" value={obligation.agreement_title} />
            <DetailRow label="Status" value={<AdminBadge label={labelize(obligation.agreement_status)} style={STATUS_STYLE[obligation.agreement_status] || 'gray'} />} />
          </PanelSection>

          <PanelSection title="Obligation">
            <DetailRow label="Title" value={concise(obligation.obligation, 120)} />
            <DetailRow label="Type" value={<AdminBadge label={labelize(obligation.type)} style={obligation.type === 'payment' ? 'blue' : 'sky'} />} />
            <DetailRow label="Status" value={<AdminBadge label={labelize(obligation.status)} style={STATUS_STYLE[obligation.status] || 'gray'} />} />
            <DetailRow label="Due date" value={formatDate(obligation.due_date)} />
            <DetailRow label="Completion date" value={formatDate(obligation.completion_date)} />
          </PanelSection>

          <PanelSection title="People">
            <DetailRow label="Assigned user" value={obligation.assigned_user} />
            <DetailRow label="Counterparty" value={obligation.counterparty} />
          </PanelSection>

          <PanelSection title="System Information">
            <DetailRow label="Created" value={formatDateTime(obligation.created_at)} />
            <DetailRow label="Updated" value={formatDateTime(obligation.last_updated)} />
            <DetailRow label="Internal ref" value={obligation.internal_reference} />
          </PanelSection>
        </div>
      </aside>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      padding: '11px 0',
      borderBottom: '1px solid #F3F4F6',
      gap: 16,
    }}>
      <span style={{ fontSize: 12, color: '#9CA3AF', width: 160, flexShrink: 0, paddingTop: 1 }}>
        {label}
      </span>
      <span style={{ fontSize: 13, color: '#111827', fontWeight: 500 }}>
        {value ?? <span style={{ color: '#D1D5DB' }}>—</span>}
      </span>
    </div>
  )
}

function SectionHead({ label, detail }: { label: string; detail?: string }) {
  return (
    <div style={{ margin: '20px 0 10px' }}>
      <p style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        color: '#9CA3AF',
        margin: 0,
      }}>
        {label}
      </p>
      {detail && <p style={{ margin: '4px 0 0', color: '#64748B', fontSize: 12 }}>{detail}</p>}
    </div>
  )
}

function SupportAccessPanel() {
  return (
    <section style={{ background: '#fff', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 16, padding: 18, boxShadow: '0 12px 30px rgba(15,23,42,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <p style={{ margin: 0, color: '#0F1F3D', fontSize: 17, fontWeight: 850 }}>Support Access</p>
          <p style={{ margin: '5px 0 0', color: '#64748B', fontSize: 12 }}>Future support boundary. Administrator permissions are separate from normal user flags.</p>
        </div>
        <AdminBadge label="Not Configured" style="gray" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginTop: 12 }}>
        <div>
          <Row label="Status" value="Not Configured" />
          <Row label="Policy" value="Not Configured" />
        </div>
        <div>
          <Row label="Last Access" value="—" />
          <Row label="Audit History" value="Unavailable" />
        </div>
      </div>
    </section>
  )
}

export default function AdminUserDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { operator, startViewAs } = useOperator()
  const [selectedObligation, setSelectedObligation] = useState<ObligationRow | null>(null)
  const [viewAsError, setViewAsError] = useState('')
  const [viewAsLoading, setViewAsLoading] = useState(false)
  const { data: u, loading, error } = useAdminFetch<UserDetail>(`/admin/users/${id}/`)

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <div style={{
          width: 24, height: 24, borderRadius: '50%',
          border: '3px solid #38BDF8', borderTopColor: 'transparent',
          animation: 'spin 0.7s linear infinite',
        }} />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#B91C1C' }}>
        {error}
      </div>
    )
  }

  if (!u) return null

  const displayName = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.email
  const statusKey = u.subscription_status || 'no_subscription'
  const statusLabel = STATUS_LABELS[statusKey] || statusKey
  const tierLabel = u.plan_display || planDisplay(u.plan)

  const handleViewAs = async () => {
    setViewAsError('')
    setViewAsLoading(true)
    try {
      await startViewAs(u.id)
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setViewAsError(detail || 'Unable to start View-As for this user.')
    } finally {
      setViewAsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/operator/identity/users"
          style={{ fontSize: 12, color: '#64748B', textDecoration: 'none', fontWeight: 650 }}
        >
          ← Back to Users
        </Link>
      </div>

      <section style={{ background: '#fff', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 16, padding: 18, boxShadow: '0 12px 30px rgba(15,23,42,0.05)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <p style={{ margin: 0, color: '#64748B', fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.12em' }}>User Identity</p>
            <h1 style={{ margin: '6px 0 0', color: '#0F1F3D', fontSize: 24, fontWeight: 900 }}>{displayName}</h1>
            <p style={{ margin: '5px 0 0', color: '#64748B', fontSize: 13 }}>{u.email}</p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontFamily: 'monospace', fontSize: 13, color: '#F5A623', background: '#243447', padding: '7px 10px', borderRadius: 8, fontWeight: 800 }}>
              {u.bon_id || 'No bonID'}
            </span>
            {u.is_staff && <AdminBadge label="Django staff" style="yellow" />}
            {operator?.can_view_as_user && (
              <button
                type="button"
                onClick={handleViewAs}
                disabled={viewAsLoading}
                style={{
                  border: '1px solid #0F1F3D',
                  borderRadius: 8,
                  background: '#0F1F3D',
                  color: '#fff',
                  cursor: viewAsLoading ? 'default' : 'pointer',
                  fontSize: 12,
                  fontWeight: 800,
                  padding: '7px 12px',
                  opacity: viewAsLoading ? 0.7 : 1,
                }}
              >
                {viewAsLoading ? 'Starting...' : 'View As User'}
              </button>
            )}
          </div>
        </div>

        {viewAsError && (
          <p style={{ margin: '12px 0 0', border: '1px solid #FECACA', borderRadius: 8, background: '#FEF2F2', color: '#B91C1C', padding: '9px 12px', fontSize: 13 }}>
            {viewAsError}
          </p>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 18, marginTop: 18 }}>
          <div>
            <SectionHead label="Account" />
            <Row label="Joined" value={formatDate(u.date_joined)} />
            <Row label="Django staff flag" value={u.is_staff ? 'Yes' : 'No'} />
          </div>
          <div>
            <SectionHead label="Blackbòd" />
            <Row label="Tier" value={tierLabel} />
            <Row label="Billing status" value={<AdminBadge label={statusLabel} style={SUBSCRIPTION_STYLE[statusKey] || 'gray'} />} />
            {u.is_trialing && u.trial_remaining !== null && (
              <Row label="Trial contracts left" value={u.trial_remaining} />
            )}
            <Row label="Business entities" value={u.business_count} />
          </div>
        </div>
      </section>

      <SupportAccessPanel />

      <section>
        <SectionHead label="Agreement Summary" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <AdminMetricCard label="Agreements Created" value={u.agreements_created ?? u.contract_count} />
          <AdminMetricCard label="Agreements Participating" value={u.agreements_participating} />
          <AdminMetricCard label="Accessible Agreements" value={u.agreements_accessible} tone="blue" />
          <AdminMetricCard label="Signed Agreements" value={u.signed_agreements} tone="green" />
          <AdminMetricCard label="Draft Agreements" value={u.draft_agreements} tone="yellow" />
          <AdminMetricCard label="Archived Agreements" value={u.archived_agreements} />
        </div>
      </section>

      <section>
        <SectionHead label="Obligation Summary" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <AdminMetricCard label="Open Obligations" value={u.open_obligations} tone="blue" />
          <AdminMetricCard label="Completed Obligations" value={u.completed_obligations ?? u.resolved_obligations} tone="green" />
          <AdminMetricCard label="Assigned Open Obligations" value={u.assigned_open_obligations} />
          <AdminMetricCard label="Payment Obligations" value={u.payment_obligations} />
          <AdminMetricCard label="Service Obligations" value={u.service_obligations} />
          <AdminMetricCard label="Overdue Obligations" value={u.overdue_obligations} tone="red" />
        </div>
      </section>

      <section className="space-y-3">
        <SectionHead label="User Agreements" detail="Agreements accessible to this selected user only." />
        <AdminTable
          loading={false}
          empty={u.agreements.length === 0}
          headers={['Agreement', 'Role', 'Status', 'Obligation Count', 'Last Activity']}
        >
          {u.agreements.map((agreement) => (
            <tr key={agreement.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 text-sm font-semibold text-slate-800">{agreement.title}</td>
              <td className="px-4 py-3 text-sm text-slate-500">{agreement.role}</td>
              <td className="px-4 py-3"><AdminBadge label={labelize(agreement.status)} style={STATUS_STYLE[agreement.status] || 'gray'} /></td>
              <td className="px-4 py-3 text-sm font-semibold text-slate-700">{agreement.obligation_count}</td>
              <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(agreement.last_activity_at)}</td>
            </tr>
          ))}
        </AdminTable>
      </section>

      <section className="space-y-3">
        <SectionHead label="User Obligations" detail="Obligations attached to agreements where this selected user participates." />
        <AdminTable
          loading={false}
          empty={u.obligations.length === 0}
          headers={['Actions', 'Agreement', 'Obligation', 'Type', 'Assigned User', 'Due Date', 'Status']}
        >
          {u.obligations.map((obligation) => (
            <tr key={`${obligation.type}-${obligation.id}`} className="hover:bg-slate-50">
              <td className="px-4 py-3" style={{ position: 'sticky', left: 0, zIndex: 1, background: '#fff', boxShadow: '8px 0 16px rgba(15,23,42,0.04)' }}><ActionButton onClick={() => setSelectedObligation(obligation)}>View</ActionButton></td>
              <td className="px-4 py-3">
                <div style={{ color: '#0F1F3D', fontSize: 13, fontWeight: 750 }}>{obligation.agreement_title}</div>
                <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{labelize(obligation.agreement_status)}</div>
              </td>
              <td className="px-4 py-3">
                <div style={{ color: '#334155', fontSize: 13, fontWeight: 650, maxWidth: 360 }}>{concise(obligation.obligation)}</div>
              </td>
              <td className="px-4 py-3"><AdminBadge label={labelize(obligation.type)} style={obligation.type === 'payment' ? 'blue' : 'sky'} /></td>
              <td className="px-4 py-3">
                <div style={{ color: '#334155', fontSize: 13 }}>{obligation.assigned_user}</div>
                <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{obligation.assigned_user_email || '—'}</div>
              </td>
              <td className="px-4 py-3 text-xs text-slate-500">{formatDate(obligation.due_date)}</td>
              <td className="px-4 py-3"><AdminBadge label={labelize(obligation.status)} style={STATUS_STYLE[obligation.status] || 'gray'} /></td>
            </tr>
          ))}
        </AdminTable>
      </section>

      {selectedObligation && (
        <UserObligationInspectionPanel
          obligation={selectedObligation}
          onClose={() => setSelectedObligation(null)}
        />
      )}
    </div>
  )
}
