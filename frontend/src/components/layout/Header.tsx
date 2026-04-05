import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserCircleIcon, ChevronDownIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
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

  return (
    <div className="fixed top-10 left-60 right-0 z-40 flex h-16 items-center border-b border-slate-200 bg-white px-5">

      {/* Left — welcome + bonID */}
      <div className="shrink-0 min-w-[150px]">
        <p className="text-[13px] font-semibold leading-tight text-[#0F1F3D]">
          Welcome back, {firstName}
        </p>
        <p className="mt-0.5 text-[11px] leading-tight text-slate-400">
          bonID: {bonId}
        </p>
      </div>

      {/* Center — search bar */}
      <div className="flex flex-1 justify-center">
        <div className="relative w-[300px]">
          <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            readOnly
            placeholder="Search contracts, users, obligations..."
            className="w-full cursor-pointer rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-[13px] text-slate-500 placeholder:text-slate-400 focus:outline-none"
          />
        </div>
      </div>

      {/* Right — user menu */}
      <div className="relative shrink-0" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <UserCircleIcon className="h-5 w-5 text-slate-400" />
          <span className="max-w-[140px] truncate text-[13px] font-medium">{displayName}</span>
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
