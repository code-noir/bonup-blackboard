import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '@/api/client'
import type { BusinessEntity } from '@/types/entities'
import { useAuth } from '@/context/AuthContext'

const STATUS_STYLES: Record<string, { background: string; color: string }> = {
  ACTIVE:    { background: '#243447', color: '#FFFFFF' },
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
  onAskAI,
  onHelp,
}: {
  entityFilter: string
  displayName: string
  entities: BusinessEntity[]
  onSelect: (name: string, id: string | null) => void
  onAskAI: () => void
  onHelp: () => void
}) {
  const isPersonal = entityFilter === 'Personal' || entityFilter === displayName
  const viewingName = isPersonal ? displayName : entityFilter

  const allEntities = [
    { name: displayName, personal: true, id: null as string | null },
    ...entities.map((e) => ({ name: e.name, personal: false, id: e.id })),
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

      {/* RIGHT: Ask AI + Help buttons */}
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, flexShrink: 0 }}>
        <button
          onClick={onAskAI}
          style={{
            height: 28, padding: '0 18px',
            background: '#1D4ED8', color: '#ffffff',
            border: 'none', borderRadius: 6,
            fontSize: 12, fontWeight: 600, cursor: 'pointer',
            whiteSpace: 'nowrap', fontFamily: "'Outfit', sans-serif",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#1e40af')}
          onMouseLeave={(e) => (e.currentTarget.style.background = '#1D4ED8')}
        >
          Ask AI
        </button>
        <button
          onClick={onHelp}
          style={{
            height: 28, padding: '0 18px',
            background: '#F5A623', color: '#0F1F3D',
            border: 'none', borderRadius: 6,
            fontSize: 12, fontWeight: 600, cursor: 'pointer',
            whiteSpace: 'nowrap', fontFamily: "'Outfit', sans-serif",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#D4900A')}
          onMouseLeave={(e) => (e.currentTarget.style.background = '#F5A623')}
        >
          Help
        </button>
      </div>

      {/* CENTER: Entity switcher — absolutely centered in the bar */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: 0, right: 0,
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
                  onClick={() => {
                    console.log('[ContextBar] pill clicked:', entity.name, '| id:', entity.id, '| personal:', entity.personal)
                    onSelect(entity.personal ? 'Personal' : entity.name, entity.personal ? null : entity.id)
                  }}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5,
                    fontSize: 13, fontWeight: active ? 600 : 400,
                    color: active ? '#243447' : '#6B7280',
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
  const [entityFilter, setEntityFilter] = useState<string>(() => {
    try {
      const raw = localStorage.getItem('bb_active_entity')
      if (raw) {
        const parsed = JSON.parse(raw) as { id: string | null; name: string }
        return parsed.name
      }
    } catch {}
    return 'Personal'
  })
  const [activeEntityId, setActiveEntityId] = useState<string | null>(() => {
    try {
      const raw = localStorage.getItem('bb_active_entity')
      if (raw) {
        const parsed = JSON.parse(raw) as { id: string | null; name: string }
        return parsed.id
      }
    } catch {}
    return null
  })
  const [contracts, setContracts] = useState<ContractRow[]>([])
  const [contractsLoading, setContractsLoading] = useState(false)
  const [entities, setEntities] = useState<BusinessEntity[]>([])


  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || 'You'
  const initials = ([user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('') || '?').toUpperCase()

  function onSelectEntity(name: string, id: string | null) {
    setEntityFilter(name)
    setActiveEntityId(id)
    localStorage.setItem('bb_active_entity', JSON.stringify({ id, name }))
  }

  // Fetch entities once on mount
  useEffect(() => {
    api.get<{ results: BusinessEntity[] }>('/entities/')
      .then(({ data }) => setEntities(data.results))
      .catch(() => {})
  }, [])

  // Refetch contracts whenever active entity changes.
  // AbortController ensures a stale in-flight response never overwrites newer results.
  // tabOpen resets so the list closes and reopens cleanly with the new entity's data.
  useEffect(() => {
    console.log('[ENTITY SWITCH] activeEntityId is now: ' + activeEntityId)
    const entityParam = activeEntityId === null ? 'personal' : activeEntityId
    console.log('[Contracts] activeEntityId changed → fetching for entity:', entityParam)

    const controller = new AbortController()
    setTabOpen(false)
    setContracts([])
    setContractsLoading(true)

    api.get<{ id: string; title: string; status: string; version: number; counterparty_email: string; structure_type: string; state: string; created_at: string; max_versions: number }[]>(
      '/contracts/',
      { params: { entity: entityParam }, signal: controller.signal }
    )
      .then(({ data }) => {
        console.log('[Contracts] received', data.length, 'contracts for entity:', entityParam)
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
        setContractsLoading(false)
      })
      .catch((err) => {
        if (axios.isCancel(err)) {
          console.log('[Contracts] fetch aborted for entity:', entityParam)
          return  // do NOT call setContractsLoading — the new fetch owns loading state
        }
        setContractsLoading(false)
      })

    // Abort the in-flight request if entity changes before it resolves
    return () => controller.abort()
  }, [activeEntityId])

  const [isHovered, setIsHovered] = useState(false)
  const [selectedVideo, setSelectedVideo] = useState(0)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [showAskAI, setShowAskAI] = useState(false)
  const [askAiCollapsed, setAskAiCollapsed] = useState(false)
  const [askAiPos, setAskAiPos] = useState({ x: 0, y: 0 })
  const askAiDrag = useRef({ active: false, offsetX: 0, offsetY: 0 })

  function handleAskAiDragStart(e: React.MouseEvent<HTMLDivElement>) {
    // Only drag on the header bar itself, not its buttons
    if ((e.target as HTMLElement).closest('button')) return
    e.preventDefault()
    askAiDrag.current = { active: true, offsetX: e.clientX - askAiPos.x, offsetY: e.clientY - askAiPos.y }
    function onMove(ev: MouseEvent) {
      if (!askAiDrag.current.active) return
      setAskAiPos({ x: ev.clientX - askAiDrag.current.offsetX, y: ev.clientY - askAiDrag.current.offsetY })
    }
    function onUp() {
      askAiDrag.current.active = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

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
  const INITIAL_CHAT = [{ role: 'ai', text: 'Hi! I can help you understand contracts, obligations, and how to get started. What would you like to know?' }]
  const [chat, setChat] = useState(INITIAL_CHAT)

  // Reset Ask AI conversation when entity context switches
  useEffect(() => {
    setChat(INITIAL_CHAT)
    setMessage('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeEntityId])

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
        onSelect={onSelectEntity}
        onAskAI={() => {
          setShowAskAI(true)
          setAskAiCollapsed(false)
          setAskAiPos({ x: Math.max(0, window.innerWidth / 2 - 260), y: Math.max(0, window.innerHeight / 2 - 180) })
        }}
        onHelp={() => setShowHelp(true)}
      />

      {/* Spacer to push content below the fixed context bar */}
      <div style={{ height: 44, flexShrink: 0 }} />


      {/* ── SECTION 1: TAB SYSTEM ── */}
      <div style={{ position: 'relative' }}>
        {/* Create a Contract button — absolute, aligned with the tab row */}
        <div style={{ position: 'absolute', top: 50, right: 22, zIndex: 1 }}>
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

        {/* Section title */}
        <p style={{
          fontSize: 18,
          fontWeight: 700,
          color: '#0F1F3D',
          margin: '0 0 10px 4px',
          userSelect: 'none' as const,
          letterSpacing: '-0.01em',
        }}>
          My Contracts
        </p>

        {/* Tab row */}
        <div
          style={{
            background: '#fff',
            borderRadius: 11,
            border: '1px solid rgba(0,0,0,0.05)',
            padding: '0 22px',
            display: 'flex',
            alignItems: 'center',
            gap: 0,
          }}
        >
          {['In Progress', 'Under Review', 'In Negotiation', 'Active', 'Archived'].map((tab, i) => (
            <div
              key={i}
              onClick={() => { setActiveTab(i); setTabOpen(true) }}
              style={{
                padding: '18px 24px',
                fontSize: 15,
                fontWeight: 600,
                color: activeTab === i ? '#243447' : '#9CA3AF',
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

            {/* Tab 0: In Progress */}
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
                      background: viewMode === 'list' ? '#243447' : 'transparent',
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
                      background: viewMode === 'card' ? '#243447' : 'transparent',
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
                            onClick={() => {
                              const entityParam = activeEntityId ?? 'personal'
                              const nameParam = activeEntityId ? `&name=${encodeURIComponent(entityFilter)}` : ''
                              navigate(`/contracts/create?id=${row.id}&entity=${entityParam}${nameParam}`)
                            }}
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
                        onClick={() => {
                          const entityParam = activeEntityId ?? 'personal'
                          const nameParam = activeEntityId ? `&name=${encodeURIComponent(entityFilter)}` : ''
                          navigate(`/contracts/create?id=${row.id}&entity=${entityParam}${nameParam}`)
                        }}
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

            {/* Tab 1: Under Review — empty state */}
            {activeTab === 1 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No contracts under review</p>
              </div>
            )}

            {/* Tab 2: In Negotiation — empty state */}
            {activeTab === 2 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No contracts in negotiation</p>
              </div>
            )}

            {/* Tab 3: Active — empty state */}
            {activeTab === 3 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No active contracts</p>
              </div>
            )}

            {/* Tab 4: Archived — empty state */}
            {activeTab === 4 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0, textAlign: 'center' }}>No archived contracts</p>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* ── HELP MODAL ── */}
      {showHelp && (
        <>
          {/* Backdrop */}
          {/* Backdrop */}
          <div onClick={() => setShowHelp(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200 }} />
          {/* Centered wide modal */}
          <div style={{
            position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 'min(880px, 92vw)', maxHeight: '88vh',
            background: '#ffffff', borderRadius: 12, zIndex: 201,
            display: 'flex', flexDirection: 'column',
            boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
          }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #E5E7EB', flexShrink: 0 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D' }}>Contract Tutorials</span>
              <button onClick={() => setShowHelp(false)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 22, color: '#9CA3AF', lineHeight: 1, padding: '0 2px' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}>×</button>
            </div>
            {/* Body: playlist + player side by side */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {/* Playlist */}
              <div style={{ width: 240, flexShrink: 0, borderRight: '1px solid #E5E7EB', overflowY: 'auto', padding: '10px 12px' }}>
                {tutorialVideos.map((title, i) => (
                  <button key={i} onClick={() => setSelectedVideo(i)} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 12px', borderRadius: 7, cursor: 'pointer',
                    border: 'none', textAlign: 'left', width: '100%',
                    background: selectedVideo === i ? '#FFF8EC' : 'transparent', transition: 'background 0.1s',
                  }}
                    onMouseEnter={(e) => { if (selectedVideo !== i) e.currentTarget.style.background = '#F9FAFB' }}
                    onMouseLeave={(e) => { if (selectedVideo !== i) e.currentTarget.style.background = 'transparent' }}>
                    <span style={{ fontSize: 9, color: selectedVideo === i ? '#F5A623' : '#9CA3AF', lineHeight: 1, flexShrink: 0 }}>▶</span>
                    <span style={{ fontSize: 12, color: selectedVideo === i ? '#0F1F3D' : '#374151', fontWeight: selectedVideo === i ? 600 : 400, lineHeight: 1.4 }}>{title}</span>
                  </button>
                ))}
              </div>
              {/* Player */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '20px 24px', overflowY: 'auto' }}>
                <p style={{ fontSize: 14, fontWeight: 600, color: '#0F1F3D', margin: '0 0 12px' }}>{tutorialVideos[selectedVideo]}</p>
                <div style={{ width: '100%', aspectRatio: '16 / 9', background: '#243447', borderRadius: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                  <div style={{ width: 52, height: 52, borderRadius: '50%', background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ color: '#fff', fontSize: 20, marginLeft: 4 }}>▶</span>
                  </div>
                  <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', margin: 0 }}>Tutorial coming soon</p>
                </div>
              </div>
            </div>
            {/* Footer */}
            <div style={{ padding: '14px 24px', borderTop: '1px solid #E5E7EB', display: 'flex', justifyContent: 'flex-end', flexShrink: 0 }}>
              <button onClick={() => { setShowHelp(false); navigate('/contracts/new') }} style={{ background: '#F5A623', color: '#243447', fontSize: 13, fontWeight: 600, height: 34, padding: '0 20px', borderRadius: 7, border: 'none', cursor: 'pointer' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#D4900A')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '#F5A623')}>
                Create a Contract
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── ASK AI FLOATING WIDGET ── */}
      {showAskAI && (
        <div style={{
          position: 'fixed',
          left: askAiPos.x,
          top: askAiPos.y,
          width: 'min(500px, 48vw)', minWidth: 340,
          background: '#ffffff', borderRadius: 12, zIndex: 300,
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          userSelect: 'none',
        }}>
          {/* Drag handle / Header */}
          <div
            onMouseDown={handleAskAiDragStart}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px', borderBottom: '1px solid #E5E7EB', flexShrink: 0,
              cursor: 'move', borderRadius: '12px 12px 0 0',
              background: '#F9FAFB',
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0F1F3D', pointerEvents: 'none' }}>
              ✦ Ask AI about contracts
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <button
                onClick={() => setAskAiCollapsed((v) => !v)}
                style={{ background: 'transparent', border: '1px solid #E5E7EB', borderRadius: 5, cursor: 'pointer', fontSize: 11, color: '#6B7280', padding: '2px 8px', lineHeight: 1.4 }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#9CA3AF')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#E5E7EB')}
              >
                {askAiCollapsed ? '⤢ Expand' : '⤡ Collapse'}
              </button>
              <button
                onClick={() => setShowAskAI(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 20, color: '#9CA3AF', lineHeight: 1, padding: '0 2px' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
              >×</button>
            </div>
          </div>

          {/* Body — hidden when collapsed */}
          {!askAiCollapsed && (
            <>
              <div style={{ height: 260, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 8, background: '#F9FAFB', userSelect: 'text' }}>
                {chat.map((msg, i) =>
                  msg.role === 'ai' ? (
                    <div key={i} style={{ display: 'flex', justifyContent: 'flex-start' }}>
                      <span style={{ background: '#E8F4FD', color: '#0F1F3D', borderRadius: 8, padding: '9px 13px', fontSize: 13, maxWidth: '85%', lineHeight: 1.5 }}>{msg.text}</span>
                    </div>
                  ) : (
                    <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <span style={{ background: '#243447', color: '#fff', borderRadius: 8, padding: '9px 13px', fontSize: 13, maxWidth: '85%', lineHeight: 1.5 }}>{msg.text}</span>
                    </div>
                  )
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, padding: '10px 14px', borderTop: '1px solid #E5E7EB', flexShrink: 0, background: '#ffffff', borderRadius: '0 0 12px 12px', userSelect: 'text' }}>
                <input
                  type="text" value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask a question…"
                  style={{ flex: 1, background: '#fff', border: '1px solid #E5E7EB', borderRadius: 7, fontSize: 13, padding: '7px 11px', outline: 'none', color: '#374151' }}
                />
                <button onClick={sendMessage} style={{ background: '#243447', color: '#fff', border: 'none', borderRadius: 7, padding: '0 16px', fontSize: 13, fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap' }}>Send</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
