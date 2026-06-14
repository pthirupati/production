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
}
