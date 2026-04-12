import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/client'
import type { BusinessEntity } from '@/types/entities'

const BTN: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  height: 28,
  padding: '0 10px',
  borderRadius: 7,
  fontSize: 13,
  fontWeight: 500,
  fontFamily: "'Outfit', sans-serif",
  color: '#ffffff',
  background: '#6B7280',
  border: '1px solid rgba(19,32,48,0.2)',
  cursor: 'pointer',
  whiteSpace: 'nowrap' as const,
  transition: 'background 0.15s, color 0.15s',
  WebkitFontSmoothing: 'antialiased' as const,
  MozOsxFontSmoothing: 'grayscale' as const,
}

function GhostBtn({ label }: { label: string }) {
  return (
    <button
      style={BTN}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = '#4B5563'
        e.currentTarget.style.color = '#ffffff'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = '#6B7280'
        e.currentTarget.style.color = '#ffffff'
      }}
    >
      {label}
    </button>
  )
}

function GhostBtnLink({ label, to }: { label: string; to: string }) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate(to)}
      style={BTN}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = '#4B5563'
        e.currentTarget.style.color = '#ffffff'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = '#6B7280'
        e.currentTarget.style.color = '#ffffff'
      }}
    >
      {label}
    </button>
  )
}

// ── My Contracts dropdown ─────────────────────────────────────────────────────

interface ContractEntry {
  id: string
  title: string
  sub: string
  pill: 'Draft' | 'Negotiation' | 'Active' | 'Completed' | 'Archived'
}

interface ContractCategory {
  icon: string
  label: string
  items: ContractEntry[]
}

const PILL_STYLE: Record<string, React.CSSProperties> = {
  Draft:       { background: 'rgba(255,255,255,0.1)',   color: 'rgba(255,255,255,0.65)' },
  Negotiation: { background: 'rgba(245,166,35,0.2)',    color: '#F5A623' },
  Active:      { background: 'rgba(16,185,129,0.2)',    color: '#10B981' },
  Completed:   { background: 'rgba(139,92,246,0.2)',    color: '#8B5CF6' },
  Archived:    { background: 'rgba(107,114,128,0.2)',   color: '#6B7280' },
}

const CATEGORY_DEFS: Omit<ContractCategory, 'items'>[] = [
  { icon: '🔨', label: 'In Progress' },
  { icon: '📋', label: 'Under Negotiation' },
  { icon: '✅', label: 'Active' },
  { icon: '🏁', label: 'Completed' },
  { icon: '📦', label: 'Archived' },
]

