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
  motherboardOps(sessionId, assetId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'motherboard_ops', { asset_id: assetId, op, ...extra })
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
  raidAssignHotspare(sessionId, assetId, diskId) {
    return datacenterApi.action(sessionId, 'raid_assign_hotspare', { asset_id: assetId, disk_id: diskId })
  },
  raidExpandVd(sessionId, assetId, vdId, addGb = 500) {
    return datacenterApi.action(sessionId, 'raid_expand_vd', { asset_id: assetId, vd_id: vdId, add_gb: addGb })
  },
  raidInitializeVd(sessionId, assetId, vdId, mode = 'fast') {
    return datacenterApi.action(sessionId, 'raid_initialize_vd', { asset_id: assetId, vd_id: vdId, mode })
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
  injectFailure(sessionId, preset, assetId = '') {
    return datacenterApi.action(sessionId, 'inject_failure', { preset, asset_id: assetId })
  },
  serviceMode(sessionId, assetId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'service_mode_action', { asset_id: assetId, op, ...extra })
  },
  raidDeleteVd(sessionId, assetId, vdId) {
    return datacenterApi.action(sessionId, 'raid_delete_vd', { asset_id: assetId, vd_id: vdId })
  },
  raidPatrolRead(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'raid_patrol_read', { asset_id: assetId })
  },
  raidConsistencyCheck(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'raid_consistency_check', { asset_id: assetId })
  },
  raidImportForeign(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'raid_import_foreign', { asset_id: assetId })
  },
  biosRunPost(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'bios_run_post', { asset_id: assetId })
  },
  biosSetPassword(sessionId, assetId, password) {
    return datacenterApi.action(sessionId, 'bios_set_password', { asset_id: assetId, password })
  },
  biosFlash(sessionId, assetId, version) {
    return datacenterApi.action(sessionId, 'bios_flash', { asset_id: assetId, version })
  },
  bmcNmi(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'bmc_nmi', { asset_id: assetId })
  },
  bmcFlashTarget(sessionId, assetId, target, version) {
    return datacenterApi.action(sessionId, 'bmc_flash_target', { asset_id: assetId, target, version })
  },
  bmcOpenKvm(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'bmc_open_kvm', { asset_id: assetId })
  },
  bmcLogin(sessionId, assetId, username, password) {
    return datacenterApi.action(sessionId, 'bmc_login', {
      asset_id: assetId, username, password,
    })
  },
  bmcLogout(sessionId, assetId) {
    return datacenterApi.action(sessionId, 'bmc_logout', { asset_id: assetId })
  },
  bmcSetGeneration(sessionId, assetId, generation) {
    return datacenterApi.action(sessionId, 'bmc_set_generation', { asset_id: assetId, generation })
  },
  switchCli(sessionId, switchId, command) {
    return datacenterApi.action(sessionId, 'switch_cli', { switch_id: switchId, command })
  },
  netPing(sessionId, host) {
    return datacenterApi.action(sessionId, 'net_ping', { host })
  },
  netTraceroute(sessionId, dest) {
    return datacenterApi.action(sessionId, 'net_traceroute', { dest })
  },
  netIperf(sessionId, src, dst) {
    return datacenterApi.action(sessionId, 'net_iperf', { src, dst })
  },
  netFixProtocol(sessionId, protocol) {
    return datacenterApi.action(sessionId, 'net_fix_protocol', { protocol })
  },
  cableOps(sessionId, assetId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'cable_ops', { asset_id: assetId, op, ...extra })
  },
  storageOps(sessionId, assetId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'storage_ops', { asset_id: assetId, op, ...extra })
  },
  toggleRackCasters(sessionId, rackId) {
    return datacenterApi.action(sessionId, 'toggle_rack_casters', { rack_id: rackId })
  },
  installBlanking(sessionId, rackId, u) {
    return datacenterApi.action(sessionId, 'install_blanking', { rack_id: rackId, u })
  },
  pduOutletToggle(sessionId, rackId, outletId) {
    return datacenterApi.action(sessionId, 'pdu_outlet_toggle', { rack_id: rackId, outlet_id: outletId })
  },
  opsTicketCreate(sessionId, vendor, ticketType, extra = {}) {
    return datacenterApi.action(sessionId, 'ops_ticket', { op: 'create', vendor, ticket_type: ticketType, ...extra })
  },
  opsTicketAdvance(sessionId, ticketId, advance, extra = {}) {
    return datacenterApi.action(sessionId, 'ops_ticket', { op: 'advance', ticket_id: ticketId, advance, ...extra })
  },
  trainingStart(sessionId, scenarioId) {
    return datacenterApi.action(sessionId, 'training_start', { scenario_id: scenarioId })
  },
  trainingStep(sessionId, step) {
    return datacenterApi.action(sessionId, 'training_complete_step', { step })
  },
  refreshMonitoring(sessionId) {
    return datacenterApi.action(sessionId, 'refresh_monitoring', {})
  },
  liveTick(sessionId) {
    return datacenterApi.action(sessionId, 'live_tick', {})
  },
  hypervisorOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'hypervisor_ops', { op, ...extra })
  },
  aiOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'ai_ops', { op, ...extra })
  },
  replayTwinJournal(sessionId, extra = {}) {
    return datacenterApi.action(sessionId, 'replay_twin_journal', extra)
  },
  liquidCoolingOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'liquid_cooling_ops', { op, ...extra })
  },
  pxeMaasOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'pxe_maas_ops', { op, ...extra })
  },
  rackFruOps(sessionId, rackId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'rack_fru_ops', { rack_id: rackId, op, ...extra })
  },
  fireSafetyOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'fire_safety_ops', { op, ...extra })
  },
  environmentalOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'environmental_ops', { op, ...extra })
  },
  opticalOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'optical_ops', { op, ...extra })
  },
  refreshCapacity(sessionId) {
    return datacenterApi.action(sessionId, 'refresh_capacity', {})
  },
  drOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'dr_ops', { op, ...extra })
  },
  campusPlantOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'campus_plant_ops', { op, ...extra })
  },
  accessOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'access_ops', { op, ...extra })
  },
  automationOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'automation_ops', { op, ...extra })
  },
  generateOpsReport(sessionId) {
    return datacenterApi.action(sessionId, 'generate_ops_report', {})
  },
  changeOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'change_ops', { op, ...extra })
  },
  containmentOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'containment_ops', { op, ...extra })
  },
  cablePlantOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'cable_plant_ops', { op, ...extra })
  },
  burninOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'burnin_ops', { op, ...extra })
  },
  exporterOps(sessionId, op, extra = {}) {
    return datacenterApi.action(sessionId, 'exporter_ops', { op, ...extra })
  },
  generateEvidence(sessionId) {
    return datacenterApi.action(sessionId, 'generate_evidence', {})
  },
}


export default datacenterApi
