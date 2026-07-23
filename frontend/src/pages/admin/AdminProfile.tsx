// frontend/src/pages/admin/AdminProfile.tsx
// Real data: GET /api/users/me/ — shows the operator's own account details.

import { useAdminFetch, planDisplay } from './adminShared'

interface Me {
  id: number
  email: string
  first_name: string
  last_name: string
  bon_id?: string
  is_staff: boolean
  date_joined: string
  subscription_tier?: string
  business_count?: number
  city?: string
  state_region?: string
  country?: string
  email_verified?: boolean
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      padding: '12px 0',
      borderBottom: '1px solid #F3F4F6',
      gap: 16,
    }}>
      <span style={{ fontSize: 12, color: '#9CA3AF', width: 160, flexShrink: 0, paddingTop: 1 }}>{label}</span>
      <span style={{ fontSize: 13, color: '#111827', fontWeight: 500 }}>{value ?? '—'}</span>
    </div>
  )
}

export default function AdminProfile() {
  const { data: me, loading, error } = useAdminFetch<Me>('/users/me/')

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
    return <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>
  }

  if (!me) return null

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{
        background: '#fff',
        borderRadius: 11,
        border: '1px solid rgba(0,0,0,0.07)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ background: '#243447', padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 44, height: 44, borderRadius: '50%',
            background: '#F5A623',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, fontWeight: 700, color: '#0F1F3D',
            flexShrink: 0,
          }}>
            {(me.first_name?.[0] || me.email[0]).toUpperCase()}
          </div>
          <div>
            <p style={{ fontSize: 16, fontWeight: 700, color: '#fff', margin: 0 }}>
              {[me.first_name, me.last_name].filter(Boolean).join(' ') || me.email}
            </p>
            <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
              {me.is_staff && (
                <span style={{
                  fontSize: 10, fontWeight: 700,
                  background: '#F5A623', color: '#0F1F3D',
                  padding: '2px 7px', borderRadius: 4, letterSpacing: '0.08em',
                }}>
                  OPERATOR
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Fields */}
        <div style={{ padding: '4px 24px 16px' }}>
          <Row label="bonID" value={
            me.bon_id
              ? <span style={{ fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.06em' }}>{me.bon_id}</span>
              : undefined
          } />
          <Row label="Email" value={me.email} />
          <Row label="Email verified" value={me.email_verified ? 'Yes' : 'No'} />
          <Row label="Location" value={[me.city, me.state_region, me.country].filter(Boolean).join(', ') || undefined} />
          <Row label="Blackboard tier" value={planDisplay(me.subscription_tier)} />
          <Row label="Business entities" value={me.business_count} />
          <Row label="Joined" value={new Date(me.date_joined).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })} />
          <Row label="Staff access" value={me.is_staff ? 'Yes — Operator Console' : 'No'} />
        </div>
      </div>
    </div>
  )
}
