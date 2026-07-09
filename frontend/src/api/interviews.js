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
  // Deterministic, local resume score + tips (no paid API). Pass the chosen
  // technology id / role / level so the score reflects the target. Backend:
  // POST /interviews/profile/resume-score/. Returns
  // { overall_score, subscores, matched_keywords, missing_keywords, tips, has_resume }.
  scoreResume(payload = {}) {
    return api.post('/interviews/profile/resume-score/', payload, { silentError: true }).then(r => r.data)
  },
  listCampaigns() {
    return api.get('/interviews/campaigns/', { silentError: true }).then(r => r.data)
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
  // WS8: hard-delete a past/COMPLETED interview from history.
  // DELETE /api/interviews/<campaign_id>/ -> { deleted: true, id }.
  // Returns 409 { error, status } for in_progress/scheduled interviews
  // (caller should toast and keep the row); 404 for non-owned ids (no IDOR).
  deleteHistory(id) {
    return api.delete(`/interviews/${id}/`, { silentError: true }).then(r => r.data)
  },
  getCampaign(id) {
    return api.get(`/interviews/campaigns/${id}/`).then(r => r.data)
  },
  getRound(id, { silent = false } = {}) {
    return api.get(`/interviews/rounds/${id}/`, silent ? { silentError: true } : undefined).then(r => r.data)
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
  pauseRound(id) {
    return api.post(`/interviews/rounds/${id}/pause/`).then(r => r.data)
  },
  resumeRound(id) {
    return api.post(`/interviews/rounds/${id}/resume/`).then(r => r.data)
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

  // Validate an inline practical command/code answer for the current question.
  // Deterministic + free (reuses the labs grading engines). Backend:
  // POST /interviews/rounds/:id/practical-validate/.
  // Returns { validated, method, feedback, question_id }.
  validatePractical(roundId, answer) {
    return api.post(`/interviews/rounds/${roundId}/practical-validate/`, { answer }).then(r => r.data)
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
    return api.get('/interviews/sample/', { silentError: true }).then(r => r.data)
  },

  startSampleInterview() {
    return api.post('/interviews/sample/').then(r => r.data)
  },

  deleteRound(roundId) {
    return api.delete(`/interviews/rounds/${roundId}/`).then(r => r.data)
  },

  // --- Parity features (NEW endpoints) ---

  // Performance analytics: candidate trend + competency radar + headline stats.
  getMyAnalytics() {
    return api.get('/interviews/analytics/me/', { silentError: true }).then(r => r.data)
  },
  // Recruiter candidate comparison/ranking (403 unless staff or has sent an invite).
  compareCandidates(params = {}) {
    return api.get('/interviews/analytics/compare/', { params, silentError: true }).then(r => r.data)
  },

  // Interview templates / job-role library.
  listTemplates() {
    return api.get('/interviews/templates/', { silentError: true }).then(r => r.data)
  },
  getTemplate(id) {
    return api.get(`/interviews/templates/${id}/`).then(r => r.data)
  },
  // One-click launch of an interview from a template. mode: 'live' | 'async_video'.
  launchTemplate(id, mode = 'live') {
    return api.post(`/interviews/templates/${id}/launch/`, { mode }).then(r => r.data)
  },

  // Candidate invitation flow (shareable links).
  listInvitations() {
    return api.get('/interviews/invitations/', { silentError: true }).then(r => r.data)
  },
  createInvitation(payload) {
    return api.post('/interviews/invitations/', payload).then(r => r.data)
  },
  revokeInvitation(id) {
    return api.delete(`/interviews/invitations/${id}/`).then(r => r.data)
  },
  // Public preview of an invite by token (no auth required).
  getInvitation(token) {
    return api.get(`/interviews/invite/${token}/`, { silentError: true }).then(r => r.data)
  },
  acceptInvitation(token) {
    return api.post(`/interviews/invite/${token}/accept/`).then(r => r.data)
  },

  // One-way async video interview.
  getAsyncPrompts(roundId) {
    return api.get(`/interviews/rounds/${roundId}/async/prompts/`).then(r => r.data)
  },
  startAsyncRound(roundId) {
    return api.post(`/interviews/rounds/${roundId}/async/prompts/`).then(r => r.data)
  },
  // Submit one recorded answer. `blob` is the MediaRecorder Blob (optional).
  submitAsyncResponse(roundId, { questionIndex, transcript, durationSeconds, blob }) {
    const form = new FormData()
    form.append('question_index', String(questionIndex))
    form.append('transcript', transcript || '')
    form.append('duration_seconds', String(durationSeconds || 0))
    if (blob) form.append('video', blob, `answer-${questionIndex}.webm`)
    return api.post(`/interviews/rounds/${roundId}/async/response/`, form).then(r => r.data)
  },
  finalizeAsyncRound(roundId) {
    return api.post(`/interviews/rounds/${roundId}/async/finalize/`).then(r => r.data)
  },
  getAsyncReview(roundId) {
    return api.get(`/interviews/rounds/${roundId}/async/review/`).then(r => r.data)
  },

  // Rich transcript w/ timestamps + résumé highlights mapped to questions.
  getRoundTranscript(roundId) {
    return api.get(`/interviews/rounds/${roundId}/transcript/`, { silentError: true }).then(r => r.data)
  },
}
