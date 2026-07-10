/**
 * Cross-tab lab lifecycle sync — stop/expiry/completion broadcasts and child-tab cleanup.
 */

const CHILD_TABS_KEY = 'fixitlab.lab.childTabs'

function channelName(sessionId) {
  return `fixitlab_lab_sync_${sessionId || 'global'}`
}

/** Register this window as a lab child tab (e.g. VMware opened from LabRunner). */
export function registerLabChildTab(sessionId, label = 'lab-child') {
  if (!sessionId || typeof window === 'undefined') return
  try {
    const raw = sessionStorage.getItem(CHILD_TABS_KEY)
    const map = raw ? JSON.parse(raw) : {}
    const list = map[sessionId] || []
    list.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, label, ts: Date.now() })
    map[sessionId] = list.slice(-20)
    sessionStorage.setItem(CHILD_TABS_KEY, JSON.stringify(map))
  } catch { /* storage unavailable */ }
  if (typeof BroadcastChannel !== 'undefined') {
    try {
      const ch = new BroadcastChannel(channelName(sessionId))
      ch.postMessage({ type: 'lab_child_opened', sessionId, label })
      ch.close()
    } catch { /* */ }
  }
}

/** Broadcast user activity from child tabs (VMware, etc.) to reset parent idle timer. */
export function broadcastLabActivity(sessionId) {
  if (!sessionId || typeof BroadcastChannel === 'undefined') return
  try {
    const ch = new BroadcastChannel(channelName(sessionId))
    ch.postMessage({ type: 'lab_activity', sessionId, ts: Date.now() })
    ch.close()
  } catch { /* */ }
}

/** Broadcast lab stopped/expired/completed to all tabs for this session. */
export function broadcastLabStopped(sessionId, reason = 'stopped', extra = {}) {
  if (!sessionId || typeof BroadcastChannel === 'undefined') return
  try {
    const ch = new BroadcastChannel(channelName(sessionId))
    ch.postMessage({ type: 'lab_stopped', sessionId, reason, ...extra })
    ch.close()
  } catch { /* */ }
}

/** Subscribe to lab lifecycle events for a session. Returns unsubscribe fn. */
export function subscribeLabSync(sessionId, handler) {
  if (!sessionId || typeof BroadcastChannel === 'undefined') return () => {}
  const ch = new BroadcastChannel(channelName(sessionId))
  ch.onmessage = (event) => {
    const data = event.data || {}
    if (data.sessionId && data.sessionId !== sessionId) return
    handler(data)
  }
  return () => {
    try { ch.close() } catch { /* */ }
  }
}

/** Try to close child tabs and this window when lab ends (best-effort). */
export function closeLabChildTabs(sessionId) {
  if (typeof window === 'undefined') return
  if (typeof BroadcastChannel !== 'undefined' && sessionId) {
    try {
      const ch = new BroadcastChannel(channelName(sessionId))
      ch.postMessage({ type: 'lab_force_close', sessionId })
      ch.close()
    } catch { /* */ }
  }
  try {
    const raw = sessionStorage.getItem(CHILD_TABS_KEY)
    if (raw && sessionId) {
      const map = JSON.parse(raw)
      delete map[sessionId]
      sessionStorage.setItem(CHILD_TABS_KEY, JSON.stringify(map))
    }
  } catch { /* */ }
}

/** Handle force-close in child tabs (VMware, etc.). Returns true if this tab should exit. */
export function handleLabForceClose(data, sessionId, { onClose } = {}) {
  if (!data || data.sessionId !== sessionId) return false
  if (data.type === 'lab_stopped' || data.type === 'lab_force_close') {
    if (typeof onClose === 'function') onClose(data)
    return true
  }
  return false
}
