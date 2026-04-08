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
  fontSize: 11,
  fontWeight: 500,
  fontFamily: "'Outfit', sans-serif",
  color: 'rgba(255,255,255,0.58)',
  background: 'transparent',
  border: '1px solid rgba(255,255,255,0.12)',
  cursor: 'pointer',
  whiteSpace: 'nowrap' as const,
  transition: 'background 0.15s, color 0.15s',
}

function GhostBtn({ label }: { label: string }) {
  return (
    <button
      style={BTN}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
        e.currentTarget.style.color = '#ffffff'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'rgba(255,255,255,0.58)'
      }}
    >
      {label}
    </button>
  )
}

// ── My Contracts dropdown ─────────────────────────────────────────────────────

interface ContractEntry { id: string; title: string; status: string }

const PLACEHOLDER_CONTRACTS: Record<string, ContractEntry[]> = {
  'In Progress': [
    { id: 'ip1', title: 'Freelance Web Dev Agreement', status: 'In Progress' },
    { id: 'ip2', title: 'Photography Services Contract', status: 'In Progress' },
    { id: 'ip3', title: 'Office Space Lease', status: 'In Progress' },
  ],
  'Under Negotiation': [
    { id: 'un1', title: 'Software Licensing Deal', status: 'Under Negotiation' },
    { id: 'un2', title: 'Marketing Retainer Agreement', status: 'Under Negotiation' },
    { id: 'un3', title: 'Partnership MOU', status: 'Under Negotiation' },
  ],
  'Active': [
    { id: 'ac1', title: 'Annual Maintenance Contract', status: 'Active' },
    { id: 'ac2', title: 'SaaS Subscription Agreement', status: 'Active' },
    { id: 'ac3', title: 'Consulting Services MSA', status: 'Active' },
  ],
  'Completed': [
    { id: 'co1', title: 'Logo Design Contract', status: 'Completed' },
    { id: 'co2', title: 'Event Photography Agreement', status: 'Completed' },
    { id: 'co3', title: 'Copywriting Services Contract', status: 'Completed' },
  ],
  'Archived': [
    { id: 'ar1', title: 'Old Vendor Agreement 2023', status: 'Archived' },
    { id: 'ar2', title: 'Expired NDA', status: 'Archived' },
    { id: 'ar3', title: 'Legacy Lease Agreement', status: 'Archived' },
  ],
}

const CATEGORY_ICONS: Record<string, string> = {
  'In Progress': '🔨',
  'Under Negotiation': '📋',
  'Active': '✅',
  'Completed': '🏁',
  'Archived': '📦',
}

const PILL_COLORS: Record<string, { bg: string; color: string }> = {
  'In Progress':       { bg: 'rgba(59,130,246,0.18)',  color: '#93C5FD' },
  'Under Negotiation': { bg: 'rgba(245,158,11,0.18)',  color: '#FCD34D' },
  'Active':            { bg: 'rgba(34,197,94,0.18)',   color: '#86EFAC' },
  'Completed':         { bg: 'rgba(156,163,175,0.18)', color: '#D1D5DB' },
  'Archived':          { bg: 'rgba(107,114,128,0.12)', color: '#9CA3AF' },
}

function MyContractsBtn() {
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const isBuilding = location.pathname === '/contracts/create'

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Inject the WIP contract into In Progress when on /contracts/create
  const categories = Object.entries(PLACEHOLDER_CONTRACTS).map(([cat, items]) => {
    if (cat === 'In Progress' && isBuilding) {
      const wipTitle = localStorage.getItem('bb_wip_contract_title') || 'Untitled Contract'
      return [cat, [{ id: 'wip', title: wipTitle, status: 'In Progress' }, ...items]] as [string, ContractEntry[]]
    }
    return [cat, items] as [string, ContractEntry[]]
  })

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={BTN}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
          e.currentTarget.style.color = '#ffffff'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = 'rgba(255,255,255,0.58)'
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
          minWidth: 280, zIndex: 200, padding: '8px 0',
          maxHeight: 480, overflowY: 'auto',
        }}>
          {categories.map(([cat, items]) => (
            <div key={cat}>
              <div style={{
                fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em',
                color: 'rgba(255,255,255,0.3)', padding: '8px 16px 4px',
              }}>
                {CATEGORY_ICONS[cat]} {cat}
              </div>
              {items.map((contract) => {
                const pill = PILL_COLORS[contract.status] ?? PILL_COLORS['Archived']
                return (
                  <div
                    key={contract.id}
                    onClick={() => { setOpen(false); navigate('/contracts') }}
                    style={{
                      padding: '8px 16px', fontSize: 12,
                      color: 'rgba(255,255,255,0.7)', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.07)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {contract.id === 'wip' ? <strong style={{ color: '#ffffff' }}>{contract.title}</strong> : contract.title}
                    </span>
                    <span style={{
                      fontSize: 9, padding: '2px 6px', borderRadius: 4, flexShrink: 0,
                      background: pill.bg, color: pill.color, fontWeight: 500,
                    }}>
                      {contract.status}
                    </span>
                  </div>
                )
              })}
            </div>
          ))}
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
          e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
          e.currentTarget.style.color = '#ffffff'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = 'rgba(255,255,255,0.58)'
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

  useEffect(() => {
    function onCollapse(e: Event) {
      setCollapsed((e as CustomEvent<boolean>).detail)
    }
    window.addEventListener('topbar-collapse', onCollapse)
    return () => window.removeEventListener('topbar-collapse', onCollapse)
  }, [])

  return (
    <div
      className="fixed right-0 z-40 flex h-[44px] items-center gap-2 px-5"
      style={{
        top: 114,
        left: 'var(--sidebar-w, 216px)',
        background: '#132030',
        maxHeight: collapsed ? 0 : 44,
        overflow: 'hidden',
        opacity: collapsed ? 0 : 1,
        transition: 'max-height 0.3s ease, opacity 0.2s ease',
      }}
    >
      <MyContractsBtn />
      <MyEntitiesBtn />
      <GhostBtn label="▶  Start Live Session" />
      <GhostBtn label="+ New Contract" />
      <GhostBtn label="⊟ Browse Templates" />
      <GhostBtn label="⌕ Find a User" />
      <GhostBtn label="⚡ Negotiation Prep" />
      <GhostBtn label="✓ My Obligations" />
      <GhostBtn label="◎ Sol Balance" />
      <GhostBtn label="✦ Ask AI" />
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
