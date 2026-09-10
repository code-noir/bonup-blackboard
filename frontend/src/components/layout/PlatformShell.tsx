import CustomerSignOutButton from './CustomerSignOutButton'
import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  HomeIcon,
  ClipboardDocumentListIcon,
  CreditCardIcon,
  Cog6ToothIcon,
  IdentificationIcon,
  RectangleStackIcon,
  ShoppingBagIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'
import ViewAsBanner from './ViewAsBanner'

const platformNav = [
  { to: '/hub', label: 'Home', Icon: HomeIcon },
  { to: '/apps/blackbod', label: 'Blackbòd', Icon: ClipboardDocumentListIcon },
  { to: '/store', label: 'Store', Icon: ShoppingBagIcon },
  { to: '/vault', label: 'Vault', Icon: RectangleStackIcon },
  { to: '/billing', label: 'Billing', Icon: CreditCardIcon },
  { to: '/account', label: 'Account / Identity', Icon: IdentificationIcon },
  { to: '/settings', label: 'Settings', Icon: Cog6ToothIcon },
]

function PlatformNavItem({ to, label, Icon, compact }: { to: string; label: string; Icon: React.ElementType; compact: boolean }) {
  return (
    <NavLink
      to={to}
      end={to !== '/apps/blackbod' && to !== '/store' && to !== '/vault'}
      style={({ isActive }) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        minHeight: 40,
        padding: compact ? '0 10px' : '10px 12px',
        borderRadius: 8,
        color: isActive ? '#FFFFFF' : 'rgba(255,255,255,0.68)',
        background: isActive ? 'rgba(245,166,35,0.14)' : 'transparent',
        borderLeft: isActive ? '2px solid #F5A623' : '2px solid transparent',
        textDecoration: 'none',
        fontSize: 14,
        fontWeight: isActive ? 700 : 500,
        whiteSpace: 'nowrap',
      })}
      title={compact ? label : undefined}
    >
      <Icon className="h-[18px] w-[18px] shrink-0" />
      {!compact && <span>{label}</span>}
    </NavLink>
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



  const sidebarWidth = compact ? 64 : 232
  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || ''
  const initials = ([user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('') || '?').toUpperCase()
  const currentTitle = platformNav.find((item) => location.pathname === item.to || (item.to !== '/hub' && location.pathname.startsWith(item.to + '/')))?.label || 'Home'

  return (
    <div className="min-h-screen bg-[#F7F8FA]" style={{ ['--sidebar-w' as string]: `${sidebarWidth}px` }}>
      <ViewAsBanner />
      <aside
        className="fixed bottom-0 left-0 top-0 z-40 flex flex-col"
        style={{
          width: sidebarWidth,
          background: '#111827',
          borderRight: '1px solid rgba(255,255,255,0.10)',
          transition: 'width 0.3s ease',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: compact ? '18px 0' : '22px 20px 18px', background: '#0B1220', borderBottom: '1px solid rgba(255,255,255,0.10)', textAlign: compact ? 'center' : 'left' }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: compact ? 0 : 4 }}>
            <span style={{ color: 'rgba(255,255,255,0.45)' }}>bon</span>
            <span style={{ color: '#F5A623' }}>UP</span>
          </div>
          {!compact && <div style={{ fontSize: 24, fontWeight: 800, color: '#FFFFFF', lineHeight: 1 }}>World</div>}
        </div>

        <nav className={`flex-1 overflow-y-auto ${compact ? 'px-2 py-3' : 'px-3 py-3'}`}>
          {platformNav.map((item) => <PlatformNavItem key={item.to} {...item} compact={compact} />)}
        </nav>
      </aside>

      <header
        className="fixed right-0 top-0 z-30 flex h-[64px] items-center justify-between border-b border-slate-200 bg-white px-6"
        style={{ left: sidebarWidth }}
      >
        <div>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 800, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#D4900A' }}>bonUP</p>
          <p style={{ margin: '2px 0 0', fontSize: 16, fontWeight: 800, color: '#0F1F3D' }}>{currentTitle}</p>
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
