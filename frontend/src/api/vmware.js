import api from './client'

export const vmwareApi = {
  getState: (sessionId, scenario = '') => {
    if (!sessionId) {
      return api.get('/vmware/demo/', { params: scenario ? { scenario } : undefined, silentError: true }).then(r => r.data)
    }
    return api.get(`/vmware/sessions/${sessionId}/`, { params: scenario ? { scenario } : undefined, silentError: true }).then(r => r.data)
  },
  action: (sessionId, action, payload = {}) => {
    if (!sessionId) {
      return api.post('/vmware/demo/action/', { action, payload }, { silentError: true }).then(r => r.data)
    }
    return api.post(`/vmware/sessions/${sessionId}/action/`, { action, payload }, { silentError: true }).then(r => r.data)
  },
  release: (sessionId) => {
    if (!sessionId) {
      return Promise.resolve({ released: true })
    }
    return api.post(`/vmware/sessions/${sessionId}/release/`, {}, { silentError: true }).then(r => r.data)
  },
}
