import { useState, useEffect } from 'react'
import { WifiOff } from 'lucide-react'

/**
 * Shows a fixed banner when the user goes offline.
 * Auto-hides when connectivity is restored.
 */
export default function OfflineBanner() {
  const [offline, setOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const goOffline = () => setOffline(true)
    const goOnline = () => setOffline(false)

    window.addEventListener('offline', goOffline)
    window.addEventListener('online', goOnline)
    return () => {
      window.removeEventListener('offline', goOffline)
      window.removeEventListener('online', goOnline)
    }
  }, [])

  if (!offline) return null

  return (
    <div
      className="fixed top-0 inset-x-0 z-[100] bg-accent-red/95 text-white text-sm text-center py-2 px-4 flex items-center justify-center gap-2 shadow-lg"
      role="alert"
      aria-live="assertive"
    >
      <WifiOff size={16} />
      <span>You're offline. Some features may be unavailable.</span>
    </div>
  )
}
