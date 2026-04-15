// frontend/src/pages/admin/AdminActivity.tsx
// Real data from GET /api/admin/activity/
// Shows all ContractActivity records system-wide.

import { useState } from 'react'
import { AdminTable, AdminPager, useAdminFetch } from './adminShared'

interface ActivityRecord {
  id: string
  contract_id: string
  user_id: number
  activity_type: string
  description: string
  created_at: string
}

interface Page {
  count: number
  page: number
  page_size: number
  results: ActivityRecord[]
}

export default function AdminActivity() {
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState('')

  const url = `/admin/activity/?page=${page}${typeFilter ? `&activity_type=${encodeURIComponent(typeFilter)}` : ''}`
  const { data, loading, error } = useAdminFetch<Page>(url)

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <label style={{ fontSize: 12, color: '#6B7280' }}>Filter by type:</label>
        <input
          type="text"
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
          placeholder="e.g. contract_created"
          style={{ fontSize: 12, padding: '5px 10px', border: '1px solid #D1D5DB', borderRadius: 6, background: '#fff', width: 200 }}
        />
      </div>

      {error && <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['Type', 'Description', 'User ID', 'Contract ID', 'When']}
      >
        {data?.results.map((a) => (
          <tr key={a.id} className="hover:bg-slate-50">
            <td className="px-4 py-3 text-xs font-mono text-slate-600">{a.activity_type}</td>
            <td className="px-4 py-3 text-sm text-slate-700 max-w-xs truncate">{a.description || '—'}</td>
            <td className="px-4 py-3 text-xs font-mono text-slate-400">{a.user_id ?? '—'}</td>
            <td className="px-4 py-3 text-xs font-mono text-slate-400">
              {a.contract_id ? a.contract_id.slice(0, 8) + '…' : '—'}
            </td>
            <td className="px-4 py-3 text-xs text-slate-400">
              {new Date(a.created_at).toLocaleString()}
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
