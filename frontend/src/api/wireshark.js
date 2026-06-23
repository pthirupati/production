import api from './client'

// Mirrors api/vmware.js + api/monitoring.js: session-scoped calls that fall back
// transparently to a per-user demo sandbox so the Wireshark simulator ALWAYS
// loads (expired session, non-wireshark lab, or a reloaded standalone URL). The
// backend mounts wireshark under /api/vmware/wireshark/ (the vmware_sim app owns
// the engines).
async function getStateWithFallback(sessionId, scenario) {
  const params = scenario ? { scenario } : undefined
  if (!sessionId) {
    const { data } = await api.get('/vmware/wireshark/demo/', { params, silentError: true })
    return data
  }
  try {
    const { data } = await api.get(`/vmware/wireshark/sessions/${sessionId}/`, { params, silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.get('/vmware/wireshark/demo/', { params, silentError: true })
      return data
    }
    throw err
  }
}

async function actionWithFallback(sessionId, action, payload) {
  if (!sessionId) {
    const { data } = await api.post('/vmware/wireshark/demo/action/', { action, payload }, { silentError: true })
    return data
  }
  try {
    const { data } = await api.post(`/vmware/wireshark/sessions/${sessionId}/action/`, { action, payload }, { silentError: true })
    return data
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || status === 400 || status === 403) {
      const { data } = await api.post('/vmware/wireshark/demo/action/', { action, payload }, { silentError: true })
      return data
    }
    throw err
  }
}

export const wiresharkApi = {
  getState: (sessionId, scenario = '') => getStateWithFallback(sessionId, scenario),
  action: (sessionId, action, payload = {}) => actionWithFallback(sessionId, action, payload),
  setCaptureFilter: (sessionId, filter) => actionWithFallback(sessionId, 'set_capture_filter', { filter }),
  setDisplayFilter: (sessionId, filter) => actionWithFallback(sessionId, 'set_display_filter', { filter }),
  followStream: (sessionId, payload) => actionWithFallback(sessionId, 'follow_tcp_stream', payload),
  selectPacket: (sessionId, packetNo) => actionWithFallback(sessionId, 'select_packet', { packet_no: packetNo }),
  markPacket: (sessionId, packetNo) => actionWithFallback(sessionId, 'mark_packet', { packet_no: packetNo }),
  clearFilters: (sessionId) => actionWithFallback(sessionId, 'clear_filters', {}),
  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/wireshark/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
