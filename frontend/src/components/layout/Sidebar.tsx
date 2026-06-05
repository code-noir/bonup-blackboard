import { useState, useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import {
  HomeIcon,
  ClipboardDocumentListIcon,
  CreditCardIcon,
  VideoCameraIcon,
  UserGroupIcon,
  RectangleStackIcon,
  SparklesIcon,
  Cog6ToothIcon,
  BuildingOffice2Icon,
  BoltIcon,
  ComputerDesktopIcon,
} from '@heroicons/react/24/outline'

function emojiIcon(emoji: string): React.ElementType {
  return function EmojiIcon(_: { className?: string; style?: React.CSSProperties }) {
    return <span style={{ fontSize: 15, lineHeight: 1 }}>{emoji}</span>
  }
}

// ---------------------------------------------------------------------------
// User workspace nav
// ---------------------------------------------------------------------------

const userNav = [
  { to: '/dashboard',   label: 'Dashboard',            Icon: HomeIcon },
  { to: '/workspace',   label: 'Workspace',            Icon: RectangleStackIcon },
  { to: '/resource',    label: 'Resource',             Icon: ClipboardDocumentListIcon },
  { to: '/contacts',    label: 'Contacts',             Icon: emojiIcon('👥') },
  { to: '/ai',          label: 'AI Assistant',         Icon: SparklesIcon },
  { to: '/analysis',    label: 'Contract Analysis',    Icon: emojiIcon('🔍') },
  { to: '/counter',     label: 'Contract Counter',     Icon: emojiIcon('⚡') },
  { to: '/entities',    label: 'My Businesses',        Icon: emojiIcon('🏢') },
]

const userBottomNav = [
  { to: '/profile',       label: 'My Profile',    Icon: emojiIcon('🧑'), goldIcon: false },
  { to: '/settings',      label: 'Settings',       Icon: Cog6ToothIcon,   goldIcon: false },
  { to: '/billing',       label: 'Billing',        Icon: emojiIcon('💳'), goldIcon: false },
]

// ---------------------------------------------------------------------------
// Operator Console nav — aligned with bonUP/Blackboard product hierarchy
// Section headers break the nav into: bonUP | Blackboard | System
// ---------------------------------------------------------------------------

type NavDef =
  | { type?: undefined; to: string; label: string; Icon: React.ElementType; goldIcon?: boolean }
  | { type: 'section'; label: string }

const operatorNav: NavDef[] = [
  { to: '/admin', label: 'Dashboard', Icon: HomeIcon },

  { type: 'section', label: 'bonUP' },
  { to: '/admin/users', label: 'Users', Icon: emojiIcon('👤') },

  { type: 'section', label: 'Blackboard' },
  { to: '/admin/subscriptions', label: 'Subscriptions', Icon: CreditCardIcon },
  { to: '/admin/plans',         label: 'Plans',          Icon: RectangleStackIcon },
  { to: '/admin/contracts',     label: 'Contracts',      Icon: ClipboardDocumentListIcon },
  { to: '/admin/entities',      label: 'Entities',       Icon: BuildingOffice2Icon },
  { to: '/admin/sol',           label: 'Sol Groups',     Icon: UserGroupIcon },
  { to: '/admin/activity',      label: 'Activity',       Icon: BoltIcon },

  { type: 'section', label: 'System' },
  { to: '/admin/live-sessions', label: 'Live Sessions', Icon: VideoCameraIcon },
]

const operatorBottomNav: NavDef[] = [
  { to: '/admin/profile',  label: 'My Profile', Icon: emojiIcon('🧑'), goldIcon: false },
  { to: '/admin/settings', label: 'Settings',    Icon: Cog6ToothIcon,   goldIcon: false },
]

// ---------------------------------------------------------------------------
// SectionHeader — nav group label (collapsed to thin rule in icon-only mode)
// ---------------------------------------------------------------------------

function SectionHeader({ label, iconOnly }: { label: string; iconOnly: boolean }) {
  if (iconOnly) {
    return (
      <div style={{
        height: 1,
        background: 'rgba(255,255,255,0.08)',
        margin: '8px 4px',
      }} />
    )
  }
  return (
    <div style={{
      fontSize: 9,
      fontWeight: 700,
      letterSpacing: '0.16em',
      textTransform: 'uppercase',
      color: 'rgba(255,255,255,0.28)',
      padding: '12px 12px 4px',
    }}>
      {label}
    </div>
  )
}

// ---------------------------------------------------------------------------
// NavItem
// ---------------------------------------------------------------------------

function NavItem({
  to,
  label,
  Icon,
  goldIcon = false,
  iconOnly = false,
  activeColor = '#F5A623',
  activeBg = 'rgba(245,166,35,0.12)',
}: {
  to: string
  label: string
  Icon: React.ElementType
  goldIcon?: boolean
  iconOnly?: boolean
  activeColor?: string
  activeBg?: string
}) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [tooltipVisible, setTooltipVisible] = useState(false)
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 })

  if (iconOnly) {
    return (
      <div
        ref={wrapperRef}
        style={{ position: 'relative', marginBottom: 2 }}
        onMouseEnter={() => {
          const rect = wrapperRef.current?.getBoundingClientRect()
          if (rect) {
            setTooltipPos({ left: rect.right + 8, top: rect.top + rect.height / 2 })
          }
          setTooltipVisible(true)
        }}
        onMouseLeave={() => setTooltipVisible(false)}
      >
        <NavLink
          to={to}
          end
          style={({ isActive }) =>
            isActive
              ? {
                  width: 40, height: 40, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', borderRadius: 8,
                  background: activeBg,
                  borderLeft: `2px solid ${activeColor}`,
                  textDecoration: 'none',
                }
              : {
                  width: 40, height: 40, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', borderRadius: 8,
                  background: 'transparent', textDecoration: 'none',
                }
          }
        >
          <Icon
            className="h-[18px] w-[18px] shrink-0"
            style={goldIcon ? { color: activeColor } : { color: 'rgba(255,255,255,0.62)' }}
          />
        </NavLink>
        {tooltipVisible && (
          <div
            style={{
              position: 'fixed', left: tooltipPos.left, top: tooltipPos.top,
              transform: 'translateY(-50%)',
              background: '#1C2B3A', color: 'white', fontSize: 11,
              padding: '4px 10px', borderRadius: 6, whiteSpace: 'nowrap',
              zIndex: 500, pointerEvents: 'none',
              border: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            {label}
          </div>
        )}
      </div>
    )
  }

  return (
    <NavLink
      to={to}
      end
      style={({ isActive }) =>
        isActive
          ? {
              display: 'flex', alignItems: 'center', gap: 11,
              padding: '10px 10px', borderRadius: 8, marginBottom: 2,
              fontSize: 14, fontWeight: 500, color: '#ffffff',
              background: activeBg,
              borderLeft: `2px solid ${activeColor}`,
              textDecoration: 'none',
            }
          : {
              display: 'flex', alignItems: 'center', gap: 11,
              padding: '10px 12px', borderRadius: 8, marginBottom: 2,
              fontSize: 14, fontWeight: 400,
              color: 'rgba(255,255,255,0.62)', textDecoration: 'none',
            }
      }
      onMouseEnter={(e) => {
        if (!e.currentTarget.getAttribute('aria-current')) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
          e.currentTarget.style.color = '#ffffff'
        }
      }}
      onMouseLeave={(e) => {
        if (!e.currentTarget.getAttribute('aria-current')) {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = 'rgba(255,255,255,0.62)'
        }
      }}
    >
      <Icon
        className="h-[18px] w-[18px] shrink-0"
        style={goldIcon ? { color: activeColor } : undefined}
      />
      {label}
    </NavLink>
  )
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

export default function Sidebar() {
  const [iconOnly, setIconOnly] = useState(false)
  const { user } = useAuth()
  const location = useLocation()

  // Operator mode is route-based: follows URL, not user identity.
  const isOperator = location.pathname.startsWith('/admin')

  useEffect(() => {
    function onSidebarMode(e: Event) {
      const ce = e as CustomEvent<string>
      if (ce.detail === 'icon-only') setIconOnly(true)
      else if (ce.detail === 'normal') setIconOnly(false)
    }
    window.addEventListener('sidebar-mode', onSidebarMode)
    return () => window.removeEventListener('sidebar-mode', onSidebarMode)
  }, [])

  // Operator mode uses sky blue active accent; user mode uses gold.
  const activeColor = isOperator ? '#38BDF8' : '#F5A623'
  const activeBg    = isOperator ? 'rgba(56,189,248,0.12)' : 'rgba(245,166,35,0.12)'

  // In user mode, staff users get an "Operator Console" entry in bottom nav.
  const baseUserBottom: NavDef[] = userBottomNav
  const footerNav: NavDef[] = (!isOperator && user?.is_staff)
    ? [...baseUserBottom, { to: '/admin', label: 'Operator Console', Icon: ComputerDesktopIcon, goldIcon: false }]
    : (isOperator ? operatorBottomNav : baseUserBottom)

  const mainNav: NavDef[] = isOperator ? operatorNav : userNav

  function renderNavItem(item: NavDef, idx: number) {
    if (item.type === 'section') {
      return <SectionHeader key={`section-${item.label}-${idx}`} label={item.label} iconOnly={iconOnly} />
    }
    return (
      <NavItem
        key={item.to}
        to={item.to}
        label={item.label}
        Icon={item.Icon}
        goldIcon={item.goldIcon}
        iconOnly={iconOnly}
        activeColor={activeColor}
        activeBg={activeBg}
      />
    )
  }

  return (
    <aside
      className="fixed top-0 left-0 bottom-0 z-40 flex flex-col"
      style={{
        width: iconOnly ? 48 : 216,
        background: '#111827',
        borderRight: '1px solid rgba(255,255,255,0.10)',
        boxShadow: '8px 0 24px rgba(15,23,42,0.12)',
        transition: 'width 0.3s ease',
        overflow: 'hidden',
      }}
    >
      {/* Brand */}
      {iconOnly ? (
        <div style={{
          textAlign: 'center', fontSize: 14, fontWeight: 800,
          color: '#F5A623',
          padding: '14px 0',
        }}>
          B
        </div>
      ) : (
        <div style={{ padding: '22px 20px 18px', background: '#0B1220', borderBottom: '1px solid rgba(255,255,255,0.10)' }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 4 }}>
            <span style={{ color: 'rgba(255,255,255,0.45)' }}>bon</span>
            <span style={{ color: '#F5A623' }}>UP</span>
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em', color: '#ffffff', lineHeight: 1 }}>
            Blackboard
          </div>
          {isOperator && (
            <div style={{
              marginTop: 6, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: '#38BDF8',
            }}>
              Operator Mode
            </div>
          )}
        </div>
      )}

      {/* Main nav */}
      <nav className={`flex-1 overflow-y-auto ${iconOnly ? 'px-1 py-3' : 'px-3 py-3'}`}>
        {mainNav.map((item, idx) => renderNavItem(item, idx))}
      </nav>

      {/* Bottom nav */}
      <div
        style={{ background: 'rgba(15,23,42,0.55)', borderTop: '1px solid rgba(255,255,255,0.10)', ...(iconOnly ? { padding: '12px 4px' } : undefined) }}
        className={iconOnly ? '' : 'px-3 py-3'}
      >
        {footerNav.map((item, idx) => renderNavItem(item, idx))}
      </div>
    </aside>
  )
}
