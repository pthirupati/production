// Browser-side crash reporting (audit Z6-6).
//
// The error boundaries reported to `console.error` — a console nobody reads — so a
// white screen in production was invisible until a user wrote in. This posts to our
// own origin, where Django logs it into the pipeline `SENTRY_DSN` already feeds.
//
// Deliberately no `@sentry/react`: the SDK would give source maps and replay, but it
// is a browser-side third-party processor receiving user data, which needs a DPDP
// consent decision and a privacy-policy change (the processor list was only just
// enumerated in Z4-6). That is the owner's call. This reaches the same dashboard
// with no new vendor and no new dependency.
//
// Everything below is written on the assumption that this runs *while the app is
// already broken*: it must never throw, never block, and never loop.

const ENDPOINT = '/api/client-errors/'

// A crash inside a render loop can fire hundreds of times a second. Reporting each
// one would DoS our own log pipeline with a single tab.
const MAX_REPORTS_PER_SESSION = 10
const DEDUPE_WINDOW_MS = 10_000

let sent = 0
const recent = new Map()

function isDuplicate(signature) {
  const now = Date.now()
  for (const [key, at] of recent) {
    if (now - at > DEDUPE_WINDOW_MS) recent.delete(key)
  }
  if (recent.has(signature)) return true
  recent.set(signature, now)
  return false
}

export function reportClientError(error, { componentStack = '', kind = 'react_error_boundary' } = {}) {
  try {
    if (sent >= MAX_REPORTS_PER_SESSION) return

    const message = String(error?.message || error || 'unknown error').slice(0, 500)
    if (!message) return
    if (isDuplicate(`${kind}:${message}`)) return
    sent += 1

    const body = JSON.stringify({
      message,
      stack: String(error?.stack || '').slice(0, 2000),
      component_stack: String(componentStack || '').slice(0, 2000),
      // Pathname only. Query strings on this platform carry password-reset and
      // payment tokens, and a crash report is not a place to put either.
      route: window.location?.pathname || '',
      release: import.meta.env?.VITE_RELEASE || '',
      kind,
    })

    // sendBeacon survives the page being torn down, which is exactly when a crash
    // report is most likely to be lost. fetch with keepalive is the fallback.
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }))
      return
    }
    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
      credentials: 'same-origin',
    }).catch(() => {})
  } catch {
    // Reporting an error must never become the error. Swallowing here is the point.
  }
}

// Errors that escape React entirely — event handlers, async callbacks, and promise
// rejections — never reach an error boundary, so they were the larger blind spot.
export function installGlobalErrorReporting() {
  if (typeof window === 'undefined' || window.__fixitlabErrorReporting) return
  window.__fixitlabErrorReporting = true

  window.addEventListener('error', (event) => {
    reportClientError(event?.error || event?.message, { kind: 'window_error' })
  })
  window.addEventListener('unhandledrejection', (event) => {
    reportClientError(event?.reason, { kind: 'unhandled_rejection' })
  })
}
