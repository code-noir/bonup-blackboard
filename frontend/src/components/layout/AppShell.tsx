import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

const TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/contracts': 'Contracts',
  '/obligations': 'Obligations',
  '/payments': 'Payments',
  '/sessions': 'Live Sessions',
  '/sol': 'Sol Groups',
  '/templates': 'Templates',
  '/search': 'Search',
  '/ai': 'AI Assistant',
  '/notifications': 'Notifications',
  '/settings': 'Settings',
}

export default function AppShell() {
  const { pathname } = useLocation()
  const base = '/' + pathname.split('/')[1]
  const title = TITLES[base] ?? 'bonUP Blackboard'

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header title={title} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
