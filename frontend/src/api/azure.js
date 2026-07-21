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
  createResourceGroup(sessionId, name, location = 'eastus') {
    return azureApi.action(sessionId, 'create_resource_group', { name, location })
  },
  createStorageAccount(sessionId, name, opts = {}) {
    return azureApi.action(sessionId, 'create_storage_account', { name, ...opts })
  },
  createBlobContainer(sessionId, account, name) {
    return azureApi.action(sessionId, 'create_blob_container', { account, name })
  },
  setSecret(sessionId, vault, name, contentType = 'text') {
    return azureApi.action(sessionId, 'set_secret', { vault, name, content_type: contentType })
  },
  assignRole(sessionId, principal, role, scope) {
    return azureApi.action(sessionId, 'assign_role', { principal, role, scope })
  },
  removeRoleAssignment(sessionId, id) {
    return azureApi.action(sessionId, 'remove_role_assignment', { id })
  },
  createLbRule(sessionId, lb, rule) {
    return azureApi.action(sessionId, 'create_load_balancer_rule', { lb, ...rule })
  },
  createSubnet(sessionId, vnet, name, addressPrefix) {
    return azureApi.action(sessionId, 'create_subnet', {
      vnet, name, address_prefix: addressPrefix,
    })
  },
  createNsg(sessionId, name) {
    return azureApi.action(sessionId, 'create_nsg', { name })
  },
  snapshotDisk(sessionId, diskName, name) {
    return azureApi.action(sessionId, 'snapshot_disk', { disk_name: diskName, name })
  },
  createVmss(sessionId, payload = {}) {
    return azureApi.action(sessionId, 'create_vmss', payload)
  },
  scaleVmss(sessionId, name, capacity) {
    return azureApi.action(sessionId, 'scale_vmss', { name, capacity })
  },
  createWebApp(sessionId, payload = {}) {
    return azureApi.action(sessionId, 'create_web_app', payload)
  },
  swapWebSlots(sessionId, name) {
    return azureApi.action(sessionId, 'swap_web_slots', { name })
  },
  createFunctionApp(sessionId, payload = {}) {
    return azureApi.action(sessionId, 'create_function_app', payload)
  },
  createFunction(sessionId, app, payload = {}) {
    return azureApi.action(sessionId, 'create_function', { app, ...payload })
  },
  createContainerApp(sessionId, payload = {}) {
    return azureApi.action(sessionId, 'create_container_app', payload)
  },
  createAksCluster(sessionId, payload = {}) {
    return azureApi.action(sessionId, 'create_aks_cluster', payload)
  },
  scaleAksNodePool(sessionId, cluster, nodePool, count) {
    return azureApi.action(sessionId, 'scale_aks_node_pool', { cluster, node_pool: nodePool, count })
  },
  createFirewallRule(sessionId, firewall, rule = {}) {
    return azureApi.action(sessionId, 'create_firewall_rule', { firewall, ...rule })
  },
  createCosmosItem(sessionId, account, database, container) {
    return azureApi.action(sessionId, 'create_cosmos_item', { account, database, container })
  },
  sentinelUpdateIncident(sessionId, incidentId, status) {
    return azureApi.action(sessionId, 'sentinel_update_incident', { incident_id: incidentId, status })
  },
  entraInviteUser(sessionId, upn, opts = {}) {
    return azureApi.action(sessionId, 'entra_invite_user', { upn, ...opts })
  },
}

export default azureApi
