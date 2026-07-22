import api from './client'

function isSubscriptionDenied(err) {
  const code = err?.response?.data?.code
  return err?.response?.status === 403 && (
    code === 'SUBSCRIPTION_REQUIRED' || code === 'SUBSCRIPTION_EXPIRED'
  )
}

/**
 * Session-scoped monitoring console with careful demo fallback.
 *
 * Never fall back to the demo on SUBSCRIPTION_REQUIRED — that would let a
 * non-monitoring subscriber open Grafana/Prometheus via a 403 soft-open
 * (same class of revenue breach as the VMware demo fallback).
 *
 * Demo fallback is only for expired/missing sessions (404/400).
 */
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
    if (isSubscriptionDenied(err)) throw err
    const status = err?.response?.status
    if (status === 404 || status === 400) {
      try {
        const { data } = await api.get('/vmware/monitoring/demo/', { params, silentError: true })
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
    const { data } = await api.post('/vmware/monitoring/demo/action/', { action, payload }, { silentError: true })
    return data
  }
  try {
    const { data } = await api.post(`/vmware/monitoring/sessions/${sessionId}/action/`, { action, payload }, { silentError: true })
    return data
  } catch (err) {
    if (isSubscriptionDenied(err)) throw err
    const status = err?.response?.status
    if (status === 404 || status === 400) {
      try {
        const { data } = await api.post('/vmware/monitoring/demo/action/', { action, payload }, { silentError: true })
        return data
      } catch (demoErr) {
        if (isSubscriptionDenied(demoErr)) throw demoErr
        throw err
      }
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
  createGrafanaUser: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_grafana_user', payload),
  createGrafanaTeam: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_grafana_team', payload),
  createServiceAccount: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_service_account', payload),
  createGrafanaAlertRule: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_grafana_alert_rule', payload),
  createContactPoint: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_contact_point', payload),
  pushgatewayPush: (sessionId, payload = {}) => actionWithFallback(sessionId, 'pushgateway_push', payload),
  blackboxProbe: (sessionId, payload = {}) => actionWithFallback(sessionId, 'blackbox_probe', payload),
  createSilence: (sessionId, payload = {}) => actionWithFallback(sessionId, 'create_silence', payload),
  expireSilence: (sessionId, id) => actionWithFallback(sessionId, 'expire_silence', { id }),
  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/monitoring/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
