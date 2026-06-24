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

  /** Authenticated dashboard panel — progress + active exams per track. */
  async dashboard() {
    const { data } = await api.get('/certifications/dashboard/')
    return data // { tracks: [...] }
  },

  async createRazorpayOrder(trackSlug) {
    const { data } = await api.post('/certifications/billing/razorpay/order/', { track_slug: trackSlug })
    return data
  },

  async verifyRazorpayPayment({ track_slug, razorpay_order_id, razorpay_payment_id, razorpay_signature }) {
    const { data } = await api.post('/certifications/billing/razorpay/verify/', {
      track_slug,
      razorpay_order_id,
      razorpay_payment_id,
      razorpay_signature,
    })
    return data
  },
}

/** Admin (IsPlatformAdmin) certification-track management — mirrors adminApi.*Technology. */
export const certAdminApi = {
  async getTracks() {
    const { data } = await api.get('/certifications/admin/tracks/')
    return data // { tracks: [...] }
  },

  async updateTrack(id, payload) {
    const { data } = await api.put(`/certifications/admin/tracks/${id}/`, payload)
    return data
  },

  async getTrackScenarios(id) {
    const { data } = await api.get(`/certifications/admin/tracks/${id}/scenarios/`)
    return data // { track, scenario_count, objectives: [...] }
  },
}
