import api from './client'

// AI / ML AGENT-WORKFLOW simulator client. Mirrors api/datascience.js +
// api/nmap.js: session-scoped calls (agent labs always carry a RUNNING
// LabSession). The backend never 500s — a missing/expired/unauthorized session
// returns {ok:false} so the simulator UI degrades gracefully instead of throwing.
// The vmware_sim app owns the engine, so the routes are mounted under
// /api/vmware/aiml/.
async function getStateReq(sessionId, scenario) {
  if (!sessionId) return null
  const params = scenario ? { scenario } : undefined
  const { data } = await api.get(`/vmware/aiml/sessions/${sessionId}/`, { params, silentError: true })
  return data
}

async function actionReq(sessionId, actionName, payload = {}) {
  if (!sessionId) return { ok: false, error: 'No active session' }
  try {
    const { data } = await api.post(
      `/vmware/aiml/sessions/${sessionId}/action/`,
      { action: actionName, payload },
      { silentError: true },
    )
    return data
  } catch (err) {
    // The backend returns 400 with {ok:false,...} for rejected actions; surface
    // that body to the UI rather than throwing so a bad config never crashes.
    const body = err?.response?.data
    if (body && typeof body === 'object') return { ok: false, ...body }
    return { ok: false, error: err?.message || 'Action failed' }
  }
}

export const aimlApi = {
  getState: (sessionId, scenario = '') => getStateReq(sessionId, scenario),
  action: (sessionId, actionName, payload = {}) => actionReq(sessionId, actionName, payload),

  // ── Convenience wrappers for the graph mutations the UI fires most ──
  addNode: (sessionId, type, config = {}, extra = {}) =>
    actionReq(sessionId, 'add_node', { type, config, ...extra }),
  removeNode: (sessionId, id) => actionReq(sessionId, 'remove_node', { id }),
  connect: (sessionId, from, to, branch) =>
    actionReq(sessionId, 'connect', branch ? { from, to, branch } : { from, to }),
  disconnect: (sessionId, from, to, branch) =>
    actionReq(sessionId, 'disconnect', branch ? { from, to, branch } : { from, to }),
  configureNode: (sessionId, id, config, merge = true) =>
    actionReq(sessionId, 'configure_node', { id, config, merge }),
  setTriggerInput: (sessionId, id, input) =>
    actionReq(sessionId, 'set_trigger_input', id ? { id, input } : { input }),
  runWorkflow: (sessionId) => actionReq(sessionId, 'run_workflow', {}),
  reset: (sessionId) => actionReq(sessionId, 'reset', {}),

  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/aiml/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
