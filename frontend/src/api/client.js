import axios from 'axios'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000, // 30s default timeout
})

// Attach JWT token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 - try refresh, then logout
// Handle network errors gracefully
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // ── Network / timeout error (no response from server) ──
    if (!error.response) {
      const message = error.code === 'ECONNABORTED'
        ? 'Request timed out. Please try again.'
        : 'Network error. Check your connection.'
      toast.error(message, { id: 'network-error', duration: 4000 })
      return Promise.reject(error)
    }

    // ── 401 Unauthorized — attempt token refresh ──
    const original = error.config
    if (error.response.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = useAuthStore.getState().refreshToken
      if (refreshToken) {
        try {
          const { data } = await axios.post('/api/auth/refresh/', {
            refresh: refreshToken,
          })
          useAuthStore.getState().setAuth(
            useAuthStore.getState().user,
            data.access,
            data.refresh || refreshToken
          )
          original.headers.Authorization = `Bearer ${data.access}`
          return api(original)
        } catch {
          useAuthStore.getState().logout()
          window.location.href = '/login'
        }
      }
    }

    // ── 429 Rate limited ──
    if (error.response.status === 429) {
      toast.error('Too many requests. Please slow down.', { id: 'rate-limit', duration: 5000 })
    }

    // ── 500+ Server error ──
    if (error.response.status >= 500) {
      toast.error('Server error. Please try again later.', { id: 'server-error', duration: 4000 })
    }

    return Promise.reject(error)
  }
)

export default api
