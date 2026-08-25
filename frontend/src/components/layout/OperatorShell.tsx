import AdminLayout from '@/pages/admin/AdminLayout'
import Sidebar from './Sidebar'
import ViewAsBanner from './ViewAsBanner'

export default function OperatorShell() {
  return (
    <div className="app-shell min-h-screen bg-[#ECEEF2]">
      <ViewAsBanner />
      <Sidebar />
      <main className="app-shell-main min-h-screen px-6 pb-10 pt-6">
        <AdminLayout />
      </main>
    </div>
  )
}
