import api from './client'

export const vmwareApi = {
  getState: (sessionId) => api.get(`/vmware/sessions/${sessionId}/`).then(r => r.data),
  action: (sessionId, action, payload = {}) =>
    api.post(`/vmware/sessions/${sessionId}/action/`, { action, payload }).then(r => r.data),
  release: (sessionId) => api.post(`/vmware/sessions/${sessionId}/release/`).then(r => r.data),
}
