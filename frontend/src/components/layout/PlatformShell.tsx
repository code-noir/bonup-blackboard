import CustomerSignOutButton from './CustomerSignOutButton'
import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BellIcon,
  ChatBubbleLeftRightIcon,
  ClipboardDocumentListIcon,
  Cog6ToothIcon,
  CreditCardIcon,
  GlobeAltIcon,
  HomeIcon,
  IdentificationIcon,
  RectangleStackIcon,
  ShoppingBagIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'
import ViewAsBanner from './ViewAsBanner'

type PlatformNavItemDefinition = {
  to?: string
  label: string
  Icon: React.ElementType
  indent?: boolean
  disabled?: boolean
  blackbodEntry?: boolean
}

type PlatformNavGroup = {
  label: string
  items: PlatformNavItemDefinition[]
}

function platformNavGroups(hasBlackboardAccess: boolean): PlatformNavGroup[] {
  return [
    {
      label: 'Platform',
      items: [
        { to: '/hub', label: 'Home', Icon: HomeIcon },
        { to: '/account', label: 'Profile', Icon: IdentificationIcon },
        { label: 'Messages', Icon: ChatBubbleLeftRightIcon, disabled: true },
          hasBlackboardAccess
          ? { to: '/apps/blackbod/notifications', label: 'Notifications', Icon: BellIcon, blackbodEntry: true }
          : { label: 'Notifications', Icon: BellIcon, disabled: true },
      ],
    },
    {
      label: 'Applications',
      items: [
        { to: '/apps/nislo', label: 'Nislo', Icon: GlobeAltIcon },
        ...(hasBlackboardAccess
          ? [
              { to: '/apps/blackbod', label: 'Blackboard', Icon: ClipboardDocumentListIcon, blackbodEntry: true },
              { to: '/apps/blackbod/workspace', label: 'Agreement Activity', Icon: ClipboardDocumentListIcon, indent: true, blackbodEntry: true },
            ]
          : []),
      ],
    },
    {
      label: 'Services',
      items: [
        { to: '/vault', label: 'Vault', Icon: RectangleStackIcon },
        { to: '/store', label: 'Store', Icon: ShoppingBagIcon },
        { to: '/billing', label: 'Billing', Icon: CreditCardIcon },
      ],
    },
    {
      label: 'Account',
      items: [
        { to: '/account', label: 'Account / Identity', Icon: IdentificationIcon },
        { to: '/settings', label: 'Settings', Icon: Cog6ToothIcon },
      ],
    },
  ]
}

function PlatformNavItem({ item, compact }: { item: PlatformNavItemDefinition; compact: boolean }) {
  const content = (
    <>
      <item.Icon className="h-[18px] w-[18px] shrink-0" />
      {!compact && <span>{item.label}</span>}
    </>
  )

  if (item.disabled || !item.to) {
    return (
      <div
        title={compact ? `${item.label} (not available yet)` : undefined}
        style={{
          alignItems: 'center',
          color: '#948A80',
          display: 'flex',
          fontSize: 14,
          fontWeight: 500,
          gap: 11,
          minHeight: 40,
          padding: compact ? '0 10px' : item.indent ? '10px 12px 10px 28px' : '10px 12px',
          whiteSpace: 'nowrap',
        }}
      >
        {content}
      </div>
    )
  }

  return (
    <NavLink
      to={item.to}
      state={item.blackbodEntry ? { blackbodEntry: true } : undefined}
      className="platform-nav-item"
      end={item.to !== '/apps/blackbod' && item.to !== '/apps/nislo' && item.to !== '/vault' && item.to !== '/store'}
      style={({ isActive }) => ({
        alignItems: 'center',
        background: isActive ? '#D8C7B2' : 'transparent',
        borderLeft: isActive ? '2px solid #C99A3D' : '2px solid transparent',
        borderRadius: 8,
        color: isActive ? '#202124' : '#4D4842',
        display: 'flex',
        fontSize: 14,
        fontWeight: isActive ? 700 : 500,
        gap: 11,
        minHeight: 40,
        padding: compact ? '0 10px' : item.indent ? '10px 12px 10px 28px' : '10px 12px',
        textDecoration: 'none',
        whiteSpace: 'nowrap',
      })}
      title={compact ? item.label : undefined}
    >
      {content}
    </NavLink>
  )
}

