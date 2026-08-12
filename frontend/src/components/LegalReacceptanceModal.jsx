import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText } from '../ui/eagerIcons'
import toast from 'react-hot-toast'
import ConfirmModal from './ConfirmModal'
import { authApi } from '../api/auth'
import { useAuthStore } from '../store/authStore'

/**
 * Blocking modal when the server says legal text moved on (audit Z4-8).
 *
 * Without this, bumping LEGAL_*_VERSION sets needs_legal_reacceptance forever
 * with no UI to call POST /api/auth/accept-terms/. Versions are stamped by
 * the server — the client only confirms it showed the current links.
 */
export default function LegalReacceptanceModal() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const user = useAuthStore((s) => s.user)
  const setAuth = useAuthStore((s) => s.setAuth)
  const accessToken = useAuthStore((s) => s.accessToken)
  const refreshToken = useAuthStore((s) => s.refreshToken)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) {
      setOpen(false)
      return
    }
    // Prefer the profile already loaded by AuthBootValidator; fall back to a fetch
    // if the persisted user predates the needs_legal_reacceptance field.
    if (typeof user?.needs_legal_reacceptance === 'boolean') {
      setOpen(Boolean(user.needs_legal_reacceptance))
      return
    }
    let cancelled = false
    authApi.getProfile()
      .then((p) => {
        if (cancelled) return
        setOpen(Boolean(p?.needs_legal_reacceptance))
        if (p) setAuth(p, accessToken, refreshToken)
      })
      .catch(() => { if (!cancelled) setOpen(false) })
    return () => { cancelled = true }
  }, [isAuthenticated, user?.needs_legal_reacceptance, setAuth, accessToken, refreshToken])

  if (!open) return null

  const accept = async () => {
    setBusy(true)
    try {
      await authApi.acceptTerms()
      const profile = await authApi.getProfile()
      setAuth(profile, accessToken, refreshToken)
      setOpen(false)
      toast.success('Thanks — your acceptance is recorded.')
    } catch {
      toast.error('Could not record acceptance. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  // Escape / backdrop must not dismiss — acceptance is the only honest clear path.
  // ConfirmModal still wires Escape to onClose; no-op keeps focus trap usable.
  return (
    <ConfirmModal open={open} onClose={() => {}} title="Updated Terms & Privacy">
      <div className="space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center shrink-0">
            <FileText size={17} className="text-indigo-300" />
          </div>
          <p className="text-sm text-surface-300 leading-relaxed">
            We updated our legal documents. Please review and accept the current
            {' '}
            <Link to="/terms" target="_blank" rel="noreferrer" className="text-accent-cyan hover:underline">
              Terms of Service
            </Link>
            {' '}and{' '}
            <Link to="/privacy" target="_blank" rel="noreferrer" className="text-accent-cyan hover:underline">
              Privacy Policy
            </Link>
            {' '}to continue using FixitLab.
          </p>
        </div>
        <button
          type="button"
          onClick={accept}
          disabled={busy}
          className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {busy ? 'Recording…' : 'I accept'}
        </button>
      </div>
    </ConfirmModal>
  )
}
