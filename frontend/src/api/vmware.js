import api from './client'

export const vmwareApi = {
  getState: (sessionId, scenario = '') => api.get(`/vmware/sessions/${sessionId}/`, { params: scenario ? { scenario } : undefined }).then(r => r.data),
  action: (sessionId, action, payload = {}) =>
    api.post(`/vmware/sessions/${sessionId}/action/`, { action, payload }).then(r => r.data),
  release: (sessionId) => api.post(`/vmware/sessions/${sessionId}/release/`).then(r => r.data),
}
