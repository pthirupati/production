import { useEffect, useRef } from 'react'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'
import axios from 'axios'

/**
 * Monitors JWT token expiry and refreshes proactively.
 * - Parses the `exp` claim from the access token
 * - Warns user 5 minutes before expiry
 * - Attempts silent refresh 2 minutes before expiry
 * - Logs out if refresh fails
 */
export default function useSessionTimeout() {
  const { accessToken, refreshToken, setAuth, user, logout } = useAuthStore()
  const timerRef = useRef(null)
  const warnedRef = useRef(false)

  useEffect(() => {
    if (!accessToken) return

    const payload = parseJwt(accessToken)
    if (!payload?.exp) return

    const checkExpiry = () => {
      const now = Math.floor(Date.now() / 1000)
      const remaining = payload.exp - now

      // Already expired
      if (remaining <= 0) {
        doRefresh()
        return
      }

      // Warn at 5 minutes
      if (remaining <= 300 && !warnedRef.current) {
        warnedRef.current = true
        toast('Your session expires soon. Refreshing...', { icon: '⏰', duration: 4000 })
        doRefresh()
      }
    }

    // Check every 60 seconds
    checkExpiry()
    timerRef.current = setInterval(checkExpiry, 60_000)

    return () => {
      clearInterval(timerRef.current)
      warnedRef.current = false
    }
  }, [accessToken])

  async function doRefresh() {
    if (!refreshToken) {
      logout()
      return
    }
    try {
      const { data } = await axios.post('/api/auth/refresh/', { refresh: refreshToken })
      setAuth(user, data.access, data.refresh || refreshToken)
      warnedRef.current = false
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
