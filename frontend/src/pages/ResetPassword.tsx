// frontend/src/pages/ResetPassword.tsx
//
// Step 2 of the password reset flow.
// Reads uid + token from ?uid=...&token=... query params.
// Submits to POST /api/users/password-reset/confirm/

import { useState, FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '@/api/client'

function EyeOpen() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: 18, height: 18 }}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}

function EyeClosed() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: 18, height: 18 }}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
    </svg>
  )
}

function PasswordField({
  id,
  label,
  value,
  onChange,
  placeholder,
  autoComplete,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  autoComplete?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div style={{ position: 'relative' }}>
        <input
          id={id}
          type={show ? 'text' : 'password'}
          autoComplete={autoComplete}
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          placeholder={placeholder ?? '••••••••'}
          style={{ paddingRight: 40 }}
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          tabIndex={-1}
          style={{
            position: 'absolute',
            right: 10,
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#9CA3AF',
            display: 'flex',
            alignItems: 'center',
            padding: 2,
          }}
          aria-label={show ? 'Hide password' : 'Show password'}
        >
          {show ? <EyeClosed /> : <EyeOpen />}
        </button>
      </div>
    </div>
  )
}

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const uid = searchParams.get('uid') ?? ''
  const token = searchParams.get('token') ?? ''

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  // Missing or clearly invalid params — show a dead link message
  if (!uid || !token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F7F8FA] px-4">
        <div className="w-full max-w-sm">
          <div className="mb-8 text-center">
            <p className="text-3xl font-bold tracking-tight text-[#1E3A6E]">
              bon<span className="text-[#F5A623]">UP</span>
            </p>
            <p className="mt-1 text-sm text-[#1E3A6E] uppercase tracking-widest">Blackbòd</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm text-center">
            <p className="text-2xl mb-3">🔗</p>
            <h2 className="mb-2 text-lg font-semibold text-slate-800">Invalid reset link</h2>
            <p className="text-sm text-slate-500 mb-6">
              This password reset link is missing required parameters. It may have already been used or is malformed.
            </p>
            <Link to="/forgot-password" className="font-medium text-sm text-[#2563EB] hover:text-[#1D4ED8]">
              Request a new link →
            </Link>
          </div>
        </div>
      </div>
    )
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      await api.post('/users/password-reset/confirm/', {
        uid,
        token,
        new_password: newPassword,
      })
      setSuccess(true)
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, string> } })?.response?.data
      const msg =
        data?.error ??
        data?.detail ??
        'Failed to reset password. The link may have expired.'
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
          {!success ? (
            <>
              <h2 className="mb-2 text-xl font-semibold text-slate-800">
                Set new password
              </h2>
              <p className="mb-6 text-sm text-slate-500">
                Choose a strong password. At least 8 characters.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <PasswordField
                  id="new-password"
                  label="New password"
                  value={newPassword}
                  onChange={setNewPassword}
                  autoComplete="new-password"
                />
                <PasswordField
                  id="confirm-password"
                  label="Confirm new password"
                  value={confirmPassword}
                  onChange={setConfirmPassword}
                  placeholder="••••••••"
                  autoComplete="new-password"
                />

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
                  {loading ? 'Saving…' : 'Set new password'}
                </button>
              </form>
            </>
          ) : (
            <>
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="mb-2 text-xl font-semibold text-slate-800">Password updated</h2>
              <p className="mb-6 text-sm text-slate-500">
                Your password has been reset successfully. Sign in with your new password.
              </p>
              <Link
                to="/login"
                className="block w-full rounded-lg bg-black px-4 py-2.5 text-center text-sm font-semibold text-white shadow-sm hover:bg-[#1a1a1a] transition-colors"
              >
                Sign in →
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
