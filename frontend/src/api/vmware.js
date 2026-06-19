import api from './client'

// When a session-scoped call fails (e.g. the lab session expired, was never a
// VMware lab, or the user reloaded the standalone simulator URL) we transparently
// fall back to the per-user demo sandbox so the simulator ALWAYS loads instead of
// dead-ending on "Could not load VMware simulator".
async function getStateWithFallback(sessionId, scenario) {
  const params = scenario ? { scenario } : undefined
  if (!sessionId) {
    const { data } = await api.get('/vmware/demo/', { params, silentError: true })
    return data
  }
  try {
    const { data } = await api.get(`/vmware/sessions/${sessionId}/`, { params, silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    // Session missing / not running / forbidden → use the demo sandbox so the
    // user still gets a fully interactive simulator for this scenario.
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.get('/vmware/demo/', { params, silentError: true })
      return data
    }
    throw err
  }
}

async function actionWithFallback(sessionId, action, payload) {
  if (!sessionId) {
    const { data } = await api.post('/vmware/demo/action/', { action, payload }, { silentError: true })
    return data
  }
  try {
    const { data } = await api.post(`/vmware/sessions/${sessionId}/action/`, { action, payload }, { silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.post('/vmware/demo/action/', { action, payload }, { silentError: true })
      return data
    }
    throw err
  }
}

export const vmwareApi = {
  getState: (sessionId, scenario = '') => getStateWithFallback(sessionId, scenario),
  action: (sessionId, action, payload = {}) => actionWithFallback(sessionId, action, payload),
  release: (sessionId) => {
    if (!sessionId) {
      return Promise.resolve({ released: true })
    }
    return api.post(`/vmware/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
