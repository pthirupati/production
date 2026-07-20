import api from './client'

const base = (sessionId) => `/vmware/k8s/sessions/${sessionId}`

export const k8sApi = {
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
  cordonNode(sessionId, name) {
    return k8sApi.action(sessionId, 'cordon_node', { name })
  },
  drainNode(sessionId, name) {
    return k8sApi.action(sessionId, 'drain_node', { name })
  },
  uncordonNode(sessionId, name) {
    return k8sApi.action(sessionId, 'uncordon_node', { name })
  },
  deletePod(sessionId, name, namespace = '') {
    return k8sApi.action(sessionId, 'delete_pod', { name, namespace })
  },
  scaleDeployment(sessionId, name, replicas, namespace = 'production') {
    return k8sApi.action(sessionId, 'scale_deployment', { name, replicas, namespace })
  },
  deleteDeployment(sessionId, name, namespace = 'production') {
    return k8sApi.action(sessionId, 'delete_deployment', { name, namespace })
  },
  restartDeployment(sessionId, name, namespace = 'production') {
    return k8sApi.action(sessionId, 'restart_deployment', { name, namespace })
  },
  applyConfigMap(sessionId, name, data = {}, namespace = 'production') {
    return k8sApi.action(sessionId, 'apply_configmap', { name, data, namespace })
  },
  applySecret(sessionId, name, keys = [], namespace = 'production', type = 'Opaque') {
    return k8sApi.action(sessionId, 'apply_secret', { name, keys, namespace, type })
  },
  createNamespace(sessionId, name, labels = {}) {
    return k8sApi.action(sessionId, 'create_namespace', { name, labels })
  },
  deleteNamespace(sessionId, name) {
    return k8sApi.action(sessionId, 'delete_namespace', { name })
  },
  bindPvc(sessionId, name, namespace = 'production', volumeName = '') {
    return k8sApi.action(sessionId, 'bind_pvc', {
      name, namespace, ...(volumeName ? { volume_name: volumeName } : {}),
    })
  },
  patchResource(sessionId, kind, name, patch = {}, namespace = '') {
    return k8sApi.action(sessionId, 'patch_resource', { kind, name, patch, namespace })
  },
}
