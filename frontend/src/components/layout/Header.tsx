import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { MagnifyingGlassIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'

const TODAY = new Date().toLocaleDateString('en-US', {
  weekday: 'long',
  year: 'numeric',
  month: 'long',
  day: 'numeric',
})

export default function Header() {
  const { user, logout, isOnTrial, trialDaysRemaining } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const firstName = user?.first_name || user?.username || ''
  const bonId = user?.bon_id ?? '—'
  const displayName =
    user?.first_name ? `${user.first_name} ${user.last_name}`.trim() : user?.username ?? ''
  const initials =
    [user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('').toUpperCase() ||
    user?.username?.[0]?.toUpperCase() ||
    '?'

  return (
    <div
      className="fixed right-0 z-40 flex h-[50px] items-center px-5"
      style={{
        top: 64,
        left: 'var(--sidebar-w, 216px)',
        background: '#172334',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Left — welcome + bonID */}
      <div className="shrink-0 min-w-[160px]">
        <p style={{ fontSize: 14, fontWeight: 500, color: 'rgba(255,255,255,0.9)', lineHeight: 1.25 }}>
          Welcome back, {firstName}
        </p>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', lineHeight: 1.25, marginTop: 6, fontFamily: "'DM Mono', monospace" }}>
          bonID:{' '}
          <span style={{ color: '#D4900A', fontWeight: 500, letterSpacing: '0.15em' }}>{bonId}</span>
        </p>
      </div>

      {/* Tier label — centered between user info and search */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
        <span
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: user?.subscription_tier === 'sol_member' ? '#BAE6FD' : '#BFDBFE',
            whiteSpace: 'nowrap',
          }}
        >
          {user?.subscription_tier === 'trial' ? 'Free Trial'
            : user?.subscription_tier === 'sol_member' ? 'Sol Member'
            : user?.subscription_tier === 'pay_as_you_go' ? 'Pay As You Go'
            : user?.subscription_tier === 'blackboard_basic' ? 'Blackboard Basic'
            : user?.subscription_tier === 'blackboard_pro' ? 'Blackboard Pro'
            : user?.subscription_tier === 'blackboard_business' ? 'Blackboard Business'
            : user?.subscription_tier === 'blackboard_premium' ? 'Blackboard Premium'
            : 'No Plan'}
        </span>
        {isOnTrial() && (() => {
          const days = trialDaysRemaining()
          const color = days > 7 ? '#2DD4BF' : days >= 3 ? '#F5A623' : '#DC2626'
          return (
            <span style={{
              fontSize: 12, fontWeight: 500, color,
              background: 'rgba(255,255,255,0.08)',
              borderRadius: 6, padding: '2px 8px',
              whiteSpace: 'nowrap',
            }}>
              Trial — {days} days left
            </span>
          )
        })()}
      </div>

      {/* Center — search */}
      <div className="flex flex-1 justify-center px-6">
        <div className="relative w-full" style={{ maxWidth: 440 }}>
          <MagnifyingGlassIcon
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
            style={{ color: '#9CA3AF' }}
          />
          <input
            type="search"
            readOnly
            placeholder="Search contracts, users, obligations..."
            className="w-full pl-9 pr-4 transition-all focus:outline-none"
            style={{
              height: 34,
              background: '#ECEEF2',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 9,
              fontSize: 13,
              color: '#1C2B3A',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.25)'
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'
            }}
          />
        </div>
      </div>

      {/* PBVD + Date */}
      <div className="shrink-0 mr-4 flex items-center" style={{ gap: 12 }}>
        <button
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            height: 26,
            padding: '0 12px',
            borderRadius: 7,
            fontSize: 11,
            fontWeight: 600,
            fontFamily: "'Outfit', sans-serif",
            color: '#000000',
            background: '#ffffff',
            border: 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#F0F0F0')}
          onMouseLeave={(e) => (e.currentTarget.style.background = '#ffffff')}
        >
          My Account
        </button>
        <span style={{ fontSize: 12, fontWeight: 400, color: 'rgba(255,255,255,0.45)', fontFamily: "'Outfit', sans-serif", whiteSpace: 'nowrap' }}>
          {TODAY}
        </span>
      </div>

      {/* Right — avatar + dropdown */}
      <div className="relative shrink-0" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-lg px-2 py-1 transition-colors"
          style={{ color: 'rgba(255,255,255,0.6)' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] text-white"
            style={{
              background: '#2E4156',
              border: '1px solid rgba(255,255,255,0.2)',
              fontWeight: 700,
            }}
          >
            {initials}
          </div>
          <span style={{ fontSize: 13, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {displayName}
          </span>
          <ChevronDownIcon className="h-3 w-3 opacity-40" />
        </button>

        {open && (
          <div className="absolute right-0 top-full z-50 mt-1 w-48 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            <div className="border-b border-slate-100 px-4 py-2">
              <p className="text-xs text-slate-500">Signed in as</p>
              <p className="truncate text-sm font-medium text-slate-800">{user?.email}</p>
            </div>
            <button
              onClick={() => { setOpen(false); navigate('/settings') }}
              className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
            >
              Settings
            </button>
            <button
              onClick={handleLogout}
              className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
