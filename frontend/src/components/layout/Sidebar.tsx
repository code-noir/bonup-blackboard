import { useState, useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
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
  { to: '/apps/blackbod/dashboard',   label: 'Dashboard',            Icon: HomeIcon },
  { to: '/apps/blackbod/workspace',   label: 'Workspace',            Icon: RectangleStackIcon },
  { to: '/apps/blackbod/resource',    label: 'Resource',             Icon: ClipboardDocumentListIcon },
  { to: '/apps/blackbod/contacts',    label: 'Contacts',             Icon: emojiIcon('👥') },
  { to: '/apps/blackbod/ai',          label: 'AI Assistant',         Icon: SparklesIcon },
  { to: '/apps/blackbod/analysis',    label: 'Contract Analysis',    Icon: emojiIcon('🔍') },
  { to: '/apps/blackbod/counter',     label: 'Contract Counter',     Icon: emojiIcon('⚡') },
  { to: '/apps/blackbod/agreement-performance', label: 'Agreement Performance', Icon: BoltIcon },
  { to: '/apps/blackbod/entities',    label: 'My Businesses',        Icon: emojiIcon('🏢') },
]

const userBottomNav = [
  { to: '/hub', label: 'bonUP Home', Icon: HomeIcon, goldIcon: false },
]

// ---------------------------------------------------------------------------
// Operator Console nav — aligned with the bonUP platform hierarchy
// ---------------------------------------------------------------------------

type NavDef =
  | { type?: undefined; to: string; label: string; Icon: React.ElementType; goldIcon?: boolean; indent?: boolean }
  | { type: 'section'; label: string }
  | { type: 'disabled'; label: string; Icon: React.ElementType; indent?: boolean }

const operatorNav: NavDef[] = [
  { to: '/operator', label: 'Home', Icon: HomeIcon },

  { type: 'section', label: 'Identity' },
  { to: '/operator/identity/users', label: 'Users', Icon: emojiIcon('👤') },
  { to: '/operator/identity/entities', label: 'Entities', Icon: BuildingOffice2Icon },
  { type: 'disabled', label: 'Administrators', Icon: emojiIcon('🛡') },

  { type: 'section', label: 'Applications' },
  { to: '/operator/apps/blackbod', label: 'Blackbòd Overview', Icon: ClipboardDocumentListIcon },
  { to: '/operator/apps/blackbod/agreements', label: 'Agreements', Icon: ClipboardDocumentListIcon, indent: true },
  { to: '/operator/apps/blackbod/obligations', label: 'Obligations', Icon: ClipboardDocumentListIcon, indent: true },
  { to: '/operator/apps/blackbod/activity', label: 'Activity', Icon: BoltIcon, indent: true },
  { to: '/operator/apps/sol/groups', label: 'Sol Groups', Icon: UserGroupIcon },
  { type: 'disabled', label: 'Unfair', Icon: SparklesIcon },

  { type: 'section', label: 'Billing' },
  { to: '/operator/billing/subscriptions', label: 'Subscriptions', Icon: CreditCardIcon },
  { to: '/operator/billing/plans', label: 'Plans', Icon: RectangleStackIcon },

  { type: 'section', label: 'Operations' },
  { to: '/operator/operations/live-sessions', label: 'Live Sessions', Icon: VideoCameraIcon },
]

