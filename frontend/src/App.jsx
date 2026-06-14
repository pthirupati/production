import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useEffect } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import OfflineBanner from './components/OfflineBanner'
import ScrollToTop from './components/ScrollToTop'
import AppRouter from './router/AppRouter'
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
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 5000,
            closeButton: true,
            style: {
              background: 'rgb(var(--s-800))',
              color: 'rgb(var(--s-100))',
              border: '1px solid rgb(var(--s-700))',
            },
          }}
        />
        <AppRouter />
      </BrowserRouter>
    </ErrorBoundary>
  )
}
