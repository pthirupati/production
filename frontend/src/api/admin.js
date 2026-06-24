import api from './client'

export const adminApi = {
  // Overview
  async getOverview() {
    const { data } = await api.get('/admin/overview/')
    return data
  },

  async getHealth() {
    const { data } = await api.get('/admin/health/', { silentError: true })
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

  // Lab Provisioning — per-technology re-seed (checkbox UI)
  async getProvisioningTechnologies() {
    const { data } = await api.get('/admin/lab-provisioning/')
    return data
  },

  async provisionTechnologies(slugs) {
    // slugs: array of folder slugs OR a comma-separated string
    const { data } = await api.post('/admin/lab-provisioning/', { technologies: slugs })
    return data
  },

  async getAnalytics(days = 30, refresh = false) {
    const q = refresh ? '&refresh=1' : ''
    const { data } = await api.get(`/admin/analytics/?days=${days}${q}`)
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

  async deleteTechnology(id, options = {}) {
    const { data } = await api.delete(`/admin/technologies/${id}/`, {
      params: options.cascade ? { cascade: 'true' } : {},
    })
    return data
  },

  async getCertificates(params = {}) {
    const { data } = await api.get('/admin/certificates/', { params })
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

  async getEnvSecrets() {
    const { data } = await api.get('/admin/env-secrets/', { silentError: true })
    return data
  },

  async testPaymentGateway() {
    const { data } = await api.post('/admin/payments/test-gateway/', {}, { silentError: true })
    return data
  },

  async syncEnvSecrets(updates) {
    const { data } = await api.post('/admin/env-secrets/sync/', { updates })
    return data
  },

  async getMonitoringContainers(kind = 'all') {
    const qs = kind && kind !== 'all' ? `?kind=${kind}` : ''
    const { data } = await api.get(`/admin/monitoring/containers/${qs}`, { silentError: true })
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

  // Fleet server monitoring (CPU/mem/disk/load per node)
  async getNodeMetrics() {
    const { data } = await api.get('/admin/monitoring/metrics/')
    return data
  },

  async getFleetMetrics() {
    const { data } = await api.get('/admin/monitoring/fleet/', { silentError: true })
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

  // ── ITSM / ServiceNow tickets (cross-user admin management) ──
  async getItsmTickets(filters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v) })
    const qs = params.toString()
    const { data } = await api.get(`/admin/itsm/tickets/${qs ? '?' + qs : ''}`)
    return data
  },
  async getItsmMeta() {
    const { data } = await api.get('/admin/itsm/meta/')
    return data
  },
  // payload: { short_description, description?, ticket_type?, priority?, assignment_group?, user_id?, scenario_id? }
  async createItsmTicket(payload) {
    const { data } = await api.post('/admin/itsm/tickets/create/', payload)
    return data
  },
  async getItsmTicket(ticketId) {
    const { data } = await api.get(`/admin/itsm/tickets/${ticketId}/`)
    return data
  },
  // action: 'transition' | 'transfer' | 'comment' | 'sub_ticket' | 'fulfil'
  async itsmTicketAction(ticketId, payload) {
    const { data } = await api.post(`/admin/itsm/tickets/${ticketId}/action/`, payload)
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

  async getSecurityDetail(metric, days = 7) {
    const { data } = await api.get(`/admin/security/?days=${days}&detail=${metric}`)
    return data
  },

  async securityAction(payload) {
    const { data } = await api.post('/admin/security/actions/', payload)
    return data
  },

  // Clear/reset the records behind a single security metric (or all of them).
  // action e.g. 'clear_failed_logins', 'clear_otp_failures', 'clear_lockouts',
  // 'clear_payment_failures', 'clear_email_failures', 'clear_rate_limit_hits',
  // 'clear_lab_resets', 'clear_security_alerts', 'clear_all'.
  async clearSecurityMetric(action) {
    const { data } = await api.post('/admin/security/actions/', { action })
    return data
  },

  async resetPlatformSettings() {
    const { data } = await api.post('/admin/config/', { reset_defaults: true })
    return data
  },

  async getInterviewOverview() {
    const { data } = await api.get('/admin/interviews/overview/')
    return data
  },
  async getInterviewCampaigns() {
    const { data } = await api.get('/admin/interviews/campaigns/')
    return data
  },
  async getInterviewQuestions() {
    const { data } = await api.get('/admin/interviews/questions/')
    return data
  },
  async createInterviewQuestion(payload) {
    const { data } = await api.post('/admin/interviews/questions/', payload)
    return data
  },
  async updateInterviewQuestion(id, payload) {
    const { data } = await api.put(`/admin/interviews/questions/${id}/`, payload)
    return data
  },
  async deleteInterviewQuestion(id) {
    await api.delete(`/admin/interviews/questions/${id}/`)
    return { deleted: true }
  },
  async getInterviewAnswerCorpora(technologyId = '') {
    const params = technologyId ? { technology: technologyId } : undefined
    const { data } = await api.get('/admin/interviews/answer-corpora/', { params })
    return data
  },
  async uploadInterviewAnswerCorpus({ technology_id, file, title, raw_text }) {
    const form = new FormData()
    form.append('technology_id', String(technology_id))
    if (file) form.append('file', file)
    if (title) form.append('title', title)
    if (raw_text) form.append('raw_text', raw_text)
    const { data } = await api.post('/admin/interviews/answer-corpora/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
  async deleteInterviewAnswerCorpus(id) {
    await api.delete(`/admin/interviews/answer-corpora/${id}/`)
    return { deleted: true }
  },
  async grantInterviewEntitlement(payload) {
    const { data } = await api.post('/admin/interviews/entitlements/', payload)
    return data
  },
  async getInterviewSettings() {
    const { data } = await api.get('/admin/interviews/settings/')
    return data
  },
  async updateInterviewSettings(payload) {
    const { data } = await api.put('/admin/interviews/settings/', payload)
    return data
  },
  async getInterviewTiers() {
    const { data } = await api.get('/admin/interviews/tiers/')
    return data
  },
  async updateInterviewTier(pk, payload) {
    const { data } = await api.put(`/admin/interviews/tiers/${pk}/`, payload)
    return data
  },
  async getInterviewVoices() {
    const { data } = await api.get('/admin/interviews/voices/')
    return data
  },
  async createInterviewVoice(payload) {
    const { data } = await api.post('/admin/interviews/voices/', payload)
    return data
  },
  async updateInterviewVoice(pk, payload) {
    const { data } = await api.put(`/admin/interviews/voices/${pk}/`, payload)
    return data
  },
  async getInterviewLiveSessions() {
    const { data } = await api.get('/admin/interviews/live/')
    return data
  },
  async requestInterviewJoin(roundId, message) {
    const { data } = await api.post('/admin/interviews/join-request/', { round_id: roundId, message })
    return data
  },
  async getInterviewJoinRequests() {
    const { data } = await api.get('/admin/interviews/join-requests/')
    return data
  },
  async getInterviewObserverSession(token) {
    const { data } = await api.get(`/admin/interviews/observer/${token}/`)
    return data
  },
  async getInterviewEntitlements() {
    const { data } = await api.get('/admin/interviews/entitlements/')
    return data
  },

  // Technology maintenance
  async getTechMaintenance(pk) {
    const { data } = await api.get(`/admin/technologies/${pk}/maintenance/`)
    return data
  },
  async setTechMaintenance(pk, payload) {
    const { data } = await api.post(`/admin/technologies/${pk}/maintenance/`, payload)
    return data
  },

  // Technology subscribers (per-tech)
  async getTechSubscribers(pk) {
    const { data } = await api.get(`/admin/technologies/${pk}/subscribers/`)
    return data
  },

  // Technology email campaign
  async sendTechEmail(pk, payload) {
    const { data } = await api.post(`/admin/technologies/${pk}/email/`, payload)
    return data
  },

  // Technology stats overview
  async getTechStats() {
    const { data } = await api.get('/admin/technologies/stats/')
    return data
  },

  // Interview maintenance
  async getInterviewMaintenance() {
    const { data } = await api.get('/admin/interviews/maintenance/')
    return data
  },
  async setInterviewMaintenance(payload) {
    const { data } = await api.post('/admin/interviews/maintenance/', payload)
    return data
  },

  // ── Campaigns / Ads / Announcements ──
  async getCampaigns(params = {}) {
    const qs = new URLSearchParams(params).toString()
    const { data } = await api.get(qs ? `/admin/campaigns/?${qs}` : '/admin/campaigns/')
    return data
  },
  async createCampaign(payload) {
    const { data } = await api.post('/admin/campaigns/', payload)
    return data
  },
  async updateCampaign(id, payload) {
    const { data } = await api.patch(`/admin/campaigns/${id}/`, payload)
    return data
  },
  async setCampaignStatus(id, action) {
    // action: 'enable' | 'cancel' | 'draft'
    const { data } = await api.patch(`/admin/campaigns/${id}/`, { action })
    return data
  },
  async deleteCampaign(id) {
    const { data } = await api.delete(`/admin/campaigns/${id}/`)
    return data
  },
  async generateSocialPosts(payload) {
    const { data } = await api.post('/admin/campaigns/social/', payload)
    return data
  },

  // Teams/Org sales inquiries + custom quotes
  async getSalesInquiries(status = '') {
    const q = status ? `?status=${encodeURIComponent(status)}` : ''
    const { data } = await api.get(`/admin/sales/${q}`)
    return data
  },
  async updateSalesInquiry(id, payload) {
    const { data } = await api.patch(`/admin/sales/${id}/`, payload)
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
