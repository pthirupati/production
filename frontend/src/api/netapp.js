import api from './client'

// Thin client for the server-authoritative NetApp ONTAP System Manager engine
// (backend apps/vmware_sim/netapp_engine.py, routes under /vmware/netapp/...).
const base = (sessionId) => `/vmware/netapp/sessions/${sessionId}`

export const netappApi = {
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
    return netappApi.action(sessionId, 'login', { user: 'admin' })
  },
  createVolume(sessionId, name, svm, aggregate, sizeGb) {
    return netappApi.action(sessionId, 'create_volume', { name, svm, aggregate, size_gb: sizeGb })
  },
  resizeVolume(sessionId, name, sizeGb) {
    return netappApi.action(sessionId, 'resize_volume', { name, size_gb: sizeGb })
  },
  createSnapmirror(sessionId, source, destination) {
    return netappApi.action(sessionId, 'create_snapmirror', { source, destination })
  },
  breakMirror(sessionId, id) {
    return netappApi.action(sessionId, 'break_mirror', { id })
  },
  createExport(sessionId, volume, clients, policy = 'default', rules = 'rw') {
    return netappApi.action(sessionId, 'create_export', { volume, clients, policy, rules })
  },
  mountLun(sessionId, path, initiator) {
    return netappApi.action(sessionId, 'mount_lun', { path, initiator })
  },
  takeSnapshot(sessionId, volume, name) {
    return netappApi.action(sessionId, 'take_snapshot', { volume, name })
  },
  createQtree(sessionId, volume, name) {
    return netappApi.action(sessionId, 'create_qtree', { volume, name })
  },
  offlineVolume(sessionId, name) {
    return netappApi.action(sessionId, 'offline_volume', { name })
  },
  onlineVolume(sessionId, name) {
    return netappApi.action(sessionId, 'online_volume', { name })
  },
  createLun(sessionId, volume, sizeGb, path) {
    return netappApi.action(sessionId, 'create_lun', { volume, size_gb: sizeGb, path })
  },
  resyncMirror(sessionId, id) {
    return netappApi.action(sessionId, 'resync_mirror', { id })
  },
  createFlexgroup(sessionId, payload = {}) {
    return netappApi.action(sessionId, 'create_flexgroup', payload)
  },
  enableSnaplock(sessionId, payload = {}) {
    return netappApi.action(sessionId, 'enable_snaplock', payload)
  },
  svmDrFailover(sessionId, id) {
    return netappApi.action(sessionId, 'svm_dr_failover', { id })
  },
  createS3Bucket(sessionId, payload = {}) {
    return netappApi.action(sessionId, 'create_s3_bucket', payload)
  },
  mavApprove(sessionId, id) {
    return netappApi.action(sessionId, 'mav_approve', { id })
  },
  createFlexcache(sessionId, payload = {}) {
    return netappApi.action(sessionId, 'create_flexcache', payload)
  },
  arpSetMode(sessionId, mode, volume) {
    return netappApi.action(sessionId, 'arp_set_mode', { mode, volume })
  },

}

export default netappApi
