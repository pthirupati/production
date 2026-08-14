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
  setNetworkTags(sessionId, name, tags) {
    return gcpApi.action(sessionId, 'set_network_tags', { instance_name: name, tags })
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
  createInstance(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_instance', payload)
  },
  deleteInstance(sessionId, name) {
    return gcpApi.action(sessionId, 'delete_instance', { name, instance_name: name })
  },
  addIamBinding(sessionId, member, role) {
    return gcpApi.action(sessionId, 'add_iam_binding', { member, role })
  },
  removeIamBinding(sessionId, member, role) {
    return gcpApi.action(sessionId, 'remove_iam_binding', { member, role })
  },
  createBucket(sessionId, name, opts = {}) {
    return gcpApi.action(sessionId, 'create_bucket', { name, ...opts })
  },
  deleteBucket(sessionId, name) {
    return gcpApi.action(sessionId, 'delete_bucket', { name })
  },
  createSubnet(sessionId, network, name, range) {
    return gcpApi.action(sessionId, 'create_subnet', { network, name, range })
  },
  createForwardingRule(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_forwarding_rule', payload)
  },
  createSnapshot(sessionId, diskName, name) {
    return gcpApi.action(sessionId, 'create_snapshot', { disk_name: diskName, name })
  },
  createCloudRunService(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_cloud_run_service', payload)
  },
  updateCloudRunTraffic(sessionId, name, trafficPct) {
    return gcpApi.action(sessionId, 'update_cloud_run_traffic', { name, traffic_pct: trafficPct })
  },
  createPubsubTopic(sessionId, name) {
    return gcpApi.action(sessionId, 'create_pubsub_topic', { name })
  },
  createPubsubSubscription(sessionId, topic, payload = {}) {
    return gcpApi.action(sessionId, 'create_pubsub_subscription', { topic, ...payload })
  },
  publishPubsub(sessionId, topic) {
    return gcpApi.action(sessionId, 'publish_pubsub', { topic })
  },
  createGkeCluster(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_gke_cluster', payload)
  },
  resizeGkeNodePool(sessionId, cluster, pool, nodeCount) {
    return gcpApi.action(sessionId, 'resize_gke_node_pool', { cluster, pool, node_count: nodeCount })
  },
  createCloudFunction(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_cloud_function', payload)
  },
  createSqlInstance(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_sql_instance', payload)
  },
  createSqlDatabase(sessionId, instance, name) {
    return gcpApi.action(sessionId, 'create_sql_database', { instance, name })
  },
  createSecret(sessionId, name) {
    return gcpApi.action(sessionId, 'create_secret', { name })
  },
  addSecretVersion(sessionId, name) {
    return gcpApi.action(sessionId, 'add_secret_version', { name })
  },
  createArmorPolicy(sessionId, name) {
    return gcpApi.action(sessionId, 'create_armor_policy', { name })
  },
  addArmorRule(sessionId, name, rule = {}) {
    return gcpApi.action(sessionId, 'add_armor_rule', { name, ...rule })
  },
  createSpannerInstance(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_spanner_instance', payload)
  },
  createSpannerDatabase(sessionId, instance, name) {
    return gcpApi.action(sessionId, 'create_spanner_database', { instance, name })
  },
  createBigQueryDataset(sessionId, datasetId) {
    return gcpApi.action(sessionId, 'create_bigquery_dataset', { dataset_id: datasetId })
  },
  createBigQueryTable(sessionId, datasetId, name) {
    return gcpApi.action(sessionId, 'create_bigquery_table', { dataset_id: datasetId, name })
  },
  runBigQuery(sessionId, sql) {
    return gcpApi.action(sessionId, 'run_bigquery_query', { sql })
  },
  createHttpLoadBalancer(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_http_load_balancer', payload)
  },
  createVpc(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_vpc', payload)
  },
  createInstanceGroup(sessionId, payload = {}) {
    return gcpApi.action(sessionId, 'create_instance_group', payload)
  },
  resizeInstanceGroup(sessionId, name, size) {
    return gcpApi.action(sessionId, 'resize_instance_group', { name, size })
  },
  uploadGcsObject(sessionId, bucket, payload = {}) {
    return gcpApi.action(sessionId, 'upload_gcs_object', { bucket, ...payload })
  },
}

export default gcpApi
