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
  const displayName =
    user?.first_name ? `${user.first_name} ${user.last_name}`.trim() : user?.username ?? ''

  return (
    <div className="fixed top-10 left-60 right-0 z-40 flex h-16 items-center border-b border-slate-200 bg-white px-6 gap-4">

      {/* Left — welcome + bonID */}
      <div className="min-w-[160px]">
        <p className="text-sm font-semibold text-slate-800 leading-tight">
          Welcome back, {firstName}
        </p>
        {user?.bon_id && (
          <p className="text-[11px] text-slate-400 leading-tight mt-0.5">
            bonID: {user.bon_id}
          </p>
        )}
      </div>

      {/* Center — search bar */}
      <div className="flex flex-1 justify-center">
        <div className="relative w-full max-w-md">
          <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            readOnly
            placeholder="Search contracts, users, obligations..."
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm text-slate-500 placeholder:text-slate-400 focus:outline-none cursor-pointer"
          />
        </div>
      </div>

      {/* Right — user menu */}
      <div className="relative min-w-[160px] flex justify-end" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <UserCircleIcon className="h-6 w-6 text-slate-400" />
          <span className="max-w-[140px] truncate font-medium">{displayName}</span>
          <ChevronDownIcon className="h-4 w-4 text-slate-400" />
        </button>

        {open && (
          <div className="absolute right-0 z-20 mt-1 w-48 rounded-lg border border-slate-200 bg-white py-1 shadow-lg top-full">
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
