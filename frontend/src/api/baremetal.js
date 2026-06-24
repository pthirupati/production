import api from './client'

const base = (sessionId) => `/vmware/baremetal/sessions/${sessionId}`

export const baremetalApi = {
  getState(sessionId, scenarioSlug = '') {
    const q = scenarioSlug ? `?scenario=${encodeURIComponent(scenarioSlug)}` : ''
    return api.get(`${base(sessionId)}${q}`, { silentError: true }).then((r) => r.data)
  },
  action(sessionId, action, payload = {}) {
    return api.post(`${base(sessionId)}/action/`, { action, payload }).then((r) => r.data)
  },
  login(sessionId) {
    return baremetalApi.action(sessionId, 'login', { user: 'admin' })
  },
  commission(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'maas_commission', { machine_id: machineId })
  },
  deploy(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'maas_deploy', { machine_id: machineId })
  },
  startLxd(sessionId, name) {
    return baremetalApi.action(sessionId, 'lxd_start', { name })
  },
  startKvm(sessionId, name) {
    return baremetalApi.action(sessionId, 'kvm_start', { name })
  },
  fixPxeVlan(sessionId) {
    return baremetalApi.action(sessionId, 'fix_pxe_vlan', {})
  },
  ipmiPowerOn(sessionId) {
    return baremetalApi.action(sessionId, 'ipmi_power_on', {})
  },
  clearThermal(sessionId) {
    return baremetalApi.action(sessionId, 'clear_thermal_alert', {})
  },
  resetCommission(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'reset_commission', { machine_id: machineId })
  },
}
