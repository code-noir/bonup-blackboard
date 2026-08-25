import { Link } from 'react-router-dom'
import { useAdminFetch } from './adminShared'

interface Summary {
  users: number
  plans: number
  subscriptions: number
  sol_groups: number
  entities: number
}

interface OperatorCardProps {
  eyebrow: string
  title: string
  description: string
  to?: string
  count?: number
  disabled?: boolean
}

function OperatorCard({ eyebrow, title, description, to, count, disabled = false }: OperatorCardProps) {
  const content = (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
        <p style={{ margin: 0, color: '#94A3B8', fontSize: 10, fontWeight: 850, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          {eyebrow}
        </p>
        {count !== undefined && (
          <span style={{ color: '#0F1F3D', fontSize: 18, fontWeight: 900 }}>
            {count.toLocaleString()}
          </span>
        )}
        {disabled && (
          <span style={{ borderRadius: 6, background: '#F1F5F9', color: '#64748B', fontSize: 11, fontWeight: 750, padding: '3px 8px' }}>
            Future
          </span>
        )}
      </div>
      <h2 style={{ margin: '8px 0 0', color: '#0F1F3D', fontSize: 18, fontWeight: 900 }}>
        {title}
      </h2>
      <p style={{ margin: '6px 0 0', color: '#64748B', fontSize: 13, lineHeight: 1.5 }}>
        {description}
      </p>
    </>
  )

  const sharedStyle = {
    display: 'block',
    minHeight: 132,
    borderRadius: 12,
    border: '1px solid rgba(15,23,42,0.08)',
    background: disabled ? '#F8FAFC' : '#fff',
    padding: 18,
    textDecoration: 'none',
    opacity: disabled ? 0.74 : 1,
  }

  if (!to || disabled) {
    return <div style={sharedStyle}>{content}</div>
  }

  return (
    <Link
      to={to}
      style={sharedStyle}
      onMouseEnter={(event) => { event.currentTarget.style.boxShadow = '0 10px 24px rgba(15,23,42,0.08)' }}
      onMouseLeave={(event) => { event.currentTarget.style.boxShadow = 'none' }}
    >
      {content}
    </Link>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <p style={{ margin: '0 0 10px', color: '#64748B', fontSize: 11, fontWeight: 850, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
        {title}
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {children}
      </div>
    </section>
  )
}

export default function OperatorHome() {
  const { data: summary, error } = useAdminFetch<Summary>('/admin/summary/')

  return (
    <div className="space-y-6">
      {error && (
        <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#B91C1C' }}>
          {error}
        </div>
      )}

      <section style={{ background: '#243447', color: '#fff', borderRadius: 12, padding: '22px 24px' }}>
        <p style={{ margin: 0, color: '#F5A623', fontSize: 11, fontWeight: 900, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
          bonUP Operator Console
        </p>
        <h1 style={{ margin: '8px 0 0', fontSize: 26, fontWeight: 900 }}>
          Platform Home
        </h1>
        <p style={{ margin: '8px 0 0', color: 'rgba(255,255,255,0.72)', fontSize: 13, maxWidth: 720, lineHeight: 1.6 }}>
          Navigate platform identity, applications, billing, and operational monitoring from one administrator surface.
        </p>
      </section>

      <Section title="Identity">
        <OperatorCard eyebrow="Identity" title="Users" description="bonID-first user records and support inspection." to="/operator/identity/users" count={summary?.users} />
        <OperatorCard eyebrow="Identity" title="Entities" description="Platform business entities connected to operating actors." to="/operator/identity/entities" count={summary?.entities} />
        <OperatorCard eyebrow="Identity" title="Administrators" description="Administrator management is not implemented yet." disabled />
      </Section>

      <Section title="Applications">
        <OperatorCard eyebrow="Blackbòd" title="Overview" description="Agreement, obligation, and contract activity monitoring." to="/operator/apps/blackbod" />
        <OperatorCard eyebrow="Sol" title="Groups" description="Rotating savings group records." to="/operator/apps/sol/groups" count={summary?.sol_groups} />
        <OperatorCard eyebrow="Unfair" title="Future Application" description="No operator application surface is implemented yet." disabled />
      </Section>

      <Section title="Billing">
        <OperatorCard eyebrow="Billing" title="Subscriptions" description="Platform subscription records." to="/operator/billing/subscriptions" count={summary?.subscriptions} />
        <OperatorCard eyebrow="Billing" title="Plans" description="Platform plan definitions and entitlement flags." to="/operator/billing/plans" count={summary?.plans} />
      </Section>

      <Section title="Operations">
        <OperatorCard eyebrow="Operations" title="Live Sessions" description="Operator-wide session monitoring placeholder." to="/operator/operations/live-sessions" />
      </Section>
    </div>
  )
}
