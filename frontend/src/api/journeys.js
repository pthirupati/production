import api from './client'

/** Learning Journeys — role-based tracks that bundle existing content. */
export const journeyApi = {
  async list() {
    const { data } = await api.get('/journeys/', { silentError: true })
    // The endpoint is unpaginated by design, but tolerate a DRF envelope so
    // adding pagination later can't blank the page.
    return Array.isArray(data) ? data : (data?.results ?? [])
  },

  async detail(slug) {
    const { data } = await api.get(`/journeys/${slug}/`, { silentError: true })
    return data
  },

  /** The caller's in-progress journey and next incomplete step.
   *
   * Resolves to `{ journey: null, next_step: null }` when they haven't started
   * one. Deliberately does NOT catch: "the fetch failed" and "you have no
   * journey" are the same object once you swallow the rejection, and callers
   * need to tell them apart (audit L2317). `silentError` only suppresses the
   * global toast — the promise still rejects.
   */
  async getNext() {
    const { data } = await api.get('/journeys/next/', { silentError: true })
    return data ?? { journey: null, next_step: null }
  },
}
