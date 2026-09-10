import axios from 'axios'

const TOKEN_KEY = 'bb_access'
const REFRESH_KEY = 'bb_refresh'
const OPERATOR_ACCESS_KEY = 'bb_admin_access'
const OPERATOR_REFRESH_KEY = 'bb_admin_refresh'
const IMPERSONATION_ACCESS_KEY = 'bb_impersonation_access'
const IMPERSONATION_SESSION_KEY = 'bb_impersonation_session_id'
const IMPERSONATION_USER_KEY = 'bb_impersonation_user'

export const tokenStorage = {
  getAccess: () => localStorage.getItem(TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
    window.dispatchEvent(new Event('bonup-auth-context-change'))
  },
  setAccess: (access: string) => localStorage.setItem(TOKEN_KEY, access),
  clear: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    window.dispatchEvent(new Event('bonup-auth-context-change'))
  },
}

export interface ImpersonationUser {
  id: number
  email: string
  first_name: string
  last_name: string
  is_staff?: boolean
}

export const operatorTokenStorage = {
  getAccess: () => localStorage.getItem(OPERATOR_ACCESS_KEY),
  getRefresh: () => localStorage.getItem(OPERATOR_REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(OPERATOR_ACCESS_KEY, access)
    localStorage.setItem(OPERATOR_REFRESH_KEY, refresh)
  },
  setAccess: (access: string) => localStorage.setItem(OPERATOR_ACCESS_KEY, access),
  clear: () => {
    localStorage.removeItem(OPERATOR_ACCESS_KEY)
    localStorage.removeItem(OPERATOR_REFRESH_KEY)
  },
}

export const impersonationTokenStorage = {
  getAccess: () => localStorage.getItem(IMPERSONATION_ACCESS_KEY),
  getSessionId: () => localStorage.getItem(IMPERSONATION_SESSION_KEY),
  getUser: (): ImpersonationUser | null => {
    const raw = localStorage.getItem(IMPERSONATION_USER_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as ImpersonationUser
    } catch {
      return null
    }
  },
  set: (access: string, sessionId: string, user: ImpersonationUser) => {
    localStorage.setItem(IMPERSONATION_ACCESS_KEY, access)
    localStorage.setItem(IMPERSONATION_SESSION_KEY, sessionId)
    localStorage.setItem(IMPERSONATION_USER_KEY, JSON.stringify(user))
    window.dispatchEvent(new Event('bonup-auth-context-change'))
  },
  clear: () => {
    const wasViewingAs = !!localStorage.getItem(IMPERSONATION_ACCESS_KEY)
    localStorage.removeItem(IMPERSONATION_ACCESS_KEY)
    localStorage.removeItem(IMPERSONATION_SESSION_KEY)
    localStorage.removeItem(IMPERSONATION_USER_KEY)
    window.dispatchEvent(new Event('bonup-auth-context-change'))
    if (wasViewingAs) window.dispatchEvent(new Event('view-as-exited'))
  },
}

type CredentialContext = 'customer' | 'operator' | 'view-as'

