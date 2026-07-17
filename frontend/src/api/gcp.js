import api from './client'

// Thin client for the server-authoritative Google Cloud Console engine
// (backend apps/vmware_sim/gcp_engine.py, routes under /vmware/gcp/...). The
// frontend never keeps its own copy of instance/firewall/disk state -- every
// action round-trips to the backend and the returned `state` is what gets
// rendered, so the console and the lab terminal can never drift out of sync.
const base = (sessionId) => `/vmware/gcp/sessions/${sessionId}`

export const gcpApi = {
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
    return gcpApi.action(sessionId, 'login', { user: 'admin@fixitlab.io' })
  },
  startInstance(sessionId, name) {
    return gcpApi.action(sessionId, 'start_instance', { instance_name: name })
  },
  stopInstance(sessionId, name) {
    return gcpApi.action(sessionId, 'stop_instance', { instance_name: name })
  },
  resetInstance(sessionId, name) {
    return gcpApi.action(sessionId, 'reset_instance', { instance_name: name })
  },
  setMachineType(sessionId, name, machineType) {
    return gcpApi.action(sessionId, 'set_machine_type', { instance_name: name, machine_type: machineType })
  },
  createFirewallRule(sessionId, rule) {
    return gcpApi.action(sessionId, 'create_firewall_rule', rule)
  },
  deleteFirewallRule(sessionId, name) {
    return gcpApi.action(sessionId, 'delete_firewall_rule', { name })
  },
  attachDisk(sessionId, instanceName, diskName) {
    return gcpApi.action(sessionId, 'attach_disk', { instance_name: instanceName, disk_name: diskName })
  },
  detachDisk(sessionId, diskName) {
    return gcpApi.action(sessionId, 'detach_disk', { disk_name: diskName })
  },
  createDisk(sessionId, name, sizeGb, type = 'pd-balanced') {
    return gcpApi.action(sessionId, 'create_disk', { name, size_gb: sizeGb, type })
  },
}

export default gcpApi
