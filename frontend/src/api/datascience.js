import api from './client'

// Data Science / Analytics DASHBOARD simulator client. Mirrors api/nmap.js but
// session-scoped only (no demo sandbox): dashboard labs always carry a RUNNING
// LabSession, and the backend never 500s — a missing/expired session returns
// {ok:false}. The vmware_sim app owns the engine, so the routes are mounted under
// /api/vmware/datascience/.
async function getStateReq(sessionId, scenario) {
  if (!sessionId) return null
  const params = scenario ? { scenario } : undefined
  const { data } = await api.get(`/vmware/datascience/sessions/${sessionId}/`, { params, silentError: true })
  return data
}

async function actionReq(sessionId, actionName, payload = {}) {
  if (!sessionId) return { ok: false, error: 'No active session' }
  const { data } = await api.post(
    `/vmware/datascience/sessions/${sessionId}/action/`,
    { action: actionName, payload },
    { silentError: true },
  )
  return data
}

export const datascienceApi = {
  getState: (sessionId, scenario = '') => getStateReq(sessionId, scenario),
  action: (sessionId, actionName, payload = {}) => actionReq(sessionId, actionName, payload),
  // Convenience wrappers for the builder actions the UI fires most.
  setDimension: (sessionId, column) => actionReq(sessionId, 'set_dimension', { column }),
  setMeasure: (sessionId, column) => actionReq(sessionId, 'set_measure', { column }),
  setAggregation: (sessionId, aggregation) => actionReq(sessionId, 'set_aggregation', { aggregation }),
  setFilter: (sessionId, column, value) => actionReq(sessionId, 'set_filter', { column, value }),
  setChartType: (sessionId, chartType) => actionReq(sessionId, 'set_chart_type', { chart_type: chartType }),
  reset: (sessionId) => actionReq(sessionId, 'reset', {}),
  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/datascience/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
