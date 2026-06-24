import api from './client'

const base = (sessionId) => `/vmware/awx/sessions/${sessionId}`

export const awxApi = {
  getState(sessionId, scenarioSlug = '') {
    const q = scenarioSlug ? `?scenario=${encodeURIComponent(scenarioSlug)}` : ''
    return api.get(`${base(sessionId)}${q}`, { silentError: true }).then((r) => r.data)
  },
  action(sessionId, action, payload = {}) {
    return api.post(`${base(sessionId)}/action/`, { action, payload }).then((r) => r.data)
  },
  login(sessionId) {
    return awxApi.action(sessionId, 'login', { user: 'admin' })
  },
  syncProject(sessionId, projectId) {
    return awxApi.action(sessionId, 'sync_project', { project_id: projectId })
  },
  launchTemplate(sessionId, templateId) {
    return awxApi.action(sessionId, 'launch_template', { template_id: templateId })
  },
  createTemplate(sessionId, name) {
    return awxApi.action(sessionId, 'create_template', { name })
  },
  attachCredential(sessionId) {
    return awxApi.action(sessionId, 'attach_credential', {})
  },
  createCredential(sessionId, name, kind) {
    return awxApi.action(sessionId, 'create_credential', { name, kind })
  },
  createProject(sessionId, name) {
    return awxApi.action(sessionId, 'create_project', { name })
  },
  createInventory(sessionId, name) {
    return awxApi.action(sessionId, 'create_inventory', { name })
  },
  createSchedule(sessionId, name, template) {
    return awxApi.action(sessionId, 'create_schedule', { name, template })
  },
  installAwx(sessionId) {
    return awxApi.action(sessionId, 'install_awx', {})
  },
}
