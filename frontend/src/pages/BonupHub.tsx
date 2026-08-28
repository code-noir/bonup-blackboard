// frontend/src/pages/BonupHub.tsx
//
// bonUP Hub — the landing page after sign-in.
// Every authenticated user arrives here first regardless of Blackboard access.
//
// Access states:
//   no Blackbòd access   -> welcome message + explain Blackbòd + access guided CTA
//   has Blackbòd access  -> welcome message + "Enter Blackbòd" button

import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function BonupHub() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const hasBlackbodAccess = user?.has_blackbod_access === true

  return (
    <div>
      <main className="mx-auto max-w-2xl px-6 py-10">
        {/* Welcome */}
        <div className="mb-10">
          <h1 className="text-3xl font-bold text-slate-900">
            Welcome to bonUP
            {user?.first_name ? `, ${user.first_name}` : ''}.
          </h1>
          {user?.bon_id && (
            <p className="mt-2 text-sm text-slate-400 font-mono">
              bonID: {user.bon_id}
            </p>
          )}
          <p className="mt-3 text-base text-slate-600">
            bonUP is your permanent identity for real contracting.
            Your bonID follows you across every agreement you make.
          </p>
        </div>

        {/* Blackboard product card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">
            Product
          </div>
          <h2 className="mb-2 text-xl font-bold text-slate-900">
            bon<span className="text-[#F5A623]">UP</span>{' '}
            <span className="text-slate-700">Blackbòd</span>
          </h2>
          <p className="mb-6 text-sm text-slate-600">
            Blackbòd is bonUP's contract lifecycle workspace.
            Create, negotiate, and track contracts — all tied to your bonID.
          </p>

          {hasBlackbodAccess ? (
            <button
              onClick={() => navigate('/apps/blackbod')}
              className="rounded-lg bg-black px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 transition-colors"
            >
              Enter Blackbòd
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-slate-500">
                Blackbòd is not currently active for your account.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => navigate('/account')}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  Complete your profile
                </button>
                <button
                  disabled
                  title="Store access coming soon"
                  className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-400 cursor-not-allowed"
                >
                  Access Blackbòd
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
