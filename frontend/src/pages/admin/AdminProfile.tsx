// frontend/src/pages/admin/AdminProfile.tsx
// Real data: GET /api/operator/me/ — shows the AdministratorAccount details.

import { useAdminFetch } from './adminShared'

interface AdminMeResponse {
  operator: AdministratorMe
}

interface AdministratorMe {
  id: number
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  is_super_admin: boolean
  can_view_as_user: boolean
  is_legacy_placeholder: boolean
  user_id?: number | null
  bon_id?: string | null
  last_login_at?: string | null
  created_at?: string
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
  const { data, loading, error } = useAdminFetch<AdminMeResponse>('/operator/me/')
  const me = data?.operator

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

  const createdAt = me.created_at
    ? new Date(me.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : undefined
  const lastLoginAt = me.last_login_at
    ? new Date(me.last_login_at).toLocaleString('en-US')
    : undefined

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{
        background: '#fff',
        borderRadius: 11,
        border: '1px solid rgba(0,0,0,0.07)',
        overflow: 'hidden',
      }}>
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
              <span style={{
                fontSize: 10, fontWeight: 700,
                background: '#F5A623', color: '#0F1F3D',
                padding: '2px 7px', borderRadius: 4, letterSpacing: '0.08em',
              }}>
                ADMINISTRATOR
              </span>
              {me.is_super_admin && (
                <span style={{
                  fontSize: 10, fontWeight: 700,
                  background: '#E0F2FE', color: '#075985',
                  padding: '2px 7px', borderRadius: 4, letterSpacing: '0.08em',
                }}>
                  SUPER ADMIN
                </span>
              )}
            </div>
          </div>
        </div>

        <div style={{ padding: '4px 24px 16px' }}>
          <Row label="bonID" value={me.bon_id || '—'} />
          <Row label="Administrator email" value={me.email} />
          <Row label="Status" value={me.is_active ? 'Active' : 'Inactive'} />
          <Row label="Super administrator" value={me.is_super_admin ? 'Yes' : 'No'} />
          <Row label="View-As access" value={me.can_view_as_user ? 'Yes' : 'No'} />
          <Row label="Last login" value={lastLoginAt} />
          <Row label="Created" value={createdAt} />
        </div>
      </div>
    </div>
  )
}
