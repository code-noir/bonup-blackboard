// frontend/src/pages/admin/AdminPlans.tsx
// Real data from GET /api/billing/plans/ (existing endpoint — no admin wrapper needed)

import { useAdminFetch, AdminTable } from './adminShared'

interface Plan {
  slug: string
  display_name: string
  price_monthly: string
  price_yearly: string | null
  max_active_contracts: number | null
  max_live_sessions_per_month: number | null
  has_lifecycle: boolean
  has_notifications: boolean
  has_negotiation_prep: boolean
  has_sol: boolean
  has_priority_support: boolean
  has_early_access: boolean
  ai_tier: string
  all_templates: boolean
}

function Flag({ v }: { v: boolean }) {
  return v
    ? <span style={{ color: '#059669', fontWeight: 600 }}>✓</span>
    : <span style={{ color: '#D1D5DB' }}>—</span>
}

export default function AdminPlans() {
  const { data, loading, error } = useAdminFetch<Plan[]>('/billing/plans/')

  const plans = Array.isArray(data) ? data : []

  return (
    <div className="space-y-4">
      {error && <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>}

      <AdminTable
        loading={loading}
        empty={!loading && !error && plans.length === 0}
        headers={['Slug', 'Display Name', '$/mo', '$/yr', 'Contracts', 'Sessions/mo', 'Sol', 'Lifecycle', 'AI Tier', 'All Templates', 'Priority Support']}
      >
        {plans.map((p) => (
          <tr key={p.slug} className="hover:bg-slate-50">
            <td className="px-4 py-3 text-xs font-mono text-slate-500">{p.slug}</td>
            <td className="px-4 py-3 text-sm font-medium text-slate-800">{p.display_name}</td>
            <td className="px-4 py-3 text-sm text-slate-700">${p.price_monthly}</td>
            <td className="px-4 py-3 text-sm text-slate-500">{p.price_yearly ? `$${p.price_yearly}` : '—'}</td>
            <td className="px-4 py-3 text-sm text-slate-500">{p.max_active_contracts ?? '∞'}</td>
            <td className="px-4 py-3 text-sm text-slate-500">{p.max_live_sessions_per_month ?? '∞'}</td>
            <td className="px-4 py-3 text-center"><Flag v={p.has_sol} /></td>
            <td className="px-4 py-3 text-center"><Flag v={p.has_lifecycle} /></td>
            <td className="px-4 py-3 text-xs font-mono text-slate-500">{p.ai_tier}</td>
            <td className="px-4 py-3 text-center"><Flag v={p.all_templates} /></td>
            <td className="px-4 py-3 text-center"><Flag v={p.has_priority_support} /></td>
          </tr>
        ))}
      </AdminTable>
    </div>
  )
}
