import api from './client'

export const communityApi = {
  async getThreads(params = {}) {
    const searchParams = new URLSearchParams()
    if (params.technology) searchParams.set('technology', params.technology)
    if (params.search) searchParams.set('search', params.search)
    if (params.page) searchParams.set('page', params.page)
    const qs = searchParams.toString()
    const { data } = await api.get(`/community/threads/${qs ? `?${qs}` : ''}`)
    return data
  },

  async getThread(threadId) {
    const { data } = await api.get(`/community/threads/${threadId}/`)
    return data
  },

  async createThread(threadData) {
    const { data } = await api.post('/community/threads/', threadData)
    return data
  },

  async updateThread(threadId, updates) {
    const { data } = await api.patch(`/community/threads/${threadId}/`, updates)
    return data
  },

  async deleteThread(threadId) {
    await api.delete(`/community/threads/${threadId}/`)
  },

  async createReply(threadId, replyData) {
    const { data } = await api.post(`/community/threads/${threadId}/replies/`, replyData)
    return data
  },

  async updateReply(replyId, updates) {
    const { data } = await api.patch(`/community/replies/${replyId}/`, updates)
    return data
  },

  async deleteReply(replyId) {
    await api.delete(`/community/replies/${replyId}/`)
  },

  async voteThread(threadId, voteType = 'up') {
    const { data } = await api.post(`/community/threads/${threadId}/vote/`, { vote_type: voteType })
    return data
  },

  async voteReply(replyId, voteType = 'up') {
    const { data } = await api.post(`/community/replies/${replyId}/vote/`, { vote_type: voteType })
    return data
  },
}
