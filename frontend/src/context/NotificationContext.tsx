import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'

type NotificationTone = 'success' | 'info' | 'warning' | 'error'

type Notification = {
  id: number
  tone: NotificationTone
  message: string
}

type NotifyOptions = {
  durationMs?: number | null
}

type NotificationContextValue = {
  success: (message: string, options?: NotifyOptions) => void
  info: (message: string, options?: NotifyOptions) => void
  warning: (message: string, options?: NotifyOptions) => void
  error: (message: string, options?: NotifyOptions) => void
  dismiss: () => void
}

const DEFAULT_DURATIONS: Record<NotificationTone, number | null> = {
  success: 4000,
  info: 4500,
  warning: 7000,
  error: null,
}

const NotificationContext = createContext<NotificationContextValue | null>(null)

function toneClasses(tone: NotificationTone) {
  if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (tone === 'error') return 'border-red-200 bg-red-50 text-red-700'
  if (tone === 'warning') return 'border-amber-200 bg-amber-50 text-amber-800'
  return 'border-slate-200 bg-white text-slate-700'
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notification, setNotification] = useState<Notification | null>(null)
  const timerRef = useRef<number | null>(null)
  const nextIdRef = useRef(1)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const dismiss = useCallback(() => {
    clearTimer()
    setNotification(null)
  }, [clearTimer])

  const show = useCallback((tone: NotificationTone, message: string, options: NotifyOptions = {}) => {
    clearTimer()
    const id = nextIdRef.current
    nextIdRef.current += 1
    setNotification({ id, tone, message })

    const duration = options.durationMs !== undefined ? options.durationMs : DEFAULT_DURATIONS[tone]
    if (duration !== null && duration > 0) {
      timerRef.current = window.setTimeout(() => {
        setNotification((current) => (current?.id === id ? null : current))
        timerRef.current = null
      }, duration)
    }
  }, [clearTimer])

  useEffect(() => clearTimer, [clearTimer])

  const value = useMemo<NotificationContextValue>(() => ({
    success: (message, options) => show('success', message, options),
    info: (message, options) => show('info', message, options),
    warning: (message, options) => show('warning', message, options),
    error: (message, options) => show('error', message, options),
    dismiss,
  }), [dismiss, show])

  return (
    <NotificationContext.Provider value={value}>
      {children}
      {notification && (
        <div className="pointer-events-none fixed right-4 top-4 z-[1000] flex w-[calc(100vw-2rem)] max-w-md justify-end sm:right-6 sm:top-6 sm:w-full">
          <div
            role={notification.tone === 'error' ? 'alert' : 'status'}
            aria-live={notification.tone === 'error' ? 'assertive' : 'polite'}
            className={`pointer-events-auto flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-sm font-semibold shadow-lg ${toneClasses(notification.tone)}`}
          >
            <p className="m-0 min-w-0 flex-1 [overflow-wrap:anywhere]">{notification.message}</p>
            <button
              type="button"
              onClick={dismiss}
              className="shrink-0 rounded-md p-1 opacity-70 hover:bg-white/60 hover:opacity-100"
              aria-label="Dismiss notification"
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </NotificationContext.Provider>
  )
}

export function useNotification() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotification must be used within NotificationProvider')
  }
  return context
}
