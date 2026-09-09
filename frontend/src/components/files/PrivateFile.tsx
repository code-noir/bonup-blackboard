import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { DELIVERY_CONTEXT_EVENT, deliveryContext, downloadObjectUrl, fetchPrivateFile, previewKind } from '../../api/fileDelivery'

function subscribe(callback: () => void) {
  window.addEventListener(DELIVERY_CONTEXT_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(DELIVERY_CONTEXT_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}
function useDeliveryContext() {
  return useSyncExternalStore(subscribe, deliveryContext, () => '')
}

export function usePrivateDownload() {
  const context = useDeliveryContext()
  const current = useRef<{ controller: AbortController; url?: string; timer?: ReturnType<typeof setTimeout> } | null>(null)
  const [state, setState] = useState({ context, loading: false, error: '' })
  const cleanup = useCallback(() => {
    const task = current.current
    current.current = null
    if (task) {
      task.controller.abort()
      if (task.url) URL.revokeObjectURL(task.url)
      if (task.timer) clearTimeout(task.timer)
    }
  }, [])
  useEffect(() => cleanup, [cleanup, context])
  const download = useCallback(async (path: string, filename: string) => {
    cleanup()
    const task: NonNullable<typeof current.current> = { controller: new AbortController() }
    current.current = task
    setState({ context, loading: true, error: '' })
    try {
      const blob = await fetchPrivateFile(path, task.controller.signal, true)
      if (task.controller.signal.aborted) return
      task.url = URL.createObjectURL(blob)
      downloadObjectUrl(task.url, filename)
      // Keep alive long enough for the browser to consume the download link.
      task.timer = setTimeout(cleanup, 60_000)
      setState({ context, loading: false, error: '' })
    } catch {
      if (!task.controller.signal.aborted) {
        cleanup()
        setState({ context, loading: false, error: 'Could not download this file.' })
      }
    }
  }, [cleanup, context])
  return { loading: state.context === context && state.loading, error: state.context === context ? state.error : '', download }
}

export function PrivateDownloadButton({ path, filename, children = 'Download' }: {
  path: string; filename: string; children?: React.ReactNode
}) {
  const { download, loading, error } = usePrivateDownload()
  return <span><button type="button" disabled={loading} onClick={() => void download(path, filename)}>{loading ? 'Loading…' : children}</button>{error && <span role="alert">{error}</span>}</span>
}

export function PrivateFilePreview({ path, title = '', thumbnail = false, className = '' }: {
  path: string; title?: string; thumbnail?: boolean; className?: string
}) {
  const context = useDeliveryContext()
  const container = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(!thumbnail)
  const [result, setResult] = useState<{ path: string; context: string; url?: string; kind?: ReturnType<typeof previewKind>; error?: string } | null>(null)
  useEffect(() => {
    if (!thumbnail || !container.current) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setVisible(true); observer.disconnect() }
    })
    observer.observe(container.current)
    return () => observer.disconnect()
  }, [thumbnail])
  useEffect(() => {
    if (!visible || !path) return
    const controller = new AbortController()
    let url: string | undefined
    fetchPrivateFile(path, controller.signal).then(blob => {
      if (controller.signal.aborted) return
      const kind = previewKind(blob.type)
      if (kind && (!thumbnail || kind === 'image')) url = URL.createObjectURL(blob)
      setResult({ path, context, url, kind })
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ path, context, error: 'Could not load this file.' })
    })
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [path, context, visible, thumbnail])
  const active = result?.path === path && result.context === context ? result : null
  return <div ref={container} className={className}>
    {!active && visible && <span role="status">Loading…</span>}
    {active?.error && <span role="alert">{active.error}</span>}
    {active && !active.url && !active.error && <span>Preview is not available. Download the file to open it.</span>}
    {active?.url && active.kind === 'image' && <img src={active.url} alt={title} className={className} />}
    {active?.url && active.kind === 'video' && <video src={active.url} controls className={className} />}
    {active?.url && active.kind === 'audio' && <audio src={active.url} controls className={className} />}
    {active?.url && active.kind === 'pdf' && <iframe src={active.url} title={title} sandbox="" className="h-[560px] w-full" />}
  </div>
}
