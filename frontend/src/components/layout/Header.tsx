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
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
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
      className="fixed left-60 right-0 z-40 flex h-[50px] items-center px-5"
      style={{
        top: 34,
        background: 'rgba(22,36,56,0.95)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      {/* Left — welcome + bonID */}
      <div className="shrink-0 min-w-[160px]">
        <p style={{ fontSize: 12, fontWeight: 500, color: 'rgba(255,255,255,0.85)', lineHeight: 1.3 }}>
          Welcome back, {firstName}
        </p>
        <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', lineHeight: 1.3, marginTop: 1 }}>
          bonID:{' '}
          <span style={{ color: '#8B5CF6', fontFamily: "'DM Mono', monospace" }}>{bonId}</span>
        </p>
      </div>

      {/* Center — search */}
      <div className="flex flex-1 justify-center">
        <div className="relative w-full max-w-[400px]">
          <MagnifyingGlassIcon
            className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
            style={{ color: 'rgba(255,255,255,0.25)' }}
          />
          <input
            type="search"
            readOnly
            placeholder="Search contracts, users, obligations..."
            className="w-full rounded-lg pl-8 pr-4 text-[12px] transition-colors focus:outline-none"
            style={{
              height: 32,
              background: 'rgba(255,255,255,0.07)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              color: 'rgba(255,255,255,0.7)',
              caretColor: '#8B5CF6',
            }}
            onFocus={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.10)'
              e.currentTarget.style.borderColor = 'rgba(139,92,246,0.4)'
            }}
            onBlur={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
            }}
          />
        </div>
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
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white"
            style={{ background: '#8B5CF6' }}
          >
            {initials}
          </div>
          <span style={{ fontSize: 12, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {displayName}
          </span>
          <ChevronDownIcon className="h-3 w-3 opacity-50" />
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