const operatorBottomNav: NavDef[] = [
  { to: '/operator/profile', label: 'My Profile', Icon: emojiIcon('🧑'), goldIcon: false },
  { to: '/operator/settings', label: 'Settings', Icon: Cog6ToothIcon, goldIcon: false },
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
  indent = false,
  activeColor = '#F5A623',
  activeBg = 'rgba(245,166,35,0.12)',
}: {
  to: string
  label: string
  Icon: React.ElementType
  goldIcon?: boolean
  iconOnly?: boolean
  indent?: boolean
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
        style={{ position: 'relative', marginBottom: 2, marginLeft: indent ? 10 : 0 }}
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
              background: '#243447', color: 'white', fontSize: 11,
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
              padding: indent ? '10px 10px 10px 24px' : '10px 10px', borderRadius: 8, marginBottom: 2,
              fontSize: 14, fontWeight: 500, color: '#ffffff',
              background: activeBg,
              borderLeft: `2px solid ${activeColor}`,
              textDecoration: 'none',
            }
          : {
              display: 'flex', alignItems: 'center', gap: 11,
              padding: indent ? '10px 12px 10px 26px' : '10px 12px', borderRadius: 8, marginBottom: 2,
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

function DisabledNavItem({ label, Icon, iconOnly = false, indent = false }: { label: string; Icon: React.ElementType; iconOnly?: boolean; indent?: boolean }) {
  if (iconOnly) {
    return (
      <div style={{ width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 2, opacity: 0.32 }} title={`${label} (future)`}>
        <Icon className="h-[18px] w-[18px] shrink-0" />
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: indent ? '10px 12px 10px 26px' : '10px 12px', borderRadius: 8, marginBottom: 2, fontSize: 14, fontWeight: 400, color: 'rgba(255,255,255,0.32)' }}>
      <Icon className="h-[18px] w-[18px] shrink-0" />
      <span>{label}</span>
      <span style={{ marginLeft: 'auto', fontSize: 9, fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase' }}>Future</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

export default function Sidebar() {
  const [iconOnly, setIconOnly] = useState(false)
  const [forceIconOnly, setForceIconOnly] = useState(false)
  const location = useLocation()

  // Operator mode is route-based: follows URL, not user identity.
  const isOperator = location.pathname.startsWith('/operator') || location.pathname.startsWith('/admin')

  useEffect(() => {
    const query = window.matchMedia('(max-width: 1100px)')
    const update = () => setForceIconOnly(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

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
  const effectiveIconOnly = forceIconOnly || iconOnly

  const activeColor = isOperator ? '#38BDF8' : '#F5A623'
  const activeBg    = isOperator ? 'rgba(56,189,248,0.12)' : 'rgba(245,166,35,0.12)'

  const footerNav: NavDef[] = isOperator ? operatorBottomNav : userBottomNav

  const mainNav: NavDef[] = isOperator ? operatorNav : userNav

  function renderNavItem(item: NavDef, idx: number) {
    if (item.type === 'section') {
      return <SectionHeader key={`section-${item.label}-${idx}`} label={item.label} iconOnly={effectiveIconOnly} />
    }
    if (item.type === 'disabled') {
      return <DisabledNavItem key={`disabled-${item.label}-${idx}`} label={item.label} Icon={item.Icon} iconOnly={effectiveIconOnly} indent={item.indent} />
    }
    return (
      <NavItem
        key={item.to}
        to={item.to}
        label={item.label}
        Icon={item.Icon}
        goldIcon={item.goldIcon}
        iconOnly={effectiveIconOnly}
        indent={item.indent}
        activeColor={activeColor}
        activeBg={activeBg}
      />
    )
  }

  return (
    <aside
      className="app-sidebar fixed top-0 left-0 bottom-0 z-40 flex flex-col"
      style={{
        width: effectiveIconOnly ? 56 : 216,
        background: '#111827',
        borderRight: '1px solid rgba(255,255,255,0.10)',
        boxShadow: '8px 0 24px rgba(15,23,42,0.12)',
        transition: 'width 0.3s ease',
        overflow: 'hidden',
      }}
    >
      {/* Brand */}
      {effectiveIconOnly ? (
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
            {isOperator ? 'Operator' : 'Blackbòd'}
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
      <nav className={`flex-1 overflow-y-auto ${effectiveIconOnly ? 'px-1 py-3' : 'px-3 py-3'}`}>
        {mainNav.map((item, idx) => renderNavItem(item, idx))}
      </nav>

      {/* Bottom nav */}
      <div
        style={{ background: 'rgba(15,23,42,0.55)', borderTop: '1px solid rgba(255,255,255,0.10)', ...(effectiveIconOnly ? { padding: '12px 4px' } : undefined) }}
        className={effectiveIconOnly ? '' : 'px-3 py-3'}
      >
        {footerNav.map((item, idx) => renderNavItem(item, idx))}
      </div>
    </aside>
  )
}
