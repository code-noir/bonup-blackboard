// frontend/src/pages/admin/AdminLayout.tsx
//
// Shared wrapper for all /admin/* pages.
// Navigation is handled entirely by the sidebar (operator mode sidebar).
// This layout provides the operator mode indicator bar at the top + the outlet.

import { Outlet, Link, useLocation } from 'react-router-dom'

const SECTION_LABELS: Record<string, string> = {
  '/admin':               'Dashboard',
  '/admin/users':         'Users',
  '/admin/subscriptions': 'Subscriptions',
  '/admin/plans':         'Plans',
  '/admin/contracts':     'Agreements',
  '/admin/obligations':   'Obligations',
  '/admin/entities':      'Entities',
  '/admin/sol':           'Sol Groups',
  '/admin/activity':      'Activity',
  '/admin/live-sessions': 'Live Sessions',
  '/admin/profile':       'My Profile',
  '/admin/settings':      'Settings',
  '/admin/billing':       'Billing Overview',
}

export default function AdminLayout() {
  const location = useLocation()

  // Match user detail routes like /admin/users/123
  const userDetailMatch = location.pathname.match(/^\/admin\/users\/(\d+)$/)

  const sectionLabel = userDetailMatch
    ? 'User Identity'
    : (SECTION_LABELS[location.pathname] ?? 'Operator Console')

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
            Operator Console
          </span>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'rgba(255,255,255,0.9)' }}>
            {sectionLabel}
          </span>
        </div>

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

      <Outlet />
    </div>
  )
}
