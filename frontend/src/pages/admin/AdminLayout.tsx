// frontend/src/pages/admin/AdminLayout.tsx
//
// Shared wrapper for bonUP Operator Console pages.
// Navigation is handled entirely by the operator mode sidebar.
// This layout provides the operator mode indicator bar at the top + the outlet.

import { useState } from 'react'
import { useOperator } from '@/context/OperatorContext'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'

const SECTION_LABELS: Record<string, string> = {
  '/operator': 'Home',
  '/operator/identity/users': 'Users',
  '/operator/identity/entities': 'Entities',
  '/operator/apps/blackbod': 'Blackbòd Overview',
  '/operator/apps/blackbod/agreements': 'Agreements',
  '/operator/apps/blackbod/obligations': 'Obligations',
  '/operator/apps/blackbod/activity': 'Activity',
  '/operator/apps/sol/groups': 'Sol Groups',
  '/operator/billing': 'Billing Overview',
  '/operator/billing/subscriptions': 'Subscriptions',
  '/operator/billing/plans': 'Plans',
  '/operator/operations/live-sessions': 'Live Sessions',
  '/operator/profile': 'My Administrator Profile',
  '/operator/settings': 'Settings',
}

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { logoutOperator, sessionNotice } = useOperator()
  const [signingOut, setSigningOut] = useState(false)
  const signOut = async () => {
    setSigningOut(true)
    await logoutOperator()
    navigate('/operator/login', { replace: true })
  }

  // Match user detail routes like /operator/identity/users/123
  const userDetailMatch = location.pathname.match(/^\/operator\/identity\/users\/(\d+)$/)

  const sectionLabel = userDetailMatch
    ? 'User Identity'
    : (SECTION_LABELS[location.pathname] ?? 'bonUP Operator Console')

  return (
    <div>
      {/* Operator mode indicator bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#243447',
        borderRadius: 10,
        padding: '10px 18px',
        marginBottom: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            background: '#F5A623',
            color: '#0F1F3D',
            fontSize: 9,
            fontWeight: 800,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            padding: '3px 9px',
            borderRadius: 4,
          }}>
            bonUP Operator Console
          </span>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'rgba(255,255,255,0.9)' }}>
            {sectionLabel}
          </span>
        </div>

        <button type="button" disabled={signingOut} onClick={signOut} className="rounded bg-white px-4 py-2 text-sm font-semibold text-slate-900 disabled:opacity-50">
          {signingOut ? 'Signing out...' : 'Sign out of Operator Console'}
        </button>
        <Link
          to="/dashboard"
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: '#0F1F3D',
            background: '#F5A623',
            textDecoration: 'none',
            padding: '6px 16px',
            borderRadius: 6,
            letterSpacing: '0.01em',
            transition: 'opacity 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.85' }}
          onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
        >
          Switch to User View →
        </Link>
      </div>

      {sessionNotice && <p role="alert" className="mb-4 rounded bg-amber-50 p-3 text-sm text-amber-900">{sessionNotice}</p>}
      <Outlet />
    </div>
  )
}
