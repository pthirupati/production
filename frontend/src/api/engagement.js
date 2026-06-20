import api from './client'

/**
 * Engagement-loop endpoints (daily challenge, streak calendar, XP/levels,
 * per-scenario stats). The backend handlers are written to NEVER 500, but every
 * call here also uses `silentError` and the callers fall back to safe defaults
 * so a transient failure degrades gracefully instead of breaking a page.
 */
export const engagementApi = {
  // GET /api/daily-challenge/ → { date, challenge: ScenarioListSerializer|null, completed? }
  async getDailyChallenge() {
    const { data } = await api.get('/daily-challenge/', { silentError: true })
    return data
  },

  // GET /api/streak/?days=N → { current_streak, longest_streak, total_active_days, days, calendar:{ISO:count} }
  async getStreak(days = 120) {
    const { data } = await api.get(`/streak/?days=${days}`, { silentError: true })
    return data
  },

  // GET /api/xp/ → { level, xp, xp_into_level, xp_for_next_level, progress_pct, next_level }
  async getXp() {
    const { data } = await api.get('/xp/', { silentError: true })
    return data
  },

  // GET /api/scenarios/<slug>/stats/ → { slug, learners, solved, completions,
  //   avg_solve_seconds, fail_rate_pct, avg_hints_used }
  async getScenarioStats(slug) {
    const { data } = await api.get(`/scenarios/${slug}/stats/`, { silentError: true })
    return data
  },
}
