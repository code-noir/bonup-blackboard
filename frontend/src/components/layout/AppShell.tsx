import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import Sidebar from './Sidebar'
import Header from './Header'
import AdBar from './AdBar'

// Fixed bar heights:
//   TopBar  — h-10  = 40px
//   Header  — h-16  = 64px
//   AdBar   — h-[52px]
//   Total           = 156px  →  pt-[156px] on main

export default function AppShell() {
  return (
    <div className="min-h-screen bg-[#F7F8FA]">
      <TopBar />
      <Sidebar />
      <Header />
      <AdBar />
      <main className="ml-60 pt-[156px] min-h-screen px-6 pb-10">
        <Outlet />
      </main>
    </div>
  )
}
