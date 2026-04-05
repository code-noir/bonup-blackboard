import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { MagnifyingGlassIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'

export default function Header() {
  const { user, logout } = useAuth()
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
        top: 50,
        left: 216,
        background: '#0D1B2E',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {/* Left — welcome + bonID */}
      <div className="shrink-0 min-w-[160px]">
        <p style={{ fontSize: 14, fontWeight: 500, color: 'rgba(255,255,255,0.86)', lineHeight: 1.25 }}>
          Welcome back, {firstName}
        </p>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', lineHeight: 1.25, marginTop: 2, fontFamily: "'DM Mono', monospace" }}>
          bonID:{' '}
          <span style={{ color: '#8B5CF6', fontWeight: 500 }}>{bonId}</span>
        </p>
      </div>

      {/* Center — search */}
      <div className="flex flex-1 justify-center px-6">
        <div className="relative w-full" style={{ maxWidth: 440 }}>
          <MagnifyingGlassIcon
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
            style={{ color: 'rgba(255,255,255,0.22)' }}
          />
          <input
            type="search"
            readOnly
            placeholder="Search contracts, users, obligations..."
            className="w-full pl-9 pr-4 transition-all focus:outline-none"
            style={{
              height: 34,
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 9,
              fontSize: 13,
              color: 'rgba(255,255,255,0.72)',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = 'rgba(139,92,246,0.45)'
              e.currentTarget.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.07)'
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
              e.currentTarget.style.boxShadow = 'none'
            }}
          />
        </div>
      </div>

      {/* Right — avatar + dropdown */}
      <div className="relative shrink-0" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-lg px-2 py-1 transition-colors"
          style={{ color: 'rgba(255,255,255,0.55)' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] text-white"
            style={{ background: '#8B5CF6', fontWeight: 700 }}
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
