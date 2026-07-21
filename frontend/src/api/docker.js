import api from './client'

const base = (sessionId) => `/vmware/docker/sessions/${sessionId}`

export const dockerApi = {
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
  /** Lab console sign-in is client-gated; engines do not yet expose a login verb. */
  login(_sessionId, user = 'admin') {
    return Promise.resolve({ ok: true, message: 'Signed in', user })
  },
  startContainer(sessionId, name) {
    return dockerApi.action(sessionId, 'start_container', { name })
  },
  stopContainer(sessionId, name, timeout = 10) {
    return dockerApi.action(sessionId, 'stop_container', { name, timeout })
  },
  removeContainer(sessionId, name, force = false) {
    return dockerApi.action(sessionId, 'remove_container', { name, force })
  },
  restartContainer(sessionId, name) {
    return dockerApi.action(sessionId, 'restart_container', { name })
  },
  pullImage(sessionId, image) {
    return dockerApi.action(sessionId, 'pull_image', { image })
  },
  removeImage(sessionId, image, force = false) {
    return dockerApi.action(sessionId, 'remove_image', { image, force })
  },
  createNetwork(sessionId, name, driver = 'bridge') {
    return dockerApi.action(sessionId, 'create_network', { name, driver })
  },
  removeNetwork(sessionId, name) {
    return dockerApi.action(sessionId, 'remove_network', { name })
  },
  connectNetwork(sessionId, container, network) {
    return dockerApi.action(sessionId, 'connect_network', { container, network })
  },
  disconnectNetwork(sessionId, container, network = '') {
    return dockerApi.action(sessionId, 'disconnect_network', { container, network })
  },
  createContainer(sessionId, payload = {}) {
    return dockerApi.action(sessionId, 'create_container', payload)
  },
  createVolume(sessionId, name, driver = 'local') {
    return dockerApi.action(sessionId, 'create_volume', { name, driver })
  },
  removeVolume(sessionId, name, force = false) {
    return dockerApi.action(sessionId, 'remove_volume', { name, force })
  },
  pruneVolumes(sessionId) {
    return dockerApi.action(sessionId, 'prune_volumes', {})
  },
  composeUp(sessionId, project = 'fixitlab', service = '') {
    return dockerApi.action(sessionId, 'docker_compose_up', {
      project, ...(service ? { service } : {}),
    })
  },
  composeDown(sessionId, project = 'fixitlab') {
    return dockerApi.action(sessionId, 'docker_compose_down', { project })
  },
  composeRestart(sessionId, project = 'fixitlab', service = '') {
    return dockerApi.action(sessionId, 'docker_compose_restart', {
      project, ...(service ? { service } : {}),
    })
  },
  execContainer(sessionId, name, cmd = 'sh') {
    return dockerApi.action(sessionId, 'exec_container', { name, cmd })
  },
  inspectContainer(sessionId, name) {
    return dockerApi.action(sessionId, 'inspect_container', { name })
  },
  statsContainer(sessionId, name) {
    return dockerApi.action(sessionId, 'stats_container', { name })
  },
  systemPrune(sessionId, { all = false, volumes = false } = {}) {
    return dockerApi.action(sessionId, 'system_prune', { all, volumes })
  },
  swarmInit(sessionId, payload = {}) {
    return dockerApi.action(sessionId, 'swarm_init', payload)
  },
  createSwarmService(sessionId, payload = {}) {
    return dockerApi.action(sessionId, 'create_swarm_service', payload)
  },
  scaleSwarmService(sessionId, name, replicas) {
    return dockerApi.action(sessionId, 'scale_swarm_service', { name, replicas })
  },
  createSecret(sessionId, name) {
    return dockerApi.action(sessionId, 'create_secret', { name })
  },
  createConfig(sessionId, name) {
    return dockerApi.action(sessionId, 'create_config', { name })
  },
  registryPush(sessionId, payload = {}) {
    return dockerApi.action(sessionId, 'registry_push', payload)
  },
  registryPull(sessionId, name, tag = 'latest') {
    return dockerApi.action(sessionId, 'registry_pull', { name, tag })
  },
}
