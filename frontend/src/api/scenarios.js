import api from './client'

export const scenarioApi = {
  async getTechnologies() {
    const { data } = await api.get('/technologies/', { silentError: true })
    return data
  },

  async getTechnologyDetail(slug) {
    const { data } = await api.get(`/technologies/${slug}/`)
    return data
  },

  async getScenarios(filters = {}) {
    const params = new URLSearchParams()
    if (filters.technology) params.append('technology', filters.technology)
    if (filters.technology_slug) params.append('technology_slug', filters.technology_slug)
    if (filters.difficulty) params.append('difficulty', filters.difficulty)
    if (filters.type) params.append('type', filters.type)
    if (filters.category) params.append('category', filters.category)
    if (filters.tag) params.append('tag', filters.tag)
    if (filters.search) params.append('search', filters.search)
    if (filters.free === '1' || filters.free === '0') params.append('free', filters.free)
    if (filters.completed === '1' || filters.completed === '0') params.append('completed', filters.completed)
    if (filters.gradeable === '1' || filters.gradeable === '0') params.append('gradeable', filters.gradeable)
    if (filters.page) params.append('page', filters.page)
    const { data } = await api.get(`/scenarios/?${params}`)
    return data
  },

  async getScenarioDetail(slug) {
    const { data } = await api.get(`/scenarios/${slug}/`)
    return data
  },

  async getTags() {
    const { data } = await api.get('/tags/')
    return data
  },

  async getPlatformStats() {
    const { data } = await api.get('/stats/', { silentError: true })
    return data
  },

  async getBookmarks() {
    const { data } = await api.get('/bookmarks/', { silentError: true })
    return data
  },

  async toggleBookmark(scenarioId) {
    const { data } = await api.post('/bookmarks/', { scenario_id: scenarioId })
    return data
  },
}
