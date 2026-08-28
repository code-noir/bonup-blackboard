import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { OperatorProvider } from '@/context/OperatorContext'
import RequireAuth from '@/components/RequireAuth'
import RequireAdmin from '@/components/admin/RequireAdmin'
import PlatformShell from '@/components/layout/PlatformShell'
import BlackbodShell from '@/components/layout/BlackbodShell'
import OperatorShell from '@/components/layout/OperatorShell'
import Login from '@/pages/Login'
import OperatorLogin from '@/pages/OperatorLogin'
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
import Store from '@/pages/Store'
import StoreReview from '@/pages/StoreReview'
import StorePaymentSuccess from '@/pages/StorePaymentSuccess'
import Vault from '@/pages/Vault'
import LifecycleManagement from '@/pages/LifecycleManagement'
import AgreementPerformance from '@/pages/AgreementPerformance'
import Negotiation from '@/pages/Negotiation'
import NotFound from '@/pages/NotFound'
import AdminHome from '@/pages/admin/AdminHome'
import OperatorHome from '@/pages/admin/OperatorHome'
import AdminUsers from '@/pages/admin/AdminUsers'
import AdminUserDetail from '@/pages/admin/AdminUserDetail'
import AdminPlans from '@/pages/admin/AdminPlans'
import AdminSubscriptions from '@/pages/admin/AdminSubscriptions'
import AdminSol from '@/pages/admin/AdminSol'
import AdminEntities from '@/pages/admin/AdminEntities'
import AdminContracts from '@/pages/admin/AdminContracts'
import AdminObligations from '@/pages/admin/AdminObligations'
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


