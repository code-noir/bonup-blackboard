// frontend/src/pages/VerifyEmail.tsx
//
// Handles the email verification link clicked from the signup email.
// URL: /verify-email?token=<uuid>
//
// On mount: reads the token from the URL and calls POST /api/users/verify-pending/
// On success: shows "verified — go sign in" message. Does NOT auto-login.
// On failure: shows the error with a link back to /register.

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '@/api/client'

type State = 'loading' | 'success' | 'error'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const [state, setState] = useState<State>('loading')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    const token = searchParams.get('token')
    if (!token) {
      setErrorMessage('No verification token found in the link. Please check your email and try again.')
      setState('error')
      return
    }

    api
      .post('/users/verify-pending/', { token })
      .then(() => {
        setState('success')
      })
      .catch((err: unknown) => {
        const data = (err as { response?: { data?: { error?: string; detail?: string } } })?.response?.data
        setErrorMessage(
          data?.error ?? data?.detail ?? 'Verification failed. The link may have expired or already been used.'
        )
        setState('error')
      })
  }, []) // run once on mount

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F8FA] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="text-3xl font-bold tracking-tight text-[#1E3A6E]">
            bon<span className="text-[#F5A623]">UP</span>
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm text-center">
          {state === 'loading' && (
            <>
              <div className="mb-4 flex justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
              </div>
              <p className="text-sm text-slate-500">Verifying your email…</p>
            </>
          )}

          {state === 'success' && (
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

          {state === 'error' && (
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
