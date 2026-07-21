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
      fan: 'replace_fan', dimm: 'replace_dimm', pcie: 'replace_pcie',
      raid: 'replace_raid', hba: 'replace_hba',
    }[component] || 'replace_power'
    return datacenterApi.action(sessionId, action, { asset_id: assetId })
  },
  reseatCable(sessionId, assetId, cableId = '') {
    return datacenterApi.action(sessionId, 'reseat_cable', { asset_id: assetId, cable_id: cableId })
  },
  plugCable(sessionId, assetId, cableId) {
    return datacenterApi.action(sessionId, 'plug_cable', { asset_id: assetId, cable_id: cableId })
  },
  unplugCable(sessionId, assetId, cableId) {
    return datacenterApi.action(sessionId, 'unplug_cable', { asset_id: assetId, cable_id: cableId })
  },
  openVendorTicket(sessionId, assetId, component, vendor) {
    return datacenterApi.action(sessionId, 'open_vendor_ticket', {
      asset_id: assetId, component, vendor,
    })
  },
  resolveVendorTicket(sessionId, ticketId) {
    return datacenterApi.action(sessionId, 'resolve_vendor_ticket', { ticket_id: ticketId })
  },
  openSerialConsole(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'open_serial_console', { asset_id: assetId })
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
  toggleChassisCover(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'toggle_chassis_cover', { asset_id: assetId })
  },
  replaceDimmSlot(sessionId, assetId, slotId) {
    return datacenterApi.action(sessionId, 'replace_dimm_slot', { asset_id: assetId, slot_id: slotId })
  },
  applyThermalPaste(sessionId, assetId, socketId) {
    return datacenterApi.action(sessionId, 'apply_thermal_paste', { asset_id: assetId, socket_id: socketId })
  },
  raidFailDisk(sessionId, assetId, diskId) {
    return datacenterApi.action(sessionId, 'raid_fail_disk', { asset_id: assetId, disk_id: diskId })
  },
  raidRebuild(sessionId, assetId, vdId) {
    return datacenterApi.action(sessionId, 'raid_rebuild', { asset_id: assetId, vd_id: vdId })
  },
  raidSetCache(sessionId, assetId, mode) {
    return datacenterApi.action(sessionId, 'raid_set_cache', { asset_id: assetId, mode })
  },
  raidCreateVd(sessionId, assetId, payload) {
    return datacenterApi.action(sessionId, 'raid_create_vd', { asset_id: assetId, ...payload })
  },
  biosEnterSetup(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'bios_enter_setup', { asset_id: assetId })
  },
  biosExitSetup(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'bios_exit_setup', { asset_id: assetId })
  },
  biosSet(sessionId, assetId, key, value) {
    return datacenterApi.action(sessionId, 'bios_set', { asset_id: assetId, key, value })
  },
  biosCmosReset(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'bios_cmos_reset', { asset_id: assetId })
  },
  bmcMountIso(sessionId, assetId, image) {
    return datacenterApi.action(sessionId, 'bmc_mount_virtual_media', { asset_id: assetId, image })
  },
  bmcRunDiagnostics(sessionId, assetId, suite) {
    return datacenterApi.action(sessionId, 'bmc_run_diagnostics', { asset_id: assetId, suite })
  },
  bmcUpdateNetwork(sessionId, assetId, payload) {
    return datacenterApi.action(sessionId, 'bmc_update_network', { asset_id: assetId, ...payload })
  },
}

export default datacenterApi
