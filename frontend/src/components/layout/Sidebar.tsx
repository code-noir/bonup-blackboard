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
  { to: '/dashboard', label: 'Dashboard', Icon: HomeIcon },
  { to: '/contracts', label: 'Contracts', Icon: DocumentTextIcon },
  { to: '/obligations', label: 'Obligations', Icon: ClipboardDocumentListIcon },
  { to: '/payments', label: 'Payments', Icon: CreditCardIcon },
  { to: '/sessions', label: 'Live Sessions', Icon: VideoCameraIcon },
  { to: '/sol', label: 'Sol Groups', Icon: UserGroupIcon },
  { to: '/templates', label: 'Templates', Icon: RectangleStackIcon },
  { to: '/search', label: 'Search', Icon: MagnifyingGlassIcon },
  { to: '/ai', label: 'AI Assistant', Icon: SparklesIcon },
]

const bottomNav = [
  { to: '/notifications', label: 'Notifications', Icon: BellIcon },
  { to: '/settings', label: 'Settings', Icon: Cog6ToothIcon },
]

function NavItem({
  to,
  label,
  Icon,
}: {
  to: string
  label: string
  Icon: React.ElementType
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-indigo-700 text-white'
            : 'text-slate-300 hover:bg-slate-700 hover:text-white',
        ].join(' ')
      }
    >
      <Icon className="h-5 w-5 shrink-0" />
      {label}
    </NavLink>
  )
}

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-slate-900">
      {/* Logo */}
      <div className="flex h-16 items-center px-5">
        <span className="text-lg font-bold tracking-tight text-white">
          bon<span className="text-indigo-400">UP</span>
          <span className="ml-2 text-xs font-normal text-slate-400 uppercase tracking-widest">
            Blackboard
          </span>
        </span>
      </div>

      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {nav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="border-t border-slate-700 px-3 py-3 space-y-0.5">
        {bottomNav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </div>
    </aside>
  )
}
