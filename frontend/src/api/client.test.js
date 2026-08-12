import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Capture toasts instead of rendering them.
const toastCalls = []
vi.mock('react-hot-toast', () => ({
  default: {
    error: (msg, opts) => { toastCalls.push({ msg, opts }) },
    success: () => {},
  },
}))

// The interceptor reads the auth store and can call logout()/window.location.
vi.mock('../store/authStore', () => ({
  useAuthStore: {
    getState: () => ({
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      user: null,
      logout: () => {},
      setAuth: () => {},
    }),
  },
}))

// jsdom isn't the default environment here; the 401 path touches window.location.
globalThis.window = globalThis.window || { location: { pathname: '/', href: '/' } }

const { default: api, TIMEOUTS } = await import('./client')

/**
 * Drive the real response interceptor by stubbing the adapter, which is the
 * layer axios calls to actually perform a request. Each entry in `script` is
 * the outcome for one attempt, so we can assert how many attempts happened.
 */
function stubAdapter(script) {
  const attempts = []
  api.defaults.adapter = async (config) => {
    attempts.push(config)
    const step = script[Math.min(attempts.length - 1, script.length - 1)]
    if (step.status && step.status < 400) {
      return { data: step.data ?? {}, status: step.status, statusText: 'OK', headers: {}, config }
    }
    const err = new Error(step.message || `Request failed with status ${step.status}`)
    err.config = config
    err.code = step.code
    if (step.status) {
      err.response = { status: step.status, data: step.data ?? {}, headers: step.headers || {}, config }
    }
    throw err
  }
  return attempts
}

const originalAdapter = api.defaults.adapter

beforeEach(() => { toastCalls.length = 0 })
afterEach(() => { api.defaults.adapter = originalAdapter })

describe('idempotent GET retry with backoff', () => {
  it('retries a GET on 503 and resolves without a toast', async () => {
    const attempts = stubAdapter([{ status: 503 }, { status: 200, data: { ok: true } }])
    const res = await api.get('/progress/')
    expect(res.data).toEqual({ ok: true })
    expect(attempts).toHaveLength(2)
    expect(toastCalls).toHaveLength(0)
  })

  it('retries a transport error on GET', async () => {
    const attempts = stubAdapter([
      { code: 'ECONNRESET', message: 'socket hang up' },
      { status: 200, data: { ok: true } },
    ])
    await api.get('/progress/')
    expect(attempts).toHaveLength(2)
  })

  it('gives up after RETRY_MAX attempts and surfaces the error', async () => {
    const attempts = stubAdapter([{ status: 503 }])
    await expect(api.get('/progress/')).rejects.toMatchObject({ response: { status: 503 } })
    // 1 initial + 2 retries
    expect(attempts).toHaveLength(3)
  })

  it('does NOT retry a POST — replaying lab start would double-provision', async () => {
    const attempts = stubAdapter([{ status: 503 }])
    await expect(api.post('/labs/7/start/', {})).rejects.toBeTruthy()
    expect(attempts).toHaveLength(1)
  })

  it('does NOT retry a 500 — an application crash will just crash again', async () => {
    const attempts = stubAdapter([{ status: 500 }])
    await expect(api.get('/progress/')).rejects.toBeTruthy()
    expect(attempts).toHaveLength(1)
  })

  it('does NOT retry a 429 — that would amplify the rate limit', async () => {
    const attempts = stubAdapter([{ status: 429 }])
    await expect(api.get('/progress/')).rejects.toBeTruthy()
    expect(attempts).toHaveLength(1)
  })

  it('does NOT retry a 404', async () => {
    const attempts = stubAdapter([{ status: 404 }])
    await expect(api.get('/progress/')).rejects.toBeTruthy()
    expect(attempts).toHaveLength(1)
  })

  it('honors noRetry opt-out', async () => {
    const attempts = stubAdapter([{ status: 503 }])
    await expect(api.get('/progress/', { noRetry: true })).rejects.toBeTruthy()
    expect(attempts).toHaveLength(1)
  })
})

describe('per-call timeout budgets', () => {
  it('keeps the 45s provisioning default on the shared instance', () => {
    // Lowering this would abort slow lab provisioning mid-flight.
    expect(api.defaults.timeout).toBe(45_000)
    expect(TIMEOUTS.provision).toBe(45_000)
  })

  it('exposes tighter budgets that callers can opt into', () => {
    expect(TIMEOUTS.read).toBeLessThan(TIMEOUTS.provision)
    expect(TIMEOUTS.long).toBeGreaterThan(TIMEOUTS.provision)
  })

  it('lets a per-call timeout override the default', async () => {
    const attempts = stubAdapter([{ status: 200, data: {} }])
    await api.get('/progress/', { timeout: TIMEOUTS.read })
    expect(attempts[0].timeout).toBe(TIMEOUTS.read)
  })
})

describe('centralized 403 handling', () => {
  it('toasts a subscription message on a plain GET 403', async () => {
    stubAdapter([{ status: 403, data: { code: 'SUBSCRIPTION_REQUIRED' } }])
    await expect(api.get('/vmware/sessions/1/')).rejects.toBeTruthy()
    expect(toastCalls).toHaveLength(1)
    expect(toastCalls[0].msg).toMatch(/subscription/i)
    expect(toastCalls[0].opts.id).toBe('forbidden')
  })

  it('toasts a neutral message for a non-subscription 403', async () => {
    stubAdapter([{ status: 403, data: {} }])
    await expect(api.get('/org/teams/9/')).rejects.toBeTruthy()
    expect(toastCalls[0].msg).toMatch(/do not have access/i)
  })

  it('stays silent on silentError — the soft-open demo fallback path', async () => {
    // vmware/monitoring/nmap/wireshark all pass silentError on these calls and
    // handle 403 themselves; a toast here would break the paywall/demo flows.
    stubAdapter([{ status: 403, data: { code: 'SUBSCRIPTION_REQUIRED' } }])
    await expect(api.get('/vmware/sessions/1/', { silentError: true })).rejects.toBeTruthy()
    expect(toastCalls).toHaveLength(0)
  })

  it('stays silent on a write 403 — those call sites render their own message', async () => {
    stubAdapter([{ status: 403, data: { error: 'Subscribe to this technology' } }])
    await expect(api.post('/labs/7/start/', {})).rejects.toBeTruthy()
    expect(toastCalls).toHaveLength(0)
  })

  it('stays silent for admin polling', async () => {
    stubAdapter([{ status: 403, data: {} }])
    await expect(api.get('/admin/metrics/')).rejects.toBeTruthy()
    expect(toastCalls).toHaveLength(0)
  })

  it('does not redirect to login on 403', async () => {
    window.location.href = '/dashboard'
    stubAdapter([{ status: 403, data: {} }])
    await expect(api.get('/org/teams/9/')).rejects.toBeTruthy()
    expect(window.location.href).toBe('/dashboard')
  })
})
