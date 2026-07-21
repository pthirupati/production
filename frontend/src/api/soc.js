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
  addIoc(sessionId, type, value, threat = 'custom') {
    return socApi.action(sessionId, 'add_ioc', { type, value, threat })
  },
  enableRule(sessionId, ruleId) {
    return socApi.action(sessionId, 'enable_rule', { rule_id: ruleId })
  },
  disableRule(sessionId, ruleId) {
    return socApi.action(sessionId, 'disable_rule', { rule_id: ruleId })
  },
  createDetectionRule(sessionId, payload = {}) {
    return socApi.action(sessionId, 'create_detection_rule', payload)
  },
  enrichAlert(sessionId, alertId) {
    return socApi.action(sessionId, 'enrich_alert', { alert_id: alertId })
  },
  unquarantineHost(sessionId, asset) {
    return socApi.action(sessionId, 'unquarantine_host', { asset })
  },
  createCase(sessionId, title, alertId) {
    return socApi.action(sessionId, 'create_case', { title, alert_id: alertId })
  },
  unblockIp(sessionId, ip) {
    return socApi.action(sessionId, 'unblock_ip', { ip })
  },
  startPamSession(sessionId, payload = {}) {
    return socApi.action(sessionId, 'start_pam_session', payload)
  },
  endPamSession(sessionId, id) {
    return socApi.action(sessionId, 'end_pam_session', { id })
  },
  scanAsset(sessionId, asset) {
    return socApi.action(sessionId, 'scan_asset', { asset })
  },
  markVulnFixed(sessionId, id) {
    return socApi.action(sessionId, 'mark_vuln_fixed', { id })
  },
  createFwRule(sessionId, payload = {}) {
    return socApi.action(sessionId, 'create_fw_rule', payload)
  },
  toggleFwRule(sessionId, id) {
    return socApi.action(sessionId, 'toggle_fw_rule', { id })
  },
  startPcap(sessionId, payload = {}) {
    return socApi.action(sessionId, 'start_pcap', payload)
  },
  stopPcap(sessionId, id) {
    return socApi.action(sessionId, 'stop_pcap', { id })
  },
  runComplianceCheck(sessionId) {
    return socApi.action(sessionId, 'run_compliance_check', {})
  },
}

export default socApi