function PlatformBillingPlaceholder() {
  return (
    <div className="mx-auto max-w-3xl py-10">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-[#D4900A]">bonUP</p>
      <h1 className="text-2xl font-bold text-slate-900">Billing</h1>
      <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          Billing management is not configured in this phase.
        </p>
      </div>
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
        Access changes are handled in bonUP.
      </p>
    </div>
  )
}

// Smart root redirect: normal authenticated users go to the user hub.
function RootRedirect() {
  const { isLoading } = useAuth()
  if (isLoading) return null
  return <Navigate to="/hub" replace />
}

function AdminUserRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/operator/identity/users/${id}`} replace />
}


function LegacyBlackbodRedirect({ to }: { to: string }) {
  const location = useLocation()
  const params = useParams<Record<string, string | undefined>>()
  let target = to

  for (const [key, value] of Object.entries(params)) {
    if (key !== '*' && value) target = target.replace(`:${key}`, value)
  }

  if (params['*']) {
    target = `${target.replace(/\/$/, '')}/${params['*']}`
  }

  return <Navigate to={`${target}${location.search}${location.hash}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <OperatorProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/operator/login" element={<OperatorLogin />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/workflow/invite/:token" element={<WorkflowInvite />} />
          <Route path="/" element={<RootRedirect />} />

          {/* bonUP Platform — authenticated platform shell */}
          <Route
            element={
              <RequireAuth>
                <PlatformShell />
              </RequireAuth>
            }
          >
            <Route path="/hub" element={<BonupHub />} />
            <Route path="/store" element={<Store />} />
            <Route path="/store/review" element={<StoreReview />} />
            <Route path="/store/payment/success" element={<StorePaymentSuccess />} />
            <Route path="/vault" element={<Vault />} />
            <Route path="/vault/review" element={<Navigate to="/store" replace />} />
            <Route path="/subscription" element={<Navigate to="/store" replace />} />
            <Route path="/billing" element={<PlatformBillingPlaceholder />} />
            <Route path="/account" element={<Profile />} />
            <Route path="/settings" element={<Placeholder name="Settings" />} />
          </Route>

          {/* Blackbòd — authenticated application shell */}
          <Route
            path="/apps/blackbod"
            element={
              <RequireAuth>
                <BlackbodShell />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="workspace" element={<WorkflowDashboard />} />
            <Route path="workflows" element={<WorkflowDashboard />} />
            <Route path="workflows/:workflowId" element={<WorkflowDetail />} />
            <Route path="agreement-exchange/:exchangeId" element={<AgreementExchange />} />
            <Route path="review" element={<ContractReview />} />
            <Route path="shared/workflows/:workflowId" element={<CounterpartyWorkflow />} />
            {/* Contract list decommissioned — creation uses metadata intake first */}
            <Route path="contracts" element={<Navigate to="/apps/blackbod/dashboard" replace />} />
            <Route path="contracts/new" element={<NewContract />} />
            <Route path="contracts/create" element={<CreateContract />} />
            <Route path="contracts/:id/view" element={<ContractDocumentView />} />
            <Route path="contracts/:id" element={<ContractDetail />} />
            <Route path="obligations/*" element={<PaygLock name="Obligations" />} />
            <Route path="payments/*" element={<PaygLock name="Payments" />} />
            <Route path="sessions/*" element={<PaygLock name="Live Sessions" />} />
            <Route path="templates/*" element={<Placeholder name="Templates" />} />
            <Route path="search" element={<Placeholder name="Search" />} />
            <Route path="contacts" element={<Contacts />} />
            <Route path="resource" element={<Resource />} />
            <Route path="ai" element={<Placeholder name="AI Assistant" />} />
            <Route path="analysis" element={<Analysis />} />
            <Route path="counter" element={<Counter />} />
            <Route path="entities" element={<Entities />} />
            <Route path="notifications" element={<PaygLock name="Notifications" />} />
            <Route path="lifecycle" element={<LifecycleManagement />} />
            <Route path="agreement-performance" element={<AgreementPerformance />} />
            <Route path="negotiation" element={<Negotiation />} />
            <Route path="negotiation/:contractId" element={<Negotiation />} />
          </Route>

          {/* Legacy Blackbòd compatibility redirects */}
          <Route path="/dashboard" element={<LegacyBlackbodRedirect to="/apps/blackbod/dashboard" />} />
          <Route path="/workspace" element={<LegacyBlackbodRedirect to="/apps/blackbod/workspace" />} />
          <Route path="/workflows" element={<LegacyBlackbodRedirect to="/apps/blackbod/workflows" />} />
          <Route path="/workflows/:workflowId" element={<LegacyBlackbodRedirect to="/apps/blackbod/workflows/:workflowId" />} />
          <Route path="/agreement-exchange/:exchangeId" element={<LegacyBlackbodRedirect to="/apps/blackbod/agreement-exchange/:exchangeId" />} />
          <Route path="/review" element={<LegacyBlackbodRedirect to="/apps/blackbod/review" />} />
          <Route path="/shared/workflows/:workflowId" element={<LegacyBlackbodRedirect to="/apps/blackbod/shared/workflows/:workflowId" />} />
          <Route path="/contracts" element={<LegacyBlackbodRedirect to="/apps/blackbod/dashboard" />} />
          <Route path="/contracts/new" element={<LegacyBlackbodRedirect to="/apps/blackbod/contracts/new" />} />
          <Route path="/contracts/create" element={<LegacyBlackbodRedirect to="/apps/blackbod/contracts/create" />} />
          <Route path="/contracts/:id/view" element={<LegacyBlackbodRedirect to="/apps/blackbod/contracts/:id/view" />} />
          <Route path="/contracts/:id" element={<LegacyBlackbodRedirect to="/apps/blackbod/contracts/:id" />} />
          <Route path="/obligations/*" element={<LegacyBlackbodRedirect to="/apps/blackbod/obligations" />} />
          <Route path="/payments/*" element={<LegacyBlackbodRedirect to="/apps/blackbod/payments" />} />
          <Route path="/sessions/*" element={<LegacyBlackbodRedirect to="/apps/blackbod/sessions" />} />
          <Route path="/templates/*" element={<LegacyBlackbodRedirect to="/apps/blackbod/templates" />} />
          <Route path="/search" element={<LegacyBlackbodRedirect to="/apps/blackbod/search" />} />
          <Route path="/contacts" element={<LegacyBlackbodRedirect to="/apps/blackbod/contacts" />} />
          <Route path="/resource" element={<LegacyBlackbodRedirect to="/apps/blackbod/resource" />} />
          <Route path="/ai" element={<LegacyBlackbodRedirect to="/apps/blackbod/ai" />} />
          <Route path="/analysis" element={<LegacyBlackbodRedirect to="/apps/blackbod/analysis" />} />
          <Route path="/counter" element={<LegacyBlackbodRedirect to="/apps/blackbod/counter" />} />
          <Route path="/entities" element={<LegacyBlackbodRedirect to="/apps/blackbod/entities" />} />
          <Route path="/notifications" element={<LegacyBlackbodRedirect to="/apps/blackbod/notifications" />} />
          <Route path="/lifecycle" element={<LegacyBlackbodRedirect to="/apps/blackbod/lifecycle" />} />
          <Route path="/agreement-performance" element={<LegacyBlackbodRedirect to="/apps/blackbod/agreement-performance" />} />
          <Route path="/negotiation" element={<LegacyBlackbodRedirect to="/apps/blackbod/negotiation" />} />
          <Route path="/negotiation/:contractId" element={<LegacyBlackbodRedirect to="/apps/blackbod/negotiation/:contractId" />} />
          <Route path="/profile" element={<Navigate to="/account" replace />} />

          {/* Operator — dedicated AdministratorAccount session, outside normal user auth */}
          <Route
            path="/operator"
            element={
              <RequireAdmin>
                <OperatorShell />
              </RequireAdmin>
            }
          >
            <Route index element={<OperatorHome />} />

            <Route path="identity/users" element={<AdminUsers />} />
            <Route path="identity/users/:id" element={<AdminUserDetail />} />
            <Route path="identity/entities" element={<AdminEntities />} />

            <Route path="apps/blackbod" element={<AdminHome />} />
            <Route path="apps/blackbod/agreements" element={<AdminContracts />} />
            <Route path="apps/blackbod/obligations" element={<AdminObligations />} />
            <Route path="apps/blackbod/activity" element={<AdminActivity />} />
            <Route path="apps/sol/groups" element={<AdminSol />} />

            <Route path="billing" element={<AdminBilling />} />
            <Route path="billing/subscriptions" element={<AdminSubscriptions />} />
            <Route path="billing/plans" element={<AdminPlans />} />

            <Route path="operations/live-sessions" element={
              <AdminPlaceholder
                section="Live Sessions"
                apiNote="GET /api/sessions/ — user-scoped; no operator-level all-sessions API yet"
                detail="A full operator view would list all live session records system-wide, usage by user, and session health metrics."
              />
            } />

            <Route path="profile" element={<AdminProfile />} />
            <Route path="settings" element={
              <AdminPlaceholder
                section="Settings"
                detail="Operator-level platform settings (feature flags, rate limits, maintenance mode) are not yet implemented."
              />
            } />
          </Route>

          {/* Legacy admin compatibility redirects */}
          <Route path="/admin" element={<Navigate to="/operator" replace />} />
          <Route path="/admin/users" element={<Navigate to="/operator/identity/users" replace />} />
          <Route path="/admin/users/:id" element={<AdminUserRedirect />} />
          <Route path="/admin/entities" element={<Navigate to="/operator/identity/entities" replace />} />
          <Route path="/admin/contracts" element={<Navigate to="/operator/apps/blackbod/agreements" replace />} />
          <Route path="/admin/obligations" element={<Navigate to="/operator/apps/blackbod/obligations" replace />} />
          <Route path="/admin/activity" element={<Navigate to="/operator/apps/blackbod/activity" replace />} />
          <Route path="/admin/sol" element={<Navigate to="/operator/apps/sol/groups" replace />} />
          <Route path="/admin/subscriptions" element={<Navigate to="/operator/billing/subscriptions" replace />} />
          <Route path="/admin/plans" element={<Navigate to="/operator/billing/plans" replace />} />
          <Route path="/admin/live-sessions" element={<Navigate to="/operator/operations/live-sessions" replace />} />
          <Route path="/admin/billing" element={<Navigate to="/operator/billing" replace />} />
          <Route path="/admin/profile" element={<Navigate to="/operator/profile" replace />} />
          <Route path="/admin/settings" element={<Navigate to="/operator/settings" replace />} />

          <Route path="*" element={<NotFound />} />
        </Routes>
        </OperatorProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
