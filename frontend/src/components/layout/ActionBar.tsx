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
  return (
    <div
      className="fixed right-0 z-40 flex h-[44px] items-center gap-2 px-5"
      style={{ top: 114, left: 'var(--sidebar-w, 216px)', background: '#132030' }}
    >
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
