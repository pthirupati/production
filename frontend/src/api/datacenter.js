import api from './client'

// Thin client for the server-authoritative physical Data Center (DCIM) engine
// (backend apps/vmware_sim/datacenter_engine.py, routes under /vmware/datacenter/...).
const base = (sessionId) => `/vmware/datacenter/sessions/${sessionId}`

export const datacenterApi = {
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
    return datacenterApi.action(sessionId, 'login', { user: 'tech' })
  },
  selectAsset(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'select_asset', { asset_id: assetId })
  },
  powerCycle(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'power_cycle', { asset_id: assetId })
  },
  replaceComponent(sessionId, component, assetId) {
    const action = {
      nic: 'replace_nic', disk: 'replace_disk', motherboard: 'replace_motherboard',
      cpu: 'replace_cpu', gpu: 'replace_gpu', power: 'replace_power',
    }[component] || 'replace_power'
    return datacenterApi.action(sessionId, action, { asset_id: assetId })
  },
  reseatCable(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'reseat_cable', { asset_id: assetId })
  },
  updateFirmware(sessionId, assetId, version) {
    return datacenterApi.action(sessionId, 'update_firmware', { asset_id: assetId, version })
  },
  enterRoom(sessionId, roomId) {
    return datacenterApi.action(sessionId, 'enter_room', { room_id: roomId })
  },
  openBmc(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'open_bmc', { asset_id: assetId })
  },
  bmcPower(sessionId, assetId, mode) {
    return datacenterApi.action(sessionId, 'bmc_power', { asset_id: assetId, mode })
  },
  tripPduBreaker(sessionId, pduId) {
    return datacenterApi.action(sessionId, 'trip_pdu_breaker', { pdu_id: pduId })
  },
  restorePdu(sessionId, pduId) {
    return datacenterApi.action(sessionId, 'restore_pdu', { pdu_id: pduId })
  },
  restoreCrac(sessionId, cracId) {
    return datacenterApi.action(sessionId, 'restore_crac', { crac_id: cracId })
  },
}

export default datacenterApi
