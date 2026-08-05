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
  commission(sessionId, machineId, opts = {}) {
    const payload = { machine_id: machineId, ...opts }
    if (opts.machine_ids) payload.machine_ids = opts.machine_ids
    return baremetalApi.action(sessionId, 'maas_commission', payload)
  },
  deploy(sessionId, machineId, opts = {}) {
    const payload = { machine_id: machineId }
    if (opts.boot_resource) payload.boot_resource = opts.boot_resource
    if (opts.distro_series) payload.distro_series = opts.distro_series
    if (opts.machine_ids) payload.machine_ids = opts.machine_ids
    return baremetalApi.action(sessionId, 'maas_deploy', payload)
  },
  release(sessionId, machineId, opts = {}) {
    const payload = { machine_id: machineId, ...opts }
    if (opts.machine_ids) payload.machine_ids = opts.machine_ids
    return baremetalApi.action(sessionId, 'maas_release', payload)
  },
  abort(sessionId, machineId, opts = {}) {
    const payload = { machine_id: machineId }
    if (opts.machine_ids) payload.machine_ids = opts.machine_ids
    return baremetalApi.action(sessionId, 'maas_abort', payload)
  },
  markBroken(sessionId, machineId, comment = '') {
    return baremetalApi.action(sessionId, 'maas_mark_broken', { machine_id: machineId, comment })
  },
  markFixed(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'maas_mark_fixed', { machine_id: machineId })
  },
  lock(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'maas_lock', { machine_id: machineId })
  },
  unlock(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'maas_unlock', { machine_id: machineId })
  },
  setZone(sessionId, machineId, zone) {
    return baremetalApi.action(sessionId, 'maas_set_zone', { machine_id: machineId, zone })
  },
  setPool(sessionId, machineId, pool) {
    return baremetalApi.action(sessionId, 'maas_set_pool', { machine_id: machineId, pool })
  },
  testHardware(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'maas_test', { machine_id: machineId })
  },
  overrideFailedTesting(sessionId, machineId) {
    return baremetalApi.action(sessionId, 'maas_override_failed_testing', { machine_id: machineId })
  },
  addMachine(sessionId, fields = {}) {
    return baremetalApi.action(sessionId, 'maas_add_machine', fields)
  },
  applyStorageLayout(sessionId, machineId, layout = 'flat') {
    return baremetalApi.action(sessionId, 'maas_apply_storage_layout', {
      machine_id: machineId,
      layout,
    })
  },
  setBootInterface(sessionId, machineId, iface) {
    return baremetalApi.action(sessionId, 'maas_set_boot_interface', {
      machine_id: machineId,
      interface: iface,
      name: iface,
    })
  },
  updateSettings(sessionId, settings = {}) {
    return baremetalApi.action(sessionId, 'maas_update_settings', settings)
  },
  /**
   * Run the same MAAS action against many machines.
   * Prefer machine_ids when the engine supports bulk; otherwise fan out.
   */
  async bulkAction(sessionId, action, machineIds, extra = {}) {
    const ids = (machineIds || []).filter((id) => id != null)
    if (!ids.length) return { ok: false, error: 'No machines selected' }
    const bulkCapable = new Set([
      'maas_commission', 'maas_deploy', 'maas_release', 'maas_abort', 'maas_power',
    ])
    if (bulkCapable.has(action)) {
      return baremetalApi.action(sessionId, action, {
        machine_ids: ids,
        machine_id: ids[0],
        ...extra,
      })
    }
    let last = null
    for (const id of ids) {
      last = await baremetalApi.action(sessionId, action, { machine_id: id, ...extra })
      if (last?.ok === false) return last
    }
    return last || { ok: true }
  },
  power(sessionId, machineId, power) {
    return baremetalApi.action(sessionId, 'maas_power', { machine_id: machineId, power })
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
  createSpace(sessionId, name, subnet) {
    return baremetalApi.action(sessionId, 'maas_create_space', { name, subnet })
  },
  addSubnet(sessionId, space, subnet) {
    return baremetalApi.action(sessionId, 'maas_add_subnet', { space, subnet })
  },
  tagMachine(sessionId, hostname, tag) {
    return baremetalApi.action(sessionId, 'maas_tag_machine', { hostname, tag })
  },
  attachScript(sessionId, name, appliedTo = ['*']) {
    return baremetalApi.action(sessionId, 'maas_attach_script', { name, applied_to: appliedTo })
  },
  publishBootResource(sessionId, { sku = 'h100', name, architecture = 'amd64/generic', source } = {}) {
    return baremetalApi.action(sessionId, 'maas_publish_boot_resource', {
      sku,
      boot_resource: name || `custom/${sku}-jammy`,
      architecture,
      source: source || `packer output-gpu-${sku}/`,
    })
  },
  deleteMachine(sessionId, machineId, hostname) {
    return baremetalApi.action(sessionId, 'maas_delete', {
      machine_id: machineId,
      hostname,
    })
  },
}
