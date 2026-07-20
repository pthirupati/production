import api from './client'

// Thin client for the server-authoritative Commvault CommCell engine
// (backend apps/vmware_sim/commvault_engine.py, routes under /vmware/commvault/...).
const base = (sessionId) => `/vmware/commvault/sessions/${sessionId}`

export const commvaultApi = {
  getState(sessionId, scenarioSlug = '') {
    const q = scenarioSlug ? `?scenario=${encodeURIComponent(scenarioSlug)}` : ''
    return api.get(`${base(sessionId)}${q}`, { silentError: true }).then((r) => r.data)
  },
  action(sessionId, action, payload = {}) {
    return api.post(`${base(sessionId)}/action/`, { action, payload }).then((r) => r.data)
  },
  release(sessionId) {
    return api.post(`${base(sessionId)}/release/`, {}).then((r) => r.data)
  },
  login(sessionId) {
    return commvaultApi.action(sessionId, 'login', { user: 'admin' })
  },
  runBackup(sessionId, client, type = 'Full') {
    return commvaultApi.action(sessionId, 'run_backup', { client, type })
  },
  runRestore(sessionId, client) {
    return commvaultApi.action(sessionId, 'run_restore', { client })
  },
  createSubclient(sessionId, client, name, policy, content) {
    return commvaultApi.action(sessionId, 'create_subclient', { client, name, policy, content })
  },
  addClient(sessionId, name, os, ip) {
    return commvaultApi.action(sessionId, 'add_client', { name, os, ip })
  },
  enablePolicy(sessionId, name) {
    return commvaultApi.action(sessionId, 'enable_policy', { name })
  },
  setRetention(sessionId, name, retentionDays) {
    return commvaultApi.action(sessionId, 'set_retention', { name, retention_days: retentionDays })
  },
  killJob(sessionId, jobId) {
    return commvaultApi.action(sessionId, 'kill_job', { job_id: jobId })
  },
  enableSchedule(sessionId, name) {
    return commvaultApi.action(sessionId, 'enable_schedule', { name })
  },
  createSchedule(sessionId, payload) {
    return commvaultApi.action(sessionId, 'create_schedule', payload)
  },
  runAuxCopy(sessionId, name) {
    return commvaultApi.action(sessionId, 'run_aux_copy', { name })
  },
  addMediaAgent(sessionId, name, os = 'Linux') {
    return commvaultApi.action(sessionId, 'add_media_agent', { name, os })
  },
  createLibrary(sessionId, name, type = 'Disk', capacityGb = 1000) {
    return commvaultApi.action(sessionId, 'create_library', { name, type, capacity_gb: capacityGb })
  },
}

export default commvaultApi
