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
  dropSession(sessionId) {
    return api.post(`${base(sessionId)}/release/`, {}).then((r) => r.data)
  },
}

export default awsSimApi
