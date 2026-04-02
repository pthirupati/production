import api from './client'

export const ratingsApi = {
  async submitRating({ ratingType = 'platform', scenario, score, review = '' }) {
    const { data } = await api.post('/ratings/rate/', {
      rating_type: ratingType,
      scenario,
      score,
      review,
    })
    return data
  },

  async getRatings({ type = 'platform', scenario } = {}) {
    const params = new URLSearchParams({ type })
    if (scenario) params.set('scenario', scenario)
    const { data } = await api.get(`/ratings/?${params}`)
    return data
  },
}