function PlatformGroupLabel({ label, compact }: { label: string; compact: boolean }) {
  return compact ? (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', margin: '10px 4px 8px' }} aria-label={label} />
  ) : (
    <div style={{ color: 'rgba(255,255,255,0.34)', fontSize: 9, fontWeight: 800, letterSpacing: '0.16em', padding: '12px 12px 5px', textTransform: 'uppercase' }}>
      {label}
    </div>
  )
}

export default function PlatformShell() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [compact, setCompact] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const query = window.matchMedia('(max-width: 1100px)')
    const update = () => setCompact(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const navGroups = platformNavGroups(user?.has_blackbod_access === true)
  const navItems = navGroups.flatMap((group) => group.items)
  const sidebarWidth = compact ? 64 : 232
  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || ''
  const initials = ([user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('') || '?').toUpperCase()
  const currentTitle = navItems.find((item) => item.to && (location.pathname === item.to || location.pathname.startsWith(item.to + '/')))?.label || 'Home'

  return (
    <div className="min-h-screen bg-[#F7F7F6]" style={{ ['--sidebar-w' as string]: `${sidebarWidth}px` }}>
      <ViewAsBanner />
      <aside
        className="fixed bottom-0 left-0 top-0 z-40 flex flex-col"
        style={{ background: '#E8DED0', borderRight: '1px solid #DDD7CF', color: '#202124', overflow: 'hidden', transition: 'width 0.3s ease', width: sidebarWidth }}
      >
        <div style={{ background: '#F2ECE4', borderBottom: '1px solid #DDD7CF', padding: compact ? '18px 0' : '22px 20px 18px', textAlign: compact ? 'center' : 'left' }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', marginBottom: compact ? 0 : 4, textTransform: 'uppercase' }}>
            <span style={{ color: '#66615C' }}>bon</span>
            <span style={{ color: '#C99A3D' }}>UP</span>
          </div>
          {!compact && <div style={{ color: '#202124', fontSize: 24, fontWeight: 800, lineHeight: 1 }}>World</div>}
        </div>

        <nav className={`flex-1 overflow-y-auto ${compact ? 'px-2 py-3' : 'px-3 py-3'}`}>
          {navGroups.map((group) => (
            <div key={group.label}>
              <PlatformGroupLabel label={group.label} compact={compact} />
              {group.items.map((item) => <PlatformNavItem key={item.label} item={item} compact={compact} />)}
            </div>
          ))}
        </nav>
      </aside>

      <header
        className="fixed right-0 top-0 z-30 flex h-[64px] items-center justify-between border-b border-slate-200 bg-white px-6"
        style={{ left: sidebarWidth }}
      >
        <div>
          <p style={{ color: '#D4900A', fontSize: 13, fontWeight: 800, letterSpacing: '0.14em', margin: 0, textTransform: 'uppercase' }}>bonUP</p>
          <p style={{ color: '#0F1F3D', fontSize: 16, fontWeight: 800, margin: '2px 0 0' }}>{currentTitle}</p>
        </div>
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((value) => !value)}
            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm text-slate-700"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#243447] text-[11px] font-bold text-white">{initials}</span>
            {!compact && <span className="max-w-[160px] truncate">{displayName}</span>}
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-2 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg" style={{ zIndex: 9999 }}>
              <div className="border-b border-slate-100 px-4 py-2">
                <p className="text-xs text-slate-500">Signed in as</p>
                <p className="truncate text-sm font-medium text-slate-800">{user?.email}</p>
              </div>
              <button type="button" onClick={() => { setMenuOpen(false); navigate('/account') }} className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50">Account / Identity</button>
              <button type="button" onClick={() => { setMenuOpen(false); navigate('/billing') }} className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50">Billing</button>
              <button type="button" onClick={() => { setMenuOpen(false); navigate('/settings') }} className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50">Settings</button>
              <CustomerSignOutButton />
            </div>
          )}
        </div>
      </header>

      <main className="min-h-screen px-6 pb-10 pt-[88px]" style={{ marginLeft: sidebarWidth }}>
        <Outlet />
      </main>
    </div>
  )
}
