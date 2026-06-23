import api from './client'

// Session-scoped calls for the Oracle PeopleSoft (PIA) GUI simulator. The backend
// mounts the engine under /api/vmware/peoplesoft/ (the vmware_sim app owns the
// engines), mirroring the windows/nmap non-demo State/Action/Release endpoints.
// No per-user demo sandbox endpoint — a missing/expired session surfaces the
// error to the caller (rendered as a friendly banner) rather than a demo swap.

async function getState(sessionId, scenario) {
  const params = scenario ? { scenario } : undefined
  const { data } = await api.get(`/vmware/peoplesoft/sessions/${sessionId}/`, { params, silentError: true })
  return data
}

async function action(sessionId, act, payload) {
  if (!sessionId) return { ok: false, error: 'No active lab session' }
  try {
    const { data } = await api.post(
      `/vmware/peoplesoft/sessions/${sessionId}/action/`,
      { action: act, payload: payload || {} },
      { silentError: true },
    )
    return data
  } catch (err) {
    const body = err?.response?.data
    if (body && typeof body === 'object') return body
    return { ok: false, error: 'Action failed — try again' }
  }
}

export const peoplesoftApi = {
  getState: (sessionId, scenario = '') => getState(sessionId, scenario),
  action: (sessionId, act, payload = {}) => action(sessionId, act, payload),
  // ── Convenience wrappers for the common PIA verbs ──
  login: (sessionId, oprid) => action(sessionId, 'login', oprid ? { oprid } : {}),
  logout: (sessionId) => action(sessionId, 'logout', {}),
  navigate: (sessionId, component) => action(sessionId, 'navigate', { component }),
  runProcess: (sessionId, name) => action(sessionId, 'run_process', { name }),
  rerunProcess: (sessionId, instance) => action(sessionId, 'rerun_process', { instance }),
  cancelProcess: (sessionId, instance) => action(sessionId, 'cancel_process', { instance }),
  assignRole: (sessionId, user, role) => action(sessionId, 'assign_role', { user, role }),
  removeRole: (sessionId, user, role) => action(sessionId, 'remove_role', { user, role }),
  addPermission: (sessionId, permission_list, permission) => action(sessionId, 'add_permission', { permission_list, permission }),
  addPermlistToRole: (sessionId, role, permission_list) => action(sessionId, 'add_permlist_to_role', { role, permission_list }),
  unlockUser: (sessionId, oprid) => action(sessionId, 'unlock_user', { oprid }),
  resetPassword: (sessionId, oprid) => action(sessionId, 'reset_password', { oprid }),
  enableUser: (sessionId, oprid) => action(sessionId, 'enable_user', { oprid }),
  disableUser: (sessionId, oprid) => action(sessionId, 'disable_user', { oprid }),
  restartIbNode: (sessionId, node) => action(sessionId, 'restart_ib_node', { node }),
  activateService: (sessionId, service) => action(sessionId, 'activate_service', { service }),
  setComponentConfig: (sessionId, component, config) => action(sessionId, 'set_component_config', { component, config }),
  reset: (sessionId) => action(sessionId, 'reset', {}),

  release: (sessionId) => {
    if (!sessionId) return Promise.resolve({ released: true })
    return api.post(`/vmware/peoplesoft/sessions/${sessionId}/release/`, {}, { silentError: true })
      .then(r => r.data)
      .catch(() => ({ released: true }))
  },
}
