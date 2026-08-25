// frontend/src/pages/admin/AdminBilling.tsx
//
// Operator billing overview:
//   - Subscription counts by status (real data from /api/admin/subscriptions/)
//   - Plan roster (real data from /api/billing/plans/)
//   - Links to detailed sub-pages

import { Link } from 'react-router-dom'
import { useAdminFetch, planDisplay } from './adminShared'

interface Sub {
  status: string
}
interface SubPage {
  count: number
  results: Sub[]
}
interface Plan {
  slug: string
  display_name: string
  price_monthly: string
  ai_tier: string
  has_sol: boolean
}

const STATUS_LABELS: Record<string, string> = {
  active:           'Active',
  trialing:         'Trialing',
  per_contract:     'Pay As You Go',
  past_due:         'Past Due',
  cancelled:        'Cancelled',
  no_subscription:  'None',
}

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 10,
      border: '1px solid rgba(0,0,0,0.07)',
      padding: '18px 20px',
    }}>
      <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 26, fontWeight: 700, color: '#0F1F3D', margin: '4px 0 0' }}>{value}</p>
      {sub && <p style={{ fontSize: 11, color: '#9CA3AF', margin: '2px 0 0' }}>{sub}</p>}
    </div>
  )
}

const STATUS_COLORS: Record<string, string> = {
  active:          '#059669',
  trialing:        '#0EA5E9',
  per_contract:    '#059669',
  past_due:        '#D97706',
  cancelled:       '#DC2626',
  no_subscription: '#9CA3AF',
}

export default function AdminBilling() {
  // Fetch up to 200 subs to build status breakdown
  const { data: subData } = useAdminFetch<SubPage>('/admin/subscriptions/?page=1&page_size=200')
  const { data: plans, loading: plansLoading } = useAdminFetch<Plan[]>('/billing/plans/')

  const allSubs = subData?.results ?? []
  const total = subData?.count ?? 0

  // Count by status
  const byStatus: Record<string, number> = {}
  allSubs.forEach((s) => {
    byStatus[s.status] = (byStatus[s.status] || 0) + 1
  })

  return (
    <div className="space-y-6">
      {/* Quick stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
        <StatCard label="Total subscriptions" value={total} />
        {Object.entries(byStatus).sort().map(([status, count]) => (
          <StatCard key={status} label={STATUS_LABELS[status] || status} value={count} />
        ))}
      </div>

      {/* Status breakdown bar (if we have data) */}
      {total > 0 && (
        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid rgba(0,0,0,0.07)', padding: '16px 20px' }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: '#374151', margin: '0 0 12px' }}>Billing status breakdown</p>
          <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', gap: 1 }}>
            {Object.entries(byStatus).map(([status, count]) => (
              <div
                key={status}
                title={`${STATUS_LABELS[status] || status}: ${count}`}
                style={{
                  flex: count,
                  background: STATUS_COLORS[status] || '#D1D5DB',
                }}
              />
            ))}
          </div>
          <div style={{ display: 'flex', gap: 14, marginTop: 10, flexWrap: 'wrap' }}>
            {Object.entries(byStatus).map(([status, count]) => (
              <span key={status} style={{ fontSize: 11, color: '#6B7280', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: STATUS_COLORS[status] || '#D1D5DB', display: 'inline-block' }} />
                {STATUS_LABELS[status] || status} ({count})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Plans roster */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid rgba(0,0,0,0.07)', overflow: 'hidden' }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid #F3F4F6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: '#0F1F3D', margin: 0 }}>Blackbòd Plans</p>
          <Link to="/operator/billing/plans" style={{ fontSize: 12, color: '#0F1F3D', textDecoration: 'none' }}>
            View full feature matrix →
          </Link>
        </div>
        {plansLoading ? (
          <p style={{ padding: '20px', fontSize: 13, color: '#9CA3AF' }}>Loading…</p>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #F3F4F6' }}>
                {['Tier', 'Internal Slug', '$/mo', 'AI Tier', 'Sol'].map((h) => (
                  <th key={h} style={{ padding: '8px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#9CA3AF' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(plans) ? plans : []).map((p) => (
                <tr key={p.slug} className="hover:bg-slate-50">
                  <td style={{ padding: '10px 16px', fontWeight: 600, color: '#111827' }}>{planDisplay(p.slug)}</td>
                  <td style={{ padding: '10px 16px', fontFamily: 'monospace', fontSize: 12, color: '#9CA3AF' }}>{p.slug}</td>
                  <td style={{ padding: '10px 16px', color: '#374151' }}>${p.price_monthly}</td>
                  <td style={{ padding: '10px 16px', fontFamily: 'monospace', fontSize: 12, color: '#6B7280' }}>{p.ai_tier}</td>
                  <td style={{ padding: '10px 16px', color: p.has_sol ? '#059669' : '#D1D5DB', fontWeight: 600 }}>{p.has_sol ? '✓' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Deep-dive links */}
      <div style={{ display: 'flex', gap: 10 }}>
        <Link to="/operator/billing/subscriptions" style={{
          fontSize: 12, fontWeight: 500, color: '#0F1F3D',
          padding: '8px 16px', borderRadius: 7,
          border: '1px solid rgba(0,0,0,0.1)', background: '#fff',
          textDecoration: 'none',
        }}>
          All Subscriptions →
        </Link>
        <Link to="/operator/billing/plans" style={{
          fontSize: 12, fontWeight: 500, color: '#0F1F3D',
          padding: '8px 16px', borderRadius: 7,
          border: '1px solid rgba(0,0,0,0.1)', background: '#fff',
          textDecoration: 'none',
        }}>
          Plan Feature Matrix →
        </Link>
      </div>
    </div>
  )
}
