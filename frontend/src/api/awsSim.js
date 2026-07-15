import api from './client'

// Thin client for the server-authoritative AWS console engine
// (backend apps/vmware_sim/aws_engine.py, routes under /vmware/aws/...).
const base = (sessionId) => `/vmware/aws/sessions/${sessionId}`

export const awsSimApi = {
  getState(sessionId, scenarioSlug = '') {
    const q = scenarioSlug ? `?scenario=${encodeURIComponent(scenarioSlug)}` : ''
    return api.get(`${base(sessionId)}${q}`, { silentError: true }).then((r) => r.data)
  },
  applyAction(sessionId, action, payload = {}) {
    return api.post(`${base(sessionId)}/action/`, { action, payload }).then((r) => r.data)
  },
  // Fire-and-forget variant used to mirror GUI clicks into the server-side
  // action log for grading. Never surfaces a toast and never rejects the
  // caller: an offline / failed sync must not break the (already-applied)
  // optimistic UI. Resolves to the server result or null on failure.
  syncAction(sessionId, action, payload = {}) {
    if (!sessionId || !action) return Promise.resolve(null)
    return api
      .post(`${base(sessionId)}/action/`, { action, payload }, { silentError: true })
      .then((r) => r.data)
      .catch(() => null)
  },
  dropSession(sessionId) {
    return api.post(`${base(sessionId)}/release/`, {}).then((r) => r.data)
  },
}

export default awsSimApi
