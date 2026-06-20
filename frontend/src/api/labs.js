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

  // Rule-based AI Mentor (free, NO LLM). Sends the user's current code + the
  // latest run/test output and gets back explanations, concept teaching, and
  // style/security suggestions. NEVER returns the reference solution unless
  // `unlock_reference: true` is passed (the UI gates that behind a confirm).
  async codeMentor(sessionId, payload) {
    const { data } = await api.post(`/labs/${sessionId}/mentor/`, payload, { silentError: true })
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

  // Segmented leaderboard. `opts` = { technology, scope: 'all'|'weekly', pageSize }.
  // The backend tolerates unknown/garbage params and never 500s.
  async getLeaderboard(opts = {}) {
    // Back-compat: a bare technology id/slug may be passed positionally.
    const { technology, scope, pageSize } =
      typeof opts === 'object' && opts !== null ? opts : { technology: opts }
    const params = new URLSearchParams()
    if (technology) params.set('technology', technology)
    if (scope && scope !== 'all') params.set('scope', scope)
    if (pageSize) params.set('page_size', pageSize)
    const qs = params.toString()
    const { data } = await api.get(`/leaderboard/${qs ? `?${qs}` : ''}`, { silentError: true })
    return data
  },

  async getUserPlan() {
    const { data } = await api.get('/plan/')
    return data
  },
}
