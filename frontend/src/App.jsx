import { BrowserRouter } from 'react-router-dom'
import DismissableToaster from './components/DismissableToaster'
import { useEffect } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import OfflineBanner from './components/OfflineBanner'
import ScrollToTop from './components/ScrollToTop'
import AppRouter from './router/AppRouter'
import ChangelogModal from './components/ChangelogModal'
import useSessionTimeout from './hooks/useSessionTimeout'
import { useThemeStore } from './store/themeStore'

function SessionMonitor() {
  useSessionTimeout()
  return null
}

function ThemeInit() {
  const initTheme = useThemeStore((s) => s.initTheme)
  useEffect(() => { initTheme() }, [])
  return null
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeInit />
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
