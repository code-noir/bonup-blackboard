// frontend/src/pages/VerifyEmail.tsx
//
// Handles the email verification link clicked from the signup email.
// URL: /verify-email?token=<uuid>
//
// On mount: reads the token from the URL and calls POST /api/users/verify-pending/
// On success: redirects to sign in with a verified-account message.
// On error/expired: shows error + resend form so the user can request a new link.

import { useEffect, useState, FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api from '@/api/client'

type VerifyState = 'loading' | 'success' | 'error'
type ResendState = 'idle' | 'sending' | 'sent' | 'error'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [verifyState, setVerifyState] = useState<VerifyState>('loading')
  const [errorMessage, setErrorMessage] = useState('')

  // Resend sub-state (only active when verifyState === 'error')
  const [resendEmail, setResendEmail] = useState('')
  const [resendState, setResendState] = useState<ResendState>('idle')
  const [resendError, setResendError] = useState('')

  useEffect(() => {
    const token = searchParams.get('token')
    if (!token) {
      setErrorMessage('No verification token found in the link. Please check your email and try again.')
      setVerifyState('error')
      return
    }

    api
      .post('/users/verify-pending/', { token })
      .then(() => {
        navigate('/login', {
          replace: true,
          state: { verified: true },
        })
      })
      .catch((err: unknown) => {
        const data = (err as { response?: { data?: { error?: string; detail?: string } } })?.response?.data
        setErrorMessage(
          data?.error ?? data?.detail ?? 'Verification failed. The link may have expired or already been used.'
        )
        setVerifyState('error')
      })
  }, [navigate, searchParams])

  async function handleResend(e: FormEvent) {
    e.preventDefault()
    if (!resendEmail.trim()) return
    setResendState('sending')
    setResendError('')
    try {
      await api.post('/users/resend-verification/', { email: resendEmail.trim() })
      setResendState('sent')
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { detail?: string; error?: string } } })?.response?.data
      setResendError(data?.detail ?? data?.error ?? 'Failed to send. Please try again.')
      setResendState('error')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F8FA] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="text-3xl font-bold tracking-tight text-[#1E3A6E]">
            bon<span className="text-[#F5A623]">UP</span>
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm text-center">
          {/* ── Loading ── */}
          {verifyState === 'loading' && (
            <>
              <div className="mb-4 flex justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
              </div>
              <p className="text-sm text-slate-500">Verifying your email…</p>
            </>
          )}

          {/* ── Success ── */}
          {verifyState === 'success' && (
            <>
              <div className="mb-4 flex justify-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-50">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="#16A34A" className="h-6 w-6">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                </div>
              </div>
              <h2 className="mb-2 text-xl font-semibold text-slate-800">Email verified</h2>
              <p className="mb-6 text-sm text-slate-500">
                Your bonUP account has been created. Sign in to continue.
              </p>
              <Link
                to="/login"
                className="block w-full rounded-lg bg-black px-4 py-2.5 text-center text-sm font-semibold text-white shadow-sm hover:bg-[#1a1a1a] transition-colors"
              >
                Sign in
              </Link>
            </>
          )}

          {/* ── Error ── */}
          {verifyState === 'error' && (
            <>
              <div className="mb-4 flex justify-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-50">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="#DC2626" className="h-6 w-6">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
              </div>
              <h2 className="mb-2 text-xl font-semibold text-slate-800">Verification failed</h2>
              <p className="mb-6 text-sm text-slate-500">{errorMessage}</p>

              {/* Resend form — shown while idle or after a resend error */}
              {(resendState === 'idle' || resendState === 'error') && (
                <form onSubmit={handleResend} className="mb-4 text-left">
                  <p className="mb-3 text-center text-sm text-slate-600">
                    Need a new verification link?
                  </p>
                  <label htmlFor="resend-email" className="mb-1.5 block text-sm font-medium text-slate-700">
                    Email address
                  </label>
                  <input
                    id="resend-email"
                    type="email"
                    required
                    value={resendEmail}
                    onChange={(e) => setResendEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  />
                  {resendState === 'error' && resendError && (
                    <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                      {resendError}
                    </p>
                  )}
                  <button
                    type="submit"
                    className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    Send new verification link
                  </button>
                </form>
              )}

              {/* Sending spinner */}
              {resendState === 'sending' && (
                <div className="mb-4 flex justify-center">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
                </div>
              )}

              {/* Resend success */}
              {resendState === 'sent' && (
                <div className="mb-4 rounded-lg bg-green-50 px-3 py-3 text-sm text-green-700">
                  New verification link sent. Check your inbox.
                </div>
              )}

              <Link
                to="/register"
                className="text-sm font-medium text-[#2563EB] hover:text-[#1D4ED8]"
              >
                Back to sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
