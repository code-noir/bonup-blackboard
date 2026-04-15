// frontend/src/pages/admin/AdminEntities.tsx
// Real data from GET /api/admin/entities/

import { useState } from 'react'
import { AdminTable, AdminBadge, AdminPager, useAdminFetch } from './adminShared'

interface Entity {
  id: string
  name: string
  owner_id: number
  business_type: string
  industry: string
  is_active: boolean
  created_at: string
}

interface Page {
  count: number
  page: number
  page_size: number
  results: Entity[]
}

export default function AdminEntities() {
  const [page, setPage] = useState(1)
  const { data, loading, error } = useAdminFetch<Page>(`/admin/entities/?page=${page}`)

  return (
    <div className="space-y-4">
      {error && <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['Name', 'Owner', 'Type', 'Industry', 'Active', 'Created']}
      >
        {data?.results.map((e) => (
          <tr key={e.id} className="hover:bg-slate-50">
            <td className="px-4 py-3 text-sm font-medium text-slate-800">{e.name}</td>
            <td className="px-4 py-3 text-sm text-slate-500">
              {e.owner_id}
            </td>
            <td className="px-4 py-3 text-xs text-slate-500">{e.business_type || '—'}</td>
            <td className="px-4 py-3 text-xs text-slate-500">{e.industry || '—'}</td>
            <td className="px-4 py-3">
              <AdminBadge label={e.is_active ? 'active' : 'inactive'} style={e.is_active ? 'green' : 'gray'} />
            </td>
            <td className="px-4 py-3 text-xs text-slate-400">
              {new Date(e.created_at).toLocaleDateString()}
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
