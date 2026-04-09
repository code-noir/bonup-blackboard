import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Header from './Header'
import ActionBar from './ActionBar'

// Sidebar: full-height, left: 0, width: 216px
// Content-side bars (left: 216px):
//   TopBar    40px  → top: 0
//   Header    74px  → top: 40
//   ActionBar 44px  → top: 114
//   Total           → pt-[158px] on main

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

      <main
        className="min-h-screen px-6 pb-10"
        style={{ marginLeft: 216, paddingTop: 158 }}
      >
        <Outlet />
      </main>
    </div>
  )
}
