import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import Sidebar from './Sidebar'
import Header from './Header'
import ActionBar from './ActionBar'

// Layout geometry (all content-side bars start at left: 216px):
//   TopBar    50px  → top: 0
//   Header    50px  → top: 50
//   ActionBar 44px  → top: 100
//   Separator  1px  → top: 144
//   Total           → pt-[145px] on main

export default function AppShell() {
  return (
    <div className="min-h-screen bg-[#ECEEF2]">
      <Sidebar />
      <TopBar />
      <Header />
      <ActionBar />

      {/* Gold→purple gradient separator */}
      <div
        className="fixed right-0 z-30 h-px"
        style={{
          top: 144,
          left: 216,
          background:
            'linear-gradient(90deg, transparent, rgba(245,166,35,0.3) 28%, rgba(139,92,246,0.3) 72%, transparent)',
        }}
      />

      <main
        className="min-h-screen px-6 pb-10"
        style={{ marginLeft: 216, paddingTop: 145 }}
      >
        <Outlet />
      </main>
    </div>
  )
}
