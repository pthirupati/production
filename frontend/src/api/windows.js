import api from './client'

// Session-scoped calls for the Windows Server GUI simulator. The backend mounts
// the engine under /api/vmware/windows/ (the vmware_sim app owns the engines),
// mirroring the nmap/datascience non-demo State/Action/Release endpoints.
//
// Unlike the VMware/Nmap sims there is NO per-user demo sandbox endpoint, so a
// missing/expired session simply surfaces the error to the caller (which renders
// a friendly "could not load" banner) instead of silently swapping to a demo.

async function getState(sessionId, scenario) {
  const params = scenario ? { scenario } : undefined
  const { data } = await api.get(`/vmware/windows/sessions/${sessionId}/`, { params, silentError: true })
  return data
}

// The action endpoint returns { ok, message?, error?, state } — we hand the whole
// envelope back so the simulator can show the message AND refresh from `state`
// without a second round-trip. Action failures come back as { ok:false, error }
// with a 400; we normalize those to the same envelope so the UI never throws.
async function action(sessionId, act, payload) {
  if (!sessionId) {
    return { ok: false, error: 'No active lab session' }
  }
  try {
    const { data } = await api.post(
      `/vmware/windows/sessions/${sessionId}/action/`,
      { action: act, payload: payload || {} },
      { silentError: true },
    )
    return data
  } catch (err) {
    // The backend returns 400 with { ok:false, error } for rejected actions
    // (e.g. starting a Disabled service). Surface that body unchanged.
    const body = err?.response?.data
    if (body && typeof body === 'object') return body
    return { ok: false, error: 'Action failed — try again' }
  }
}

export const windowsApi = {
  getState: (sessionId, scenario = '') => getState(sessionId, scenario),
  action: (sessionId, act, payload = {}) => action(sessionId, act, payload),
  // ── Convenience wrappers for the common GUI verbs (thin sugar over action) ──
  login: (sessionId) => action(sessionId, 'login', {}),
  lock: (sessionId) => action(sessionId, 'lock', {}),
  unlock: (sessionId) => action(sessionId, 'unlock', {}),
  logout: (sessionId) => action(sessionId, 'logout', {}),

  installRole: (sessionId, role) => action(sessionId, 'install_role', { role }),
  uninstallRole: (sessionId, role) => action(sessionId, 'uninstall_role', { role }),
  configureDns: (sessionId) => action(sessionId, 'configure_dns', {}),
  configureDhcp: (sessionId) => action(sessionId, 'configure_dhcp', {}),

  createUser: (sessionId, payload) => action(sessionId, 'create_ad_user', payload),
  enableUser: (sessionId, user) => action(sessionId, 'enable_ad_user', { user }),
  disableUser: (sessionId, user) => action(sessionId, 'disable_ad_user', { user }),
  unlockUser: (sessionId, user) => action(sessionId, 'unlock_ad_user', { user }),
  resetPassword: (sessionId, user) => action(sessionId, 'reset_password', { user }),
  addToGroup: (sessionId, user, group) => action(sessionId, 'add_user_to_group', { user, group }),
  removeFromGroup: (sessionId, user, group) => action(sessionId, 'remove_user_from_group', { user, group }),

  installUpdate: (sessionId, kb) => action(sessionId, 'install_update', kb ? { kb } : {}),
  retryUpdate: (sessionId, kb) => action(sessionId, 'retry_update', { kb }),
  checkUpdates: (sessionId) => action(sessionId, 'check_updates', {}),

  startService: (sessionId, service) => action(sessionId, 'start_service', { service }),
  stopService: (sessionId, service) => action(sessionId, 'stop_service', { service }),
  restartService: (sessionId, service) => action(sessionId, 'restart_service', { service }),
  setStartup: (sessionId, service, startup) => action(sessionId, 'set_startup', { service, startup }),
  initializeDisk: (sessionId, diskId, style = 'GPT') => action(sessionId, 'initialize_disk', { disk_id: diskId, style }),
  createVolume: (sessionId, payload = {}) => action(sessionId, 'create_volume', payload),
  setAdapterIp: (sessionId, payload = {}) => action(sessionId, 'set_adapter_ip', payload),

  joinDomain: (sessionId, domain) => action(sessionId, 'join_domain', domain ? { domain } : {}),
  leaveDomain: (sessionId) => action(sessionId, 'leave_domain', {}),
  renameComputer: (sessionId, name) => action(sessionId, 'rename_computer', { name }),
  reset: (sessionId) => action(sessionId, 'reset', {}),

  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/windows/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
