import { type CSSProperties, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/client'

// Tier slugs matching DB: 'trial' | 'sol_member' | 'per_contract' | 'starter' | 'professional' | 'business' | 'anchor'
const USER_TIER = 'business'

// Mock business entities — replace with API data when connected
const MOCK_ENTITIES: { id: string; name: string }[] = []

interface ContractVersionPayload {
  content_snapshot?: string
  prepared_terms?: PreparedTerms | null
  status?: string
}

interface PreparedTerm {
  description?: string
  amount?: string | null
  due_date?: string | null
  deadline?: string | null
}

interface PreparedTerms {
  payment_terms?: PreparedTerm[]
  service_obligations?: PreparedTerm[]
  delivery_obligations?: PreparedTerm[]
  milestones?: PreparedTerm[]
  deadlines?: string[]
  trigger_conditions?: string[]
  extraction_method?: string
}

interface ContractRecord {
  id: string
  title: string
  contract_type?: string
  counterparty_name?: string
  counterparty_email?: string
  entity_type?: string
  entity?: string | null
  status: string
  state?: string
  created_at?: string
  latest_version?: ContractVersionPayload | null
  display_status?: string
  display_status_label?: string
  active_exchange_id?: string | null
  latest_exchange_status?: string | null
  signed_version_id?: string | null
  lifecycle_ready?: boolean
  primary_action?: string
  primary_action_label?: string
  primary_action_url?: string
}

function contractStatusLabel(contract: ContractRecord): string {
  if (contract.display_status_label) return contract.display_status_label
  if (contract.state === 'created') return 'Created'
  if (contract.state === 'prepared') return 'Prepared'
  if (contract.state === 'ready_to_send') return 'Ready to Send'
  if (contract.status === 'draft') return 'Drafting'
  if (contract.status === 'sent') return 'Sent / Awaiting Signature'
  if (contract.status === 'active') return 'Active'
  if (contract.status === 'completed') return 'Completed / Closed'
  if (contract.status === 'archived') return 'Archived'
  return contract.status || 'Created'
}

function statusStyle(label: string): CSSProperties {
  if (label === 'Active' || label === 'Signed') return { background: '#ECFDF5', color: '#047857' }
  if (label === 'Drafting') return { background: '#F8FAFC', color: '#475569' }
  if (label === 'Prepared' || label === 'Ready to Send') return { background: '#E0F2FE', color: '#0369A1' }
  if (label === 'Under Negotiation' || label === 'Sent / Awaiting Signature') return { background: '#FEF3C7', color: '#B45309' }
  if (label === 'Rejected') return { background: '#FEF2F2', color: '#B91C1C' }
  if (label === 'Completed / Closed') return { background: '#EEF2FF', color: '#4F46E5' }
  if (label === 'Archived') return { background: '#F3F4F6', color: '#6B7280' }
  return { background: '#F8FAFC', color: '#475569' }
}

function formatDate(value?: string): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

function preparedTermsFor(contract: ContractRecord): PreparedTerms | null {
  if (contract.latest_version?.prepared_terms) return contract.latest_version.prepared_terms
  const raw = contract.latest_version?.content_snapshot
  if (!raw) return null
  try {
    const snapshot = JSON.parse(raw) as { prepared_terms?: PreparedTerms }
    return snapshot.prepared_terms ?? null
  } catch {
    return null
  }
}

function preparedCount(terms: PreparedTerms | null): number {
  if (!terms) return 0
  return (terms.payment_terms?.length ?? 0)
    + (terms.service_obligations?.length ?? 0)
    + (terms.delivery_obligations?.length ?? 0)
    + (terms.milestones?.length ?? 0)
}

function contractSummary(contract: ContractRecord): string {
  const terms = preparedTermsFor(contract)
  const preparedSnippet = terms?.payment_terms?.[0]?.description
    || terms?.service_obligations?.[0]?.description
    || terms?.delivery_obligations?.[0]?.description
    || terms?.milestones?.[0]?.description
  if (preparedSnippet) return preparedSnippet
  if (contract.counterparty_name || contract.counterparty_email) {
    return `${contract.counterparty_name || contract.counterparty_email} · ${contract.entity_type === 'business' ? 'Business' : 'Personal'} · Created ${formatDate(contract.created_at)}`
  }
  return `${contract.entity_type === 'business' ? 'Business' : 'Personal'} contract record · Created ${formatDate(contract.created_at)}`
}

function contractPhase(contract: ContractRecord): 'draft' | 'negotiation' | 'lifecycle' {
  const state = (contract.state || '').toLowerCase()
  const status = (contract.status || '').toLowerCase()

  if (['created', 'drafting'].includes(state)) return 'draft'
  if (['created', 'draft', 'drafting'].includes(status) && !['prepared', 'ready', 'ready_to_send', 'ready_for_negotiation'].includes(state)) return 'draft'

  if (['prepared', 'ready', 'ready_to_send', 'ready_for_negotiation', 'sent', 'awaiting_signature', 'countered', 'in_negotiation', 'negotiating'].includes(state)) return 'negotiation'
  if (['prepared', 'ready', 'ready_to_send', 'sent', 'awaiting_signature', 'countered', 'in_negotiation', 'negotiating'].includes(status)) return 'negotiation'

  return 'lifecycle'
}

function hasLifecycleAccess(contract: ContractRecord): boolean {
  const state = (contract.state || '').toLowerCase()
  const status = (contract.status || '').toLowerCase()
  return ['signed', 'active', 'completed', 'closed', 'archived'].includes(state)
    || ['signed', 'active', 'completed', 'closed', 'archived'].includes(status)
}

function primaryActionLabel(action?: string): string {
  if (action === 'open_lifecycle') return 'Open Agreement Timeline'
  if (action === 'open_rejected_exchange') return 'Open Exchange'
  if (action === 'open_negotiation') return 'Open Negotiation'
  if (action === 'continue_draft') return 'Continue Draft'
  if (action === 'open_contract') return 'Open'
  return 'Open'
}

function fallbackPrimaryAction(contract: ContractRecord): { label: string; url: string } | null {
  const phase = contractPhase(contract)
  if (phase === 'draft') return { label: 'Open Editor', url: `/contracts/create?id=${contract.id}` }
  if (phase === 'negotiation') return { label: 'Open Negotiation', url: `/negotiation/${contract.id}` }
  if (hasLifecycleAccess(contract)) return { label: 'Open Agreement Timeline', url: `/lifecycle?contract=${contract.id}` }
  return null
}

const actionButtonStyle = (variant: 'primary' | 'secondary' | 'disabled'): CSSProperties => ({
  height: 30,
  padding: '0 11px',
  borderRadius: 7,
  border: variant === 'secondary' ? '1px solid #CBD5E1' : 'none',
  background: variant === 'primary' ? '#0F1F3D' : variant === 'secondary' ? 'white' : '#E5E7EB',
  color: variant === 'primary' ? 'white' : variant === 'secondary' ? '#334155' : '#64748B',
  fontSize: 11,
  fontWeight: 700,
  cursor: variant === 'disabled' ? 'default' : 'pointer',
  whiteSpace: 'nowrap',
})

export default function Dashboard() {
  const navigate = useNavigate()
  const { user, isOnTrial, trialDaysRemaining, hasTrialExpired } = useAuth()
  const isPayg = user?.subscription_tier === 'per_contract'
  const [viewingAs, setViewingAs] = useState<string>('personal')
  const [contracts, setContracts] = useState<ContractRecord[]>([])
  const [contractsLoading, setContractsLoading] = useState(true)
  const [contractsError, setContractsError] = useState('')
  const [returningContractId, setReturningContractId] = useState<string | null>(null)
  const [returnToDraftError, setReturnToDraftError] = useState<{ contractId: string; message: string } | null>(null)

  useEffect(() => {
    let cancelled = false
    setContractsLoading(true)
    api.get<ContractRecord[]>('/contracts/')
      .then(({ data }) => {
        if (!cancelled) {
          setContracts(data)
        }
      })
      .catch(() => {
        if (!cancelled) setContractsError('Unable to load contracts.')
      })
      .finally(() => {
        if (!cancelled) setContractsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const firstName = user?.first_name || 'You'
  const lastName = user?.last_name || ''
  const displayName = [firstName, lastName].filter(Boolean).join(' ')

  const viewingAsLabel = viewingAs === 'personal'
    ? `${displayName} (Personal)`
    : MOCK_ENTITIES.find((e) => e.id === viewingAs)?.name ?? 'Personal'

  async function handleReturnToDraft(contract: ContractRecord) {
    const confirmed = window.confirm('This will move the contract back to draft so you can edit it before sending it for negotiation.')
    if (!confirmed) return

    setReturningContractId(contract.id)
    setReturnToDraftError(null)
    try {
      const { data } = await api.post<{ editor_url?: string }>(`/contracts/${contract.id}/return-to-draft/`, {})
      navigate(data.editor_url || `/contracts/create?id=${contract.id}`)
    } catch (error) {
      const response = error && typeof error === 'object' && 'response' in error
        ? (error as { response?: { data?: { error?: string; detail?: string } } }).response?.data
        : null
      const message = response?.error || response?.detail || 'Return to Draft failed.'
      setReturnToDraftError({ contractId: contract.id, message })
    } finally {
      setReturningContractId(null)
    }
  }

  function canReturnToDraftFromDashboard(_contract: ContractRecord, label: string) {
    return label === 'Prepared'
  }

  return (
    <div className="space-y-6">
      <p style={{ fontSize: 13, color: '#9CA3AF', paddingTop: 14, paddingBottom: 14 }}>
        Here's what's happening across your contracts.
      </p>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Contracts', value: contractsLoading ? '—' : String(contracts.length) },
        ].map(({ label, value }) => (
          <div
            key={label}
            style={{ background: '#fff', borderRadius: 11, padding: '18px 20px', border: '1px solid rgba(0,0,0,0.05)' }}
          >
            <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF' }}>{label}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Viewing as indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12, color: '#6B7280' }}>Viewing as:</span>
        <span style={{ fontSize: 12, color: '#374151', fontWeight: 500 }}>{viewingAsLabel}</span>
        <select
          value={viewingAs}
          onChange={(e) => setViewingAs(e.target.value)}
          style={{
            fontSize: 11, color: '#6B7280', border: '1px solid #E5E7EB',
            borderRadius: 6, padding: '2px 6px', background: 'white',
            cursor: 'pointer', outline: 'none',
          }}
        >
          <option value="personal">Personal</option>
          {MOCK_ENTITIES.map((e) => (
            <option key={e.id} value={e.id}>{e.name}</option>
          ))}
        </select>
      </div>

      {/* Trial banner — active */}
      {isOnTrial() && (() => {
        const days = trialDaysRemaining()
        const pct = Math.min(100, ((30 - days) / 30) * 100)
        return (
          <div style={{
            background: 'linear-gradient(to right, #0F1F3D, #1a3460)',
            borderRadius: 11, padding: '20px 24px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: 'white', margin: 0 }}>
                🎉 Your free trial
              </p>
              <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 4 }}>
                {days} days remaining — Full Blackboard Pro access included
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div>
                <div style={{ width: 200, height: 4, background: 'rgba(255,255,255,0.2)', borderRadius: 2 }}>
                  <div style={{ width: `${pct}%`, height: '100%', background: '#2DD4BF', borderRadius: 2 }} />
                </div>
                <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', marginTop: 4, textAlign: 'right' }}>
                  {days} days left
                </p>
              </div>
              <button
                onClick={() => navigate('/settings')}
                style={{
                  background: '#F5A623', color: '#0F1F3D',
                  border: 'none', borderRadius: 8,
                  padding: '8px 16px', fontSize: 12,
                  fontWeight: 600, cursor: 'pointer',
                  marginLeft: 16,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                Choose a Plan
              </button>
            </div>
          </div>
        )
      })()}

      {/* Trial banner — expired */}
      {hasTrialExpired() && (
        <div style={{
          background: 'rgba(220,38,38,0.08)',
          border: '1px solid rgba(220,38,38,0.2)',
          borderRadius: 11, padding: '16px 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, color: '#DC2626', margin: 0 }}>
              ⚠️ Your trial has ended
            </p>
            <p style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>
              Subscribe to create new contracts. Your existing contracts are safe for 1 year.
            </p>
          </div>
          <button
            onClick={() => navigate('/settings')}
            style={{
              background: '#0F1F3D', color: 'white',
              border: 'none', borderRadius: 8,
              padding: '8px 16px', fontSize: 12,
              fontWeight: 600, cursor: 'pointer',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            Choose a Plan
          </button>
        </div>
      )}

      {/* Sol Member banner */}
      {user?.subscription_tier === 'sol_member' && (
        <div style={{
          background: '#E0F2FE',
          border: '1px solid #BAE6FD',
          borderRadius: 8,
          padding: '12px 16px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <p style={{ fontSize: 13, color: '#075985', margin: 0, fontWeight: 500 }}>
            ◎ Sol Member — Saving with your community. $10/month
          </p>
        </div>
      )}

      {/* Contract Records */}
      <section>
        <h3 className="mb-3 text-base font-semibold text-slate-800">Contract Records</h3>

        {contractsLoading ? (
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" style={{ maxWidth: 520 }}>
            <p className="text-sm text-slate-500">Loading contracts...</p>
          </div>
        ) : contractsError ? (
          <div className="rounded-lg border border-red-100 bg-white p-4 shadow-sm" style={{ maxWidth: 520 }}>
            <p className="text-sm text-red-600">{contractsError}</p>
          </div>
        ) : contracts.length === 0 ? (
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" style={{ maxWidth: 520 }}>
            <p className="text-sm text-slate-500">No contract records yet.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 420px))', gap: 12, justifyContent: 'start' }}>
            {contracts.map((contract) => {
              const label = contractStatusLabel(contract)
              const summary = contractSummary(contract)
              const fallbackAction = fallbackPrimaryAction(contract)
              const primaryUrl = contract.primary_action_url || fallbackAction?.url
              const primaryLabel = contract.primary_action_label
                || (contract.primary_action ? primaryActionLabel(contract.primary_action) : fallbackAction?.label)
              const canReturnToDraft = canReturnToDraftFromDashboard(contract, label)

              return (
                <article
                  key={contract.id}
                  className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                  style={{ maxWidth: 420 }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
                    <p style={{ fontSize: 14, fontWeight: 700, color: '#0F1F3D', margin: 0, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {contract.title || 'Untitled Contract'}
                    </p>
                    <span style={{ flexShrink: 0, borderRadius: 999, padding: '4px 9px', fontSize: 11, fontWeight: 700, ...statusStyle(label) }}>
                      {label}
                    </span>
                  </div>

                  <p style={{ fontSize: 11, color: '#94A3B8', margin: '6px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {contract.contract_type || 'Contract'} · Created {formatDate(contract.created_at)}
                  </p>

                  <p style={{
                    fontSize: 12,
                    color: '#64748B',
                    margin: '10px 0 14px',
                    lineHeight: 1.45,
                    overflow: 'hidden',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}>
                    {summary}
                  </p>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={() => navigate(`/contracts/${contract.id}`)}
                      style={actionButtonStyle('secondary')}
                    >
                      Contract Summary
                    </button>

                    <button
                      type="button"
                      onClick={() => navigate(`/contracts/${contract.id}/view`)}
                      style={actionButtonStyle('secondary')}
                    >
                      View Contract
                    </button>

                    {canReturnToDraft && (
                      <button
                        type="button"
                        onClick={() => void handleReturnToDraft(contract)}
                        disabled={returningContractId === contract.id}
                        style={actionButtonStyle('secondary')}
                      >
                        {returningContractId === contract.id ? 'Returning...' : 'Return to Draft'}
                      </button>
                    )}

                    {primaryUrl && primaryLabel && (
                      <button
                        type="button"
                        onClick={() => navigate(primaryUrl)}
                        style={actionButtonStyle('primary')}
                      >
                        {primaryLabel}
                      </button>
                    )}
                  </div>
                  {returnToDraftError?.contractId === contract.id && (
                    <p style={{ margin: '10px 0 0', color: '#B91C1C', fontSize: 12, lineHeight: 1.4 }}>
                      {returnToDraftError.message}
                    </p>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </section>

      {/* Power Tools */}
      <div>
        <p style={{ fontSize: 14, fontWeight: 600, color: '#0F1F3D', marginBottom: 14 }}>Power Tools</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
          {[
            {
              icon: '🔍',
              title: 'Analyze a Contract',
              description: 'Get a full AI-powered breakdown of any contract before you sign.',
              action: 'Analyze a Contract',
              onClick: () => navigate('/analysis'),
              available: true,
              badge: isPayg ? '$25 per contract · analysis & counter included' : '',
            },
            {
              icon: '⚡',
              title: 'Counter a Contract',
              description: 'Respond to any contract with a professional AI-powered counter.',
              action: USER_TIER === 'starter' || USER_TIER === 'sol_member'
                ? 'Upgrade to Blackboard Pro — $149/month'
                : 'Counter a Contract',
              onClick: () => navigate('/counter'),
              available: true,
              badge: isPayg ? '$25 per contract · analysis & counter included' : '',
            },
            {
              icon: '🤝',
              title: 'Negotiation',
              description: 'Review prepared contracts and negotiation activity.',
              action: 'Open Negotiation',
              onClick: () => navigate('/negotiation'),
              available: true,
              badge: '',
            },
            {
              icon: '📈',
              title: 'Agreement Timeline',
              description: 'Review signed agreement activity, to-dos, due dates, services, and payments.',
              action: 'Agreement Timeline',
              onClick: () => navigate('/lifecycle'),
              available: true,
              badge: '',
            },
          ].map((tool) => (
            <div
              key={tool.title}
              style={{
                background: 'white', borderRadius: 8, padding: 20,
                border: '1px solid rgba(0,0,0,0.05)',
              }}
            >
              <div style={{ fontSize: 24, marginBottom: 8 }}>{tool.icon}</div>
              <p style={{ fontSize: 14, fontWeight: 600, color: '#0F1F3D', margin: 0 }}>{tool.title}</p>
              <p style={{ fontSize: 12, color: '#6B7280', margin: '8px 0 16px', minHeight: 48 }}>
                {tool.description}
              </p>
              {tool.badge && (
                <div style={{ marginBottom: 12 }}>
                  <span style={{
                    display: 'inline-block', fontSize: 11, color: '#065F46',
                    background: '#ECFDF5', borderRadius: 4, padding: '2px 8px',
                  }}>
                    ✓ {tool.badge}
                  </span>
                </div>
              )}
              <button
                onClick={tool.available ? tool.onClick : undefined}
                disabled={!tool.available}
                style={{
                  display: 'block', height: 32, padding: '0 16px',
                  background: tool.available ? '#0F1F3D' : '#E5E7EB',
                  color: tool.available ? 'white' : '#64748B',
                  border: 'none', borderRadius: 8,
                  fontSize: 12, fontWeight: 600,
                  cursor: tool.available ? 'pointer' : 'default',
                }}
                onMouseEnter={(e) => { if (tool.available) e.currentTarget.style.opacity = '0.85' }}
                onMouseLeave={(e) => { if (tool.available) e.currentTarget.style.opacity = '1' }}
              >
                {tool.action}
              </button>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
