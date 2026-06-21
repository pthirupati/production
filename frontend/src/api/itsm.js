import api from './client'

// ServiceNow-style ITSM ticketing for the lab runner. Endpoints are user-scoped
// and gated behind the same technology subscription as starting the lab.
export const itsmApi = {
  // Static vocabulary (types/states/priorities/teams) + the sub-ticket action
  // catalog used to render dropdowns.
  getMeta: () => api.get('/itsm/meta/', { silentError: true }),

  // The parent ticket for a scenario. POST ensures it exists (opens it on first
  // call) and binds it to the running lab session.
  getScenarioTicket: (scenarioId, params = {}) =>
    api.get(`/itsm/scenario/${scenarioId}/`, { params, silentError: true }),
  ensureScenarioTicket: (scenarioId, sessionId) =>
    api.post(`/itsm/scenario/${scenarioId}/`, { session_id: sessionId }),

  getTicket: (ticketId) => api.get(`/itsm/tickets/${ticketId}/`),
  transition: (ticketId, state, extra = {}) =>
    api.post(`/itsm/tickets/${ticketId}/transition/`, { state, ...extra }),
  transfer: (ticketId, team, reason = '') =>
    api.post(`/itsm/tickets/${ticketId}/transfer/`, { team, reason }),

  // Raise a child request to another team. `payload` is
  // { action_kind, team, short_description, description, action_params, auto_fulfil }.
  raiseSubTicket: (ticketId, payload) =>
    api.post(`/itsm/tickets/${ticketId}/sub-tickets/`, payload),
  // Explicitly let the assigned team action a (non-auto) sub-ticket.
  fulfil: (ticketId) => api.post(`/itsm/tickets/${ticketId}/fulfil/`),
}
