import api from './client'

/** Public Tutorials API (no auth required). */
export const tutorialApi = {
  async list(topic = '') {
    const params = topic ? { topic } : undefined
    const { data } = await api.get('/tutorials/', { params, silentError: true })
    return data // { tutorials: [...], topics: [...] }
  },

  async detail(slug) {
    const { data } = await api.get(`/tutorials/${slug}/`, { silentError: true })
    return data
  },
}
