import api from './client'
import { useAuthStore } from '../store/authStore'

export const authApi = {
  async sendOTP(email) {
    const { data } = await api.post('/auth/send-otp/', { email })
    return data
  },

  async verifyOTP(sessionToken, code) {
    const { data } = await api.post('/auth/verify-otp/', {
      session_token: sessionToken, code,
    })
    return data
  },

  async register(email, password, phoneNumber, sessionToken, firstName, lastName) {
    const { data } = await api.post('/auth/register/', {
      email, password, phone_number: phoneNumber || '',
      session_token: sessionToken,
      first_name: firstName || '',
      last_name: lastName || '',
    })
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    return data
  },

  async login(email, password) {
    const { data } = await api.post('/auth/login/', { email, password })
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    return data
  },

  async logout() {
    const store = useAuthStore.getState()
    const refreshToken = store.refreshToken
    try {
      if (refreshToken) {
        await api.post('/auth/logout/', { refresh: refreshToken })
      }
    } catch {
      // Ignore errors — still clear local state
    } finally {
      store.logout()
    }
  },

  async getProfile() {
    const { data } = await api.get('/auth/profile/')
    return data
  },

  async updateProfile(payload) {
    const { data } = await api.put('/auth/profile/', payload)
    return data
  },

  async changePassword(oldPassword, newPassword) {
    const { data } = await api.post('/auth/change-password/', {
      old_password: oldPassword,
      new_password: newPassword,
    })
    return data
  },

  async forgotPassword(email) {
    const { data } = await api.post('/auth/forgot-password/', { email })
    return data
  },

  async resetPassword(token, newPassword) {
    const { data } = await api.post('/auth/reset-password/', {
      token, new_password: newPassword,
    })
    return data
  },

  async getSocialConfig() {
    const { data } = await api.get('/auth/social/config/')
    return data
  },

  async socialLogin(provider, code, redirectUri, intent = 'login') {
    const { data } = await api.post(`/auth/social/${provider}/`, {
      code, redirect_uri: redirectUri, intent,
    })
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    return data
  },

  async getLabHistory() {
    const { data } = await api.get('/labs/history/')
    return data
  },

  async search(q) {
    const { data } = await api.get('/search/', { params: { q } })
    return data
  },
}
