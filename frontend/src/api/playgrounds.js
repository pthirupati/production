import api from './client'

/**
 * Public Playgrounds API (no auth, ephemeral, rate-limited).
 *
 * The client mints a per-tab ephemeral session id and sends it with each
 * action; it only keys the server's in-memory sandbox and is never persisted.
 */
function newSessionId() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  } catch {
    /* fall through */
  }
  return `pg-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export const playgroundApi = {
  newSessionId,

  async list() {
    const { data } = await api.get('/playgrounds/', { silentError: true })
    return data // { playgrounds: [...] }
  },

  async detail(slug) {
    const { data } = await api.get(`/playgrounds/${slug}/`, { silentError: true })
    return data
  },

  async run(slug, { session, input, stdin } = {}) {
    // 400 here means a normal "command failed / invalid SQL" result the page
    // should render inline — not a thrown error. We return the body either way.
    try {
      const { data } = await api.post(
        `/playgrounds/${slug}/run/`,
        { session, input, stdin },
        { silentError: true },
      )
      return data
    } catch (err) {
      const data = err?.response?.data
      if (data) return data
      throw err
    }
  },

  async reset(slug, session) {
    try {
      const { data } = await api.post(
        `/playgrounds/${slug}/reset/`,
        { session },
        { silentError: true },
      )
      return data
    } catch {
      return { reset: true }
    }
  },
}
