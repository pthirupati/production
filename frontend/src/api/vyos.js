import api from './client'

const base = (sessionId) => `/vmware/vyos/sessions/${sessionId}`

export const vyosApi = {
  getState(sessionId, scenarioSlug = '') {
    const q = scenarioSlug ? `?scenario=${encodeURIComponent(scenarioSlug)}` : ''
    return api.get(`${base(sessionId)}${q}`, { silentError: true }).then((r) => r.data)
  },
  action(sessionId, action, payload = {}) {
    return api.post(`${base(sessionId)}/action/`, { action, payload }).then((r) => r.data)
  },
  applyCli(sessionId, line) {
    return vyosApi.action(sessionId, 'cli', { line })
  },
  release(sessionId) {
    return api.post(`${base(sessionId)}/release/`).then((r) => r.data)
  },
}
