import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Header from './Header'
import ActionBar from './ActionBar'

// Sidebar: full-height, left: 0, width: 216px
// Content-side bars (left: 216px):
//   BrandBar  40px  → top: 0
//   Header    50px  → top: 40
//   ActionBar 44px  → top: 90
//   Separator  1px  → top: 133
//   Total           → pt-[134px] on main

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('bb_topbar_collapsed') === 'true')

  useEffect(() => {
    function onCollapse(e: Event) {
      setCollapsed((e as CustomEvent<boolean>).detail)
    }
    window.addEventListener('topbar-collapse', onCollapse)
    return () => window.removeEventListener('topbar-collapse', onCollapse)
  }, [])

  return (
    <div className="min-h-screen bg-[#ECEEF2]">
      <Sidebar />
      <TopBar />
      <Header />
      <ActionBar />

      {/* Gold gradient separator */}
      <div
        className="fixed right-0 z-30"
        style={{
          top: 133,
          left: 216,
          height: 1,
          background:
            'linear-gradient(90deg, transparent, rgba(245,166,35,0.45) 35%, rgba(245,166,35,0.15) 65%, transparent)',
          opacity: collapsed ? 0 : 1,
          transition: 'opacity 0.2s ease',
          pointerEvents: 'none',
        }}
      />

      <main
        className="min-h-screen px-6 pb-10"
        style={{ marginLeft: 216, paddingTop: 134 }}
      >
        <Outlet />
      </main>
    </div>
  )
}
