import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert, X } from 'lucide-react'
import { authApi } from '../api/auth'
import { useAuthStore } from '../store/authStore'

// "Turn on two-factor" suggestion for accounts holding resume / interview data
// (audit Z2-3). Recommended, never required — this must not block anything.
//
// The server decides who sees it (`mfa_recommended`), not the client. Putting the
// rule here would mean re-implementing "does this account hold sensitive career
// data" in JavaScript, and the two copies would drift.
//
// Dismissal is persisted server-side (30-day snooze) rather than in localStorage,
// so it follows the person to their next device instead of re-nagging them there.

export default function MfaRecommendationBanner() {
  const { isAuthenticated } = useAuthStore()
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) { setShow(false); return }
    let cancelled = false
    authApi.getProfile()
      .then((p) => { if (!cancelled) setShow(Boolean(p?.mfa_recommended)) })
      // A failed profile fetch must not surface a security banner on guesswork.
      .catch(() => { if (!cancelled) setShow(false) })
    return () => { cancelled = true }
  }, [isAuthenticated])

  if (!show) return null

  const dismiss = async () => {
    setBusy(true)
    // Hidden immediately either way: if the request fails the banner returns on
    // the next page load, which is better than leaving it stuck on screen.
    setShow(false)
    try {
      await authApi.dismissMfaPrompt()
    } catch { /* snooze not saved; it will reappear next time */ } finally {
      setBusy(false)
    }
  }

  return (
    <div className="glass-card border-accent-amber/25 p-4 mb-6 flex items-start gap-3">
      <div className="w-9 h-9 rounded-lg bg-accent-amber/10 border border-accent-amber/20 flex items-center justify-center shrink-0">
        <ShieldAlert size={17} className="text-accent-amber" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white">Protect your interview data</p>
        <p className="text-sm text-surface-400 mt-0.5">
          Your account holds your resume and interview history. Two-factor
          authentication means a stolen password is not enough to reach it.
        </p>
        <div className="flex items-center gap-4 mt-3">
          <Link to="/profile" className="btn-primary text-sm px-4 py-1.5">
            Set it up
          </Link>
          <button
            type="button"
            onClick={dismiss}
            disabled={busy}
            className="text-sm text-surface-400 hover:text-surface-200 transition-colors"
          >
            Not now
          </button>
        </div>
      </div>
      <button
        type="button"
        onClick={dismiss}
        disabled={busy}
        className="text-surface-500 hover:text-white transition-colors shrink-0"
        aria-label="Dismiss"
      >
        <X size={16} />
      </button>
    </div>
  )
}
