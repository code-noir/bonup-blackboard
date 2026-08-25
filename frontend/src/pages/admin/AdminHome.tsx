// frontend/src/pages/admin/AdminHome.tsx
// Blackbòd operator overview. Real counts fetched from GET /api/admin/summary/
// This page intentionally shows only Blackbòd contract-system metrics.

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '@/api/client'

interface Summary {
  contracts: number
  obligations: number
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

      <div>
        <SectionLabel label="Blackbòd" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
          <MetricCard
            value={summary?.contracts}
            label="Agreements"
            description="Total agreements in system"
            to="/operator/apps/blackbod/agreements"
            icon="📄"
          />
          <MetricCard
            value={summary?.obligations}
            label="Obligations"
            description="Payment and service obligations"
            to="/operator/apps/blackbod/obligations"
            icon="✓"
          />
          <MetricCard
            value={summary?.activity_events}
            label="Activity Events"
            description="Logged contract activity"
            to="/operator/apps/blackbod/activity"
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
        Blackbòd Overview — read-only monitoring for agreements, obligations, and contract activity.
      </div>
    </div>
  )
}
