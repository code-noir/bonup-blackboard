import api, { impersonationTokenStorage, tokenStorage } from './client'

export const DELIVERY_CONTEXT_EVENT = 'bonup-auth-context-change'
export function deliveryContext() {
  return `${tokenStorage.getRefresh() || ''}:${impersonationTokenStorage.getSessionId() || ''}`
}

// Accept only application-generated private delivery routes. Never forward JWTs
// to a persisted external URL, a public bearer route, or another API endpoint.
export function privateDeliveryPath(value: string): string {
  const id = '[0-9a-fA-F-]{36}'
  const allowed = new RegExp(`^/api/(?:uploads/${id}|contracts/${id}/documents/${id}|lifecycle/items/${id}/attachments/${id})/delivery/$`)
  if (!allowed.test(value)) throw new Error('File delivery is unavailable.')
  return value.slice('/api'.length)
}

export async function fetchPrivateFile(value: string, signal: AbortSignal, download = false) {
  const path = privateDeliveryPath(value)
  const context = deliveryContext()
  const response = await api.get<Blob>(path, {
    responseType: 'blob', signal, params: download ? { download: '1' } : { preview: '1' },
  })
  if (signal.aborted || context !== deliveryContext()) throw new DOMException('Cancelled', 'AbortError')
  return response.data
}

export function previewKind(type: string): 'image' | 'video' | 'audio' | 'pdf' | null {
  const mime = type.split(';', 1)[0].toLowerCase()
  if (['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/avif'].includes(mime)) return 'image'
  if (['video/mp4', 'video/webm', 'video/ogg'].includes(mime)) return 'video'
  if (['audio/mpeg', 'audio/mp4', 'audio/ogg', 'audio/wav', 'audio/webm'].includes(mime)) return 'audio'
  return mime === 'application/pdf' ? 'pdf' : null
}

export function downloadObjectUrl(url: string, filename: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener noreferrer'
  document.body.appendChild(link)
  link.click()
  link.remove()
}
