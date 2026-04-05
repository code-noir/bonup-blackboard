import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import RequireAuth from '@/components/RequireAuth'
import AppShell from '@/components/layout/AppShell'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Contracts from '@/pages/Contracts'
import CreateContract from '@/pages/CreateContract'
import NotFound from '@/pages/NotFound'

// Placeholder page used for routes not yet built
function Placeholder({ name }: { name: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-4xl font-bold text-slate-200">{name}</p>
      <p className="mt-3 text-sm text-slate-500">This page is coming soon.</p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Protected — wrapped in the app shell */}
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/contracts" element={<Contracts />} />
            <Route path="/contracts/create" element={<CreateContract />} />
            <Route path="/obligations/*" element={<Placeholder name="Obligations" />} />
            <Route path="/payments/*" element={<Placeholder name="Payments" />} />
            <Route path="/sessions/*" element={<Placeholder name="Live Sessions" />} />
            <Route path="/sol/*" element={<Placeholder name="Sol Groups" />} />
            <Route path="/templates/*" element={<Placeholder name="Templates" />} />
            <Route path="/search" element={<Placeholder name="Search" />} />
            <Route path="/ai" element={<Placeholder name="AI Assistant" />} />
            <Route path="/notifications" element={<Placeholder name="Notifications" />} />
            <Route path="/settings" element={<Placeholder name="Settings" />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
