// frontend/src/pages/admin/AdminSol.tsx
// Real data from GET /api/admin/sol/

import { useState } from 'react'
import { AdminTable, AdminBadge, AdminPager, useAdminFetch } from './adminShared'

interface SolGroup {
  id: string
  sol_id: string
  name: string
  status: string
  sol_type: string
  frequency: string
  contribution_amount: string
  currency: string
  active_member_count: number
  primary_manager_id: number
  is_private: boolean
  created_at: string
}

interface Page {
  count: number
  page: number
  page_size: number
  results: SolGroup[]
}

const STATUS_STYLE: Record<string, 'green' | 'yellow' | 'gray'> = {
  active:    'green',
  pending:   'yellow',
  completed: 'gray',
  cancelled: 'gray',
}

export default function AdminSol() {
  const [page, setPage] = useState(1)
  const { data, loading, error } = useAdminFetch<Page>(`/admin/sol/?page=${page}`)

  return (
    <div className="space-y-4">
      {error && <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['Sol ID', 'Name', 'Status', 'Type', 'Frequency', 'Contribution', 'Members', 'Private', 'Manager ID', 'Created']}
      >
        {data?.results.map((s) => (
          <tr key={s.id} className="hover:bg-slate-50">
            <td className="px-4 py-3 text-xs font-mono text-slate-400">{s.sol_id}</td>
            <td className="px-4 py-3 text-sm font-medium text-slate-800">{s.name}</td>
            <td className="px-4 py-3">
              <AdminBadge label={s.status} style={STATUS_STYLE[s.status] || 'gray'} />
            </td>
            <td className="px-4 py-3 text-xs text-slate-500">{s.sol_type}</td>
            <td className="px-4 py-3 text-xs text-slate-500">{s.frequency}</td>
            <td className="px-4 py-3 text-sm text-slate-700">
              {s.contribution_amount} {s.currency}
            </td>
            <td className="px-4 py-3 text-sm text-center text-slate-600">{s.active_member_count}</td>
            <td className="px-4 py-3 text-center text-xs text-slate-400">
              {s.is_private ? 'yes' : 'no'}
            </td>
            <td className="px-4 py-3 text-xs font-mono text-slate-400">{s.primary_manager_id}</td>
            <td className="px-4 py-3 text-xs text-slate-400">
              {new Date(s.created_at).toLocaleDateString()}
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
