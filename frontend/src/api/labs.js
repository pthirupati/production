import api from './client'

export const labApi = {
  async startLab(scenarioId) {
    const { data } = await api.post(`/labs/${scenarioId}/start/`)
    return data
  },

  async stopLab(sessionId) {
    const { data } = await api.post(`/labs/${sessionId}/stop/`)
    return data
  },

  async validateLab(sessionId) {
    const { data } = await api.post(`/labs/${sessionId}/validate/`)
    return data
  },

  // ── Coding IDE scenarios ──
  async getCodingSpec(sessionId) {
    const { data } = await api.get(`/labs/${sessionId}/coding-spec/`)
    return data
  },

  // Submit code for the authoritative backend grade (hidden tests). `payload`
  // is { language, files: {path: content}, entrypoint } or { language, code }.
  async codeValidate(sessionId, payload) {
    const { data } = await api.post(`/labs/${sessionId}/code-validate/`, payload)
    return data
  },

  // ── Prompt Engineering scenarios (rule-based, free — no LLM) ──
  // `submissions` is { exerciseId: promptText }. The backend re-checks each
  // prompt against the scenario's rubric and finalizes only when all pass.
  async promptValidate(sessionId, submissions) {
    const { data } = await api.post(`/labs/${sessionId}/prompt-validate/`, { submissions })
    return data
  },

  async getHints(sessionId) {
    const { data } = await api.get(`/labs/${sessionId}/hints/`)
    return data
  },

  async revealHint(sessionId) {
    const { data } = await api.post(`/labs/${sessionId}/hints/`)
    return data
  },

  async revealAiHint(sessionId) {
    const { data } = await api.post(`/labs/${sessionId}/ai-hint/`)
    return data
  },

  async getCommandHistory(sessionId) {
    const { data } = await api.get(`/labs/${sessionId}/commands/`)
    return data
  },

  async getSessionReplay(sessionId) {
    const { data } = await api.get(`/labs/${sessionId}/replay/`)
    return data
  },

  async getSessionSolution(sessionId) {
    const { data } = await api.get(`/labs/${sessionId}/solution/`)
    return data
  },

  async getSessionStatus(sessionId) {
    const { data } = await api.get(`/labs/${sessionId}/status/`)
    return data
  },

  async extendLab(sessionId) {
    const { data } = await api.post(`/labs/${sessionId}/extend/`)
    return data
  },

  async getAiReview(sessionId) {
    const { data } = await api.get(`/labs/${sessionId}/ai-review/`)
    return data
  },

  async generateAiReview(sessionId) {
    const { data } = await api.post(`/labs/${sessionId}/ai-review/`)
    return data
  },

  async getActiveLabs(statusFilter) {
    const params = statusFilter ? `?status=${statusFilter}` : ''
    const { data } = await api.get(`/labs/active/${params}`, { silentError: true })
    return data
  },

  async getProgress() {
    const { data } = await api.get('/progress/', { silentError: true })
    return data
  },

  async getAchievements() {
    const { data } = await api.get('/achievements/', { silentError: true })
    return data
  },

  async getAchievementsCertificate(technology) {
    const params = technology ? `?technology=${technology}` : ''
    const { data } = await api.get(`/achievements/certificate/${params}`)
    return data
  },

  async getLeaderboard(technologyId) {
    const params = technologyId ? `?technology=${technologyId}` : ''
    const { data } = await api.get(`/leaderboard/${params}`)
    return data
  },

  async getUserPlan() {
    const { data } = await api.get('/plan/')
    return data
  },
}
