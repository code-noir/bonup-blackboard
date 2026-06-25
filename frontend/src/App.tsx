import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import RequireAuth from '@/components/RequireAuth'
import RequireAdmin from '@/components/admin/RequireAdmin'
import AppShell from '@/components/layout/AppShell'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import ForgotPassword from '@/pages/ForgotPassword'
import ResetPassword from '@/pages/ResetPassword'
import VerifyEmail from '@/pages/VerifyEmail'
import BonupHub from '@/pages/BonupHub'
import Dashboard from '@/pages/Dashboard'
import CreateContract from '@/pages/CreateContract'
import NewContract from '@/pages/NewContract'
import ContractDetail from '@/pages/ContractDetail'
import ContractDocumentView from '@/pages/ContractDocumentView'
import WorkflowDashboard from '@/pages/WorkflowDashboard'
import WorkflowDetail from '@/pages/WorkflowDetail'
import AgreementExchange from '@/pages/AgreementExchange'
import WorkflowInvite from '@/pages/WorkflowInvite'
import CounterpartyWorkflow from '@/pages/CounterpartyWorkflow'
import ContractReview from '@/pages/ContractReview'
import Analysis from '@/pages/Analysis'
import Counter from '@/pages/Counter'
import Contacts from '@/pages/Contacts'
import Resource from '@/pages/Resource'
import Entities from '@/pages/Entities'
import Profile from '@/pages/Profile'
import Billing from '@/pages/Billing'
import LifecycleManagement from '@/pages/LifecycleManagement'
import AgreementPerformance from '@/pages/AgreementPerformance'
import Negotiation from '@/pages/Negotiation'
import NotFound from '@/pages/NotFound'
import AdminLayout from '@/pages/admin/AdminLayout'
import AdminHome from '@/pages/admin/AdminHome'
import AdminUsers from '@/pages/admin/AdminUsers'
import AdminUserDetail from '@/pages/admin/AdminUserDetail'
import AdminPlans from '@/pages/admin/AdminPlans'
import AdminSubscriptions from '@/pages/admin/AdminSubscriptions'
import AdminSol from '@/pages/admin/AdminSol'
import AdminEntities from '@/pages/admin/AdminEntities'
import AdminContracts from '@/pages/admin/AdminContracts'
import AdminActivity from '@/pages/admin/AdminActivity'
import AdminPlaceholder from '@/pages/admin/AdminPlaceholder'
import AdminBilling from '@/pages/admin/AdminBilling'
import AdminProfile from '@/pages/admin/AdminProfile'

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

// Smart root redirect: staff → /admin, everyone else → /hub
function RootRedirect() {
  const { user, isLoading } = useAuth()
  if (isLoading) return null
  return <Navigate to={user?.is_staff ? '/admin' : '/hub'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/workflow/invite/:token" element={<WorkflowInvite />} />
          <Route path="/" element={<RootRedirect />} />

          {/* bonUP Hub — authenticated, no AppShell */}
          <Route
            element={
              <RequireAuth>
                <Outlet />
              </RequireAuth>
            }
          >
            <Route path="/hub" element={<BonupHub />} />
          </Route>

          {/* Protected — wrapped in the app shell */}
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/workspace" element={<WorkflowDashboard />} />
            <Route path="/workflows" element={<WorkflowDashboard />} />
            <Route path="/workflows/:workflowId" element={<WorkflowDetail />} />
            <Route path="/agreement-exchange/:exchangeId" element={<AgreementExchange />} />
            <Route path="/review" element={<ContractReview />} />
            <Route path="/shared/workflows/:workflowId" element={<CounterpartyWorkflow />} />
            {/* Contract list decommissioned — creation uses metadata intake first */}
            <Route path="/contracts" element={<Navigate to="/dashboard" replace />} />
            <Route path="/contracts/new" element={<NewContract />} />
            <Route path="/contracts/create" element={<CreateContract />} />
            <Route path="/contracts/:id/view" element={<ContractDocumentView />} />
            <Route path="/contracts/:id" element={<ContractDetail />} />
            <Route path="/obligations/*" element={<PaygLock name="Obligations" />} />
            <Route path="/payments/*" element={<PaygLock name="Payments" />} />
            <Route path="/sessions/*" element={<PaygLock name="Live Sessions" />} />
            <Route path="/sol/*" element={<PaygLock name="Sol Groups" />} />
            <Route path="/templates/*" element={<Placeholder name="Templates" />} />
            <Route path="/search" element={<Placeholder name="Search" />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/resource" element={<Resource />} />
            <Route path="/ai" element={<Placeholder name="AI Assistant" />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/counter" element={<Counter />} />
            <Route path="/entities" element={<Entities />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/notifications" element={<PaygLock name="Notifications" />} />
            <Route path="/settings" element={<Placeholder name="Settings" />} />
            <Route path="/billing" element={<Billing />} />
            <Route path="/lifecycle" element={<LifecycleManagement />} />
            <Route path="/agreement-performance" element={<AgreementPerformance />} />
            <Route path="/negotiation" element={<Negotiation />} />
            <Route path="/negotiation/:contractId" element={<Negotiation />} />

            {/* Admin — staff only, nested inside the AppShell */}
            <Route
              path="/admin"
              element={
                <RequireAdmin>
                  <AdminLayout />
                </RequireAdmin>
              }
            >
              {/* Dashboard */}
              <Route index element={<AdminHome />} />

              {/* bonUP */}
              <Route path="users" element={<AdminUsers />} />
              <Route path="users/:id" element={<AdminUserDetail />} />

              {/* Blackboard */}
              <Route path="subscriptions" element={<AdminSubscriptions />} />
              <Route path="plans" element={<AdminPlans />} />
              <Route path="contracts" element={<AdminContracts />} />
              <Route path="entities" element={<AdminEntities />} />
              <Route path="sol" element={<AdminSol />} />
              <Route path="activity" element={<AdminActivity />} />

              {/* System */}
              <Route path="live-sessions" element={
                <AdminPlaceholder
                  section="Live Sessions"
                  apiNote="GET /api/sessions/ — user-scoped; no operator-level all-sessions API yet"
                  detail="A full operator view would list all live session records system-wide, usage by user, and session health metrics."
                />
              } />

              {/* Deep-dive / secondary pages */}
              <Route path="billing" element={<AdminBilling />} />
              <Route path="profile" element={<AdminProfile />} />
              <Route path="settings" element={
                <AdminPlaceholder
                  section="Settings"
                  detail="Operator-level platform settings (feature flags, rate limits, maintenance mode) are not yet implemented."
                />
              } />
            </Route>
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
