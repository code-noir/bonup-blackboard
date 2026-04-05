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

const nav = [
  { to: '/dashboard',    label: 'Dashboard',    Icon: HomeIcon },
  { to: '/contracts',    label: 'Contracts',     Icon: DocumentTextIcon },
  { to: '/obligations',  label: 'Obligations',   Icon: ClipboardDocumentListIcon },
  { to: '/payments',     label: 'Payments',      Icon: CreditCardIcon },
  { to: '/sessions',     label: 'Live Sessions', Icon: VideoCameraIcon },
  { to: '/sol',          label: 'Sol Groups',    Icon: UserGroupIcon },
  { to: '/templates',    label: 'Templates',     Icon: RectangleStackIcon },
  { to: '/search',       label: 'Search',        Icon: MagnifyingGlassIcon },
  { to: '/ai',           label: 'AI Assistant',  Icon: SparklesIcon },
]

const bottomNav = [
  { to: '/notifications', label: 'Notifications', Icon: BellIcon,      goldIcon: true },
  { to: '/settings',      label: 'Settings',       Icon: Cog6ToothIcon, goldIcon: false },
]

function NavItem({
  to,
  label,
  Icon,
  goldIcon = false,
}: {
  to: string
  label: string
  Icon: React.ElementType
  goldIcon?: boolean
}) {
  return (
    <NavLink
      to={to}
      style={({ isActive }) =>
        isActive
          ? {
              display: 'flex', alignItems: 'center', gap: 11,
              padding: '9px 8px 9px 8px',
              borderRadius: 7,
              fontSize: 13.5,
              fontWeight: 500,
              color: '#ffffff',
              background: 'rgba(139,92,246,0.14)',
              borderLeft: '2px solid #8B5CF6',
              textDecoration: 'none',
            }
          : {
              display: 'flex', alignItems: 'center', gap: 11,
              padding: '9px 10px',
              borderRadius: 7,
              fontSize: 13.5,
              fontWeight: 400,
              color: 'rgba(255,255,255,0.42)',
              textDecoration: 'none',
            }
      }
      onMouseEnter={(e) => {
        if (!e.currentTarget.getAttribute('aria-current')) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
          e.currentTarget.style.color = 'rgba(255,255,255,0.82)'
        }
      }}
      onMouseLeave={(e) => {
        if (!e.currentTarget.getAttribute('aria-current')) {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = 'rgba(255,255,255,0.42)'
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
  return (
    <aside
      className="fixed top-0 left-0 bottom-0 z-40 flex flex-col"
      style={{ width: 216, background: '#09111F' }}
    >
      {/* Brand section */}
      <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 4 }}>
          <span style={{ color: 'rgba(255,255,255,0.38)' }}>bon</span>
          <span style={{ color: 'rgba(245,166,35,0.55)' }}>UP</span>
        </div>
        <div
          style={{
            fontSize: 28,
            fontWeight: 800,
            letterSpacing: '-0.03em',
            color: '#ffffff',
            textShadow: '0 0 1px #fff, 0 0 8px rgba(255,255,255,0.4)',
            lineHeight: 1,
          }}
        >
          Blackboard
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
        {nav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="px-3 py-3 space-y-0.5" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        {bottomNav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </div>
    </aside>
  )
}
