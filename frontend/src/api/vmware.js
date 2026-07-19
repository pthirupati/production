import api from './client'

function isSubscriptionDenied(err) {
  const code = err?.response?.data?.code
  return err?.response?.status === 403 && (
    code === 'SUBSCRIPTION_REQUIRED' || code === 'SUBSCRIPTION_EXPIRED'
  )
}

/**
 * Session-scoped VMware console with a careful demo fallback.
 *
 * Cross-tech Linux labs use /vmware/:sessionId — those must NEVER fall back to
 * the standalone demo on 403, or a Linux-only subscriber could open a full
 * VMware inventory without a VMware subscription (revenue breach).
 *
 * Demo fallback is only for expired/missing sessions (404/400) when the user
 * is already on a path that can open the standalone console.
 */
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
    if (isSubscriptionDenied(err)) throw err
    const status = err?.response?.status
    if (status === 404 || status === 400) {
      try {
        const { data } = await api.get('/vmware/demo/', { params, silentError: true })
        return data
      } catch (demoErr) {
        if (isSubscriptionDenied(demoErr)) throw demoErr
        throw err
      }
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
    if (isSubscriptionDenied(err)) throw err
    const status = err?.response?.status
    if (status === 404 || status === 400) {
      try {
        const { data } = await api.post('/vmware/demo/action/', { action, payload }, { silentError: true })
        return data
      } catch (demoErr) {
        if (isSubscriptionDenied(demoErr)) throw demoErr
        throw err
      }
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
