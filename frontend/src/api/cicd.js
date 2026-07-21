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
  argoCreateApp(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'argo_create_app', payload)
  },
  fluxReconcile(sessionId, name) {
    return cicdApi.action(sessionId, 'flux_reconcile', { name })
  },
  fluxSuspend(sessionId, name, suspended = true, kind = 'kustomization') {
    return cicdApi.action(sessionId, 'flux_suspend', { name, suspended, kind })
  },
  fluxHelmReconcile(sessionId, name) {
    return cicdApi.action(sessionId, 'flux_helm_reconcile', { name })
  },
  fluxCreateKustomization(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'flux_create_kustomization', payload)
  },
  fluxCreateHelmRelease(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'flux_create_helmrelease', payload)
  },
  githubCreateIssue(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'github_create_issue', payload)
  },
  githubCloseIssue(sessionId, number) {
    return cicdApi.action(sessionId, 'github_close_issue', { number })
  },
  githubCreatePr(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'github_create_pr', payload)
  },
  githubMergePr(sessionId, number) {
    return cicdApi.action(sessionId, 'github_merge_pr', { number })
  },
  githubApprovePr(sessionId, number) {
    return cicdApi.action(sessionId, 'github_approve_pr', { number })
  },
  githubRerunWorkflow(sessionId, runId) {
    return cicdApi.action(sessionId, 'github_rerun_workflow', { run_id: runId })
  },
  upsertSecret(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'upsert_secret', payload)
  },
  deleteSecret(sessionId, name) {
    return cicdApi.action(sessionId, 'delete_secret', { name })
  },
  upsertVariable(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'upsert_variable', payload)
  },
  deleteVariable(sessionId, name) {
    return cicdApi.action(sessionId, 'delete_variable', { name })
  },
  upsertEnvironment(sessionId, payload = {}) {
    return cicdApi.action(sessionId, 'upsert_environment', payload)
  },
  clearEnvironmentDeployment(sessionId, name) {
    return cicdApi.action(sessionId, 'clear_environment_deployment', { name })
  },
}

export default cicdApi
