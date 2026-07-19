import api from './client'

// Thin client for the server-authoritative Azure Portal engine (backend
// apps/vmware_sim/azure_engine.py, routes under /vmware/azure/...). The
// frontend never keeps its own copy of VM/NSG/disk state -- every action
// round-trips to the backend and the returned `state` is what gets rendered,
// so the portal and the lab terminal can never drift out of sync.
const base = (sessionId) => `/vmware/azure/sessions/${sessionId}`

export const azureApi = {
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
    return azureApi.action(sessionId, 'login', { user: 'admin@fixitlab.onmicrosoft.com' })
  },
  startVm(sessionId, vmName) {
    return azureApi.action(sessionId, 'start_vm', { vm_name: vmName })
  },
  stopVm(sessionId, vmName) {
    return azureApi.action(sessionId, 'stop_vm', { vm_name: vmName })
  },
  restartVm(sessionId, vmName) {
    return azureApi.action(sessionId, 'restart_vm', { vm_name: vmName })
  },
  resizeVm(sessionId, vmName, size) {
    return azureApi.action(sessionId, 'resize_vm', { vm_name: vmName, size })
  },
  addNsgRule(sessionId, nsgName, rule) {
    return azureApi.action(sessionId, 'add_nsg_rule', { nsg_name: nsgName, ...rule })
  },
  removeNsgRule(sessionId, nsgName, name) {
    return azureApi.action(sessionId, 'remove_nsg_rule', { nsg_name: nsgName, name })
  },
  attachDisk(sessionId, vmName, diskName) {
    return azureApi.action(sessionId, 'attach_disk', { vm_name: vmName, disk_name: diskName })
  },
  detachDisk(sessionId, diskName) {
    return azureApi.action(sessionId, 'detach_disk', { disk_name: diskName })
  },
  createDisk(sessionId, name, sizeGb, sku = 'Standard_SSD_LRS') {
    return azureApi.action(sessionId, 'create_disk', { name, size_gb: sizeGb, sku })
  },
  createVm(sessionId, payload = {}) {
    return azureApi.action(sessionId, 'create_vm', payload)
  },
}

export default azureApi
