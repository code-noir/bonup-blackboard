// frontend/src/pages/admin/AdminObligations.tsx
// Real data from GET /api/admin/obligations/
// Read-only operator view of payment and service obligations system-wide.

import { useState } from 'react'
import { AdminBadge, AdminPager, AdminTable, formatDate, formatDateTime, useAdminFetch } from './adminShared'

interface AdminObligation {
  id: string
  agreement_id: string
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

interface Page {
  count: number
  page: number
  page_size: number
  results: AdminObligation[]
}

const STATUS_STYLE: Record<string, 'green' | 'yellow' | 'blue' | 'gray' | 'red'> = {
  active: 'green',
  pending: 'blue',
  due: 'yellow',
  grace: 'yellow',
  overdue: 'red',
  defaulted: 'red',
  resolved: 'green',
}

const TYPE_FILTERS = ['', 'payment', 'service']
const STATUS_FILTERS = ['', 'active', 'pending', 'due', 'grace', 'overdue', 'defaulted', 'resolved']

function labelize(value: string | null | undefined) {
  return value ? value.replace(/_/g, ' ') : 'unknown'
}

function titleize(value: string | null | undefined) {
  const label = labelize(value)
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function concise(value: string | null | undefined, maxLength = 96) {
  const text = (value || '').replace(/\s+/g, ' ').trim()
  if (text.length <= maxLength) return text || '—'
  return `${text.slice(0, maxLength - 1).trim()}...`
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

function ObligationInspectionPanel({ obligation, onClose }: { obligation: AdminObligation; onClose: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="obligation-inspection-title"
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
            <h2 id="obligation-inspection-title" style={{ margin: '6px 0 0', color: '#0F1F3D', fontSize: 22, fontWeight: 900 }}>{concise(obligation.obligation, 72)}</h2>
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
            <DetailRow label="Status" value={<AdminBadge label={titleize(obligation.agreement_status)} style={STATUS_STYLE[obligation.agreement_status] || 'gray'} />} />
          </PanelSection>

          <PanelSection title="Obligation">
            <DetailRow label="Title" value={concise(obligation.obligation, 120)} />
            <DetailRow label="Type" value={<AdminBadge label={titleize(obligation.type)} style={obligation.type === 'payment' ? 'blue' : 'sky'} />} />
            <DetailRow label="Status" value={<AdminBadge label={titleize(obligation.status)} style={STATUS_STYLE[obligation.status] || 'gray'} />} />
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

export default function AdminObligations() {
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedObligation, setSelectedObligation] = useState<AdminObligation | null>(null)

  const url = `/admin/obligations/?page=${page}${typeFilter ? `&type=${typeFilter}` : ''}${statusFilter ? `&state=${statusFilter}` : ''}`
  const { data, loading, error } = useAdminFetch<Page>(url)

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <p style={{ margin: 0, color: '#0F1F3D', fontSize: 18, fontWeight: 850 }}>Obligations</p>
          <p style={{ margin: '4px 0 0', color: '#64748B', fontSize: 12 }}>System-wide read-only payment and service obligation inventory.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748B' }}>
            Type
            <select
              value={typeFilter}
              onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
              style={{ fontSize: 12, padding: '7px 10px', border: '1px solid #D1D5DB', borderRadius: 8, background: '#fff', color: '#0F1F3D' }}
            >
              {TYPE_FILTERS.map((value) => <option key={value} value={value}>{value ? labelize(value) : 'All'}</option>)}
            </select>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748B' }}>
            Status
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
              style={{ fontSize: 12, padding: '7px 10px', border: '1px solid #D1D5DB', borderRadius: 8, background: '#fff', color: '#0F1F3D' }}
            >
              {STATUS_FILTERS.map((value) => <option key={value} value={value}>{value ? labelize(value) : 'All'}</option>)}
            </select>
          </label>
        </div>
      </div>

      {error && <AdminBadge label={error} style="red" />}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['Actions', 'Agreement', 'Obligation', 'Type', 'Assigned User', 'Due Date', 'Status', 'Last Updated']}
      >
        {data?.results.map((obligation) => (
          <tr key={`${obligation.type}-${obligation.id}`} className="hover:bg-slate-50">
            <td className="px-4 py-3" style={{ position: 'sticky', left: 0, zIndex: 1, background: '#fff', boxShadow: '8px 0 16px rgba(15,23,42,0.04)' }}><ActionButton onClick={() => setSelectedObligation(obligation)}>View</ActionButton></td>
            <td className="px-4 py-3">
              <div style={{ color: '#0F1F3D', fontSize: 13, fontWeight: 750 }}>{obligation.agreement_title}</div>
              <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{titleize(obligation.agreement_status)}</div>
            </td>
            <td className="px-4 py-3">
              <div style={{ color: '#334155', fontSize: 13, fontWeight: 650, maxWidth: 360 }}>{concise(obligation.obligation)}</div>
            </td>
            <td className="px-4 py-3"><AdminBadge label={titleize(obligation.type)} style={obligation.type === 'payment' ? 'blue' : 'sky'} /></td>
            <td className="px-4 py-3">
              <div style={{ color: '#334155', fontSize: 13 }}>{obligation.assigned_user}</div>
              <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{obligation.assigned_user_email || '-'}</div>
            </td>
            <td className="px-4 py-3 text-xs text-slate-500">{formatDate(obligation.due_date)}</td>
            <td className="px-4 py-3"><AdminBadge label={titleize(obligation.status)} style={STATUS_STYLE[obligation.status] || 'gray'} /></td>
            <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(obligation.last_updated)}</td>
          </tr>
        ))}
      </AdminTable>

      {data && (
        <AdminPager
          page={data.page}
          pageSize={data.page_size}
          total={data.count}
          onPage={setPage}
        />
      )}

      {selectedObligation && (
        <ObligationInspectionPanel
          obligation={selectedObligation}
          onClose={() => setSelectedObligation(null)}
        />
      )}
    </div>
  )
}
