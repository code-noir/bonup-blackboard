// frontend/src/pages/admin/AdminHome.tsx
// Operator dashboard. Real counts fetched from GET /api/admin/summary/
// Separated into bonUP Platform metrics and Blackboard product metrics.

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '@/api/client'

interface Summary {
  users: number
  plans: number
  subscriptions: number
  sol_groups: number
  entities: number
  contracts: number
  activity_events: number
}

function SectionLabel({ label }: { label: string }) {
  return (
    <p style={{
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      color: '#9CA3AF',
      margin: '0 0 10px',
    }}>
      {label}
    </p>
  )
}

function MetricCard({
  value,
  label,
  description,
  to,
  icon,
}: {
  value: number | undefined
  label: string
  description: string
  to: string
  icon: string
}) {
  return (
    <Link
      to={to}
      style={{
        background: '#fff',
        borderRadius: 11,
        padding: '18px 20px 14px',
        border: '1px solid rgba(0,0,0,0.06)',
        textDecoration: 'none',
        display: 'block',
        transition: 'box-shadow 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)')}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
    >
      <div style={{ fontSize: 22, marginBottom: 8 }}>{icon}</div>
      <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF', margin: 0 }}>
        {label}
      </p>
      <p style={{ fontSize: 26, fontWeight: 700, color: '#0F1F3D', margin: '3px 0 4px' }}>
        {value !== undefined ? value.toLocaleString() : '—'}
      </p>
      <p style={{ fontSize: 11, color: '#CBD5E1', margin: 0 }}>{description}</p>
    </Link>
  )
}

export default function AdminHome() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<Summary>('/admin/summary/')
      .then((r) => setSummary(r.data))
      .catch(() => setError('Failed to load summary.'))
  }, [])

  return (
    <div className="space-y-6">
      {error && (
        <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#B91C1C' }}>
          {error}
        </div>
      )}

      {/* bonUP Platform */}
      <div>
        <SectionLabel label="bonUP Platform" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
          <MetricCard
            key="users"
            value={summary?.users}
            label="bonUP Users"
            description="Total registered accounts"
            to="/admin/users"
            icon="👤"
          />
        </div>
      </div>

      {/* Blackboard */}
      <div>
        <SectionLabel label="Blackboard" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
          <MetricCard
            value={summary?.subscriptions}
            label="Subscriptions"
            description="Active Blackboard subscriptions"
            to="/admin/subscriptions"
            icon="💳"
          />
          <MetricCard
            value={summary?.plans}
            label="Plan Types"
            description="Available plan definitions"
            to="/admin/plans"
            icon="📋"
          />
          <MetricCard
            value={summary?.entities}
            label="Entities"
            description="Active business entities"
            to="/admin/entities"
            icon="🏢"
          />
          <MetricCard
            value={summary?.contracts}
            label="Contracts"
            description="Total contracts in system"
            to="/admin/contracts"
            icon="📄"
          />
          <MetricCard
            value={summary?.sol_groups}
            label="Sol Groups"
            description="Total Sol groups"
            to="/admin/sol"
            icon="◎"
          />
          <MetricCard
            value={summary?.activity_events}
            label="Activity Events"
            description="Logged contract activity"
            to="/admin/activity"
            icon="⚡"
          />
        </div>
      </div>

      {/* Phase note */}
      <div style={{
        background: '#F8FAFC',
        border: '1px solid #E2E8F0',
        borderRadius: 8,
        padding: '12px 16px',
        fontSize: 12,
        color: '#64748B',
      }}>
        Operator Console — Phase 1. Read-only monitoring and inspection across all platform data.
        Write operations (plan changes, user management) are coming in Phase 2.
      </div>
    </div>
  )
}
