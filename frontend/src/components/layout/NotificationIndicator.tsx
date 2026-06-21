import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BellIcon } from '@heroicons/react/24/outline'
import api from '@/api/client'

type NotificationItem = {
  id: string
  notification_type: string
  title: string
  message: string
  is_read: boolean
  redirect_url?: string
  metadata?: Record<string, unknown>
  created_at: string
}

type NotificationResponse = {
  results: NotificationItem[]
}

type NotificationCountResponse = {
  unread_count: number
}

function relativeTime(value: string) {
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return ''
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function NotificationIndicator() {
  const navigate = useNavigate()
  const ref = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  async function loadUnread() {
    const [{ data: listData }, { data: countData }] = await Promise.all([
      api.get<NotificationResponse>('/notifications/unread/'),
      api.get<NotificationCountResponse>('/notifications/unread-count/'),
    ])
    setItems(listData.results || [])
    setUnreadCount(countData.unread_count || 0)
  }

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [{ data: listData }, { data: countData }] = await Promise.all([
          api.get<NotificationResponse>('/notifications/unread/'),
          api.get<NotificationCountResponse>('/notifications/unread-count/'),
        ])
        if (!cancelled) {
          setItems(listData.results || [])
          setUnreadCount(countData.unread_count || 0)
        }
      } catch {
        if (!cancelled) {
          setItems([])
          setUnreadCount(0)
        }
      }
    }
    load()
    const interval = window.setInterval(load, 20000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [])

  useEffect(() => {
    function handler(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  async function openNotification(item: NotificationItem) {
    try {
      await api.post(`/notifications/${item.id}/read/`)
    } catch {
      // The navigation target is still the source of truth if read marking fails.
    }
    setOpen(false)
    await loadUnread().catch(() => {})
    const target = item.redirect_url || (typeof item.metadata?.redirect_url === 'string' ? item.metadata.redirect_url : '')
    if (target) navigate(target)
  }

  return (
    <div className="relative shrink-0" ref={ref}>
      <button
        type="button"
        aria-label="Notifications"
        onClick={() => setOpen((value) => !value)}
        className="relative flex h-8 w-8 items-center justify-center rounded-lg transition-colors"
        style={{ color: 'rgba(255,255,255,0.7)' }}
        onMouseEnter={(event) => (event.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
        onMouseLeave={(event) => (event.currentTarget.style.background = 'transparent')}
      >
        <BellIcon className="h-5 w-5" />
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              right: 3,
              top: 3,
              minWidth: 16,
              height: 16,
              borderRadius: 999,
              background: '#DC2626',
              border: '1px solid #172334',
              color: 'white',
              fontSize: 10,
              fontWeight: 800,
              lineHeight: '14px',
              textAlign: 'center',
              padding: '0 3px',
            }}
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-lg border border-slate-200 bg-white shadow-lg" style={{ zIndex: 9999 }}>
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <p className="text-sm font-semibold text-slate-900">Notifications</p>
            <span className="text-xs text-slate-500">{unreadCount} unread</span>
          </div>
          <div style={{ maxHeight: 340, overflowY: 'auto' }}>
            {items.length === 0 ? (
              <p className="px-4 py-5 text-sm text-slate-500">No unread notifications.</p>
            ) : items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => openNotification(item)}
                className="w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                  <span className="shrink-0 text-[11px] text-slate-400">{relativeTime(item.created_at)}</span>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-600">{item.message}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
