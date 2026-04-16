// frontend/src/pages/Register.tsx
//
// Stage 1 of signup: submits { email, password, first_name, last_name } to
// POST /api/users/register/ which creates a PendingSignup record.
// NO account or bonID is created here.
// NO auto-login. User is redirected to sign in only after email verification.
//
// Post-submit states:
//   submitted — fresh 201: "Check your email" + verify link + resend option
//   duplicate — 409 conflict: "Already sent" + verify link + resend CTA
//
// The API always returns email_verification_token in the response.
// The frontend constructs a direct /verify-email?token=... link from it.
// In dev this is the primary way to verify (console email also prints the link).
// In production the link arrives via real email; the on-screen link is still
// shown as a fallback so users are never blocked.

import { useState, FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { useAuth } from '@/context/AuthContext'

// ── Reusable form field components ────────────────────────────────────────────

function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  error,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  autoComplete?: string
  error?: string
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
          style={{ paddingRight: 40 }}
          className={`w-full rounded-lg border px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${
            error
              ? 'border-red-400 focus:border-red-400 focus:ring-red-400/20'
              : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500/20'
          }`}
          placeholder="••••••••"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          tabIndex={-1}
          aria-label={show ? 'Hide password' : 'Show password'}
          style={{
            position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#9CA3AF', display: 'flex', alignItems: 'center', padding: 2,
          }}
        >
          {show ? (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: 18, height: 18 }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: 18, height: 18 }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          )}
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function TextField({
  id,
  label,
  value,
  onChange,
  type = 'text',
  autoComplete,
  placeholder,
  error,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  autoComplete?: string
  placeholder?: string
  error?: string
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type={type}
        autoComplete={autoComplete}
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full rounded-lg border px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${
          error
            ? 'border-red-400 focus:border-red-400 focus:ring-red-400/20'
            : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500/20'
        }`}
      />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

// ── Types ──────────────────────────────────────────────────────────────────────

type FieldErrors = {
  email?: string
  password?: string
  first_name?: string
  last_name?: string
}

// submitted — fresh 201 response
// duplicate — 409: a verification email was already sent to this address
type PostState = {
  kind: 'submitted' | 'duplicate'
  email: string
  verifyToken: string | null  // from API response — used to build the direct link
  resending: boolean
  resent: boolean
  resentToken: string | null  // updated token after a successful resend
  resendError: string
}

function extractFieldErrors(data: Record<string, unknown>): FieldErrors {
  const out: FieldErrors = {}
  for (const key of ['email', 'password', 'first_name', 'last_name'] as const) {
    const v = data[key]
    if (Array.isArray(v)) out[key] = v[0]
    else if (typeof v === 'string') out[key] = v
  }
  return out
}

// ── Shared post-submit card ────────────────────────────────────────────────────

function PendingCard({
  state,
  onResend,
}: {
  state: PostState
  onResend: () => void
}) {
  const isDuplicate = state.kind === 'duplicate'

  // The most current token: use resentToken if we have one (reflects the
  // latest resend), otherwise fall back to the original verifyToken.
  const activeToken = state.resentToken ?? state.verifyToken
  const verifyUrl = activeToken
    ? `${window.location.origin}/verify-email?token=${activeToken}`
    : null

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F8FA] px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="text-3xl font-bold tracking-tight text-[#1E3A6E]">
            bon<span className="text-[#F5A623]">UP</span>
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm text-center">
          {/* Icon */}
          <div className="mb-4 flex justify-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="#4F46E5" className="h-6 w-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
              </svg>
            </div>
          </div>

          {/* Heading */}
          <h2 className="mb-2 text-xl font-semibold text-slate-800">
            {verifyUrl
              ? 'Verify your email'
              : isDuplicate
              ? 'Verification pending'
              : 'Check your email'}
          </h2>

          {/*
            Copy is conditional on whether the on-screen verify button is
            available (verifyUrl present).

            When verifyUrl IS present — the button is the primary path.
            Do not imply Gmail delivery; the button works regardless of
            whether a real email arrived.

            When verifyUrl is NOT present (409 duplicate, no token yet) —
            direct the user to resend to get a working link.
          */}
          {verifyUrl ? (
            // On-screen button is available — lead with it
            <>
              <p className="mb-5 text-sm text-slate-600">
                Click the button below to verify{' '}
                <span className="font-medium text-slate-800">{state.email}</span>{' '}
                and complete your bonUP account setup.
                {!state.resent && (
                  <span className="block mt-2 text-xs text-slate-400">
                    A link was also sent to the server console (check your terminal).
                  </span>
                )}
              </p>

              {/* Primary action */}
              <a
                href={verifyUrl}
                className="mb-4 block w-full rounded-lg bg-[#1E3A6E] px-4 py-2.5 text-center text-sm font-semibold text-white shadow-sm hover:bg-[#16305a] transition-colors"
              >
                Verify my email
              </a>
            </>
          ) : isDuplicate ? (
            // 409 duplicate, no token available yet — prompt resend
            <>
              <p className="mb-1 text-sm text-slate-600">
                A verification link was previously requested for
              </p>
              <p className="mb-4 text-sm font-medium text-slate-900">{state.email}</p>
              <p className="mb-4 text-sm text-slate-500">
                No link is available on screen. Click{' '}
                <strong>Resend verification email</strong> below to get a new one.
              </p>
            </>
          ) : (
            // Fallback: submitted but no token in response (should not happen in dev)
            <>
              <p className="mb-1 text-sm text-slate-600">We sent a verification link to</p>
              <p className="mb-4 text-sm font-medium text-slate-900">{state.email}</p>
              <p className="mb-4 text-sm text-slate-500">
                Click the link in the email to verify your address and complete
                your bonUP account setup.
              </p>
            </>
          )}

          {/* Resend controls */}
          {!state.resent && (
            <div className="mb-4">
              {state.resendError && (
                <p className="mb-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                  {state.resendError}
                </p>
              )}
              <button
                type="button"
                onClick={onResend}
                disabled={state.resending}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-60 transition-colors"
              >
                {state.resending ? 'Sending…' : 'Resend verification email'}
              </button>
            </div>
          )}

          <Link
            to="/login"
            className="text-sm font-medium text-[#2563EB] hover:text-[#1D4ED8]"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Register() {
  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [loading, setLoading] = useState(false)
  const [generalError, setGeneralError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [confirmError, setConfirmError] = useState('')

  const [postState, setPostState] = useState<PostState | null>(null)

  if (isAuthenticated) {
    navigate('/hub', { replace: true })
    return null
  }

  // ── Post-submit screens ──────────────────────────────────────────────────────

  if (postState !== null) {
    async function handleResend() {
      if (!postState) return
      setPostState((s) => s && { ...s, resending: true, resendError: '' })
      try {
        const resp = await api.post('/users/resend-verification/', { email: postState.email })
        const newToken = (resp.data?.email_verification_token as string) ?? null
        setPostState((s) =>
          s && { ...s, resending: false, resent: true, resentToken: newToken }
        )
      } catch (err: unknown) {
        const data = (err as { response?: { data?: Record<string, unknown> } })?.response?.data
        const msg =
          (data?.detail as string) ??
          (data?.error as string) ??
          'Failed to resend. Please try again.'
        setPostState((s) => s && { ...s, resending: false, resendError: msg })
      }
    }

    return <PendingCard state={postState} onResend={handleResend} />
  }

  // ── Signup form ──────────────────────────────────────────────────────────────

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setGeneralError('')
    setFieldErrors({})
    setConfirmError('')

    const fe: FieldErrors = {}
    if (!firstName.trim()) fe.first_name = 'First name is required.'
    if (!lastName.trim()) fe.last_name = 'Last name is required.'
    if (Object.keys(fe).length > 0) {
      setFieldErrors(fe)
      return
    }

    if (password !== confirmPassword) {
      setConfirmError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const resp = await api.post('/users/register/', {
        email: email.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      })
      setPostState({
        kind: 'submitted',
        email: email.trim(),
        verifyToken: (resp.data?.email_verification_token as string) ?? null,
        resending: false,
        resent: false,
        resentToken: null,
        resendError: '',
      })
    } catch (err: unknown) {
      const res = err as { response?: { status?: number; data?: Record<string, unknown> } }
      const data = res?.response?.data

      // 409 = a verification email was already sent to this address
      if (res?.response?.status === 409 && data?.pending_verification) {
        setPostState({
          kind: 'duplicate',
          email: (data.email as string) || email.trim(),
          verifyToken: null,  // no token returned on 409 — user must resend
          resending: false,
          resent: false,
          resentToken: null,
          resendError: '',
        })
        return
      }

      if (data) {
        const fe = extractFieldErrors(data)
        if (Object.keys(fe).length > 0) {
          setFieldErrors(fe)
        } else {
          const detail = data.detail ?? data.error ?? data.non_field_errors
          setGeneralError(
            Array.isArray(detail)
              ? String(detail[0])
              : typeof detail === 'string'
              ? detail
              : 'Registration failed. Please try again.',
          )
        }
      } else {
        setGeneralError('Registration failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F8FA] px-4 py-10">
      <div className="w-full max-w-sm">
        {/* Logo — bonUP only, no product name at signup */}
        <div className="mb-8 text-center">
          <p className="text-3xl font-bold tracking-tight text-[#1E3A6E]">
            bon<span className="text-[#F5A623]">UP</span>
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="mb-6 text-xl font-semibold text-slate-800">
            Create your account
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <TextField
                id="first-name"
                label="First name *"
                value={firstName}
                onChange={setFirstName}
                autoComplete="given-name"
                placeholder="Your real first name"
                error={fieldErrors.first_name}
              />
              <TextField
                id="last-name"
                label="Last name *"
                value={lastName}
                onChange={setLastName}
                autoComplete="family-name"
                placeholder="Your real last name"
                error={fieldErrors.last_name}
              />
            </div>

            <TextField
              id="email"
              label="Email address"
              type="email"
              value={email}
              onChange={setEmail}
              autoComplete="email"
              placeholder="you@example.com"
              error={fieldErrors.email}
            />

            <PasswordField
              id="password"
              label="Password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              error={fieldErrors.password}
            />

            <PasswordField
              id="confirm-password"
              label="Confirm password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              autoComplete="new-password"
              error={confirmError || undefined}
            />

            {generalError && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                {generalError}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-black px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 disabled:opacity-60 transition-colors"
            >
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-[#2563EB] hover:text-[#1D4ED8]">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