// Resolve only our API origin before credentials are attached. Never trust an
// arbitrary absolute URL or an overridden Axios baseURL.
export function apiPath(value: string, baseURL = '/api'): string {
  if (!['/api', '/api/'].includes(baseURL) || !value || value.trim() !== value ||
      /^[a-z][a-z\d+.-]*:/i.test(value) || value.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(value)) {
    throw new Error('API destination is unavailable.')
  }
  // Reject ambiguous path encodings, separators and dot segments before URL parsing.
  // Query values may legitimately contain encoded URLs; they are not destinations.
  const inputPath = value.split(/[?#]/, 1)[0]
  if (/%(?:2f|5c|2e|25|0[0-9a-f]|1[0-9a-f]|7f)/i.test(inputPath) ||
      inputPath.includes('//') || inputPath.split('/').some(part => part === '.' || part === '..')) {
    throw new Error('API destination is unavailable.')
  }
  const raw = value.startsWith('/api/') ? value : `/api/${value.replace(/^\//, '')}`
  const url = new URL(raw, window.location.origin)
  // Axios combines /api with this suffix. Validate that final combination as well:
  // stripping /api must never produce an absolute/protocol-relative destination.
  const suffix = url.pathname.slice(4) + url.search
  const destination = new URL(`/api/${suffix.replace(/^\//, '')}`, window.location.origin)
  if (!url.pathname.startsWith('/api/') || !/^\/(?!\/)/.test(suffix) ||
      destination.origin !== window.location.origin || destination.href !== url.href || url.hash) {
    throw new Error('API destination is unavailable.')
  }
  return url.pathname + url.search
}

function contextFor(path: string): CredentialContext {
  if (path.startsWith('/api/operator/view-as/exit/') && impersonationTokenStorage.getAccess()) return 'view-as'
  if (path.startsWith('/api/operator/') || path.startsWith('/api/admin/')) return 'operator'
  return impersonationTokenStorage.getAccess() ? 'view-as' : 'customer'
}

function contextIdentity(context: CredentialContext) {
  if (context === 'view-as') return impersonationTokenStorage.getAccess()
  const storage = context === 'operator' ? operatorTokenStorage : tokenStorage
  return storage.getRefresh() || storage.getAccess()
}

function accessFor(context: CredentialContext) {
  return context === 'view-as' ? impersonationTokenStorage.getAccess() : context === 'operator' ? operatorTokenStorage.getAccess() : tokenStorage.getAccess()
}

const api = axios.create({ baseURL: '/api', headers: { 'Content-Type': 'application/json' } })
type RequestConfig = import('axios').InternalAxiosRequestConfig & {
  _retry?: boolean
  _context?: CredentialContext
  _identity?: string | null
}

api.interceptors.request.use((rawConfig) => {
  const config = rawConfig as RequestConfig
  const path = apiPath(config.url || '', config.baseURL)
  config.url = path.slice(4)
  config._context = contextFor(path)
  config._identity = contextIdentity(config._context)
  const token = accessFor(config._context)
  if (token) config.headers.Authorization = `Bearer ${token}`
  else delete config.headers.Authorization
  return config
})

const refreshes: Partial<Record<'customer' | 'operator', { identity: string | null; promise: Promise<string> }>> = {}

function stillCurrent(config: RequestConfig) {
  return config._context === contextFor(apiPath(config.url || '', config.baseURL)) &&
    config._identity === contextIdentity(config._context!)
}

async function refreshAccess(context: 'customer' | 'operator', identity: string | null) {
  const storage = context === 'operator' ? operatorTokenStorage : tokenStorage
  const refresh = storage.getRefresh()
  if (!refresh) throw new Error('Authentication expired.')
  const { data } = await axios.post(context === 'operator' ? '/api/operator/auth/token/refresh/' : '/api/auth/token/refresh/', { refresh })
  if (contextIdentity(context) !== identity) throw new axios.CanceledError('Authentication context changed.')
  storage.setAccess(data.access)
  return data.access as string
}

api.interceptors.response.use(
  (response) => {
    if (!stillCurrent(response.config as RequestConfig)) throw new axios.CanceledError('Authentication context changed.')
    return response
  },
  async (err) => {
    const original = err.config as RequestConfig | undefined
    if (!original || err.response?.status !== 401 || original._retry) return Promise.reject(err)
    if (!stillCurrent(original)) return Promise.reject(new axios.CanceledError('Authentication context changed.'))
    original._retry = true
    const context = original._context!
    if (context === 'view-as') {
      impersonationTokenStorage.clear()
      return Promise.reject(new axios.CanceledError('View-As ended.'))
    }
    const identity = original._identity ?? null
    try {
      // Customer and operator refreshes must never share a queue or token.
      let entry = refreshes[context]
      if (!entry || entry.identity !== identity) {
        entry = { identity, promise: refreshAccess(context, identity) }
        refreshes[context] = entry
      }
      try { await entry.promise } finally { if (refreshes[context] === entry) delete refreshes[context] }
      if (!stillCurrent(original) || original.signal?.aborted) throw new axios.CanceledError('Authentication context changed.')
      return api(original)
    } catch (refreshError) {
      if (stillCurrent(original) && !axios.isCancel(refreshError)) {
        const storage = context === 'operator' ? operatorTokenStorage : tokenStorage
        storage.clear()
        window.location.href = context === 'operator' ? '/operator/login' : '/login'
      }
      return Promise.reject(refreshError)
    }
  },
)

export default api
