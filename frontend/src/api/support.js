import api from './client'

export const supportApi = {
  async getConfig() {
    const { data } = await api.get('/support/config/')
    return data
  },

  async sendMessage(message, pagePath = '') {
    const { data } = await api.post('/support/chat/', { message, page_path: pagePath })
    return data
  },
}
