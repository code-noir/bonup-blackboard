// src/pages/ContractDetail.tsx
// Contract detail / editor page — reached at /contracts/:id

import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import api from '@/api/client'
import { useAuth } from '@/context/AuthContext'

// ── Types ────────────────────────────────────────────────────────────────────

interface ContractData {
  id: string
  title: string
  contract_type: string
  language: string
  start_date: string | null
  end_date: string | null
  contract_value: string | null
  currency: string
  description: string
  jurisdiction: string
  governing_law: string
  confidentiality: string
  dispute_resolution: string
  counterparty_name: string
  counterparty_email: string
  structure_type: string
  entity_type: 'personal' | 'business'
  entity: string | null
  status: string
  version: number
  state: string
  created_at: string
}

// ── Design tokens ─────────────────────────────────────────────────────────────

const NAVY = '#1C2B3A'
const AMBER = '#F5A623'
const BG = '#ECEEF2'

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(d: string | null): string {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    })
  } catch { return d }
}

function statusColor(s: string): { background: string; color: string } {
  switch (s.toUpperCase()) {
    case 'DRAFT':    return { background: 'rgba(107,114,128,0.12)', color: '#6B7280' }
    case 'SENT':     return { background: 'rgba(245,166,35,0.15)', color: '#D4900A' }
    case 'ACTIVE':   return { background: 'rgba(16,185,129,0.12)', color: '#059669' }
    case 'COMPLETED': return { background: 'rgba(99,102,241,0.12)', color: '#6366F1' }
    case 'ARCHIVED': return { background: 'rgba(107,114,128,0.1)', color: '#9CA3AF' }
    default:         return { background: 'rgba(107,114,128,0.12)', color: '#6B7280' }
  }
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function Section({
  title,
  children,
  last,
}: {
  title: string
  children: React.ReactNode
  last?: boolean
}) {
  return (
    <div style={{
      padding: '22px 28px',
      borderBottom: last ? 'none' : '1px solid #F0F2F5',
    }}>
      <div style={{
        fontSize: 10, fontWeight: 700, letterSpacing: '1.3px',
        textTransform: 'uppercase', color: '#B0BAC8', marginBottom: 16,
        fontFamily: "'Outfit', sans-serif",
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function Row2({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
      {children}
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: '0.8px',
        textTransform: 'uppercase', color: '#B0BAC8',
        fontFamily: "'Outfit', sans-serif", marginBottom: 4,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 13, color: value === '—' ? '#C0CAD6' : NAVY,
        fontFamily: "'Outfit', sans-serif", lineHeight: 1.5,
      }}>
        {value || '—'}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ContractDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()

  // entity context passed from NewContract via navigation state
  const locationState = location.state as { entityName?: string; entityType?: string } | null
  const stateEntityName = locationState?.entityName ?? null

  const [contract, setContract] = useState<ContractData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.get<ContractData>(`/contracts/${id}/`)
      .then(({ data }) => setContract(data))
      .catch(() => setError('Contract not found or you do not have access.'))
      .finally(() => setLoading(false))
  }, [id])

  function handleBack() {
    navigate('/contracts')
  }

  // ── Loading ──

  if (loading) {
    return (
      <div style={{
        fontFamily: "'Outfit', sans-serif", background: BG,
        minHeight: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <p style={{ fontSize: 13, color: '#9CA3AF' }}>Loading contract…</p>
      </div>
    )
  }

  if (error || !contract) {
    return (
      <div style={{
        fontFamily: "'Outfit', sans-serif", background: BG,
        minHeight: '100vh', padding: '40px 20px',
      }}>
        <div style={{ maxWidth: 620, margin: '0 auto' }}>
          <p style={{ fontSize: 13, color: '#DC2626' }}>{error || 'Contract not found.'}</p>
          <button
            onClick={handleBack}
            style={{ marginTop: 16, fontSize: 13, color: '#6B7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            ← Back to contracts
          </button>
        </div>
      </div>
    )
  }

  const sc = statusColor(contract.status)
  const displayTitle = contract.title || `Contract #${contract.id.slice(-8).toUpperCase()}`
  const valueDisplay = contract.contract_value
    ? `${contract.currency} ${Number(contract.contract_value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
    : '—'

  const isPersonal = contract.entity_type === 'personal'
  const entityDisplayName = isPersonal
    ? ([user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'Personal')
    : (stateEntityName ?? 'Business')

  return (
    <div style={{
      fontFamily: "'Outfit', sans-serif",
      background: BG, minHeight: '100vh', padding: '40px 20px',
    }}>
      <div style={{ maxWidth: 780, margin: '0 auto' }}>

        {/* ── Back link ── */}
        <button
          onClick={handleBack}
          style={{
            fontSize: 12, color: '#8892A0',
            background: 'none', border: 'none', cursor: 'pointer',
            padding: 0, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 6,
            fontFamily: "'Outfit', sans-serif",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = NAVY)}
          onMouseLeave={(e) => (e.currentTarget.style.color = '#8892A0')}
        >
          ← Back to contracts
        </button>

        {/* ── Entity indicator ── */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: isPersonal ? 'rgba(15,31,61,0.05)' : 'rgba(245,166,35,0.1)',
          borderRadius: 8, padding: '7px 14px', marginBottom: 16,
        }}>
          <span style={{
            fontSize: 13, fontWeight: 600,
            color: isPersonal ? NAVY : '#D4900A',
            fontFamily: "'Outfit', sans-serif",
          }}>
            {entityDisplayName}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: isPersonal ? '#6B7280' : '#D4900A',
            fontFamily: "'Outfit', sans-serif",
          }}>
            {isPersonal ? 'Personal' : 'Business'}
          </span>
        </div>

        {/* ── Header ── */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
            <h1 style={{
              fontSize: 24, fontWeight: 700, color: NAVY,
              letterSpacing: '-0.4px', margin: 0, flex: 1,
              fontFamily: "'Outfit', sans-serif",
            }}>
              {displayTitle}
            </h1>
            <span style={{
              ...sc,
              display: 'inline-flex', alignItems: 'center',
              borderRadius: 20, padding: '4px 14px',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
              textTransform: 'uppercase',
              fontFamily: "'Outfit', sans-serif",
              flexShrink: 0, marginTop: 4,
            }}>
              {contract.status}
            </span>
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 16, marginTop: 8, flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 12, color: '#8892A0', fontFamily: "'Outfit', sans-serif" }}>
              {contract.contract_type || 'Contract'} · v{contract.version}
            </span>
            <span style={{ fontSize: 12, color: '#8892A0', fontFamily: "'Outfit', sans-serif" }}>
              Created {formatDate(contract.created_at)}
            </span>
          </div>
        </div>

        {/* ── Parties ── */}
        <div style={{
          background: '#fff', borderRadius: 18, border: '1px solid #E2E5EB',
          overflow: 'hidden', marginBottom: 12,
        }}>
          <Section title="Parties">
            <Row2>
              <Field
                label="Counterparty"
                value={contract.counterparty_name || '—'}
              />
              <Field
                label="Counterparty Email"
                value={
                  contract.counterparty_email === 'pending@bonup.placeholder'
                    ? 'Not yet provided'
                    : contract.counterparty_email
                }
              />
            </Row2>
          </Section>
        </div>

        {/* ── Contract details ── */}
        <div style={{
          background: '#fff', borderRadius: 18, border: '1px solid #E2E5EB',
          overflow: 'hidden', marginBottom: 12,
        }}>
          <Section title="Contract basics">
            <Row2>
              <Field label="Contract type" value={contract.contract_type || '—'} />
              <Field label="Language" value={contract.language || '—'} />
            </Row2>
            {contract.description && (
              <div style={{ marginTop: 16 }}>
                <div style={{
                  fontSize: 10, fontWeight: 600, letterSpacing: '0.8px',
                  textTransform: 'uppercase', color: '#B0BAC8',
                  fontFamily: "'Outfit', sans-serif", marginBottom: 6,
                }}>Description</div>
                <div style={{
                  fontSize: 13, color: NAVY, lineHeight: 1.6,
                  fontFamily: "'Outfit', sans-serif",
                  background: '#F7F8FA', borderRadius: 9,
                  padding: '12px 14px',
                }}>
                  {contract.description}
                </div>
              </div>
            )}
          </Section>

          <Section title="Timeline &amp; Value">
            <Row2>
              <Field label="Proposed start" value={formatDate(contract.start_date)} />
              <Field label="Proposed end" value={formatDate(contract.end_date)} />
            </Row2>
            <div style={{ marginTop: 16 }}>
              <Field label="Contract value" value={valueDisplay} />
            </div>
          </Section>

          {(contract.jurisdiction || contract.governing_law || contract.confidentiality || contract.dispute_resolution) && (
            <Section title="Legal terms" last>
              <Row2>
                <Field label="Jurisdiction" value={contract.jurisdiction || '—'} />
                <Field label="Governing law" value={contract.governing_law || '—'} />
              </Row2>
              <div style={{ marginTop: 16 }}>
                <Row2>
                  <Field label="Confidentiality" value={contract.confidentiality || '—'} />
                  <Field label="Dispute resolution" value={contract.dispute_resolution || '—'} />
                </Row2>
              </div>
            </Section>
          )}

          {!(contract.jurisdiction || contract.governing_law || contract.confidentiality || contract.dispute_resolution) && (
            <Section title="Legal terms" last>
              <p style={{ fontSize: 12, color: '#C0CAD6', margin: 0, fontFamily: "'Outfit', sans-serif" }}>
                No legal terms specified.
              </p>
            </Section>
          )}
        </div>

        {/* ── State / metadata ── */}
        <div style={{
          background: '#fff', borderRadius: 18, border: '1px solid #E2E5EB',
          padding: '20px 28px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 20, height: 20, borderRadius: '50%',
              background: NAVY, color: AMBER,
              fontSize: 11, fontWeight: 800,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, fontFamily: "'Outfit', sans-serif",
            }}>i</div>
            <p style={{ fontSize: 12, color: '#6A7585', lineHeight: 1.6, margin: 0, fontFamily: "'Outfit', sans-serif" }}>
              This contract is saved as{' '}
              <strong style={{ color: NAVY }}>{contract.status} · Version {contract.version}</strong>.
              The other party sees nothing until you send it.
            </p>
          </div>
        </div>

      </div>
    </div>
  )
}
