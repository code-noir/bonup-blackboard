import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '@/api/client'
import type { BusinessEntity } from '@/types/entities'
import { useAuth } from '@/context/AuthContext'

const STATUS_STYLES: Record<string, { background: string; color: string }> = {
  ACTIVE:    { background: '#0F1F3D', color: '#FFFFFF' },
  PENDING:   { background: '#F59E0B', color: '#1F2937' },
  OVERDUE:   { background: '#EF4444', color: '#FFFFFF' },
  COMPLETED: { background: '#9CA3AF', color: '#FFFFFF' },
}

const STATUS_DARK: Record<string, { background: string; color: string }> = {
  DRAFT:     { background: 'rgba(107,114,128,0.15)', color: '#6B7280' },
  ACTIVE:    { background: 'rgba(255,255,255,0.15)', color: '#ffffff' },
  PENDING:   { background: '#F5A623',                color: '#0F1F3D' },
  OVERDUE:   { background: '#DC2626',                color: '#ffffff' },
  COMPLETED: { background: 'rgba(255,255,255,0.1)',  color: 'rgba(255,255,255,0.6)' },
  SENT:      { background: 'rgba(245,166,35,0.2)',   color: '#F5A623' },
  ARCHIVED:  { background: 'rgba(107,114,128,0.1)',  color: '#9CA3AF' },
}

