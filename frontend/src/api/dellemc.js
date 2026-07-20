import api from './client'

// Thin client for the server-authoritative Dell EMC Unisphere / PowerMax engine
// (backend apps/vmware_sim/dellemc_engine.py, routes under /vmware/dellemc/...).
const base = (sessionId) => `/vmware/dellemc/sessions/${sessionId}`

export const dellemcApi = {
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
    return dellemcApi.action(sessionId, 'login', { user: 'admin' })
  },
  createStorageGroup(sessionId, name) {
    return dellemcApi.action(sessionId, 'create_storage_group', { name })
  },
  createVolume(sessionId, sizeGb, storageGroup) {
    return dellemcApi.action(sessionId, 'create_volume', { size_gb: sizeGb, storage_group: storageGroup })
  },
  mapVolume(sessionId, volumeId, storageGroup) {
    return dellemcApi.action(sessionId, 'map_volume', { volume_id: volumeId, storage_group: storageGroup })
  },
  addHost(sessionId, name, initiators, hostType = 'Linux') {
    return dellemcApi.action(sessionId, 'add_host', { name, initiators, host_type: hostType })
  },
  createMaskingView(sessionId, name, storageGroup, host, portGroup) {
    return dellemcApi.action(sessionId, 'create_masking_view', { name, storage_group: storageGroup, host, port_group: portGroup })
  },
  expandVolume(sessionId, volumeId, sizeGb) {
    return dellemcApi.action(sessionId, 'expand_volume', { volume_id: volumeId, size_gb: sizeGb })
  },
  createSnapshot(sessionId, volumeId, name) {
    return dellemcApi.action(sessionId, 'create_snapshot', { volume_id: volumeId, name })
  },
  setHostIoLimit(sessionId, storageGroup, iops) {
    return dellemcApi.action(sessionId, 'set_host_io_limit', { storage_group: storageGroup, iops })
  },
  createPortGroup(sessionId, name, ports) {
    return dellemcApi.action(sessionId, 'create_port_group', { name, ports })
  },
  failoverSrdf(sessionId, name) {
    return dellemcApi.action(sessionId, 'failover_srdf', { name })
  },
  deleteMaskingView(sessionId, name) {
    return dellemcApi.action(sessionId, 'delete_masking_view', { name })
  },
}

export default dellemcApi
