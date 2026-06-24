import api from './client'

/** Public Tutorials API (no auth required). */
export const tutorialApi = {
  async list(topic = '') {
    const params = topic ? { topic } : undefined
    const { data } = await api.get('/tutorials/', { params, silentError: true })
    // Tolerate any response shape: { tutorials, topics }, a bare array, or a
    // DRF { results } envelope — so a backend/serializer change can't blank the page.
    const tutorials = Array.isArray(data) ? data : (data?.tutorials ?? data?.results ?? [])
    const topics = data?.topics ?? [...new Set(tutorials.map((t) => t.topic).filter(Boolean))]
    return { tutorials, topics }
  },

  async detail(slug) {
    const { data } = await api.get(`/tutorials/${slug}/`, { silentError: true })
    return data
  },

  async curriculum() {
    const { data } = await api.get('/tutorials/curriculum/', { silentError: true })
    return data // { curriculum: [{ topic, tutorial_count, total_sections, tutorials }] }
  },
}
