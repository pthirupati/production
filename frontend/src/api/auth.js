import api from './client'
import { useAuthStore } from '../store/authStore'
import { rehydrateAwsSimForUser, resetAwsSimOnLogout } from '../components/aws/store/awsStore'

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
    await rehydrateAwsSimForUser()
    return data
  },

  async login(email, password) {
    const { data } = await api.post('/auth/login/', { email, password })
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    await rehydrateAwsSimForUser()
    return data
  },

  async logout() {
    const store = useAuthStore.getState()
    const refreshToken = store.refreshToken
    try {
      // Always hit the logout endpoint so the backend can:
      //   1. Blacklist the refresh token (if provided in body)
      //   2. Clear the httpOnly access_token and refresh_token cookies
      // withCredentials is set globally on the axios instance so cookies are sent.
      await api.post('/auth/logout/', refreshToken ? { refresh: refreshToken } : {})
    } catch {
      // Ignore errors — still clear local state
    } finally {
      resetAwsSimOnLogout()
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

  async deleteAccount({ password, confirm, refresh }) {
    const { data } = await api.post('/auth/account/delete/', {
      password: password || '',
      confirm,
      refresh: refresh || null,
    })
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

  async socialLogin(provider, code, redirectUri, state = '') {
    const { data } = await api.post(`/auth/social/${provider}/`, {
      code, redirect_uri: redirectUri, state,
    })
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    await rehydrateAwsSimForUser()
    return data
  },

  async socialLink(provider, code, redirectUri, state = '') {
    const { data } = await api.post(`/auth/social/link/${provider}/`, {
      code, redirect_uri: redirectUri, state,
    })
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
