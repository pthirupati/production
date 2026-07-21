import api from './client'

const base = (sessionId) => `/vmware/cicd/sessions/${sessionId}`

export const cicdApi = {
  getState(sessionId, scenarioSlug = '') {
    const q = scenarioSlug ? `?scenario=${encodeURIComponent(scenarioSlug)}` : ''
    return api.get(`${base(sessionId)}${q}`, { silentError: true }).then((r) => r.data)
  },
  action(sessionId, action, payload = {}) {
    return api.post(`${base(sessionId)}/action/`, { action, payload }, { silentError: true }).then((r) => r.data)
  },
  release(sessionId) {
    return api.post(`${base(sessionId)}/release/`, {}, { silentError: true }).then((r) => r.data)
  },
  setImage(sessionId, job, image) {
    return cicdApi.action(sessionId, 'set_image', { job, image })
  },
  approveJob(sessionId, job) {
    return cicdApi.action(sessionId, 'approve_job', { job })
  },
  fixJob(sessionId, job, script) {
    return cicdApi.action(sessionId, 'fix_job', { job, script })
  },
  runPipeline(sessionId) {
    return cicdApi.action(sessionId, 'run_pipeline', {})
  },
  argoSync(sessionId, name) {
    return cicdApi.action(sessionId, 'argo_sync', { name })
  },
  fluxReconcile(sessionId, name) {
    return cicdApi.action(sessionId, 'flux_reconcile', { name })
  },
}

export default cicdApi
