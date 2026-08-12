import api from './client'
import { useAuthStore } from '../store/authStore'
import { useNotificationStore } from '../store/notificationStore'
import { useDataStore } from '../store/dataStore'
import { useLabStore } from '../store/labStore'
import { rehydrateAwsSimForUser, resetAwsSimOnLogout } from '../utils/awsSimLifecycle'

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

  async register(email, password, phoneNumber, sessionToken, firstName, lastName, acceptedLegal = true) {
    const { data } = await api.post('/auth/register/', {
      email, password, phone_number: phoneNumber || '',
      session_token: sessionToken,
      first_name: firstName || '',
      last_name: lastName || '',
      accepted_legal: Boolean(acceptedLegal),
    })
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    await rehydrateAwsSimForUser()
    return data
  },

  async login(email, password) {
    const { data } = await api.post('/auth/login/', { email, password })
    // Audit Z2-3: the password step returns a challenge, not a session, when the
    // account has MFA. Calling setAuth on that payload would store `undefined`
    // tokens and leave the app in a half-signed-in state that looks authenticated
    // to the router but fails every request.
    if (data.mfa_required) return data
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    await rehydrateAwsSimForUser()
    return data
  },

  /** Second login step: exchange the challenge + a code (or recovery code). */
  async verifyMfa({ mfaToken, code, recoveryCode }) {
    const { data } = await api.post('/auth/mfa/verify/', {
      mfa_token: mfaToken,
      ...(recoveryCode ? { recovery_code: recoveryCode } : { code }),
    })
    useAuthStore.getState().setAuth(data.user, data.access, data.refresh)
    await rehydrateAwsSimForUser()
    return data
  },

  async dismissMfaPrompt() {
    const { data } = await api.post('/auth/mfa/dismiss-prompt/')
    return data
  },

  async mfaStatus() {
    const { data } = await api.get('/auth/mfa/status/')
    return data
  },

  async mfaEnroll() {
    const { data } = await api.post('/auth/mfa/enroll/')
    return data
  },

  async mfaConfirm(code) {
    const { data } = await api.post('/auth/mfa/confirm/', { code })
    return data
  },

  async mfaDisable(password, code) {
    const { data } = await api.post('/auth/mfa/disable/', { password, code })
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
      // Clear EVERY per-user store, not just auth + the AWS sim.
      //
      // Logout is an SPA navigation (navigate('/login')), not a full reload, so
      // the JS heap survives. Previously only authStore and the AWS sim were
      // reset, which meant user A's notifications, unread badge, cached
      // technologies (with A's entitlement overlay) and active lab session were
      // still in memory when user B signed in on the same tab. Note the
      // forced-401 path in api/client.js uses window.location.href and so was
      // never affected — that asymmetry is why this went unnoticed.
      void resetAwsSimOnLogout()
      try { useNotificationStore.getState().reset() } catch { /* non-fatal */ }
      try { useDataStore.getState().reset() } catch { /* non-fatal */ }
      try { useLabStore.getState().clearSession() } catch { /* non-fatal */ }
      store.logout()
    }
  },

  async getProfile() {
    const { data } = await api.get('/auth/profile/')
    return data
  },

  async acceptTerms() {
    const { data } = await api.post('/auth/accept-terms/', {})
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
