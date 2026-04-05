import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import Sidebar from './Sidebar'
import Header from './Header'
import AdBar from './AdBar'

// Brand bar: 34px + Header: 50px + AdBar: 48px + Separator: 1px = 133px total

export default function AppShell() {
  return (
    <div className="min-h-screen bg-[#F0F2F5]">
      <TopBar />
      <Sidebar />
      <Header />
      <AdBar />
      {/* Gradient separator — full width, sits below all three fixed bars */}
      <div
        className="fixed left-0 right-0 z-20 h-px"
        style={{
          top: 132,
          background:
            'linear-gradient(90deg, transparent 0%, rgba(245,166,35,0.35) 30%, rgba(139,92,246,0.35) 70%, transparent 100%)',
        }}
      />
      <main className="ml-60 pt-[133px] min-h-screen px-6 pb-10">
        <Outlet />
      </main>
    </div>
  )
}
