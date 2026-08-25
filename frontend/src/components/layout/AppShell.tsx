import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Header from './Header'
import ActionBar from './ActionBar'
import ViewAsBanner from './ViewAsBanner'

// Sidebar: full-height, left: 0, width: 216px
// Content-side bars (left: 216px):
//   TopBar    40px  → top: 0
//   Header    74px  → top: 40
//   ActionBar 44px  → top: 114 on selected non-editor pages
//   Total           → pt-[158px] on main when ActionBar is shown

// Pages where the action bar should be visible
const ACTION_BAR_ROUTES = ['/apps/blackbod/dashboard', '/apps/blackbod/sessions']

export default function AppShell() {
  const location = useLocation()
  const showActionBar = ACTION_BAR_ROUTES.some(
    (p) => location.pathname === p || location.pathname.startsWith(p + '/')
  )

  return (
    <div className="app-shell min-h-screen bg-[#ECEEF2]">
      <ViewAsBanner />
      <Sidebar />
      <TopBar />
      <Header />
      {showActionBar && <ActionBar />}

      <main
        className={`app-shell-main min-h-screen px-6 pb-10 ${showActionBar ? 'has-action-bar' : ''}`}
      >
        <Outlet />
      </main>
    </div>
  )
}
