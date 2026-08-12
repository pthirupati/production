import axios from 'axios'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

/**
 * In-flight token refresh, shared by every concurrent 401 (single-flight).
 * Module scope on purpose: the interceptor runs per-request, so a local would
 * give each request its own refresh and defeat the point. See the 401 handler.
 */
let refreshPromise = null

/**
 * Named timeout budgets, so a caller can pick one instead of hardcoding a number.
 *
 * The default stays 45s because it is sized for the SLOWEST thing on the shared
 * instance (lab provisioning). That makes every fast read wait 45s before it
 * gives up, but lowering the default is not an option: a timeout produces no
 * `error.response`, so a prematurely-aborted provisioning call falls into the
 * network branch below and reads as "Request timed out" while the backend keeps
 * provisioning — orphaning a lab the user believes failed.
 *
 * So the default is unchanged and callers opt IN to a tighter budget:
 *   api.get('/progress/', { timeout: TIMEOUTS.read })
 */
export const TIMEOUTS = {
  read: 10_000,      // plain GETs of already-computed data
  action: 30_000,    // writes that do real work but aren't provisioning
  provision: 45_000, // lab start/stop — matches the instance default
  long: 120_000,     // AI generation / bulk export
}

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
    // CSRF defense for the httpOnly-cookie auth path (SECURITY_AUDIT A-01):
    // a custom header a cross-site <form> POST cannot set. The backend requires
    // it on cookie-authenticated state changes; harmless on the Bearer path.
    'X-Requested-With': 'XMLHttpRequest',
  },
  timeout: TIMEOUTS.provision, // 45s default — sized for the slowest lab operation
  // Required so the browser sends the httpOnly access_token / refresh_token
  // cookies with every request (cross-origin and same-origin).
  withCredentials: true,
})

/**
 * Retry budget for idempotent reads only.
 *
 * Deliberately narrow. A blanket retry would replay POST /labs/{id}/start/ and
 * double-provision a lab, and would multiply the 429 path that the interceptor
 * below surfaces exactly once. So we retry only when ALL of these hold:
 *   - the verb is GET or HEAD (idempotent by contract)
 *   - the failure is a transport error or a 502/503/504 — never a 4xx, never a
 *     500 (a real application crash will crash again; retrying just delays the
 *     error and triples the load on an already-sick backend)
 *   - the caller did not opt out with `noRetry: true`
 * 401 is excluded structurally: it is handled and returned before we get here,
 * and it has its own single-flight replay that must not be stacked on top of.
 */
const RETRY_MAX = 2
const RETRY_BASE_MS = 300
const RETRYABLE_STATUS = new Set([502, 503, 504])

function retryDelay(attempt) {
  // Exponential backoff with full jitter: 300ms then 600ms, each randomized
  // across [0, delay) so a burst of parallel reads that failed together does
  // not re-hit the backend in a synchronized second wave.
  return Math.random() * RETRY_BASE_MS * 2 ** attempt
}

function isRetryable(error) {
  const original = error.config
  if (!original || original.noRetry === true) return false
  const method = (original.method || 'get').toLowerCase()
  if (method !== 'get' && method !== 'head') return false
  if ((original._retryCount || 0) >= RETRY_MAX) return false
  if (!error.response) {
    // Transport-level failure. Exclude explicit cancellation — an aborted
    // request (see useFetch) must stay aborted, not quietly fire again.
    if (axios.isCancel?.(error) || error.code === 'ERR_CANCELED') return false
    return true
  }
  return RETRYABLE_STATUS.has(error.response.status)
}

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
    // ── Retry idempotent reads BEFORE any user-visible handling ──
    // Placed first on purpose: a transient blip that succeeds on attempt 2 must
    // never flash a "Network error" toast, and must never be counted as a 5xx.
    if (isRetryable(error)) {
      const original = error.config
      original._retryCount = (original._retryCount || 0) + 1
      await new Promise((resolve) => setTimeout(resolve, retryDelay(original._retryCount - 1)))
      return api(original)
    }

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

    // ── 403 Forbidden — entitlement/permission denial ──
    //
    // Centralized here so every module stops inventing its own message, but
    // deliberately quiet by default. Several api modules use 403 as a SOFT-DENY
    // signal they handle themselves: vmware.js/monitoring.js re-throw
    // SUBSCRIPTION_REQUIRED to drive a paywall, and nmap.js/wireshark.js lump
    // 403 in with 404/400 to fall back to a demo sandbox. Every one of those
    // calls already passes `silentError: true`, so honoring `isSilent` keeps
    // their local handling authoritative and fires no spurious toast.
    //
    // Scoped to GET for the same reason. A 403 on a write is an action the user
    // explicitly triggered, and those call sites already render their own
    // feedback next to the button they clicked — TechnologyDetail.jsx toasts
    // "Subscribe to this technology…" after a 403 from POST /labs/{id}/start/,
    // and ScenarioDetail.jsx deliberately stays silent on a 403 from
    // POST /jira/tickets/scenario/{id}/. Neither passes `silentError`, so
    // toasting writes here would double up on the first and break the second.
    const isRead = (original?.method || 'get').toLowerCase() === 'get'
    if (error.response.status === 403 && isRead && !isAuthRequest && !isSilent) {
      const isAdminPoll = /^\/admin\//.test(path)
      const data = error.response.data
      const code = data?.code
      // Subscription denials get the actionable message; a plain permission
      // denial gets a neutral one. Never redirect — the caller decides whether
      // a 403 means "upgrade", "not yours", or "ignore".
      const msg = code === 'SUBSCRIPTION_REQUIRED' || code === 'SUBSCRIPTION_EXPIRED'
        ? (data?.detail || data?.error || 'This feature requires an active subscription.')
        : (data?.detail || data?.error || data?.message || 'You do not have access to this resource.')
      if (!isAdminPoll) {
        toast.error(msg.length > 120 ? msg.slice(0, 120) + '…' : msg, { id: 'forbidden', duration: 5000 })
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
