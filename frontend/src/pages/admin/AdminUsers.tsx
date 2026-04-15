// frontend/src/pages/admin/AdminUsers.tsx
// bonID-first identity index. Real data from GET /api/admin/users/
// Supports ?q= search by bonID, email, or name.
// Clicking a row navigates to the user's identity detail page.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AdminTable, AdminBadge, AdminPager, useAdminFetch, planDisplay } from './adminShared'

interface AdminUser {
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
  business_count: number
}

interface Page {
  count: number
  page: number
  page_size: number
  results: AdminUser[]
}

const STATUS_STYLE: Record<string, 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'sky'> = {
  active:           'green',
  trialing:         'sky',
  per_contract:     'green',
  past_due:         'yellow',
  cancelled:        'red',
  no_subscription:  'gray',
}

const STATUS_LABELS: Record<string, string> = {
  active:           'Active',
  trialing:         'Trialing',
  per_contract:     'Pay As You Go',
  past_due:         'Past Due',
  cancelled:        'Cancelled',
  no_subscription:  'None',
}

export default function AdminUsers() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [inputVal, setInputVal] = useState('')
  const [page, setPage] = useState(1)
  const { data, loading, error } = useAdminFetch<Page>(
    `/admin/users/?page=${page}${q ? `&q=${encodeURIComponent(q)}` : ''}`
  )

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setPage(1)
    setQ(inputVal.trim())
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Search by bonID, email, or name…"
          style={{
            flex: 1, maxWidth: 400, padding: '7px 12px', fontSize: 13,
            border: '1px solid #D1D5DB', borderRadius: 7, outline: 'none',
          }}
        />
        <button
          type="submit"
          style={{
            padding: '7px 18px', fontSize: 13, fontWeight: 500,
            background: '#0F1F3D', color: '#fff', border: 'none',
            borderRadius: 7, cursor: 'pointer',
          }}
        >
          Search
        </button>
        {q && (
          <button
            type="button"
            onClick={() => { setQ(''); setInputVal(''); setPage(1) }}
            style={{ padding: '7px 12px', fontSize: 13, color: '#6B7280', border: '1px solid #D1D5DB', borderRadius: 7, background: '#fff', cursor: 'pointer' }}
          >
            Clear
          </button>
        )}
      </form>

      {error && <AdminBadge label={error} style="red" />}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['bonID', 'Email', 'Name', 'Tier', 'Billing', 'Entities', 'Staff', 'Joined']}
      >
        {data?.results.map((u) => {
          const statusKey = u.subscription_status || 'no_subscription'
          const statusStyle = STATUS_STYLE[statusKey] || 'gray'
          const statusLabel = STATUS_LABELS[statusKey] || statusKey
          const tierLabel = u.plan_display || planDisplay(u.plan)
          return (
            <tr
              key={u.id}
              onClick={() => navigate(`/admin/users/${u.id}`)}
              style={{ cursor: 'pointer' }}
              className="hover:bg-slate-50"
            >
              <td className="px-4 py-3">
                <span style={{
                  fontFamily: 'monospace',
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#0F1F3D',
                  letterSpacing: '0.04em',
                }}>
                  {u.bon_id || <span style={{ color: '#D1D5DB' }}>—</span>}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-slate-500">{u.email}</td>
              <td className="px-4 py-3 text-sm text-slate-500">
                {[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}
              </td>
              <td className="px-4 py-3 text-sm text-slate-700">{tierLabel}</td>
              <td className="px-4 py-3">
                <AdminBadge label={statusLabel} style={statusStyle} />
              </td>
              <td className="px-4 py-3 text-sm text-center text-slate-500">{u.business_count}</td>
              <td className="px-4 py-3 text-center">
                {u.is_staff && (
                  <span style={{ fontSize: 11, color: '#0F1F3D', fontWeight: 600, background: '#F5A623', padding: '2px 7px', borderRadius: 4 }}>
                    staff
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {new Date(u.date_joined).toLocaleDateString()}
              </td>
            </tr>
          )
        })}
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
