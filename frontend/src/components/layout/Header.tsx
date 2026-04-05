import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserCircleIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/context/AuthContext'

export default function Header({ title }: { title?: string }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
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

  const displayName =
    user?.first_name
      ? `${user.first_name} ${user.last_name}`.trim()
      : user?.username ?? ''

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <h1 className="text-lg font-semibold text-slate-800">
        {title ?? 'Dashboard'}
      </h1>

      {/* User menu */}
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <UserCircleIcon className="h-6 w-6 text-slate-400" />
          <span className="max-w-[160px] truncate font-medium">
            {displayName}
          </span>
          <ChevronDownIcon className="h-4 w-4 text-slate-400" />
        </button>

        {open && (
          <div className="absolute right-0 z-20 mt-1 w-48 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            <div className="border-b border-slate-100 px-4 py-2">
              <p className="text-xs text-slate-500">Signed in as</p>
              <p className="truncate text-sm font-medium text-slate-800">
                {user?.email}
              </p>
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
    </header>
  )
}
