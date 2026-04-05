import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import Sidebar from './Sidebar'
import Header from './Header'

export default function AppShell() {
  return (
    <div className="min-h-screen bg-[#F7F8FA]">
      {/* Fixed: full-width navy top bar — h-10 (40px) */}
      <TopBar />

      {/* Fixed: sidebar — starts below top bar */}
      <Sidebar />

      {/* Fixed: header bar — starts below top bar, left of sidebar */}
      <Header />

      {/* Scrollable main content — offset for both fixed bars + sidebar */}
      {/* top-10 (40px) + h-16 (64px) = 104px; sidebar w-60 (240px)    */}
      <main className="ml-60 pt-[104px] min-h-screen px-6 pb-10">
        <Outlet />
      </main>
    </div>
  )
}
