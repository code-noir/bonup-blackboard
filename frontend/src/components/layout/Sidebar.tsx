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
            ? 'border-l-2 border-[#F5A623] bg-white/10 pl-[10px] text-white'
            : 'border-l-2 border-transparent pl-[10px] text-white/80 hover:bg-white/10 hover:text-white',
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
    <aside className="fixed top-10 left-0 bottom-0 z-40 flex w-60 flex-col bg-[#0F1F3D]">
      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
        {nav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="border-t border-white/10 px-3 py-3 space-y-0.5">
        {bottomNav.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </div>
    </aside>
  )
}
