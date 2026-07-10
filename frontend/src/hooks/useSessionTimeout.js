import { useEffect, useRef } from 'react'
import { useAuthStore } from '../store/authStore'
import { authApi } from '../api/auth'
import toast from 'react-hot-toast'
import axios from 'axios'

/**
 * Monitors JWT token expiry and refreshes proactively.
 * - Parses the `exp` claim from the access token
 * - Warns user 5 minutes before expiry
 * - Attempts silent refresh 2 minutes before expiry
 * - Logs out if refresh fails
 * - Cookie-only sessions: periodic profile poll detects expiry
 */
export default function useSessionTimeout() {
  const { accessToken, refreshToken, setAuth, user, logout, isAuthenticated } = useAuthStore()
  const timerRef = useRef(null)
  const warnedRef = useRef(false)

  // Cookie-only sessions (no in-memory JWT): poll profile to detect expiry
  useEffect(() => {
    if (accessToken || !isAuthenticated) return

    const poll = async () => {
      try {
        await authApi.getProfile()
      } catch {
        toast.error('Session expired — please log in again', { duration: 5000 })
        logout()
        window.location.href = '/login'
      }
    }

    poll()
    const interval = setInterval(poll, 5 * 60_000)
    return () => clearInterval(interval)
  }, [accessToken, isAuthenticated, logout])

  useEffect(() => {
    if (!accessToken) return

    const payload = parseJwt(accessToken)
    if (!payload?.exp) return

    const checkExpiry = () => {
      const now = Math.floor(Date.now() / 1000)
      const remaining = payload.exp - now

      if (remaining <= 0) {
        doRefresh()
        return
      }

      if (remaining <= 300 && !warnedRef.current) {
        warnedRef.current = true
        doRefresh()
      }
    }

    checkExpiry()
    timerRef.current = setInterval(checkExpiry, 60_000)

    return () => {
      clearInterval(timerRef.current)
      warnedRef.current = false
    }
  }, [accessToken])

  async function doRefresh() {
    try {
      const payload = refreshToken ? { refresh: refreshToken } : {}
      const { data } = await axios.post('/api/auth/refresh/', payload, {
        withCredentials: true,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      if (data?.access) {
        setAuth(user, data.access, data.refresh || refreshToken)
        warnedRef.current = false
        return
      }
      if (!refreshToken && useAuthStore.getState().isAuthenticated) {
        warnedRef.current = false
        return
      }
      throw new Error('no access token')
    } catch {
      toast.error('Session expired — please log in again', { duration: 5000 })
      logout()
      window.location.href = '/login'
    }
  }
}

function parseJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(base64))
  } catch {
    return null
  }
}
