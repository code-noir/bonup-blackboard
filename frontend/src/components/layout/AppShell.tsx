import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Header from './Header'
import ActionBar from './ActionBar'

// Sidebar: full-height, left: 0, width: 216px
// Content-side bars (left: 216px):
//   TopBar    64px  → top: 0
//   Header    50px  → top: 64
//   ActionBar 44px  → top: 114
//   Separator  1px  → top: 158
//   Total           → pt-[159px] on main

export default function AppShell() {
  return (
    <div className="min-h-screen bg-[#ECEEF2]">
      <Sidebar />
      <TopBar />
      <Header />
      <ActionBar />

      {/* Gold gradient separator */}
      <div
        className="fixed right-0 z-30 h-px"
        style={{
          top: 158,
          left: 216,
          background:
            'linear-gradient(90deg, transparent, rgba(245,166,35,0.45) 35%, rgba(245,166,35,0.15) 65%, transparent)',
        }}
      />

      <main
        className="min-h-screen px-6 pb-10"
        style={{ marginLeft: 216, paddingTop: 159 }}
      >
        <Outlet />
      </main>
    </div>
  )
}
