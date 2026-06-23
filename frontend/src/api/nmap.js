import api from './client'

// Mirrors api/vmware.js + api/monitoring.js: session-scoped calls that fall back
// transparently to a per-user demo sandbox so the Nmap simulator ALWAYS loads
// (expired session, non-nmap lab, or a reloaded standalone URL). The backend
// mounts nmap under /api/vmware/nmap/ (the vmware_sim app owns the engines).
async function getStateWithFallback(sessionId, scenario) {
  const params = scenario ? { scenario } : undefined
  if (!sessionId) {
    const { data } = await api.get('/vmware/nmap/demo/', { params, silentError: true })
    return data
  }
  try {
    const { data } = await api.get(`/vmware/nmap/sessions/${sessionId}/`, { params, silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.get('/vmware/nmap/demo/', { params, silentError: true })
      return data
    }
    throw err
  }
}

async function actionWithFallback(sessionId, action, payload) {
  if (!sessionId) {
    const { data } = await api.post('/vmware/nmap/demo/action/', { action, payload }, { silentError: true })
    return data
  }
  try {
    const { data } = await api.post(`/vmware/nmap/sessions/${sessionId}/action/`, { action, payload }, { silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.post('/vmware/nmap/demo/action/', { action, payload }, { silentError: true })
      return data
    }
    throw err
  }
}

export const nmapApi = {
  getState: (sessionId, scenario = '') => getStateWithFallback(sessionId, scenario),
  action: (sessionId, action, payload = {}) => actionWithFallback(sessionId, action, payload),
  // Convenience wrapper for the most common action.
  scan: (sessionId, payload) => actionWithFallback(sessionId, 'scan', payload),
  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/nmap/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
