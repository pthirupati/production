import api from './client'

// Thin client for the server-authoritative SOC / SIEM engine
// (backend apps/vmware_sim/soc_engine.py, routes under /vmware/soc/...).
const base = (sessionId) => `/vmware/soc/sessions/${sessionId}`

export const socApi = {
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
    return socApi.action(sessionId, 'login', { user: 'analyst' })
  },
  acknowledgeAlert(sessionId, alertId) {
    return socApi.action(sessionId, 'acknowledge_alert', { alert_id: alertId })
  },
  escalateIncident(sessionId, alertId) {
    return socApi.action(sessionId, 'escalate_incident', { alert_id: alertId })
  },
  runPlaybook(sessionId, playbookId) {
    return socApi.action(sessionId, 'run_playbook', { playbook_id: playbookId })
  },
  quarantineHost(sessionId, asset) {
    return socApi.action(sessionId, 'quarantine_host', { asset })
  },
  blockIp(sessionId, ip) {
    return socApi.action(sessionId, 'block_ip', { ip })
  },
  searchLogs(sessionId, query) {
    return socApi.action(sessionId, 'search_logs', { query })
  },
  closeIncident(sessionId, incidentId, alertId) {
    return socApi.action(sessionId, 'close_incident', { incident_id: incidentId, alert_id: alertId })
  },
}

export default socApi
