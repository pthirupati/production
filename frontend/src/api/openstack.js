import api from './client'

const base = (sessionId) => `/vmware/openstack/sessions/${sessionId}`

export const openstackApi = {
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
  login(sessionId, user = 'admin') {
    return openstackApi.action(sessionId, 'login', { user })
  },
  startInstance(sessionId, name) {
    return openstackApi.action(sessionId, 'start_instance', { name })
  },
  stopInstance(sessionId, name) {
    return openstackApi.action(sessionId, 'stop_instance', { name })
  },
  createInstance(sessionId, payload) {
    return openstackApi.action(sessionId, 'create_instance', payload)
  },
  attachVolume(sessionId, volumeName, instanceName) {
    return openstackApi.action(sessionId, 'attach_volume', {
      name: volumeName, instance: instanceName,
    })
  },
  resizeInstance(sessionId, name, flavor) {
    return openstackApi.action(sessionId, 'resize_instance', { name, flavor })
  },
}