interface ApiContract {
  id: string
  structure_type: string
  counterparty_email: string
  state: string
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

function apiContractToEntry(c: ApiContract): ContractEntry & { category: string } {
  const title = `${structureLabel(c.structure_type)} #${c.id.slice(-6).toUpperCase()}`
  const sub = c.counterparty_email === 'pending@bonup.placeholder' ? '' : c.counterparty_email
  let pill: ContractEntry['pill'] = 'Active'
  let category = 'Active'
  if (c.state === 'fulfilled') {
    pill = 'Completed'
    category = 'Completed'
  } else if (c.state === 'active' || c.state === 'at_risk') {
    pill = 'Active'
    category = 'Active'
  }
  return { id: c.id, title, sub, pill, category }
}

function MyContractsBtn() {
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [contracts, setContracts] = useState<ApiContract[]>([])
  const ref = useRef<HTMLDivElement>(null)

  const isBuilding = location.pathname === '/contracts/new'

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  useEffect(() => {
    if (open) {
      api.get<ApiContract[]>('/contracts/')
        .then(({ data }) => setContracts(Array.isArray(data) ? data : []))
        .catch(() => setContracts([]))
    }
  }, [open])

  const wipTitle = isBuilding
    ? (localStorage.getItem('bb_wip_contract_title') || 'Untitled Contract')
    : null

  const categories: ContractCategory[] = CATEGORY_DEFS.map((def) => ({
    ...def,
    items: contracts.map(apiContractToEntry).filter((e) => e.category === def.label),
  }))

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={BTN}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(19,32,48,0.07)'
          e.currentTarget.style.color = '#ffffff'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = '#ffffff'
        }}
      >
        My Contracts&nbsp;<span style={{ fontSize: 9, opacity: 0.7 }}>▾</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0,
          background: '#1C2B3A', borderRadius: 8,
          border: '1px solid rgba(255,255,255,0.1)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
          minWidth: 280, zIndex: 9999, padding: '8px 0',
          maxHeight: 500, overflowY: 'auto',
        }}>
          {categories.map((cat) => {
            const items: ContractEntry[] = cat.label === 'In Progress' && wipTitle
              ? [{ id: 'wip', title: wipTitle, sub: 'Building now', pill: 'Draft' }, ...cat.items]
              : cat.items
            return (
              <div key={cat.label}>
                <div style={{
                  fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em',
                  color: 'rgba(255,255,255,0.3)', padding: '8px 16px 4px',
                  marginTop: cat.label === 'In Progress' ? 0 : 8,
                }}>
                  {cat.icon} {cat.label}
                </div>
                {items.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', padding: '8px 16px' }}>
                    No contracts yet
                  </div>
                ) : items.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => { setOpen(false); navigate('/contracts') }}
                    style={{
                      padding: '6px 16px', fontSize: 12,
                      color: 'rgba(255,255,255,0.7)', cursor: 'pointer',
                      display: 'flex', alignItems: 'center',
                      justifyContent: 'space-between', gap: 8,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.07)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {c.title}
                      {c.sub ? <span style={{ color: 'rgba(255,255,255,0.35)', marginLeft: 4 }}>— {c.sub}</span> : null}
                    </span>
                    <span style={{
                      fontSize: 10, padding: '1px 6px', borderRadius: 4,
                      flexShrink: 0, fontWeight: 500,
                      ...PILL_STYLE[c.pill],
                    }}>
                      {c.pill}
                    </span>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function bizInitials(name: string): string {
  const words = name.trim().split(/\s+/)
  return words.length >= 2
    ? (words[0][0] + words[words.length - 1][0]).toUpperCase()
    : name.substring(0, 2).toUpperCase()
}

function MyEntitiesBtn() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [entities, setEntities] = useState<BusinessEntity[]>([])
  const ref = useRef<HTMLDivElement>(null)

  // Derive active entity from contracts page state if we're on /contracts
  const activeEntity: string = (location.state as { entityFilter?: string } | null)?.entityFilter ?? 'All'

  useEffect(() => {
    api.get<{ results: BusinessEntity[] }>('/entities/')
      .then(({ data }) => setEntities(data.results))
      .catch(() => {})
  }, [])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function selectEntity(name: string) {
    setOpen(false)
    navigate('/contracts', { state: { entityFilter: name } })
  }

  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'You'
  const initials = ([user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('') || user?.username?.[0] || '?').toUpperCase()

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={BTN}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#4B5563'
          e.currentTarget.style.color = '#ffffff'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#6B7280'
          e.currentTarget.style.color = '#ffffff'
        }}
      >
        ⊕ My Entities&nbsp;<span style={{ fontSize: 9, opacity: 0.7 }}>▾</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0,
          background: '#1C2B3A', borderRadius: 8,
          border: '1px solid rgba(255,255,255,0.1)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
          minWidth: 220, zIndex: 200, padding: '8px 0',
        }}>
          <div style={{
            fontSize: 10, color: 'rgba(255,255,255,0.3)',
            textTransform: 'uppercase', letterSpacing: '0.1em',
            padding: '6px 16px 4px',
          }}>
            Switch Entity
          </div>

          {/* Personal */}
          <div
            onClick={() => selectEntity('Personal')}
            style={{
              padding: '10px 16px', display: 'flex', alignItems: 'center',
              gap: 10, cursor: 'pointer', fontSize: 13,
              color: 'rgba(255,255,255,0.7)', transition: 'background 0.1s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
              e.currentTarget.style.color = '#ffffff'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = 'rgba(255,255,255,0.7)'
            }}
          >
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: '#0F1F3D', color: 'white',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 600, flexShrink: 0,
            }}>
              {initials}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontWeight: 500, color: 'inherit' }}>{displayName}</span>
                <span style={{
                  background: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)',
                  fontSize: 10, padding: '1px 6px', borderRadius: 4,
                }}>Personal</span>
              </div>
            </div>
            {activeEntity === 'Personal' && (
              <span style={{ color: '#F5A623', fontSize: 13, flexShrink: 0 }}>✓</span>
            )}
          </div>

          {/* Business entities */}
          {entities.map((e) => (
            <div
              key={e.id}
              onClick={() => selectEntity(e.name)}
              style={{
                padding: '10px 16px', display: 'flex', alignItems: 'center',
                gap: 10, cursor: 'pointer', fontSize: 13,
                color: 'rgba(255,255,255,0.7)', transition: 'background 0.1s',
              }}
              onMouseEnter={(ev) => {
                ev.currentTarget.style.background = 'rgba(255,255,255,0.07)'
                ev.currentTarget.style.color = '#ffffff'
              }}
              onMouseLeave={(ev) => {
                ev.currentTarget.style.background = 'transparent'
                ev.currentTarget.style.color = 'rgba(255,255,255,0.7)'
              }}
            >
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: '#1E3A55', color: 'white',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 600, flexShrink: 0,
              }}>
                {bizInitials(e.name)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 500, color: 'inherit' }}>{e.name}</span>
                  <span style={{
                    background: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)',
                    fontSize: 10, padding: '1px 6px', borderRadius: 4,
                  }}>{e.business_type}</span>
                </div>
              </div>
              {activeEntity === e.name && (
                <span style={{ color: '#F5A623', fontSize: 13, flexShrink: 0 }}>✓</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ActionBar() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('bb_topbar_collapsed') === 'true')
  const [askAiOpen, setAskAiOpen] = useState(false)

  useEffect(() => {
    function onCollapse(e: Event) {
      setCollapsed((e as CustomEvent<boolean>).detail)
    }
    window.addEventListener('topbar-collapse', onCollapse)
    return () => window.removeEventListener('topbar-collapse', onCollapse)
  }, [])

  function toggleAskAi() {
    const next = !askAiOpen
    setAskAiOpen(next)
    window.dispatchEvent(new CustomEvent('ask-ai-toggle', { detail: next }))
  }

  return (
    <div
      className="fixed right-0 flex h-[44px] items-center gap-2 px-5"
      style={{
        top: 114,
        left: 'var(--sidebar-w, 216px)',
        background: '#F3F4F6',
        maxHeight: collapsed ? 0 : 44,
        overflow: collapsed ? 'hidden' : 'visible',
        opacity: collapsed ? 0 : 1,
        transition: 'max-height 0.3s ease, opacity 0.2s ease',
        zIndex: 30,
      }}
    >
      <MyEntitiesBtn />
      <GhostBtn label="▶  Book a Live Session" />
      <GhostBtnLink label="+ New Contract" to="/contracts/new" />

      <GhostBtn label="⚡ Negotiation Prep" />
      <button
        onClick={toggleAskAi}
        style={{
          ...BTN,
          background: askAiOpen ? '#4B5563' : '#6B7280',
          color: '#ffffff',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(19,32,48,0.07)'
          e.currentTarget.style.color = '#ffffff'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = askAiOpen ? '#4B5563' : '#6B7280'
          e.currentTarget.style.color = '#ffffff'
        }}
      >
        ✦ Ask AI
      </button>
      <GhostBtn label="🔍 Analyze Contract" />
      <GhostBtn label="⚡ Contract Counter" />
      <GhostBtn label="🌐 Language" />
      <GhostBtn label="+ Contact" />
      <button
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          height: 26,
          padding: '0 12px',
          borderRadius: 7,
          fontSize: 11,
          fontWeight: 600,
          fontFamily: "'Outfit', sans-serif",
          color: '#0F2830',
          background: '#2DD4BF',
          border: 'none',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'opacity 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
      >
        PBVD
      </button>
      <GhostBtn label="+ Invite a Friend" />
    </div>
  )
}
