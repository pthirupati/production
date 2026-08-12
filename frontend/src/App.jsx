import { BrowserRouter } from 'react-router-dom'
import DismissableToaster from './components/DismissableToaster'
import { useEffect, useState } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import OfflineBanner from './components/OfflineBanner'
import ScrollToTop from './components/ScrollToTop'
import AppRouter from './router/AppRouter'
import ChangelogModal from './components/ChangelogModal'
import LegalReacceptanceModal from './components/LegalReacceptanceModal'
import useSessionTimeout from './hooks/useSessionTimeout'
import { useThemeStore } from './store/themeStore'
import { useAuthStore } from './store/authStore'
import { authApi } from './api/auth'
import { rehydrateAwsSimForUser, waitAwsPersistHydrated } from './utils/awsSimLifecycle'

function SessionMonitor() {
  useSessionTimeout()
  return null
}

function ThemeInit() {
  const initTheme = useThemeStore((s) => s.initTheme)
  useEffect(() => { initTheme() }, [])
  return null
}

/** Validate persisted auth against the server on boot; clear stale local state.
 * Gates children so LabRunner / AWS console never mount mid-rehydrate (race that
 * undoes AwsLabOverlay's clean-seed reset and can throw Lab environment error).
 */
function AuthBootValidator({ children }) {
  const [checked, setChecked] = useState(false)
  const logout = useAuthStore((s) => s.logout)
  const setAuth = useAuthStore((s) => s.setAuth)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        if (useAuthStore.getState().isAuthenticated) {
          try {
            const profile = await authApi.getProfile()
            if (cancelled) return
            const { accessToken, refreshToken } = useAuthStore.getState()
            setAuth(profile, accessToken, refreshToken)
            await rehydrateAwsSimForUser()
          } catch {
            if (!cancelled) logout()
            await waitAwsPersistHydrated()
          }
        } else {
          await waitAwsPersistHydrated()
        }
      } finally {
        if (!cancelled) setChecked(true)
      }
    })()
    return () => { cancelled = true }
  }, [logout, setAuth])

  if (!checked) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-surface-950">
        <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
      </div>
    )
  }
  return children
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeInit />
        <AuthBootValidator>
          <ScrollToTop />
          <OfflineBanner />
          <SessionMonitor />
          <DismissableToaster />
          <ChangelogModal />
          <LegalReacceptanceModal />
          <AppRouter />
        </AuthBootValidator>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
