import api from './client'

export const orgApi = {
  async list() {
    const { data } = await api.get('/org/')
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
  async cancelInvite(slug, inviteId) {
    const { data } = await api.delete(`/org/${slug}/invites/${inviteId}/`)
    return data
  },
}
