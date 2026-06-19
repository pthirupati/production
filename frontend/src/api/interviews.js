import api from './client'

export const interviewsApi = {
  getPlans() {
    return api.get('/interviews/plans/', { silentError: true }).then(r => r.data)
  },
  getEntitlement() {
    return api.get('/interviews/entitlement/', { silentError: true }).then(r => r.data)
  },
  getVoices() {
    return api.get('/interviews/voices/').then(r => r.data)
  },
  getProfile() {
    return api.get('/interviews/profile/', { silentError: true }).then(r => r.data)
  },
  updateProfile(data, resumeFile) {
    const payload = {
      primary_technology: data.primary_technology || null,
      secondary_technologies: Array.isArray(data.secondary_technologies) ? data.secondary_technologies : [],
      experience_level: data.experience_level || 'mid',
      years_experience: Number(data.years_experience) || 0,
      current_company: data.current_company || '',
      current_package_lpa: data.current_package_lpa ?? null,
      target_role: data.target_role || '',
      target_companies: Array.isArray(data.target_companies) ? data.target_companies : [],
      voice_id: data.voice_id || 'indian-female',
      voice_locale: data.voice_locale || '',
      location: data.location || '',
      notice_period_days: data.notice_period_days ?? null,
      resume_text: data.resume_text || '',
    }

    if (resumeFile) {
      const form = new FormData()
      Object.entries(payload).forEach(([k, v]) => {
        if (v === undefined || v === null) return
        form.append(k, typeof v === 'object' ? JSON.stringify(v) : String(v))
      })
      form.append('resume', resumeFile)
      return api.put('/interviews/profile/', form).then(r => r.data)
    }

    return api.put('/interviews/profile/', payload).then(r => r.data)
  },
  listCampaigns() {
    return api.get('/interviews/campaigns/').then(r => r.data)
  },
  createCampaign(payload) {
    return api.post('/interviews/campaigns/', payload).then(r => r.data)
  },
  cancelCampaign(id) {
    return api.delete(`/interviews/campaigns/${id}/`).then(r => r.data)
  },
  archiveCampaign(id) {
    return api.delete(`/interviews/campaigns/${id}/`).then(r => r.data)
  },
  getCampaign(id) {
    return api.get(`/interviews/campaigns/${id}/`).then(r => r.data)
  },
  getRound(id) {
    return api.get(`/interviews/rounds/${id}/`).then(r => r.data)
  },
  scheduleRound(id, scheduledAt) {
    return api.post(`/interviews/rounds/${id}/schedule/`, { scheduled_at: scheduledAt }).then(r => r.data)
  },
  startRound(id) {
    return api.post(`/interviews/rounds/${id}/start/`).then(r => r.data)
  },
  sendMessage(id, answer, extra = {}) {
    return api.post(`/interviews/rounds/${id}/message/`, { answer, ...extra }).then(r => r.data)
  },
  reportAv(id, micOn, cameraOn) {
    return api.post(`/interviews/rounds/${id}/av/`, { mic_on: micOn, camera_on: cameraOn }).then(r => r.data)
  },
  extendRound(id, minutes = 10) {
    return api.post(`/interviews/rounds/${id}/extend/`, { minutes }).then(r => r.data)
  },
  endRound(id, reason = 'completed') {
    return api.post(`/interviews/rounds/${id}/end/`, { reason }).then(r => r.data)
  },
  verifyCertificate(certificateId) {
    return api.get('/interviews/certificate/verify/', { params: { certificate_id: certificateId } }).then(r => r.data)
  },

  getVoiceConfig() {
    return api.get('/interviews/voice/config/').then(r => r.data)
  },

  getPendingJoinRequests(roundId) {
    return api.get(`/interviews/rounds/${roundId}/join-requests/`).then(r => r.data)
  },

  respondJoinRequest(requestId, approve) {
    return api.post(`/interviews/join-requests/${requestId}/respond/`, { approve }).then(r => r.data)
  },

  createRazorpayOrder(planCode) {
    return api.post('/interviews/billing/razorpay/order/', { plan_code: planCode }).then(r => r.data)
  },

  verifyRazorpayPayment(payload) {
    return api.post('/interviews/billing/razorpay/verify/', payload).then(r => r.data)
  },

  demoActivatePlan(planCode = 'pro') {
    return api.post('/interviews/billing/demo-activate/', { plan_code: planCode }).then(r => r.data)
  },

  startPracticalLab(roundId) {
    return api.post(`/interviews/rounds/${roundId}/practical-lab/`).then(r => r.data)
  },

  downloadRoundIcal(roundId) {
    return api.get(`/interviews/rounds/${roundId}/ical/`, { responseType: 'blob' }).then(r => r.data)
  },

  listCertificates() {
    return api.get('/interviews/certificates/').then(r => r.data)
  },

  deleteResume() {
    return api.delete('/interviews/profile/resume/').then(r => r.data)
  },

  exportTranscripts(download = false) {
    return api.get('/interviews/export/transcripts/', {
      params: download ? { format: 'download' } : {},
      responseType: download ? 'blob' : 'json',
    }).then(r => r.data)
  },

  createStripeCheckout(planCode, currency = 'USD') {
    return api.post('/interviews/billing/stripe/checkout/', { plan_code: planCode, currency }).then(r => r.data)
  },

  getSampleInfo() {
    return api.get('/interviews/sample/').then(r => r.data)
  },

  startSampleInterview() {
    return api.post('/interviews/sample/').then(r => r.data)
  },

  deleteRound(roundId) {
    return api.delete(`/interviews/rounds/${roundId}/`).then(r => r.data)
  },
}
