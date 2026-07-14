import api from './client'

export const orgApi = {
  async list() {
    const { data } = await api.get('/org/')
    return data
  },
  async create(payload) {
    // payload: { name, billing_email?, seat_limit? }
    const { data } = await api.post('/org/create/', payload)
    return data
  },
  async get(slug) {
    const { data } = await api.get(`/org/${slug}/`)
    return data
  },
  async inviteMember(slug, email, role = 'member') {
    const { data } = await api.post(`/org/${slug}/`, { email, role })
    return data
  },
  async getAnalytics(slug) {
    const { data } = await api.get(`/org/${slug}/analytics/`)
    return data
  },
  async getMember(slug, userId) {
    const { data } = await api.get(`/org/${slug}/members/${userId}/`)
    return data
  },
  async removeMember(slug, userId) {
    const { data } = await api.delete(`/org/${slug}/members/${userId}/remove/`)
    return data
  },
  async leaveTeam(slug) {
    const { data } = await api.delete(`/org/${slug}/leave/`)
    return data
  },
  async deleteTeam(slug) {
    const { data } = await api.delete(`/org/${slug}/`)
    return data
  },
  async cancelInvite(slug, inviteId) {
    const { data } = await api.delete(`/org/${slug}/invites/${inviteId}/`)
    return data
  },
  async updateSettings(slug, settings) {
    const { data } = await api.patch(`/org/${slug}/settings/`, settings)
    return data
  },
}
