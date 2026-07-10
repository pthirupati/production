import { BrowserRouter } from 'react-router-dom'
import DismissableToaster from './components/DismissableToaster'
import { useEffect, useState } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import OfflineBanner from './components/OfflineBanner'
import ScrollToTop from './components/ScrollToTop'
import AppRouter from './router/AppRouter'
import ChangelogModal from './components/ChangelogModal'
import useSessionTimeout from './hooks/useSessionTimeout'
import { useThemeStore } from './store/themeStore'
import { useAuthStore } from './store/authStore'
import { authApi } from './api/auth'
import { rehydrateAwsSimForUser } from './components/aws/store/awsStore'

function SessionMonitor() {
  useSessionTimeout()
  return null
}

function ThemeInit() {
  const initTheme = useThemeStore((s) => s.initTheme)
  useEffect(() => { initTheme() }, [])
  return null
}

/** Validate persisted auth against the server on boot; clear stale local state. */
function AuthBootValidator() {
  const [checked, setChecked] = useState(() => !useAuthStore.getState().isAuthenticated)
  const logout = useAuthStore((s) => s.logout)
  const setAuth = useAuthStore((s) => s.setAuth)

  useEffect(() => {
    if (checked) return
    let cancelled = false
    ;(async () => {
      try {
        const profile = await authApi.getProfile()
        if (cancelled) return
        const { accessToken, refreshToken } = useAuthStore.getState()
        setAuth(profile, accessToken, refreshToken)
        await rehydrateAwsSimForUser()
      } catch {
        if (!cancelled) logout()
      } finally {
        if (!cancelled) setChecked(true)
      }
    })()
    return () => { cancelled = true }
  }, [checked, logout, setAuth])

  if (!checked) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-surface-950">
        <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
      </div>
    )
  }
  return null
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeInit />
        <AuthBootValidator />
        <ScrollToTop />
        <OfflineBanner />
        <SessionMonitor />
        <DismissableToaster />
        <ChangelogModal />
        <AppRouter />
      </BrowserRouter>
    </ErrorBoundary>
  )
}
