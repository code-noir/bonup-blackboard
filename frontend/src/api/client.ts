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
    localStorage.removeItem(IMPERSONATION_ACCESS_KEY)
    localStorage.removeItem(IMPERSONATION_SESSION_KEY)
    localStorage.removeItem(IMPERSONATION_USER_KEY)
    window.dispatchEvent(new Event('bonup-auth-context-change'))
  },
}

function pathFor(configUrl?: string) {
  if (!configUrl) return ''
  try {
    return new URL(configUrl, window.location.origin).pathname
  } catch {
    return configUrl
  }
}

function tokenForRequest(configUrl?: string) {
  const path = pathFor(configUrl)
  if (path.startsWith('/api/operator/view-as/exit/') && impersonationTokenStorage.getAccess()) {
    return impersonationTokenStorage.getAccess()
  }
  if (path.startsWith('/api/operator/') || path.startsWith('/operator/') || path.startsWith('/api/admin/') || path.startsWith('/admin/')) {
    return operatorTokenStorage.getAccess()
  }
  return impersonationTokenStorage.getAccess() || tokenStorage.getAccess()
}

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = tokenForRequest(config.url)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshing = false
let refreshQueue: Array<(token: string) => void> = []

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status !== 401 || original._retry) {
      return Promise.reject(err)
    }
    original._retry = true

    const path = pathFor(original.url)
    const isOperatorRequest = path.startsWith('/api/operator/') || path.startsWith('/operator/') || path.startsWith('/api/admin/') || path.startsWith('/admin/')
    const isImpersonating = !!impersonationTokenStorage.getAccess() && !isOperatorRequest
    if (isImpersonating || path.startsWith('/api/operator/view-as/exit/') || path.startsWith('/operator/view-as/exit/')) {
      impersonationTokenStorage.clear()
      return Promise.reject(err)
    }

    if (refreshing) {
      return new Promise((resolve) => {
        refreshQueue.push((newToken) => {
          original.headers.Authorization = `Bearer ${newToken}`
          resolve(api(original))
        })
      })
    }

    refreshing = true
    try {
      const refresh = isOperatorRequest ? operatorTokenStorage.getRefresh() : tokenStorage.getRefresh()
      if (!refresh) throw new Error('no refresh token')
      const refreshUrl = isOperatorRequest ? '/api/operator/auth/token/refresh/' : '/api/auth/token/refresh/'
      const { data } = await axios.post(refreshUrl, { refresh })
      if (isOperatorRequest) operatorTokenStorage.setAccess(data.access)
      else tokenStorage.setAccess(data.access)
      refreshQueue.forEach((cb) => cb(data.access))
      refreshQueue = []
      original.headers.Authorization = `Bearer ${data.access}`
      if (original.url?.includes('/delivery/')) return api(original)
      const { signal: _dropped, ...retryConfig } = original
      return api(retryConfig)
    } catch {
      if (isOperatorRequest) {
        operatorTokenStorage.clear()
        window.location.href = '/operator/login'
      } else {
        tokenStorage.clear()
        window.location.href = '/login'
      }
      return Promise.reject(err)
    } finally {
      refreshing = false
    }
  },
)

export default api
