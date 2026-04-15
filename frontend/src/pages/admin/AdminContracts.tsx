// frontend/src/pages/admin/AdminContracts.tsx
// Real data from GET /api/admin/contracts/
// Truth screen — shows all contracts system-wide.

import { useState } from 'react'
import { AdminTable, AdminBadge, AdminPager, useAdminFetch } from './adminShared'

interface AdminContract {
  id: string
  title: string
  initiator_id: number
  counterparty_email: string
  entity_type: string
  status: string
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
  pending:   'blue',
  active:    'green',
  completed: 'gray',
  cancelled: 'red',
  rejected:  'red',
}

const STATUS_FILTERS = ['', 'draft', 'pending', 'active', 'completed', 'cancelled', 'rejected']

export default function AdminContracts() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')

  const url = `/admin/contracts/?page=${page}${statusFilter ? `&status=${statusFilter}` : ''}`
  const { data, loading, error } = useAdminFetch<Page>(url)

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <label style={{ fontSize: 12, color: '#6B7280' }}>Filter by status:</label>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          style={{ fontSize: 12, padding: '5px 10px', border: '1px solid #D1D5DB', borderRadius: 6, background: '#fff' }}
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>{s || 'All'}</option>
          ))}
        </select>
      </div>

      {error && <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['Title', 'Initiator', 'Counterparty', 'Entity Type', 'Status', 'Created']}
      >
        {data?.results.map((c) => (
          <tr key={c.id} className="hover:bg-slate-50">
            <td className="px-4 py-3 text-sm font-medium text-slate-800">{c.title}</td>
            <td className="px-4 py-3 text-sm text-slate-500">
              {c.initiator_id}
            </td>
            <td className="px-4 py-3 text-sm text-slate-500">{c.counterparty_email || '—'}</td>
            <td className="px-4 py-3 text-xs text-slate-500">{c.entity_type}</td>
            <td className="px-4 py-3">
              <AdminBadge label={c.status} style={STATUS_STYLE[c.status] || 'gray'} />
            </td>
            <td className="px-4 py-3 text-xs text-slate-400">
              {new Date(c.created_at).toLocaleDateString()}
            </td>
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
