import { useState, useEffect, useRef } from 'react'
import { NavLink } from 'react-router-dom'
import {
  HomeIcon,
  DocumentTextIcon,
  ClipboardDocumentListIcon,
  CreditCardIcon,
  VideoCameraIcon,
  UserGroupIcon,
  RectangleStackIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  BellIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline'

function emojiIcon(emoji: string): React.ElementType {
  return function EmojiIcon(_: { className?: string; style?: React.CSSProperties }) {
    return <span style={{ fontSize: 15, lineHeight: 1 }}>{emoji}</span>
  }
}

const nav = [
  { to: '/dashboard',   label: 'Dashboard',           Icon: HomeIcon },
  { to: '/contracts',   label: 'Contracts',            Icon: DocumentTextIcon },
  { to: '/obligations', label: 'Obligations',          Icon: ClipboardDocumentListIcon },
  { to: '/payments',    label: 'Payments',             Icon: CreditCardIcon },
  { to: '/sessions',    label: 'Live Sessions',        Icon: VideoCameraIcon },
  { to: '/sol',         label: 'Sol Groups',           Icon: UserGroupIcon },
  { to: '/templates',   label: 'Templates',            Icon: RectangleStackIcon },
  { to: '/search',      label: 'Search',               Icon: MagnifyingGlassIcon },
  { to: '/ai',          label: 'AI Assistant',         Icon: SparklesIcon },
  { to: '/analysis',    label: 'Contract Analysis',    Icon: emojiIcon('🔍') },
  { to: '/counter',     label: 'Contract Counter',     Icon: emojiIcon('⚡') },
  { to: '/entities',    label: 'My Businesses',        Icon: emojiIcon('🏢') },
]

const bottomNav = [
  { to: '/notifications', label: 'Notifications', Icon: BellIcon,         goldIcon: true },
  { to: '/profile',       label: 'My Profile',    Icon: emojiIcon('🧑'), goldIcon: false },
  { to: '/settings',      label: 'Settings',       Icon: Cog6ToothIcon,   goldIcon: false },
]

function NavItem({
  to,
  label,
  Icon,
  goldIcon = false,
  iconOnly = false,
}: {
  to: string
  label: string
  Icon: React.ElementType
  goldIcon?: boolean
  iconOnly?: boolean
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
          style={({ isActive }) =>
            isActive
              ? {
                  width: 40,
                  height: 40,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 8,
                  background: 'rgba(245,166,35,0.12)',
                  borderLeft: '2px solid #F5A623',
                  textDecoration: 'none',
                }
              : {
                  width: 40,
                  height: 40,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 8,
                  background: 'transparent',
                  textDecoration: 'none',
                }
          }
        >
          <Icon
            className="h-[18px] w-[18px] shrink-0"
            style={goldIcon ? { color: '#F5A623' } : { color: 'rgba(255,255,255,0.62)' }}
          />
        </NavLink>
        {tooltipVisible && (
          <div
            style={{
              position: 'fixed',
              left: tooltipPos.left,
              top: tooltipPos.top,
              transform: 'translateY(-50%)',
              background: '#1C2B3A',
              color: 'white',
              fontSize: 11,
              padding: '4px 10px',
              borderRadius: 6,
              whiteSpace: 'nowrap',
              zIndex: 500,
              pointerEvents: 'none',
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
      style={({ isActive }) =>
        isActive
          ? {
              display: 'flex',
              alignItems: 'center',
              gap: 11,
              padding: '10px 10px 10px 10px',
              borderRadius: 8,
              marginBottom: 2,
              fontSize: 14,
              fontWeight: 500,
              color: '#ffffff',
              background: 'rgba(245,166,35,0.12)',
              borderLeft: '2px solid #F5A623',
              paddingLeft: 10,
              textDecoration: 'none',
            }
          : {
              display: 'flex',
              alignItems: 'center',
              gap: 11,
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 2,
              fontSize: 14,
              fontWeight: 400,
              color: 'rgba(255,255,255,0.62)',
              textDecoration: 'none',
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
        style={goldIcon ? { color: '#F5A623' } : undefined}
      />
      {label}
    </NavLink>
  )
}

export default function Sidebar() {
  const [iconOnly, setIconOnly] = useState(false)

  useEffect(() => {
    function onSidebarMode(e: Event) {
      const ce = e as CustomEvent<string>
      if (ce.detail === 'icon-only') setIconOnly(true)
      else if (ce.detail === 'normal') setIconOnly(false)
    }
    window.addEventListener('sidebar-mode', onSidebarMode)
    return () => window.removeEventListener('sidebar-mode', onSidebarMode)
  }, [])

  return (
    <aside
      className="fixed top-0 left-0 bottom-0 z-40 flex flex-col"
      style={{
        width: iconOnly ? 48 : 216,
        background: '#1C2B3A',
        transition: 'width 0.3s ease',
        overflow: 'hidden',
      }}
    >
      {/* Brand section */}
      {iconOnly ? (
        <div style={{ textAlign: 'center', fontSize: 14, fontWeight: 800, color: '#F5A623', padding: '14px 0' }}>
          B
        </div>
      ) : (
        <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.2em',
            textTransform: 'uppercase',
            marginBottom: 4,
          }}>
            <span style={{ color: 'rgba(255,255,255,0.45)' }}>bon</span>
            <span style={{ color: '#F5A623' }}>UP</span>
          </div>
          <div style={{
            fontSize: 26,
            fontWeight: 800,
            letterSpacing: '-0.02em',
            color: '#ffffff',
            lineHeight: 1,
          }}>
            Blackboard
          </div>
        </div>
      )}

      {/* Main nav */}
      <nav className={`flex-1 overflow-y-auto ${iconOnly ? 'px-1 py-3' : 'px-3 py-3'}`}>
        {nav.map((item) => (
          <NavItem key={item.to} {...item} iconOnly={iconOnly} />
        ))}
      </nav>

      {/* Bottom nav */}
      <div
        style={{
          borderTop: '1px solid rgba(255,255,255,0.08)',
          ...(iconOnly ? { padding: '12px 4px' } : undefined),
        }}
        className={iconOnly ? '' : 'px-3 py-3'}
      >
        {bottomNav.map((item) => (
          <NavItem key={item.to} {...item} iconOnly={iconOnly} />
        ))}
      </div>
    </aside>
  )
}
