// frontend/src/pages/admin/adminShared.tsx
//
// Shared primitives used across all admin pages:
//   AdminTable  — loading/empty-aware wrapper around <table>
//   AdminBadge  — coloured status badge
//   AdminPager  — simple prev/next pagination
//   useAdminFetch — data fetching hook
//   planDisplay — maps internal plan slugs to operator-facing display names

import { useEffect, useState } from 'react'
import api from '@/api/client'

// ---------------------------------------------------------------------------
// Plan display name mapping
// Internal slugs are never shown to the operator — always use display names.
// ---------------------------------------------------------------------------

const PLAN_DISPLAY_MAP: Record<string, string> = {
  // Legacy slugs
  starter:               'Personal',
  professional:          'Pro',
  business:              'Business',
  anchor:                'Enterprise',
  // Current slugs
  blackboard_basic:      'Personal',
  blackboard_pro:        'Pro',
  blackboard_business:   'Business',
  blackboard_enterprise: 'Enterprise',
  // Special states
  trial:                 'Trial',
  sol_member:            'Sol Member',
  per_contract:          'Pay As You Go',
  no_subscription:       '—',
}

export function planDisplay(slug: string | null | undefined): string {
  if (!slug) return '—'
  return PLAN_DISPLAY_MAP[slug] || slug
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

// ---------------------------------------------------------------------------
// useAdminFetch
// ---------------------------------------------------------------------------

export function useAdminFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api.get<T>(url)
      .then((r) => { if (!cancelled) setData(r.data) })
      .catch((err) => {
        if (!cancelled) {
          const msg = err?.response?.data?.detail || err?.response?.data?.error || 'Failed to load.'
          setError(String(msg))
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [url])

  return { data, loading, error }
}

// ---------------------------------------------------------------------------
// AdminTable
// ---------------------------------------------------------------------------

interface AdminTableProps {
  headers: string[]
  loading: boolean
  empty: boolean
  children: React.ReactNode
}

export function AdminTable({ headers, loading, empty, children }: AdminTableProps) {
  return (
    <div style={{ background: '#fff', borderRadius: 11, border: '1px solid rgba(0,0,0,0.07)', overflow: 'hidden' }}>
      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
          <div style={{ width: 24, height: 24, borderRadius: '50%', border: '3px solid #38BDF8', borderTopColor: 'transparent', animation: 'spin 0.7s linear infinite' }} />
        </div>
      )}
      {!loading && empty && (
        <div style={{ textAlign: 'center', padding: '48px 0', fontSize: 13, color: '#9CA3AF' }}>
          No records found.
        </div>
      )}
      {!loading && !empty && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #F3F4F6' }}>
                {headers.map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: '10px 16px',
                      textAlign: 'left',
                      fontSize: 11,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: '#9CA3AF',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody style={{ divideColor: '#F9FAFB' }}>
              {children}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AdminBadge
// ---------------------------------------------------------------------------

const BADGE_STYLES = {
  green:  { bg: '#ECFDF5', color: '#065F46' },
  red:    { bg: '#FEF2F2', color: '#B91C1C' },
  yellow: { bg: '#FEF9C3', color: '#854D0E' },
  blue:   { bg: '#EFF6FF', color: '#1D4ED8' },
  gray:   { bg: '#F9FAFB', color: '#6B7280' },
  sky:    { bg: '#F0F9FF', color: '#0369A1' },
  navy:   { bg: '#EFF4FF', color: '#3730A3' },
}

export function AdminBadge({
  label,
  style = 'gray',
}: {
  label: string
  style?: keyof typeof BADGE_STYLES
}) {
  const s = BADGE_STYLES[style]
  return (
    <span style={{
      display: 'inline-block',
      fontSize: 11,
      fontWeight: 500,
      padding: '2px 8px',
      borderRadius: 99,
      background: s.bg,
      color: s.color,
    }}>
      {label}
    </span>
  )
}


// ---------------------------------------------------------------------------
// AdminMetricCard
// ---------------------------------------------------------------------------

export function AdminMetricCard({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: number | undefined
  tone?: 'default' | 'blue' | 'green' | 'yellow' | 'red'
}) {
  const colors = {
    default: { bg: '#FFFFFF', border: '#E5E7EB', value: '#0F1F3D' },
    blue: { bg: '#F0F9FF', border: '#BAE6FD', value: '#0369A1' },
    green: { bg: '#ECFDF5', border: '#BBF7D0', value: '#065F46' },
    yellow: { bg: '#FEFCE8', border: '#FEF08A', value: '#854D0E' },
    red: { bg: '#FEF2F2', border: '#FECACA', value: '#B91C1C' },
  }[tone]

  return (
    <div style={{ background: colors.bg, border: `1px solid ${colors.border}`, borderRadius: 12, padding: 14 }}>
      <p style={{ margin: 0, color: '#64748B', fontSize: 11, fontWeight: 800 }}>{label}</p>
      <p style={{ margin: '7px 0 0', color: colors.value, fontSize: 24, fontWeight: 900 }}>
        {value !== undefined ? value.toLocaleString() : '—'}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AdminPager
// ---------------------------------------------------------------------------

interface AdminPagerProps {
  page: number
  pageSize: number
  total: number
  onPage: (p: number) => void
}

export function AdminPager({ page, pageSize, total, onPage }: AdminPagerProps) {
  const totalPages = Math.ceil(total / pageSize)
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  if (totalPages <= 1) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 4px' }}>
      <span style={{ fontSize: 12, color: '#9CA3AF' }}>
        {start}–{end} of {total.toLocaleString()}
      </span>
      <div style={{ display: 'flex', gap: 6 }}>
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          style={{
            padding: '5px 12px', fontSize: 12, borderRadius: 6,
            border: '1px solid #D1D5DB', background: page <= 1 ? '#F9FAFB' : '#fff',
            color: page <= 1 ? '#D1D5DB' : '#374151', cursor: page <= 1 ? 'default' : 'pointer',
          }}
        >
          Prev
        </button>
        <span style={{ fontSize: 12, color: '#6B7280', padding: '5px 4px' }}>
          {page} / {totalPages}
        </span>
        <button
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          style={{
            padding: '5px 12px', fontSize: 12, borderRadius: 6,
            border: '1px solid #D1D5DB', background: page >= totalPages ? '#F9FAFB' : '#fff',
            color: page >= totalPages ? '#D1D5DB' : '#374151', cursor: page >= totalPages ? 'default' : 'pointer',
          }}
        >
          Next
        </button>
      </div>
    </div>
  )
}
