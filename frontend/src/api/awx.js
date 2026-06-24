import api from './client'

const base = (sessionId) => `/vmware-sim/awx/sessions/${sessionId}`

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
}
