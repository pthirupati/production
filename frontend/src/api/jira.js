import api from './client'

export const jiraApi = {
  getUserTickets: () => api.get('/jira/tickets/'),
  getScenarioTicket: (scenarioId) => api.get(`/jira/tickets/scenario/${scenarioId}/`),
}
