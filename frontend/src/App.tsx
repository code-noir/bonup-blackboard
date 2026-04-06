import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import RequireAuth from '@/components/RequireAuth'
import AppShell from '@/components/layout/AppShell'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Contracts from '@/pages/Contracts'
import CreateContract from '@/pages/CreateContract'
import Analysis from '@/pages/Analysis'
import Counter from '@/pages/Counter'
import Entities from '@/pages/Entities'
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

// Lock screen shown to Pay As You Go users for monthly-only features
function PaygLock({ name }: { name: string }) {
  const { user } = useAuth()
  if (user?.subscription_tier !== 'per_contract') {
    return <Placeholder name={name} />
  }
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center px-6">
      <div className="text-5xl mb-4">🔒</div>
      <p className="text-2xl font-bold text-slate-200 mb-2">{name}</p>
      <p className="mt-2 text-sm text-slate-400 max-w-sm">
        This feature requires a monthly plan.
      </p>
      <p className="mt-1 text-sm text-slate-500 max-w-sm">
        Upgrade to Blackboard Basic — $19/month
      </p>
      <a
        href="/settings"
        style={{
          display: 'block',
          marginTop: '1.5rem',
          backgroundColor: '#F5A623',
          color: '#0F1F3D',
          fontWeight: 600,
          padding: '0.625rem 2rem',
          borderRadius: '8px',
          textDecoration: 'none',
          width: '100%',
          maxWidth: '320px',
          textAlign: 'center',
        }}
      >
        Upgrade to Blackboard Basic
      </a>
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
            <Route path="/obligations/*" element={<PaygLock name="Obligations" />} />
            <Route path="/payments/*" element={<PaygLock name="Payments" />} />
            <Route path="/sessions/*" element={<PaygLock name="Live Sessions" />} />
            <Route path="/sol/*" element={<PaygLock name="Sol Groups" />} />
            <Route path="/templates/*" element={<Placeholder name="Templates" />} />
            <Route path="/search" element={<Placeholder name="Search" />} />
            <Route path="/ai" element={<Placeholder name="AI Assistant" />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/counter" element={<Counter />} />
            <Route path="/entities" element={<Entities />} />
            <Route path="/notifications" element={<PaygLock name="Notifications" />} />
            <Route path="/settings" element={<Placeholder name="Settings" />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
