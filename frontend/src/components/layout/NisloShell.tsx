import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  ArrowLeftIcon,
  BellAlertIcon,
  BellIcon,
  ChatBubbleLeftRightIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  GlobeAltIcon,
  HomeModernIcon,
  MagnifyingGlassIcon,
  RectangleStackIcon,
  UserCircleIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'
import CustomerSignOutButton from './CustomerSignOutButton'

const navItems = [
  { to: '/apps/nislo/discover', label: 'Discover', Icon: GlobeAltIcon },
  { to: '/apps/nislo/friends', label: 'Friends', Icon: UserGroupIcon },
  { to: '/apps/nislo/invites', label: 'Invites', Icon: BellAlertIcon },
  { to: '/apps/nislo/communities', label: 'My Communities', Icon: HomeModernIcon },
]

function sidebarItems(hasBlackboardAccess: boolean) {
  return [
    { to: '/hub', label: 'Home', Icon: HomeModernIcon, exact: true },
    { to: '/apps/nislo', label: 'Nislo', Icon: GlobeAltIcon },
    ...(hasBlackboardAccess ? [{ to: '/apps/blackbod', label: 'Blackboard', Icon: RectangleStackIcon }] : []),
    { to: '/vault', label: 'Vault', Icon: RectangleStackIcon },
    { label: 'Messages', Icon: ChatBubbleLeftRightIcon, disabled: true },
    ...(hasBlackboardAccess ? [{ to: '/notifications', label: 'Notifications', Icon: BellIcon }] : []),
    { to: '/account', label: 'Profile', Icon: UserCircleIcon, exact: true },
    { to: '/settings', label: 'Settings', Icon: Cog6ToothIcon, exact: true },
  ]
}

function NavItem({ to, label, Icon }: { to: string; label: string; Icon: React.ElementType }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => `nislo-nav-item ${isActive ? 'nislo-nav-item-active' : ''}`}
    >
      <Icon className="h-5 w-5" />
      <span>{label}</span>
    </NavLink>
  )
}

function SidebarItem({ to, label, Icon, exact = false, disabled = false }: { to?: string; label: string; Icon: React.ElementType; exact?: boolean; disabled?: boolean }) {
  if (disabled || !to) {
    return (
      <button className="nislo-sidebar-item nislo-shell-disabled" type="button" disabled title={`${label} is not available in this slice`}>
        <Icon className="h-[18px] w-[18px] shrink-0" />
        <span className="nislo-sidebar-label">{label}</span>
      </button>
    )
  }
  return (
    <NavLink
      to={to}
      end={exact}
      className={({ isActive }) => `nislo-sidebar-item ${isActive ? 'nislo-sidebar-item-active' : ''}`}
      title={label}
    >
      <Icon className="h-[18px] w-[18px] shrink-0" />
      <span className="nislo-sidebar-label">{label}</span>
    </NavLink>
  )
}

export default function NisloShell() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const hasBlackboardAccess = user?.has_blackbod_access === true
  const platformSidebarItems = sidebarItems(hasBlackboardAccess)
  const initials = ([user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('') || '?').toUpperCase()
  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || 'bonUP member'

  return (
    <div className="nislo-app">
      <header className="nislo-platform-bar">
        <div className="nislo-platform-context">
          <button type="button" className="nislo-platform-logo" onClick={() => navigate('/hub')} aria-label="Return to bonUP Home">
            <ArrowLeftIcon className="h-4 w-4" />
            <span><b>bon</b><strong>UP</strong></span>
          </button>
          <span className="nislo-platform-divider" aria-hidden="true" />
          <span className="nislo-platform-app">Nislo</span>
        </div>
        <div className="nislo-platform-search" aria-label="bonUP search is not available in this slice">
          <MagnifyingGlassIcon className="h-4 w-4" />
          <span>Search bonUP</span>
          <span className="nislo-shell-note">Coming later</span>
        </div>
        <div className="nislo-platform-actions">
          {hasBlackboardAccess && (
            <NavLink className="nislo-platform-icon" to="/notifications" aria-label="Notifications" title="Notifications">
              <BellIcon className="h-5 w-5" />
            </NavLink>
          )}
          <button className="nislo-platform-icon nislo-shell-disabled" type="button" disabled aria-label="Messages are not available yet" title="Messages are not available in this slice">
            <ChatBubbleLeftRightIcon className="h-5 w-5" />
          </button>
          <div className="nislo-user-menu-wrap">
          <button
            type="button"
            className="nislo-user-button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
          >
            <span className="nislo-avatar nislo-avatar-gold">{initials}</span>
            <span className="nislo-user-name">{displayName}</span>
            <ChevronDownIcon className="h-4 w-4 opacity-60" />
          </button>
          {menuOpen && (
            <div className="nislo-user-menu">
              <p className="nislo-menu-label">Signed in as</p>
              <p className="nislo-menu-email">{user?.email}</p>
              <button type="button" onClick={() => { setMenuOpen(false); navigate('/account') }}>Account / Identity</button>
              <CustomerSignOutButton />
            </div>
          )}
          </div>
        </div>
      </header>

      <aside className="nislo-platform-sidebar" aria-label="bonUP platform navigation">
        <div className="nislo-sidebar-heading">bonUP</div>
        <p className="nislo-sidebar-section-label">Platform</p>
        <nav className="nislo-sidebar-nav">
          {platformSidebarItems.map((item) => <SidebarItem key={item.to || item.label} {...item} />)}
        </nav>
        <div className="nislo-sidebar-promo">
          <span className="nislo-sidebar-promo-mark">✦</span>
          <strong>Bring your people</strong>
          <span>Invite someone into your circle.</span>
          <button type="button" onClick={() => navigate('/apps/nislo/invites?invite=1')}>Invite people</button>
        </div>
        <div className="nislo-sidebar-footer">Nislo / Golden Nest</div>
      </aside>

      <div className="nislo-workspace-bar">
        <div className="nislo-workspace-heading">
          <span className="nislo-wordmark-mark">✦</span>
          <div>
            <p className="nislo-eyebrow">bonUP social application</p>
            <p className="nislo-wordmark-title">NISLO</p>
          </div>
        </div>
        <nav className="nislo-primary-nav" aria-label="Nislo workspace navigation">
          {navItems.map((item) => <NavItem key={item.to} {...item} />)}
        </nav>
      </div>

      <main className="nislo-main">
        <div className="nislo-page-wrap">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
