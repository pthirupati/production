import api from './client'

export const adminApi = {
  // Overview
  async getOverview() {
    const { data } = await api.get('/admin/overview/')
    return data
  },

  async getHealth() {
    const { data } = await api.get('/admin/health/')
    return data
  },

  async sendTestEmail(toEmail) {
    const { data } = await api.post('/admin/email/test/', toEmail ? { to_email: toEmail } : {})
    return data
  },

  async syncScenarios() {
    const { data } = await api.post('/admin/scenarios/sync/')
    return data
  },

  async getAnalytics(days = 30) {
    const { data } = await api.get(`/admin/analytics/?days=${days}`)
    return data
  },

  async getActivityFeed() {
    const { data } = await api.get('/admin/activity/')
    return data
  },

  async getAuditLogs(filters = {}) {
    const params = new URLSearchParams(filters)
    const { data } = await api.get(`/admin/audit-logs/?${params}`)
    return data
  },

  // Technologies
  async getTechnologies() {
    const { data } = await api.get('/admin/technologies/')
    return data
  },

  async createTechnology(payload) {
    const { data } = await api.post('/admin/technologies/', payload)
    return data
  },

  async updateTechnology(id, payload) {
    const { data } = await api.put(`/admin/technologies/${id}/`, payload)
    return data
  },

  async deleteTechnology(id) {
    const { data } = await api.delete(`/admin/technologies/${id}/`)
    return data
  },

  // Tags
  async getTags() {
    const { data } = await api.get('/admin/tags/')
    return data
  },

  async createTag(payload) {
    const { data } = await api.post('/admin/tags/', payload)
    return data
  },

  async updateTag(id, payload) {
    const { data } = await api.put(`/admin/tags/${id}/`, payload)
    return data
  },

  async deleteTag(id) {
    const { data } = await api.delete(`/admin/tags/${id}/`)
    return data
  },

  // Scenarios
  async getScenarios(filters = {}) {
    const params = new URLSearchParams(filters)
    const { data } = await api.get(`/admin/scenarios/?${params}`)
    return data
  },

  async getScenarioDetail(id) {
    const { data } = await api.get(`/admin/scenarios/${id}/`)
    return data
  },

  async createScenario(payload) {
    const { data } = await api.post('/admin/scenarios/', payload)
    return data
  },

  async updateScenario(id, payload) {
    const { data } = await api.put(`/admin/scenarios/${id}/`, payload)
    return data
  },

  async deleteScenario(id) {
    const { data } = await api.delete(`/admin/scenarios/${id}/`)
    return data
  },

  // Hints
  async addHint(scenarioId, payload) {
    const { data } = await api.post(`/admin/scenarios/${scenarioId}/hints/`, payload)
    return data
  },

  async updateHint(id, payload) {
    const { data } = await api.put(`/admin/hints/${id}/`, payload)
    return data
  },

  async deleteHint(id) {
    const { data } = await api.delete(`/admin/hints/${id}/`)
    return data
  },

  // Users
  async getUsers(filters = {}) {
    const params = new URLSearchParams(filters)
    const { data } = await api.get(`/admin/users/?${params}`)
    return data
  },

  async getUserDetail(id) {
    const { data } = await api.get(`/admin/users/${id}/`)
    return data
  },

  async createUser(payload) {
    const { data } = await api.post('/admin/users/', payload)
    return data
  },

  async updateUser(id, payload) {
    const { data } = await api.put(`/admin/users/${id}/`, payload)
    return data
  },

  async deleteUser(id) {
    const { data } = await api.delete(`/admin/users/${id}/`)
    return data
  },

  async bulkUserAction(userIds, action) {
    const { data } = await api.post('/admin/users/bulk/', { user_ids: userIds, action })
    return data
  },

  // Labs
  async getActiveLabs(params = {}) {
    const qs = new URLSearchParams(params).toString()
    const { data } = await api.get(qs ? `/admin/labs/active/?${qs}` : '/admin/labs/active/')
    return data
  },

  async bulkTerminateLabs(payload) {
    const { data } = await api.post('/admin/labs/bulk/', payload)
    return data
  },

  async terminateLab(sessionId) {
    const { data } = await api.post(`/admin/labs/${sessionId}/terminate/`)
    return data
  },

  async terminateIdleLabs() {
    const { data } = await api.post('/admin/labs/terminate-idle/')
    return data
  },

  // ── Data Exports (CSV downloads) ──

  async exportUsers() {
    const response = await api.get('/admin/export/users/', { responseType: 'blob' })
    downloadBlob(response.data, 'users.csv')
  },

  async exportLabs(days = 30) {
    const response = await api.get(`/admin/export/labs/?days=${days}`, { responseType: 'blob' })
    downloadBlob(response.data, 'labs.csv')
  },

  async exportProgress() {
    const response = await api.get('/admin/export/progress/', { responseType: 'blob' })
    downloadBlob(response.data, 'progress.csv')
  },

  // ── New Admin Features ──

  async getMaintenanceMode() {
    const { data } = await api.get('/admin/maintenance/')
    return data
  },

  async setMaintenanceMode(payload) {
    const body = typeof payload === 'object'
      ? payload
      : { enabled: payload, message: arguments[1] }
    const { data } = await api.post('/admin/maintenance/', body)
    return data
  },

  async getInactiveUsers(days = 90) {
    const { data } = await api.get(`/admin/users/inactive/?days=${days}`)
    return data
  },

  async getSubscriptionLogs(filters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v) })
    const qs = params.toString()
    const { data } = await api.get(`/admin/subscriptions/${qs ? '?' + qs : ''}`)
    return data
  },

  async getInvoices(filters = {}) {
    const params = new URLSearchParams(filters)
    const qs = params.toString()
    const { data } = await api.get(`/admin/invoices/${qs ? '?' + qs : ''}`)
    return data
  },

  async downloadInvoice(invoiceId) {
    return api.get(`/billing/invoices/${invoiceId}/download/`, { responseType: 'blob' })
  },

  async getThreads() {
    const { data } = await api.get('/admin/threads/')
    return data
  },

  async deleteThread(threadId) {
    const { data } = await api.delete(`/admin/threads/${threadId}/`)
    return data
  },

  async updateThread(threadId, updates) {
    const { data } = await api.patch(`/admin/threads/${threadId}/`, updates)
    return data
  },

  async getConfig() {
    const { data } = await api.get('/admin/config/')
    return data
  },

  async updateConfig(payload) {
    const { data } = await api.post('/admin/config/', payload)
    return data
  },


  async getMonitoringContainers(kind = 'all') {
    const qs = kind && kind !== 'all' ? `?kind=${kind}` : ''
    const { data } = await api.get(`/admin/monitoring/containers/${qs}`)
    return data
  },

  async uploadBanner(file, folder = 'platform', purpose = null) {
    const form = new FormData()
    form.append('file', file)
    form.append('folder', folder)
    if (purpose) form.append('purpose', purpose)
    const { data } = await api.post('/admin/upload/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async getMonitoringContainer(id) {
    const { data } = await api.get(`/admin/monitoring/containers/${id}/`)
    return data
  },

  async getMonitoringLogs(id, params = {}) {
    const qs = new URLSearchParams(params).toString()
    const { data } = await api.get(qs ? `/admin/monitoring/containers/${id}/logs/?${qs}` : `/admin/monitoring/containers/${id}/logs/`)
    return data
  },

  async getOverviewWithCurrency(currency = 'INR') {
    const { data } = await api.get(`/admin/overview/?currency=${currency}`)
    return data
  },

  async getJiraTickets(filters = {}) {
    const params = new URLSearchParams(filters)
    const { data } = await api.get(`/admin/jira/tickets/?${params}`)
    return data
  },

  async createJiraTicket(userId, scenarioId) {
    const { data } = await api.post('/admin/jira/tickets/create/', {
      user_id: userId,
      scenario_id: scenarioId,
    })
    return data
  },

  async getThreadDetail(threadId) {
    const { data } = await api.get(`/admin/threads/${threadId}/`)
    return data
  },

  async replyToThread(threadId, body) {
    const { data } = await api.post(`/admin/threads/${threadId}/`, { body })
    return data
  },

  async getCoupons() {
    const { data } = await api.get('/admin/coupons/')
    return data
  },

  async createCoupon(payload) {
    const { data } = await api.post('/admin/coupons/', payload)
    return data
  },

  async updateCoupon(id, payload) {
    const { data } = await api.put(`/admin/coupons/${id}/`, payload)
    return data
  },

  async deleteCoupon(id) {
    const { data } = await api.delete(`/admin/coupons/${id}/`)
    return data
  },

  async getOrganizations() {
    const { data } = await api.get('/admin/organizations/')
    return data
  },

  async createOrganization(payload) {
    const { data } = await api.post('/admin/organizations/', payload)
    return data
  },

  async addOrganizationMember(orgId, payload) {
    const { data } = await api.post(`/admin/organizations/${orgId}/`, payload)
    return data
  },

  async deactivateOrganization(orgId) {
    const { data } = await api.delete(`/admin/organizations/${orgId}/`)
    return data
  },

  async getSecurityMetrics(days = 7) {
    const { data } = await api.get(`/admin/security/?days=${days}`)
    return data
  },
}

/** Trigger a browser download for a Blob */
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
