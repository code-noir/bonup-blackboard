import axios from 'axios'

const TOKEN_KEY = 'bb_access'
const REFRESH_KEY = 'bb_refresh'

export const tokenStorage = {
  getAccess: () => localStorage.getItem(TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  setAccess: (access: string) => localStorage.setItem(TOKEN_KEY, access),
  clear: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach access token to every request
api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401 try a silent refresh; if that fails, clear tokens
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
      const refresh = tokenStorage.getRefresh()
      if (!refresh) throw new Error('no refresh token')
      const { data } = await axios.post('/api/auth/token/refresh/', { refresh })
      tokenStorage.setAccess(data.access)
      refreshQueue.forEach((cb) => cb(data.access))
      refreshQueue = []
      original.headers.Authorization = `Bearer ${data.access}`
      return api(original)
    } catch {
      tokenStorage.clear()
      window.location.href = '/login'
      return Promise.reject(err)
    } finally {
      refreshing = false
    }
  },
)

export default api
