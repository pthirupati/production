import api from './client'

/** Certification tracks API. List/detail/verify are public; exam actions need auth. */
export const certApi = {
  async list() {
    const { data } = await api.get('/certifications/', { silentError: true })
    return data // { tracks: [...] }
  },

  async detail(slug) {
    const { data } = await api.get(`/certifications/${slug}/`, { silentError: true })
    return data
  },

  async startExam(slug) {
    const { data } = await api.post(`/certifications/${slug}/exam/start/`)
    return data
  },

  async exam(id) {
    const { data } = await api.get(`/certifications/exam/${id}/`)
    return data
  },

  async submitExam(id) {
    const { data } = await api.post(`/certifications/exam/${id}/submit/`)
    return data
  },

  async myCertificates() {
    const { data } = await api.get('/certifications/certificates/')
    return data
  },

  async verify(certificateId) {
    const { data } = await api.get('/certifications/certificate/verify/', {
      params: { id: certificateId },
      silentError: true,
    })
    return data
  },
}