const TH_DARK: React.CSSProperties = {
  fontSize: 11,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: '#9CA3AF',
  fontWeight: 500,
  padding: '0 12px 8px 0',
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

const TD_DARK: React.CSSProperties = {
  fontSize: 13,
  color: '#374151',
  padding: '8px 12px 8px 0',
}

interface ContractRow { id: string; title: string; party: string; status: string; version: string; createdAt: string }

function stateToStatus(state: string): string {
  if (state === 'fulfilled') return 'COMPLETED'
  if (state === 'at_risk') return 'OVERDUE'
  return 'ACTIVE'
}

function structureLabel(type: string): string {
  const map: Record<string, string> = {
    ONE_TIME: 'One-Time',
    ONGOING: 'Ongoing',
    COLLABORATIVE: 'Collaborative',
    RESOLUTION: 'Resolution',
  }
  return map[type] ?? type
}

const CARD: React.CSSProperties = {
  background: '#fff',
  borderRadius: 11,
  border: '1px solid rgba(0,0,0,0.05)',
}

const TH: React.CSSProperties = {
  fontSize: 11,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: '#9CA3AF',
  fontWeight: 500,
  padding: '0 12px 12px 0',
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

const TD: React.CSSProperties = {
  fontSize: 13,
  color: '#374151',
  padding: '13px 12px 13px 0',
}

function ContractContextBar({
  entityFilter,
  displayName,
  entities,
  onSelect,
}: {
  entityFilter: string
  displayName: string
  entities: BusinessEntity[]
  onSelect: (name: string) => void
}) {
  const isPersonal = entityFilter === 'Personal' || entityFilter === displayName
  const viewingName = isPersonal ? displayName : entityFilter

  const allEntities = [
    { name: displayName, personal: true },
    ...entities.map((e) => ({ name: e.name, personal: false })),
  ]

  return (
    <div style={{
      position: 'fixed',
      top: 158,
      left: 'var(--sidebar-w, 216px)',
      right: 0,
      height: 44,
      background: '#ffffff',
      borderBottom: '1px solid #E5E7EB',
      display: 'flex',
      alignItems: 'center',
      paddingLeft: 20,
      paddingRight: 20,
      zIndex: 25,
    }}>
      {/* LEFT: Viewing as */}
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flexShrink: 0, marginRight: 16 }}>
        <span style={{
          fontSize: 9, color: '#6B7280', textTransform: 'uppercase',
          letterSpacing: '0.08em', fontFamily: "'Outfit', sans-serif",
        }}>
          Viewing as
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
          <span style={{
            fontSize: 13, fontWeight: 700, color: '#0F1F3D',
            fontFamily: "'Outfit', sans-serif", whiteSpace: 'nowrap',
          }}>
            {viewingName}
          </span>
          <span style={{
            fontSize: 9, fontWeight: 500, fontFamily: "'Outfit', sans-serif",
            padding: '1px 5px', borderRadius: 3,
            color: '#10B981',
            background: 'rgba(16,185,129,0.12)',
          }}>
            {isPersonal ? 'Personal' : 'Business'}
          </span>
        </div>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 24, background: '#E5E7EB', flexShrink: 0, marginRight: 16 }} />

      {/* CENTER: Entity switcher — absolutely centered in the bar */}
      <div style={{
        position: 'absolute', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', alignItems: 'center',
        pointerEvents: 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', pointerEvents: 'auto' }}>
          {allEntities.map((entity, i) => {
            const active = entity.personal
              ? (entityFilter === 'Personal' || entityFilter === displayName)
              : entityFilter === entity.name
            return (
              <span key={entity.name} style={{ display: 'inline-flex', alignItems: 'center' }}>
                {i > 0 && (
                  <span style={{
                    color: '#D1D5DB', padding: '0 10px', fontSize: 13,
                    userSelect: 'none', lineHeight: 1,
                  }}>|</span>
                )}
                <span
                  onClick={() => onSelect(entity.personal ? 'Personal' : entity.name)}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5,
                    fontSize: 13, fontWeight: active ? 600 : 400,
                    color: active ? '#0F1F3D' : '#6B7280',
                    cursor: 'pointer', userSelect: 'none',
                    fontFamily: "'Outfit', sans-serif",
                    transition: 'color 0.15s',
                  }}
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = '#374151' }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = '#6B7280' }}
                >
                  {active && (
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%',
                      background: '#10B981', display: 'inline-block', flexShrink: 0,
                    }} />
                  )}
                  {entity.name}
                </span>
              </span>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function Contracts() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState(0)
  const initialEntity = (location.state as { entityFilter?: string } | null)?.entityFilter ?? 'Personal'
  const [entityFilter, setEntityFilter] = useState(initialEntity)
  const [contracts, setContracts] = useState<ContractRow[]>([])
  const [contractsLoading, setContractsLoading] = useState(false)
  const [entities, setEntities] = useState<BusinessEntity[]>([])
  const [showEntityModal, setShowEntityModal] = useState(false)
  const [bizDropdownOpen, setBizDropdownOpen] = useState(false)
  const bizDropdownRef = useRef<HTMLDivElement>(null)

  // Contract Details modal state
  const [showDetailsModal, setShowDetailsModal] = useState(false)
  const [cdEntityLabel, setCdEntityLabel] = useState('')
  const [cdEntityId, setCdEntityId] = useState<string | null>(null)
  const [cdTitle, setCdTitle] = useState('')
  const [cdType, setCdType] = useState('')
  const [cdLanguage, setCdLanguage] = useState('English')
  const [cdStartDate, setCdStartDate] = useState('')
  const [cdEndDate, setCdEndDate] = useState('')
  const [cdValue, setCdValue] = useState('')
  const [cdCurrency, setCdCurrency] = useState('USD')
  const [cdJurisdiction, setCdJurisdiction] = useState('')
  const [cdGoverningLaw, setCdGoverningLaw] = useState('')
  const [cdConfidentiality, setCdConfidentiality] = useState('Not confidential')
  const [cdDispute, setCdDispute] = useState('Negotiation')
  const [cdDescription, setCdDescription] = useState('')
  const [cdTitleError, setCdTitleError] = useState(false)
  const [cdTypeError, setCdTypeError] = useState(false)
  const [cdLoading, setCdLoading] = useState(false)
  const [cdError, setCdError] = useState('')

  function openDetailsModal(entityLabel: string, entityId: string | null = null) {
    setCdEntityLabel(entityLabel)
    setCdEntityId(entityId)
    setCdTitle('')
    setCdType('')
    setCdLanguage('English')
    setCdStartDate('')
    setCdEndDate('')
    setCdValue('')
    setCdCurrency('USD')
    setCdJurisdiction('')
    setCdGoverningLaw('')
    setCdConfidentiality('Not confidential')
    setCdDispute('Negotiation')
    setCdDescription('')
    setCdTitleError(false)
    setCdTypeError(false)
    setCdError('')
    setShowDetailsModal(true)
  }

  function handleCreateContract() {
    let hasError = false
    if (!cdTitle.trim()) { setCdTitleError(true); hasError = true }
    if (!cdType) { setCdTypeError(true); hasError = true }
    if (hasError) return

    setCdLoading(true)
    setCdError('')

    const structureType =
      cdType === 'Employment Contract' ? 'ONGOING' :
      cdType === 'Partnership Agreement' || cdType === 'Joint Venture' ? 'COLLABORATIVE' :
      cdType === 'Settlement Agreement' ? 'RESOLUTION' : 'ONE_TIME'

    const isPersonal = cdEntityLabel === 'Personal'
    api.post<{ id: string }>('/contracts/', {
      title: cdTitle.trim(),
      contract_type: cdType,
      language: cdLanguage || 'English',
      start_date: cdStartDate || null,
      end_date: cdEndDate || null,
      contract_value: cdValue ? cdValue : null,
      jurisdiction: cdJurisdiction,
      governing_law: cdGoverningLaw,
      confidentiality: cdConfidentiality,
      dispute_resolution: cdDispute,
      description: cdDescription,
      counterparty_email: 'pending@bonup.placeholder',
      structure_type: structureType,
      currency: cdCurrency || 'USD',
      entity_type: isPersonal ? 'personal' : 'business',
      ...(isPersonal ? {} : { entity: cdEntityId }),
    })
      .then(({ data }) => {
        // Verify all fields saved correctly
        api.get(`/contracts/${data.id}/`).then(({ data: full }) => {
          console.log('[Contract created] full response:', full)
        })
        setShowDetailsModal(false)
        // Navigate back to contracts list with entity pre-selected
        navigate('/contracts', {
          state: { entityFilter: cdEntityLabel },
        })
      })
      .catch((err) => {
        const msg = err?.response?.data
          ? Object.values(err.response.data).flat().join(' ')
          : 'Failed to create contract. Please try again.'
        setCdError(String(msg))
      })
      .finally(() => setCdLoading(false))
  }

  const tier = user?.subscription_tier ?? ''
  const isEnterprise = tier === 'anchor'
  const isBusiness = tier === 'business'
  const isPro = tier === 'professional'
  const bizDropdownTier = isEnterprise || isBusiness

  // Close biz dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (bizDropdownRef.current && !bizDropdownRef.current.contains(e.target as Node)) {
        setBizDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function openCreateModal() {
    if (entityFilter === 'Personal') {
      openDetailsModal('Personal', null)
    } else if (entityFilter !== 'Business') {
      const match = entities.find(e => e.name === entityFilter)
      openDetailsModal(entityFilter, match?.id ?? null)
    } else {
      setShowEntityModal(true)
    }
  }

  function handleSelectPersonal() {
    setShowEntityModal(false)
    openDetailsModal('Personal', null)
  }

  function handleSelectBusiness(name: string) {
    setShowEntityModal(false)
    const match = entities.find(e => e.name === name)
    openDetailsModal(name, match?.id ?? null)
  }

  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'You'
  const initials = ([user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('') || user?.username?.[0] || '?').toUpperCase()

  // Fetch entities once on mount
  useEffect(() => {
    api.get<{ results: BusinessEntity[] }>('/entities/')
      .then(({ data }) => setEntities(data.results))
      .catch(() => {})
  }, [])

  // Refetch contracts whenever entity filter changes.
  // Always pass entity param — never omit it — so the backend never mixes entities.
  useEffect(() => {
    const params: Record<string, string> = {}
    if (entityFilter === 'Personal') {
      params.entity = 'personal'
    } else if (entityFilter !== 'Business') {
      // specific named business entity
      const match = entities.find(e => e.name === entityFilter)
      if (match) {
        params.entity = match.id
      } else {
        // entity not yet loaded — skip fetch until entities arrive
        return
      }
    } else {
      // Generic "Business" tab with no specific entity selected — show nothing
      setContracts([])
      return
    }
    setContracts([])
    setContractsLoading(true)
    api.get<{ id: string; title: string; status: string; version: number; counterparty_email: string; structure_type: string; state: string; created_at: string; max_versions: number }[]>(
      '/contracts/', { params }
    )
      .then(({ data }) => {
        setContracts(data.map((c) => {
          const title = c.title || `${structureLabel(c.structure_type)} #${c.id.slice(-6).toUpperCase()}`
          const party = c.counterparty_email === 'pending@bonup.placeholder'
            ? 'No party yet'
            : c.counterparty_email
          const date = c.created_at
            ? new Date(c.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
            : '—'
          return {
            id: c.id,
            title,
            party,
            status: c.status.toUpperCase(),
            version: `v${c.version ?? 1}`,
            createdAt: date,
          }
        }))
      })
      .catch(() => {})
      .finally(() => setContractsLoading(false))
  }, [entityFilter, entities])

  const [isHovered, setIsHovered] = useState(false)
  const [selectedVideo, setSelectedVideo] = useState(0)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showHelp, setShowHelp] = useState(false)

  const tutorialVideos = [
    'How to create a contract',
    'Understanding obligations',
    'How to negotiate a contract',
    'Signing and rejecting versions',
    'Using contract templates',
    'Managing payments in Blackboard',
    'How Live Sessions work',
    'What is a PBVD?',
    'Sol groups explained',
    'Role switching guide',
  ]
  const [tabOpen, setTabOpen] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'card'>('list')
  const [message, setMessage] = useState('')
  const [chat, setChat] = useState([
    {
      role: 'ai',
      text: 'Hi! I can help you understand contracts, obligations, and how to get started. What would you like to know?',
    },
  ])

  function sendMessage() {
    const trimmed = message.trim()
    if (!trimmed) return
    setChat((prev) => [...prev, { role: 'user', text: trimmed }])
    setMessage('')
    // Placeholder AI response
    setTimeout(() => {
      setChat((prev) => [
        ...prev,
        { role: 'ai', text: 'This AI assistant is coming soon. Stay tuned!' },
      ])
    }, 600)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') sendMessage()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      <ContractContextBar
        entityFilter={entityFilter}
        displayName={displayName}
        entities={entities}
        onSelect={setEntityFilter}
      />

      {/* Spacer to push content below the fixed context bar */}
      <div style={{ height: 44, flexShrink: 0 }} />



      {/* ── ENTITY SELECTION MODAL ── */}
      {showEntityModal && (
        <>
          <div
            onClick={() => setShowEntityModal(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 499 }}
          />
          <div style={{
            position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'white', borderRadius: 12,
            padding: 24, width: 320,
            boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
            zIndex: 500,
          }}>
            {/* Close */}
            <button
              onClick={() => setShowEntityModal(false)}
              style={{
                position: 'absolute', top: 12, right: 14,
                background: 'transparent', border: 'none',
                fontSize: 18, color: '#9CA3AF', cursor: 'pointer', lineHeight: 1,
              }}
            >
              ×
            </button>

            <p style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D', margin: '0 0 6px' }}>
              Who are you contracting as?
            </p>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '0 0 20px' }}>
              Choose the identity for this contract
            </p>

            {/* Personal card */}
            <div
              onClick={handleSelectPersonal}
              style={{
                background: 'white', borderRadius: 10,
                border: '1px solid #E5E7EB',
                padding: '14px 16px', marginBottom: 10,
                cursor: 'pointer', display: 'flex',
                alignItems: 'center', gap: 12,
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#0F1F3D'
                e.currentTarget.style.background = '#F8FAFC'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#E5E7EB'
                e.currentTarget.style.background = 'white'
              }}
            >
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: '#0F1F3D', color: 'white',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 600, flexShrink: 0,
              }}>
                {initials}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  <span style={{ fontSize: 14, fontWeight: 500, color: '#0F1F3D' }}>{displayName}</span>
                  <span style={{
                    background: '#E5E7EB', color: '#374151',
                    fontSize: 11, padding: '2px 8px', borderRadius: 4,
                  }}>Personal</span>
                </div>
                {user?.bon_id && (
                  <span style={{ fontSize: 11, color: '#8B5CF6', fontFamily: 'DM Mono, monospace' }}>
                    {user.bon_id}
                  </span>
                )}
              </div>
            </div>

            {/* Business section */}
            <div style={{
              background: 'white', borderRadius: 10,
              border: '1px solid #E5E7EB',
              overflow: 'hidden',
            }}>
              {entities.length === 0 ? (
                <div style={{ padding: '14px 16px' }}>
                  <p style={{ fontSize: 13, color: '#9CA3AF', margin: '0 0 10px' }}>
                    No businesses added yet
                  </p>
                  <span
                    onClick={() => { setShowEntityModal(false); navigate('/entities') }}
                    style={{ fontSize: 13, color: '#0F1F3D', fontWeight: 500, cursor: 'pointer' }}
                  >
                    + Add a Business
                  </span>
                </div>
              ) : (
                <>
                  {entities.map((e) => (
                    <div
                      key={e.id}
                      onClick={() => handleSelectBusiness(e.name)}
                      style={{
                        padding: '14px 16px', display: 'flex',
                        alignItems: 'center', gap: 12,
                        cursor: 'pointer', borderBottom: '1px solid #F3F4F6',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(ev) => (ev.currentTarget.style.background = '#F8FAFC')}
                      onMouseLeave={(ev) => (ev.currentTarget.style.background = 'transparent')}
                    >
                      <div style={{
                        width: 36, height: 36, borderRadius: '50%',
                        background: '#F3F4F6', color: '#374151',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13, fontWeight: 600, flexShrink: 0,
                      }}>
                        {e.name.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 500, color: '#0F1F3D' }}>{e.name}</div>
                        <div style={{ fontSize: 11, color: '#9CA3AF' }}>{e.business_type}</div>
                      </div>
                    </div>
                  ))}
                  <div style={{ padding: '10px 16px' }}>
                    <span
                      onClick={() => { setShowEntityModal(false); navigate('/entities') }}
                      style={{ fontSize: 12, color: '#6B7280', cursor: 'pointer' }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#0F1F3D')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
                    >
                      + Add a Business
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── CONTRACT DETAILS MODAL ── */}
      {showDetailsModal && (
        <>
          <div
            onClick={() => setShowDetailsModal(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 499 }}
          />
          <div style={{
            position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'white', borderRadius: 16,
            padding: 36, width: 560,
            maxHeight: '85vh', overflowY: 'auto',
            boxShadow: '0 16px 48px rgba(0,0,0,0.15)',
            zIndex: 500,
          }}>
            {/* Close */}
            <button
              onClick={() => setShowDetailsModal(false)}
              style={{
                position: 'absolute', top: 16, right: 18,
                background: 'transparent', border: 'none',
                fontSize: 20, color: '#9CA3AF', cursor: 'pointer', lineHeight: 1,
              }}
            >×</button>

            {/* Header */}
            <p style={{ fontSize: 20, fontWeight: 700, color: '#0F1F3D', margin: '0 0 4px' }}>
              New Contract
            </p>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '0 0 24px' }}>
              Creating as: {cdEntityLabel || 'Personal'}
            </p>

            {/* Form — helper styles */}
            {(() => {
              const LBL: React.CSSProperties = {
                fontSize: 11, fontWeight: 500, color: '#6B7280',
                display: 'block', marginBottom: 4,
                textTransform: 'uppercase', letterSpacing: '0.06em',
              }
              const FLD: React.CSSProperties = {
                width: '100%', border: '1px solid #D1D5DB', borderRadius: 8,
                padding: '9px 12px', fontSize: 13, color: '#374151',
                fontFamily: "'Outfit', sans-serif", outline: 'none',
                boxSizing: 'border-box', background: 'white',
              }
              const FLD_ERR: React.CSSProperties = { ...FLD, borderColor: '#DC2626' }
              function onFocus(e: React.FocusEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
                e.currentTarget.style.borderColor = '#0F1F3D'
                e.currentTarget.style.boxShadow = '0 0 0 2px rgba(15,31,61,0.08)'
              }
              function onBlur(e: React.FocusEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
                e.currentTarget.style.borderColor = (e.currentTarget as HTMLElement).dataset.err ? '#DC2626' : '#D1D5DB'
                e.currentTarget.style.boxShadow = 'none'
              }

              return (
                <div>
                  {/* Row 1: Contract Title (full width) */}
                  <div style={{ marginBottom: 14 }}>
                    <label style={LBL}>Contract Title *</label>
                    <input
                      type="text"
                      value={cdTitle}
                      onChange={(e) => { setCdTitle(e.target.value); if (e.target.value.trim()) setCdTitleError(false) }}
                      placeholder="e.g. Lawn Care Services Agreement"
                      style={cdTitleError ? FLD_ERR : FLD}
                      data-err={cdTitleError ? '1' : undefined}
                      onFocus={onFocus}
                      onBlur={onBlur}
                    />
                    {cdTitleError && <p style={{ fontSize: 11, color: '#DC2626', margin: '4px 0 0' }}>Title is required</p>}
                  </div>

                  {/* Row 2: Contract Type + Language */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                    <div>
                      <label style={LBL}>Contract Type *</label>
                      <select
                        value={cdType}
                        onChange={(e) => { setCdType(e.target.value); if (e.target.value) setCdTypeError(false) }}
                        style={cdTypeError ? FLD_ERR : FLD}
                        data-err={cdTypeError ? '1' : undefined}
                        onFocus={onFocus}
                        onBlur={onBlur}
                      >
                        <option value="">Select type…</option>
                        <option>Service Agreement</option>
                        <option>Employment Contract</option>
                        <option>Freelance Contract</option>
                        <option>NDA / Confidentiality</option>
                        <option>Partnership Agreement</option>
                        <option>Sales Contract</option>
                        <option>Lease Agreement</option>
                        <option>Loan Agreement</option>
                        <option>Settlement Agreement</option>
                        <option>Consulting Agreement</option>
                        <option>Licensing Agreement</option>
                        <option>Distribution Agreement</option>
                        <option>Joint Venture</option>
                        <option>Purchase Agreement</option>
                        <option>Other</option>
                      </select>
                      {cdTypeError && <p style={{ fontSize: 11, color: '#DC2626', margin: '4px 0 0' }}>Type is required</p>}
                    </div>
                    <div>
                      <label style={LBL}>Language</label>
                      <select value={cdLanguage} onChange={(e) => setCdLanguage(e.target.value)} style={FLD} onFocus={onFocus} onBlur={onBlur}>
                        <option>English</option>
                        <option>Haitian Creole</option>
                        <option>Spanish</option>
                        <option>French</option>
                        <option>Portuguese</option>
                        <option>Arabic</option>
                        <option>Swahili</option>
                      </select>
                    </div>
                  </div>

                  {/* Row 3: Start + End Date */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                    <div>
                      <label style={LBL}>Start Date</label>
                      <input type="date" value={cdStartDate} onChange={(e) => setCdStartDate(e.target.value)} style={FLD} onFocus={onFocus} onBlur={onBlur} />
                    </div>
                    <div>
                      <label style={LBL}>End Date</label>
                      <input type="date" value={cdEndDate} onChange={(e) => setCdEndDate(e.target.value)} style={FLD} onFocus={onFocus} onBlur={onBlur} />
                    </div>
                  </div>

                  {/* Row 4: Contract Value + Currency */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                    <div>
                      <label style={LBL}>Contract Value</label>
                      <input type="number" value={cdValue} onChange={(e) => setCdValue(e.target.value)} placeholder="0.00" min={0} step={0.01} style={FLD} onFocus={onFocus} onBlur={onBlur} />
                    </div>
                    <div>
                      <label style={LBL}>Currency</label>
                      <select value={cdCurrency} onChange={(e) => setCdCurrency(e.target.value)} style={FLD} onFocus={onFocus} onBlur={onBlur}>
                        {([['USD','US Dollar'],['CAD','Canadian Dollar'],['EUR','Euro'],['GBP','British Pound'],['MXN','Mexican Peso'],['BRL','Brazilian Real'],['AUD','Australian Dollar'],['JPY','Japanese Yen'],['CNY','Chinese Yuan'],['INR','Indian Rupee']] as [string,string][]).map(([code, name]) => (
                          <option key={code} value={code}>{code} — {name}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Row 5: Jurisdiction + Governing Law */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                    <div>
                      <label style={LBL}>Jurisdiction</label>
                      <input type="text" value={cdJurisdiction} onChange={(e) => setCdJurisdiction(e.target.value)} placeholder="e.g. New York, USA" style={FLD} onFocus={onFocus} onBlur={onBlur} />
                    </div>
                    <div>
                      <label style={LBL}>Governing Law</label>
                      <input type="text" value={cdGoverningLaw} onChange={(e) => setCdGoverningLaw(e.target.value)} placeholder="e.g. Laws of New York State" style={FLD} onFocus={onFocus} onBlur={onBlur} />
                    </div>
                  </div>

                  {/* Row 6: Confidentiality + Dispute Resolution */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                    <div>
                      <label style={LBL}>Confidentiality</label>
                      <select value={cdConfidentiality} onChange={(e) => setCdConfidentiality(e.target.value)} style={FLD} onFocus={onFocus} onBlur={onBlur}>
                        <option>Not confidential</option>
                        <option>Confidential</option>
                        <option>Strictly confidential</option>
                      </select>
                    </div>
                    <div>
                      <label style={LBL}>Dispute Resolution</label>
                      <select value={cdDispute} onChange={(e) => setCdDispute(e.target.value)} style={FLD} onFocus={onFocus} onBlur={onBlur}>
                        <option>Negotiation</option>
                        <option>Mediation</option>
                        <option>Arbitration</option>
                        <option>Litigation</option>
                        <option>Arbitration then Litigation</option>
                      </select>
                    </div>
                  </div>

                  {/* Row 7: Description */}
                  <div style={{ marginBottom: 16 }}>
                    <label style={LBL}>Description</label>
                    <textarea
                      value={cdDescription}
                      onChange={(e) => setCdDescription(e.target.value)}
                      placeholder="Brief description of this contract…"
                      rows={2}
                      style={{ ...FLD, resize: 'vertical' }}
                      onFocus={onFocus}
                      onBlur={onBlur}
                    />
                  </div>

                  {/* Version info box */}
                  <div style={{
                    background: '#F8FAFC', borderRadius: 8,
                    padding: '12px 16px', border: '1px solid #E5E7EB', marginTop: 16,
                  }}>
                    <p style={{ fontSize: 12, color: '#6B7280', margin: 0 }}>
                      This contract will be saved as <strong>Draft · Version 1</strong>
                    </p>
                    <p style={{ fontSize: 11, color: '#9CA3AF', margin: '4px 0 0' }}>
                      You have 3 versions before you must start over. Contracts become active only when signed by all parties.
                    </p>
                  </div>

                  {/* Error */}
                  {cdError && (
                    <p style={{ fontSize: 12, color: '#DC2626', margin: '12px 0 0' }}>{cdError}</p>
                  )}

                  {/* Buttons */}
                  <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
                    <button
                      onClick={() => setShowDetailsModal(false)}
                      style={{
                        flex: 1, height: 40,
                        background: 'transparent', border: '1px solid #D1D5DB',
                        color: '#374151', borderRadius: 8, fontSize: 14,
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreateContract}
                      disabled={cdLoading}
                      style={{
                        flex: 1, height: 40,
                        background: '#0F1F3D', color: 'white',
                        border: 'none', borderRadius: 8,
                        fontSize: 14, fontWeight: 600,
                        cursor: cdLoading ? 'wait' : 'pointer',
                        opacity: cdLoading ? 0.7 : 1,
                      }}
                    >
                      {cdLoading ? 'Creating…' : 'Create Contract'}
                    </button>
                  </div>
                </div>
              )
            })()}
          </div>
        </>
      )}

      {/* ── SECTION 1: TAB SYSTEM ── */}
      <div style={{ position: 'relative' }}>
        {/* Create a Contract button — absolute top right */}
        <div style={{ position: 'absolute', top: 9, right: 22, zIndex: 1 }}>
          <button
            onClick={() => navigate('/contracts/new')}
            style={{
              background: '#000000',
              color: '#fff',
              fontSize: 13,
              fontWeight: 500,
              height: 34,
              padding: '0 18px',
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Create a Contract
          </button>
        </div>

        {/* Tab row */}
        <div
          style={{
            background: '#fff',
            borderRadius: 11,
            border: '1px solid rgba(0,0,0,0.05)',
            padding: '0 22px',
            display: 'flex',
            gap: 0,
          }}
        >
          {['My Contracts', 'Pending Review', 'Active Obligations', 'Negotiations', 'Expiring Soon', 'Archived'].map((tab, i) => (
            <div
              key={i}
              onClick={() => { setActiveTab(i); setTabOpen(true) }}
              style={{
                padding: '18px 24px',
                fontSize: 15,
                fontWeight: 600,
                color: activeTab === i ? '#0F1F3D' : '#9CA3AF',
                borderBottom: activeTab === i ? '2px solid #F5A623' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.2s',
                marginBottom: -1,
                userSelect: 'none' as const,
              }}
            >
              {tab}
            </div>
          ))}
        </div>

        {/* Content area — expands on tab click */}
        <div
          style={{
            maxHeight: tabOpen ? '320px' : '0',
            overflow: 'hidden',
            opacity: tabOpen ? 1 : 0,
            transition: 'max-height 0.5s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s ease',
            transitionDelay: tabOpen ? '0s' : '0.1s',
          }}
        >
          <div
            style={{
              background: '#F0F4F8',
              borderRadius: '0 0 11px 11px',
              height: 320,
              overflowY: 'auto',
              padding: '0 22px 20px',
            }}
          >

            {/* Tab 0: My Contracts */}
            {activeTab === 0 && contractsLoading && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>Loading contracts…</p>
              </div>
            )}
            {activeTab === 0 && !contractsLoading && contracts.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 220, gap: 12 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>
                  No contracts yet for {entityFilter}
                </p>
                <button
                  onClick={() => navigate('/contracts/new')}
                  style={{ background: '#000000', color: '#fff', fontSize: 13, fontWeight: 500, height: 34, padding: '0 18px', borderRadius: 8, border: 'none', cursor: 'pointer' }}
                >
                  Create a Contract
                </button>
              </div>
            )}
            {activeTab === 0 && !contractsLoading && contracts.length > 0 && (
              <div>
                {/* View toggle */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 12, paddingBottom: 4, gap: 4 }}>
                  <button
                    onClick={() => setViewMode('list')}
                    title="List view"
                    style={{
                      width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      borderRadius: 5, border: '1px solid #D1D5DB', cursor: 'pointer',
                      background: viewMode === 'list' ? '#0F1F3D' : 'transparent',
                      color: viewMode === 'list' ? '#fff' : '#6B7280',
                      transition: 'all 0.15s',
                    }}
                  >
                    <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                      <rect x="0" y="1" width="13" height="2" rx="1" fill="currentColor"/>
                      <rect x="0" y="5.5" width="13" height="2" rx="1" fill="currentColor"/>
                      <rect x="0" y="10" width="13" height="2" rx="1" fill="currentColor"/>
                    </svg>
                  </button>
                  <button
                    onClick={() => setViewMode('card')}
                    title="Card view"
                    style={{
                      width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      borderRadius: 5, border: '1px solid #D1D5DB', cursor: 'pointer',
                      background: viewMode === 'card' ? '#0F1F3D' : 'transparent',
                      color: viewMode === 'card' ? '#fff' : '#6B7280',
                      transition: 'all 0.15s',
                    }}
                  >
                    <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                      <rect x="0" y="0" width="5.5" height="5.5" rx="1" fill="currentColor"/>
                      <rect x="7.5" y="0" width="5.5" height="5.5" rx="1" fill="currentColor"/>
                      <rect x="0" y="7.5" width="5.5" height="5.5" rx="1" fill="currentColor"/>
                      <rect x="7.5" y="7.5" width="5.5" height="5.5" rx="1" fill="currentColor"/>
                    </svg>
                  </button>
                </div>

                {/* List view */}
                {viewMode === 'list' && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 4 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #E5E7EB' }}>
                      <th style={TH_DARK}>Contract Title</th>
                      <th style={TH_DARK}>Party</th>
                      <th style={TH_DARK}>Status</th>
                      <th style={TH_DARK}>Version</th>
                      <th style={TH_DARK}>Created</th>
                      <th style={{ ...TH_DARK, paddingRight: 0 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {contracts.map((row, i) => (
                      <tr
                        key={row.id}
                        style={{
                          borderBottom: '1px solid #E5E7EB',
                          background: hoveredRow === i ? '#E8EDF2' : 'transparent',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={() => setHoveredRow(i)}
                        onMouseLeave={() => setHoveredRow(null)}
                      >
                        <td style={{ ...TD_DARK, fontWeight: 500 }}>{row.title}</td>
                        <td style={{ ...TD_DARK, color: row.party === 'No party yet' ? '#9CA3AF' : TD_DARK.color }}>{row.party}</td>
                        <td style={TD_DARK}>
                          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_DARK[row.status] }}>
                            {row.status}
                          </span>
                        </td>
                        <td style={{ ...TD_DARK, color: '#9CA3AF' }}>{row.version}</td>
                        <td style={{ ...TD_DARK, color: '#9CA3AF' }}>{row.createdAt}</td>
                        <td style={{ ...TD_DARK, paddingRight: 0 }}>
                          <button
                            onClick={() => navigate(`/contracts/new?id=${row.id}`)}
                            style={{ fontSize: 12, fontWeight: 500, color: '#374151', background: 'transparent', border: '1px solid #D1D5DB', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = '#E5E7EB' }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                          >
                            Open
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
                )}

                {/* Card view */}
                {viewMode === 'card' && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, paddingTop: 4, paddingBottom: 8 }}>
                    {contracts.map((row) => (
                      <div
                        key={row.id}
                        onClick={() => navigate(`/contracts/new?id=${row.id}`)}
                        style={{
                          background: '#fff', borderRadius: 8, border: '1px solid #E5E7EB',
                          padding: '14px 16px', cursor: 'pointer', display: 'flex',
                          flexDirection: 'column', gap: 6, transition: 'border-color 0.15s',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#9CA3AF')}
                        onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#E5E7EB')}
                      >
                        <span style={{ fontSize: 13, fontWeight: 600, color: '#0F1F3D', lineHeight: 1.3 }}>{row.title}</span>
                        <span style={{ fontSize: 12, color: row.party === 'No party yet' ? '#9CA3AF' : '#6B7280' }}>{row.party}</span>
                        <span style={{ display: 'inline-block', alignSelf: 'flex-start', padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_DARK[row.status] }}>
                          {row.status}
                        </span>
                        <span style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{row.createdAt}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 1: Pending Review — empty state */}
            {activeTab === 1 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No Pending Review yet</p>
              </div>
            )}

            {/* Tab 2: Active Obligations — empty state */}
            {activeTab === 2 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No Active Obligations yet</p>
              </div>
            )}

            {/* Tab 3: Negotiations — empty state */}
            {activeTab === 3 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No Negotiations yet</p>
              </div>
            )}

            {/* Tab 4: Expiring Soon — empty state */}
            {activeTab === 4 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No Expiring Soon yet</p>
              </div>
            )}

            {/* Tab 5: Archived — empty state */}
            {activeTab === 5 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No Archived yet</p>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* ── SECTION 2: ASK AI ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 20 }}>

        {/* ASK AI */}
        <div
          style={{
            ...CARD,
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <p style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', margin: '0 0 16px 0' }}>
            Ask AI about contracts
          </p>

          {/* Chat area */}
          <div
            style={{
              flex: 1,
              minHeight: 180,
              background: '#F9FAFB',
              borderRadius: 8,
              padding: 12,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            {chat.map((msg, i) =>
              msg.role === 'ai' ? (
                <div key={i} style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <span
                    style={{
                      background: '#E8F4FD',
                      color: '#0F1F3D',
                      borderRadius: 8,
                      padding: '10px 14px',
                      fontSize: 13,
                      maxWidth: '85%',
                      lineHeight: 1.5,
                    }}
                  >
                    {msg.text}
                  </span>
                </div>
              ) : (
                <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <span
                    style={{
                      background: '#0F1F3D',
                      color: '#fff',
                      borderRadius: 8,
                      padding: '10px 14px',
                      fontSize: 13,
                      maxWidth: '85%',
                      lineHeight: 1.5,
                    }}
                  >
                    {msg.text}
                  </span>
                </div>
              )
            )}
          </div>

          {/* Input bar */}
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question…"
              style={{
                flex: 1,
                background: '#fff',
                border: '1px solid #E5E7EB',
                borderRadius: 8,
                fontSize: 13,
                padding: '8px 12px',
                outline: 'none',
                color: '#374151',
              }}
            />
            <button
              onClick={sendMessage}
              style={{
                background: '#000',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                padding: '0 16px',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Send
            </button>
          </div>
        </div>

      </div>

      {/* ── FLOATING HELP BUTTON ── */}
      <button
        onClick={() => setShowHelp(true)}
        style={{
          position: 'fixed',
          bottom: 28,
          right: 28,
          background: '#F5A623',
          color: '#0F1F3D',
          fontSize: 13,
          fontWeight: 700,
          height: 40,
          padding: '0 20px',
          borderRadius: 20,
          border: 'none',
          cursor: 'pointer',
          boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
          zIndex: 50,
          transition: 'background 0.15s, transform 0.15s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#D4900A'
          e.currentTarget.style.transform = 'scale(1.04)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#F5A623'
          e.currentTarget.style.transform = 'scale(1)'
        }}
      >
        Help
      </button>

      {/* ── HELP PANEL ── */}
      {showHelp && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setShowHelp(false)}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.35)',
              zIndex: 200,
            }}
          />
          {/* Panel */}
          <div style={{
            position: 'fixed',
            top: 0, right: 0, bottom: 0,
            width: 400,
            background: '#ffffff',
            zIndex: 201,
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
          }}>
            {/* Header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '18px 22px', borderBottom: '1px solid #E5E7EB',
            }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D' }}>
                Contract Tutorials
              </span>
              <button
                onClick={() => setShowHelp(false)}
                style={{
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  fontSize: 20, color: '#9CA3AF', lineHeight: 1, padding: '0 2px',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
              >
                ×
              </button>
            </div>

            {/* Playlist */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              {tutorialVideos.map((title, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedVideo(i)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '12px 14px', borderRadius: 8, cursor: 'pointer',
                    border: 'none', textAlign: 'left', width: '100%',
                    background: selectedVideo === i ? '#FFF8EC' : 'transparent',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => { if (selectedVideo !== i) e.currentTarget.style.background = '#F9FAFB' }}
                  onMouseLeave={(e) => { if (selectedVideo !== i) e.currentTarget.style.background = 'transparent' }}
                >
                  <span style={{ fontSize: 9, color: selectedVideo === i ? '#F5A623' : '#9CA3AF', lineHeight: 1, flexShrink: 0 }}>▶</span>
                  <span style={{
                    fontSize: 13,
                    color: selectedVideo === i ? '#0F1F3D' : '#374151',
                    fontWeight: selectedVideo === i ? 600 : 400,
                    lineHeight: 1.4,
                  }}>
                    {title}
                  </span>
                </button>
              ))}
            </div>

            {/* Player */}
            <div style={{ padding: '0 22px 22px' }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#0F1F3D', margin: '0 0 8px' }}>
                {tutorialVideos[selectedVideo]}
              </p>
              <div style={{
                width: '100%', aspectRatio: '16 / 9',
                background: '#1C2B3A', borderRadius: 8,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 8,
              }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: 'rgba(255,255,255,0.15)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <span style={{ color: '#fff', fontSize: 16, marginLeft: 3 }}>▶</span>
                </div>
                <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', margin: 0 }}>Tutorial coming soon</p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
