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
  toggleSchedule(sessionId, scheduleId) {
    return awxApi.action(sessionId, 'toggle_schedule', { schedule_id: scheduleId })
  },
  deleteSchedule(sessionId, scheduleId) {
    return awxApi.action(sessionId, 'delete_schedule', { schedule_id: scheduleId })
  },
  relaunchJob(sessionId, jobId) {
    return awxApi.action(sessionId, 'relaunch_job', { job_id: jobId })
  },
  cancelJob(sessionId, jobId) {
    return awxApi.action(sessionId, 'cancel_job', { job_id: jobId })
  },
  toggleHost(sessionId, hostId) {
    return awxApi.action(sessionId, 'toggle_host', { host_id: hostId })
  },
  installAwx(sessionId) {
    return awxApi.action(sessionId, 'install_awx', {})
  },
  createWorkflowTemplate(sessionId, name) {
    return awxApi.action(sessionId, 'create_workflow_template', { name })
  },
  launchWorkflow(sessionId, workflowId) {
    return awxApi.action(sessionId, 'launch_workflow', { workflow_id: workflowId })
  },
  approveWorkflow(sessionId, id, approve = true) {
    return awxApi.action(sessionId, 'approve_workflow', { id, approve })
  },
  createNotification(sessionId, payload = {}) {
    return awxApi.action(sessionId, 'create_notification', payload)
  },
  createExecutionEnvironment(sessionId, payload = {}) {
    return awxApi.action(sessionId, 'create_execution_environment', payload)
  },
}
