import api from './client'

export const jiraApi = {
  getUserTickets: () => api.get('/jira/tickets/'),
  getScenarioTicket: (scenarioId, params = {}) =>
    api.get(`/jira/tickets/scenario/${scenarioId}/`, { params }),
  ensureScenarioTicket: (scenarioId) => api.post(`/jira/tickets/scenario/${scenarioId}/`),
  getIssue: (issueKey) => api.get(`/jira/issues/${issueKey}/`),
  transitionIssue: (issueKey, status) =>
    api.post(`/jira/issues/${issueKey}/transition/`, { status }),
  addComment: (issueKey, text) =>
    api.post(`/jira/issues/${issueKey}/comments/`, { text }),
}
