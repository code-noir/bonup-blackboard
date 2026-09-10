// frontend/src/pages/ForgotPassword.tsx
//
// Step 1 of the password reset flow.
// Submits to POST /api/users/password-reset/
//
// Recovery credentials are delivered by email, never returned to this screen.

import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import api from '@/api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.post<{ detail: string }>(
        '/users/password-reset/',
        { email: email.trim() },
      )
      setSubmitted(true)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string; error?: string } } })
          ?.response?.data?.detail ??
        (err as { response?: { data?: { error?: string } } })
          ?.response?.data?.error ??
        'Something went wrong. Please try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F8FA] px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 text-center">
          <p className="text-3xl font-bold tracking-tight text-[#1E3A6E]">
            bon<span className="text-[#F5A623]">UP</span>
          </p>
          <p className="mt-1 text-sm text-[#1E3A6E] uppercase tracking-widest">
            Blackbòd
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          {!submitted ? (
            <>
              <h2 className="mb-2 text-xl font-semibold text-slate-800">
                Reset your password
              </h2>
              <p className="mb-6 text-sm text-slate-500">
                Enter your account email and we'll send you a reset link.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label
                    htmlFor="email"
                    className="mb-1.5 block text-sm font-medium text-slate-700"
                  >
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    placeholder="you@example.com"
                  />
                </div>

                {error && (
                  <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-lg bg-black px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 disabled:opacity-60 transition-colors"
                >
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-slate-500">
                Remember it?{' '}
                <Link to="/login" className="font-medium text-[#2563EB] hover:text-[#1D4ED8]">
                  Sign in
                </Link>
              </p>
            </>
          ) : (
            <>
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="mb-2 text-xl font-semibold text-slate-800">Check your email</h2>
              <p className="text-sm text-slate-500">
                If <span className="font-medium text-slate-700">{email}</span> is registered,
                a password reset link has been sent.
              </p>

              <p className="mt-6 text-center text-sm text-slate-500">
                <Link to="/login" className="font-medium text-[#2563EB] hover:text-[#1D4ED8]">
                  ← Back to sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
