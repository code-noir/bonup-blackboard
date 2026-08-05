// frontend/src/pages/admin/AdminContracts.tsx
// Real data from GET /api/admin/contracts/
// Truth screen — shows all agreements system-wide without exposing raw IDs as primary values.

import { useState } from 'react'
import { AdminTable, AdminBadge, AdminPager, useAdminFetch, formatDate } from './adminShared'

interface AdminContract {
  id: string
  title: string
  initiator_name: string
  initiator_email: string | null
  initiator_bon_id: string | null
  counterparty: string
  counterparty_email: string
  entity_type: string
  status: string
  obligation_count: number
  created_at: string
}

interface Page {
  count: number
  page: number
  page_size: number
  results: AdminContract[]
}

const STATUS_STYLE: Record<string, 'green' | 'yellow' | 'blue' | 'gray' | 'red'> = {
  draft:     'yellow',
  sent:      'blue',
  pending:   'blue',
  active:    'green',
  signed:    'green',
  completed: 'gray',
  archived:  'gray',
  cancelled: 'red',
  rejected:  'red',
}

const STATUS_FILTERS = ['', 'draft', 'sent', 'signed', 'active', 'completed', 'archived', 'cancelled', 'rejected']

function statusLabel(status: string) {
  return status ? status.replace(/_/g, ' ') : 'unknown'
}

export default function AdminContracts() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')

  const url = `/admin/contracts/?page=${page}${statusFilter ? `&status=${statusFilter}` : ''}`
  const { data, loading, error } = useAdminFetch<Page>(url)

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <p style={{ margin: 0, color: '#0F1F3D', fontSize: 18, fontWeight: 850 }}>Agreements</p>
          <p style={{ margin: '4px 0 0', color: '#64748B', fontSize: 12 }}>System-wide read-only agreement inventory.</p>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748B' }}>
          Status
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            style={{ fontSize: 12, padding: '7px 10px', border: '1px solid #D1D5DB', borderRadius: 8, background: '#fff', color: '#0F1F3D' }}
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s} value={s}>{s ? statusLabel(s) : 'All'}</option>
            ))}
          </select>
        </label>
      </div>

      {error && <AdminBadge label={error} style="red" />}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['Agreement', 'Initiator Name', 'bonID', 'Counterparty', 'Status', 'Created', 'Obligation Count']}
      >
        {data?.results.map((agreement) => (
          <tr key={agreement.id} className="hover:bg-slate-50">
            <td className="px-4 py-3">
              <div style={{ color: '#0F1F3D', fontSize: 13, fontWeight: 750 }}>{agreement.title}</div>
              <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{agreement.entity_type}</div>
            </td>
            <td className="px-4 py-3">
              <div style={{ color: '#334155', fontSize: 13 }}>{agreement.initiator_name}</div>
              <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{agreement.initiator_email || '—'}</div>
            </td>
            <td className="px-4 py-3 text-xs font-mono text-slate-500">{agreement.initiator_bon_id || '—'}</td>
            <td className="px-4 py-3">
              <div style={{ color: '#334155', fontSize: 13 }}>{agreement.counterparty}</div>
              {agreement.counterparty !== agreement.counterparty_email && (
                <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{agreement.counterparty_email}</div>
              )}
            </td>
            <td className="px-4 py-3">
              <AdminBadge label={statusLabel(agreement.status)} style={STATUS_STYLE[agreement.status] || 'gray'} />
            </td>
            <td className="px-4 py-3 text-xs text-slate-500">{formatDate(agreement.created_at)}</td>
            <td className="px-4 py-3 text-sm font-semibold text-slate-700">{agreement.obligation_count}</td>
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
    </div>
  )
}
