import api from './client'

export const jiraApi = {
  getUserTickets: () => api.get('/jira/tickets/'),
  getScenarioTicket: (scenarioId, params = {}) =>
    api.get(`/jira/tickets/scenario/${scenarioId}/`, { params }),
  ensureScenarioTicket: (scenarioId) => api.post(`/jira/tickets/scenario/${scenarioId}/`),
}
