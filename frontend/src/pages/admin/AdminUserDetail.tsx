// frontend/src/pages/admin/AdminUserDetail.tsx
//
// bonID-first identity record for a single bonUP user.
// Real data from GET /api/admin/users/<id>/
// Behaves as an identity record / bonID record, not a generic profile.

import { Link, useParams } from 'react-router-dom'
import { useAdminFetch, planDisplay } from './adminShared'

interface UserDetail {
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
  is_trialing: boolean
  trial_remaining: number | null
  business_count: number
  contract_count: number
}

const STATUS_LABELS: Record<string, string> = {
  active:           'Active',
  trialing:         'Trialing',
  per_contract:     'Pay As You Go',
  past_due:         'Past Due',
  cancelled:        'Cancelled',
  no_subscription:  'None',
}

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  active:          { bg: '#ECFDF5', color: '#065F46' },
  trialing:        { bg: '#F0F9FF', color: '#0369A1' },
  per_contract:    { bg: '#F0FDF4', color: '#15803D' },
  past_due:        { bg: '#FEF9C3', color: '#854D0E' },
  cancelled:       { bg: '#FEF2F2', color: '#B91C1C' },
  no_subscription: { bg: '#F9FAFB', color: '#6B7280' },
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      padding: '11px 0',
      borderBottom: '1px solid #F3F4F6',
      gap: 16,
    }}>
      <span style={{ fontSize: 12, color: '#9CA3AF', width: 160, flexShrink: 0, paddingTop: 1 }}>
        {label}
      </span>
      <span style={{ fontSize: 13, color: '#111827', fontWeight: 500 }}>
        {value ?? <span style={{ color: '#D1D5DB' }}>—</span>}
      </span>
    </div>
  )
}

function SectionHead({ label }: { label: string }) {
  return (
    <p style={{
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      color: '#9CA3AF',
      margin: '20px 0 4px',
    }}>
      {label}
    </p>
  )
}

export default function AdminUserDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: u, loading, error } = useAdminFetch<UserDetail>(`/admin/users/${id}/`)

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <div style={{
          width: 24, height: 24, borderRadius: '50%',
          border: '3px solid #38BDF8', borderTopColor: 'transparent',
          animation: 'spin 0.7s linear infinite',
        }} />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#B91C1C' }}>
        {error}
      </div>
    )
  }

  if (!u) return null

  const displayName = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.email
  const statusKey = u.subscription_status || 'no_subscription'
  const statusLabel = STATUS_LABELS[statusKey] || statusKey
  const statusColor = STATUS_COLORS[statusKey] || STATUS_COLORS.no_subscription
  const tierLabel = u.plan_display || planDisplay(u.plan)

  return (
    <div>
      {/* Back link */}
      <div style={{ marginBottom: 16 }}>
        <Link
          to="/admin/users"
          style={{ fontSize: 12, color: '#6B7280', textDecoration: 'none' }}
        >
          ← Back to Users
        </Link>
      </div>

      <div style={{ maxWidth: 580 }}>
        {/* bonID header card */}
        <div style={{
          background: '#0F1F3D',
          borderRadius: '11px 11px 0 0',
          padding: '24px 28px',
        }}>
          {/* bonID — primary identity anchor */}
          <div style={{ marginBottom: 16 }}>
            <p style={{
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: '0.16em',
              textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.4)',
              margin: '0 0 4px',
            }}>
              bonID
            </p>
            <p style={{
              fontFamily: 'monospace',
              fontSize: 28,
              fontWeight: 700,
              color: '#F5A623',
              margin: 0,
              letterSpacing: '0.1em',
            }}>
              {u.bon_id || '—'}
            </p>
          </div>

          {/* Name row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>{displayName}</span>
            {u.is_staff && (
              <span style={{
                fontSize: 10, fontWeight: 700,
                background: '#F5A623', color: '#0F1F3D',
                padding: '2px 8px', borderRadius: 4, letterSpacing: '0.08em',
              }}>
                OPERATOR
              </span>
            )}
          </div>
        </div>

        {/* Detail card body */}
        <div style={{
          background: '#fff',
          borderRadius: '0 0 11px 11px',
          border: '1px solid rgba(0,0,0,0.07)',
          borderTop: 'none',
          padding: '4px 28px 20px',
        }}>
          <SectionHead label="bonUP Identity" />
          <Row label="bonID" value={
            <span style={{ fontFamily: 'monospace', color: '#0F1F3D', fontWeight: 700 }}>
              {u.bon_id || '—'}
            </span>
          } />
          <Row label="Email" value={u.email} />
          <Row label="Full name" value={
            [u.first_name, u.last_name].filter(Boolean).join(' ') || undefined
          } />
          <Row label="User ID (internal)" value={
            <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#6B7280' }}>{u.id}</span>
          } />
          <Row label="Joined" value={
            new Date(u.date_joined).toLocaleDateString('en-US', {
              year: 'numeric', month: 'long', day: 'numeric',
            })
          } />
          <Row label="Staff access" value={
            u.is_staff
              ? <span style={{ color: '#0F1F3D', fontWeight: 600 }}>Yes — Operator Console</span>
              : 'No'
          } />

          <SectionHead label="Blackboard" />
          <Row label="Tier" value={tierLabel} />
          <Row label="Billing status" value={
            <span style={{
              display: 'inline-block',
              fontSize: 11, fontWeight: 500,
              padding: '2px 9px', borderRadius: 99,
              background: statusColor.bg, color: statusColor.color,
            }}>
              {statusLabel}
            </span>
          } />
          {u.is_trialing && u.trial_remaining !== null && (
            <Row label="Trial contracts left" value={u.trial_remaining} />
          )}

          <SectionHead label="Usage" />
          <Row label="Business entities" value={u.business_count} />
          <Row label="Contracts" value={u.contract_count} />
        </div>
      </div>
    </div>
  )
}
