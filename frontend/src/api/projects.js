import api from './client'

/** Capstone projects catalog — audit §C3 browse surface. */
export const projectApi = {
  async list(params = {}) {
    const { data } = await api.get('/projects/', { params, silentError: true })
    return data // { projects, count }
  },

  async get(slug) {
    const { data } = await api.get(`/projects/${slug}/`, { silentError: true })
    return data
  },

  async start(projectId) {
    const { data } = await api.post(`/projects/${projectId}/start/`)
    return data
  },
}
