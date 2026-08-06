import axios from 'axios'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

/**
 * In-flight token refresh, shared by every concurrent 401 (single-flight).
 * Module scope on purpose: the interceptor runs per-request, so a local would
 * give each request its own refresh and defeat the point. See the 401 handler.
 */
let refreshPromise = null

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
    // CSRF defense for the httpOnly-cookie auth path (SECURITY_AUDIT A-01):
    // a custom header a cross-site <form> POST cannot set. The backend requires
    // it on cookie-authenticated state changes; harmless on the Bearer path.
    'X-Requested-With': 'XMLHttpRequest',
  },
  timeout: 45_000, // 45s default timeout — lab operations can be slow
  // Required so the browser sends the httpOnly access_token / refresh_token
  // cookies with every request (cross-origin and same-origin).
  withCredentials: true,
})

// Attach JWT token; strip JSON Content-Type for multipart uploads
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
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

    const original = error.config
    const path = original?.url || ''
    const isAuthRequest = /\/auth\//.test(path)
    // The login/refresh endpoints themselves must never trigger the
    // refresh-and-retry dance (that would loop) — the page renders its own error.
    const isAuthEndpoint = /\/auth\/(login|refresh|register|social|verify-otp|send-otp)/.test(path)
    const isSilent = original?.silentError === true

    const redirectToLogin = (message) => {
      useAuthStore.getState().logout()
      if (message) toast.error(message, { id: 'session-expired', duration: 6000 })
      // Avoid a redirect loop if we're already on an auth page.
      if (!/^\/(login|register|reset-password|forgot-password)/.test(window.location.pathname)) {
        window.location.href = '/login'
      }
    }

    // ── 401 Unauthorized — attempt token refresh, then surface an accurate message ──
    if (error.response.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true
      const { refreshToken, isAuthenticated } = useAuthStore.getState()
      // Attempt refresh if we have either a stored refresh token (legacy) or
      // an active session (cookies will carry the refresh_token automatically).
      if (refreshToken || isAuthenticated) {
        try {
          // Single-flight refresh. Every concurrent 401 awaits the SAME promise
          // instead of firing its own POST /api/auth/refresh/.
          //
          // Without this, any page issuing parallel requests that 401 together
          // fired N refreshes — Dashboard fires ten. The backend rotates refresh
          // tokens and blacklists the old one (ROTATE_REFRESH_TOKENS +
          // BLACKLIST_AFTER_ROTATION), so the first call succeeded and the other
          // nine presented a token that had just been blacklisted, failed, and hit
          // redirectToLogin() — throwing the user to /login mid-session with
          // "Your session has expired." on the busiest screen in the app.
          if (!refreshPromise) {
            const payload = refreshToken ? { refresh: refreshToken } : {}
            refreshPromise = axios
              .post('/api/auth/refresh/', payload, { withCredentials: true })
              .then(({ data }) => {
                useAuthStore.getState().setAuth(
                  useAuthStore.getState().user,
                  data.access,
                  data.refresh || useAuthStore.getState().refreshToken,
                )
                return data.access
              })
              .finally(() => {
                // Clear before the awaiters resume so a genuinely later 401 can
                // start a fresh refresh rather than reusing a settled promise.
                refreshPromise = null
              })
          }
          const newAccess = await refreshPromise
          if (newAccess) {
            original.headers.Authorization = `Bearer ${newAccess}`
          }
          return api(original)
        } catch {
          // Refresh failed — the session is genuinely over (expired or revoked).
          // Show a clear, non-scary message and send the user to log in again,
          // rather than a generic "server error" popup.
          redirectToLogin('Your session has expired. Please sign in again.')
        }
      }
    }

    // ── 429 Rate limited (skip auth forms — they render their own inline error) ──
    if (error.response.status === 429 && !isAuthRequest) {
      const isAdminPoll = /^\/admin\//.test(path)
      const isLabStart = /\/labs\/\d+\/start\//.test(path)
      const retryAfter = error.response.headers?.['retry-after']
      const msg = isLabStart
        ? 'Lab start limit reached. Wait a minute or resume an active lab from Dashboard.'
        : retryAfter
          ? `Too many requests — retry in ${retryAfter}s.`
          : 'Too many requests. Please wait a moment.'
      // Admin dashboards poll many endpoints — don't spam toasts on burst 429.
      if (!isSilent && !isAdminPoll) {
        toast.error(msg, { id: 'rate-limit', duration: 6000 })
      }
    }

    // 500+ Server error (skip auth forms and silent bootstrap requests)
    if (error.response.status >= 500 && !isAuthRequest && !isSilent) {
      const isAdminPoll = /^\/admin\//.test(path)
      if (isAdminPoll) {
        return Promise.reject(error)
      }
      const data = error.response.data
      const msg = data?.error || data?.detail || data?.message || 'Server error. Please try again later.'
      toast.error(msg.length > 120 ? msg.slice(0, 120) + '…' : msg, { id: 'server-error', duration: 5000 })
    }

    return Promise.reject(error)
  }
)

export default api
