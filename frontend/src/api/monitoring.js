import api from './client'

// Mirrors api/vmware.js: a session-scoped call that transparently falls back to
// the per-user demo sandbox so the Grafana/Prometheus simulator ALWAYS loads
// (expired session, non-monitoring lab, or a reloaded standalone URL).
async function getStateWithFallback(sessionId, scenario) {
  const params = scenario ? { scenario } : undefined
  if (!sessionId) {
    const { data } = await api.get('/vmware/monitoring/demo/', { params, silentError: true })
    return data
  }
  try {
    const { data } = await api.get(`/vmware/monitoring/sessions/${sessionId}/`, { params, silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.get('/vmware/monitoring/demo/', { params, silentError: true })
      return data
    }
    throw err
  }
}

async function actionWithFallback(sessionId, action, payload) {
  if (!sessionId) {
    const { data } = await api.post('/vmware/monitoring/demo/action/', { action, payload }, { silentError: true })
    return data
  }
  try {
    const { data } = await api.post(`/vmware/monitoring/sessions/${sessionId}/action/`, { action, payload }, { silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.post('/vmware/monitoring/demo/action/', { action, payload }, { silentError: true })
      return data
    }
    throw err
  }
}

export const monitoringApi = {
  getState: (sessionId, scenario = '') => getStateWithFallback(sessionId, scenario),
  action: (sessionId, action, payload = {}) => actionWithFallback(sessionId, action, payload),
  query: (sessionId, expr) => actionWithFallback(sessionId, 'query', { expr }),
  createPlaylist: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_playlist', payload),
  createSnapshot: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_snapshot', payload),
  createLibraryPanel: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_library_panel', payload),
  createFolder: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_folder', payload),
  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/monitoring/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
