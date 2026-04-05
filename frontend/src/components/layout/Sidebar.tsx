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
  { to: '/dashboard',   label: 'Dashboard',    Icon: HomeIcon },
  { to: '/contracts',   label: 'Contracts',     Icon: DocumentTextIcon },
  { to: '/obligations', label: 'Obligations',   Icon: ClipboardDocumentListIcon },
  { to: '/payments',    label: 'Payments',      Icon: CreditCardIcon },
  { to: '/sessions',    label: 'Live Sessions', Icon: VideoCameraIcon },
  { to: '/sol',         label: 'Sol Groups',    Icon: UserGroupIcon },
  { to: '/templates',   label: 'Templates',     Icon: RectangleStackIcon },
  { to: '/search',      label: 'Search',        Icon: MagnifyingGlassIcon },
  { to: '/ai',          label: 'AI Assistant',  Icon: SparklesIcon },
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
  return (
    <aside
      className="fixed top-0 left-0 bottom-0 z-40 flex flex-col"
      style={{ width: 216, background: '#1C2B3A' }}
    >
      {/* Brand section */}
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

      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3">
        {nav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="px-3 py-3" style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        {bottomNav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </div>
    </aside>
  )
}
