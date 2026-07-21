import api from './client'

const base = (sessionId) => `/vmware/terraform/sessions/${sessionId}`

export const terraformApi = {
  getState(sessionId, scenarioSlug = '') {
    const q = scenarioSlug ? `?scenario=${encodeURIComponent(scenarioSlug)}` : ''
    return api.get(`${base(sessionId)}${q}`, { silentError: true }).then((r) => r.data)
  },
  action(sessionId, action, payload = {}) {
    return api.post(`${base(sessionId)}/action/`, { action, payload }).then((r) => r.data)
  },
  createWorkspace(sessionId, name, project = 'Training') {
    return terraformApi.action(sessionId, 'tfc_create_workspace', { name, project })
  },
  queueRun(sessionId, workspace, apply = false) {
    return terraformApi.action(sessionId, 'tfc_queue_run', { workspace, apply })
  },
  applyRun(sessionId, runId) {
    return terraformApi.action(sessionId, 'tfc_apply_run', { run_id: runId })
  },
  lockWorkspace(sessionId, workspace, locked = true) {
    return terraformApi.action(sessionId, 'tfc_lock_workspace', { workspace, locked })
  },
  setVariable(sessionId, payload = {}) {
    return terraformApi.action(sessionId, 'tfc_set_variable', payload)
  },
  createAgentPool(sessionId, name, agents = 1) {
    return terraformApi.action(sessionId, 'tfc_create_agent_pool', { name, agents })
  },
  createTeam(sessionId, name, access = 'write', members = 1) {
    return terraformApi.action(sessionId, 'tfc_create_team', { name, access, members })
  },
  setTeamAccess(sessionId, { team, workspace = 'lab-workspace', permission = 'Write', inherited = false } = {}) {
    return terraformApi.action(sessionId, 'tfc_set_team_access', { team, workspace, permission, inherited })
  },
  createWsNotification(sessionId, { name, workspace = 'lab-workspace', triggers = 'Errored runs' } = {}) {
    return terraformApi.action(sessionId, 'tfc_create_ws_notification', { name, workspace, triggers })
  },
  updateOrgSetting(sessionId, section, key, value) {
    return terraformApi.action(sessionId, 'tfc_update_org_setting', { section, key, value })
  },
}
