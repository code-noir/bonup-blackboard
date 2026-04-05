import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserCircleIcon, ChevronDownIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'

// ---------------------------------------------------------------------------
// Rotating ad banner
// ---------------------------------------------------------------------------

const BONUP_ADS = [
  'bonUP Pro — Upgrade your experience',
  'bonUP Templates — Start any contract in seconds',
  'bonUP Sessions — Go live with your partner',
  'bonUP Sol — Manage your payments seamlessly',
]

const PARTNER_ADS = [
  'Advertise with bonUP — Reach your audience',
  'Partner Spotlight — Coming soon',
  'Your brand here — Contact us',
  'bonUP Partners — Growing network',
]

function AdBanner({
  ads,
  bg,
  color,
  offsetMs = 0,
}: {
  ads: string[]
  bg: string
  color: string
  offsetMs?: number
}) {
  const [index, setIndex] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    // Delay the first tick so banners don't switch simultaneously
    const boot = setTimeout(() => {
      const id = setInterval(() => {
        setVisible(false)
        setTimeout(() => {
          setIndex((i) => (i + 1) % ads.length)
          setVisible(true)
        }, 350)
      }, 4000)
      return () => clearInterval(id)
    }, offsetMs)
    return () => clearTimeout(boot)
  }, [ads.length, offsetMs])

  return (
    <div
      className="flex h-12 w-[180px] shrink-0 items-center justify-center rounded-lg px-3 text-center"
      style={{ backgroundColor: bg }}
    >
      <p
        className="text-[11px] font-medium leading-tight transition-opacity duration-300"
        style={{ color, opacity: visible ? 1 : 0 }}
      >
        {ads[index]}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

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

  return (
    <div className="fixed top-10 left-60 right-0 z-40 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4">

      {/* 1. Welcome + bonID */}
      <div className="shrink-0 min-w-[140px]">
        <p className="text-[13px] font-semibold leading-tight text-[#0F1F3D]">
          Welcome back, {firstName}
        </p>
        <p className="mt-0.5 text-[11px] leading-tight text-slate-400">
          bonID: {bonId}
        </p>
      </div>

      {/* 2. Search bar */}
      <div className="relative shrink-0 w-[220px]">
        <MagnifyingGlassIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          readOnly
          placeholder="Search contracts, users, obligations..."
          className="w-full cursor-pointer rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-[12px] text-slate-500 placeholder:text-slate-400 focus:outline-none"
        />
      </div>

      {/* 3. bonUP ad banner (navy) */}
      <AdBanner ads={BONUP_ADS} bg="#0F1F3D" color="#ffffff" offsetMs={0} />

      {/* 4. Partner ad banner (gold) */}
      <AdBanner ads={PARTNER_ADS} bg="#F5A623" color="#0F1F3D" offsetMs={2000} />

      {/* 5. User menu — pushed to the right */}
      <div className="relative ml-auto shrink-0" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <UserCircleIcon className="h-5 w-5 text-slate-400" />
          <span className="max-w-[130px] truncate text-[13px] font-medium">{displayName}</span>
          <ChevronDownIcon className="h-3.5 w-3.5 text-slate-400" />
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
