// frontend/src/pages/admin/AdminSubscriptions.tsx
// Real data from GET /api/admin/subscriptions/
// Shows Blackboard tier display names (Personal/Pro/Business/Enterprise) — not raw slugs.

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AdminTable, AdminBadge, AdminPager, useAdminFetch, planDisplay } from './adminShared'

interface Sub {
  id: number
  user_id: number
  plan: string
  plan_display: string
  status: string
  billing_period: string
  contracts_used: number
  sessions_used: number
  is_trialing: boolean
  trial_remaining: number
  current_period_start: string
  stripe_customer_id: string | null
}

interface Page {
  count: number
  page: number
  page_size: number
  results: Sub[]
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

const STATUS_FILTERS = [
  { value: '',                label: 'All' },
  { value: 'active',          label: 'Active' },
  { value: 'trialing',        label: 'Trialing' },
  { value: 'per_contract',    label: 'Pay As You Go' },
  { value: 'past_due',        label: 'Past Due' },
  { value: 'cancelled',       label: 'Cancelled' },
  { value: 'no_subscription', label: 'None' },
]

export default function AdminSubscriptions() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')

  const url = `/admin/subscriptions/?page=${page}${statusFilter ? `&status=${statusFilter}` : ''}`
  const { data, loading, error } = useAdminFetch<Page>(url)

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ fontSize: 12, color: '#6B7280' }}>Filter by billing:</label>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            style={{ fontSize: 12, padding: '5px 10px', border: '1px solid #D1D5DB', borderRadius: 6, background: '#fff' }}
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </div>
        <Link
          to="/operator/billing"
          style={{ fontSize: 12, color: '#0F1F3D', textDecoration: 'none', padding: '5px 12px', border: '1px solid #E2E8F0', borderRadius: 6 }}
        >
          Billing Overview →
        </Link>
      </div>

      {error && <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>}

      <AdminTable
        loading={loading}
        empty={!loading && !error && (data?.results.length === 0)}
        headers={['ID', 'User', 'Tier', 'Billing', 'Period', 'Contracts Used', 'Sessions Used', 'Trial Left', 'Period Start', 'Stripe']}
      >
        {data?.results.map((s) => {
          const statusKey = s.status
          const tierLabel = s.plan_display || planDisplay(s.plan)
          const statusLabel = STATUS_LABELS[statusKey] || statusKey
          return (
            <tr key={s.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 text-xs font-mono text-slate-400">{s.id}</td>
              <td className="px-4 py-3 text-sm font-mono text-slate-500">{s.user_id}</td>
              <td className="px-4 py-3 text-sm text-slate-700">{tierLabel}</td>
              <td className="px-4 py-3">
                <AdminBadge label={statusLabel} style={STATUS_STYLE[statusKey] || 'gray'} />
              </td>
              <td className="px-4 py-3 text-xs text-slate-500">{s.billing_period}</td>
              <td className="px-4 py-3 text-sm text-center text-slate-600">{s.contracts_used}</td>
              <td className="px-4 py-3 text-sm text-center text-slate-600">{s.sessions_used}</td>
              <td className="px-4 py-3 text-sm text-center text-slate-500">
                {s.is_trialing ? s.trial_remaining : '—'}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {s.current_period_start ? new Date(s.current_period_start).toLocaleDateString() : '—'}
              </td>
              <td className="px-4 py-3 text-xs font-mono text-slate-400">
                {s.stripe_customer_id ? (
                  <span title={s.stripe_customer_id}>{s.stripe_customer_id.slice(0, 14)}…</span>
                ) : (
                  <span style={{ color: '#D1D5DB' }}>—</span>
                )}
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
