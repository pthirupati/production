import { useState, useCallback } from 'react'
import { Monitor, Smartphone, X } from 'lucide-react'
import { useIsMobile } from '../hooks/useMediaQuery'

// Audit Z6-9. Mobile responsiveness is implemented — `useIsMobile()` is threaded
// through eleven sites in LabRunner — but nothing warned before starting. So a phone
// user provisioned a container, consumed one of a small daily lab quota, and landed
// in a terminal that needs a physical keyboard and Ctrl-C. On the 3D datacenter
// scenarios they got 1,029 kB gz of WebGL plus Rapier physics, which OOMs many mobile
// browsers outright.
//
// Deliberately a WARNING, not a block. Some people do have a Bluetooth keyboard on a
// tablet, and the 1024px breakpoint catches small laptop windows too — refusing
// outright would be wrong for both. What was missing was informed consent, not
// permission. Browse, catalog, blog and progress stay fully mobile and are untouched.

const CONSENT_KEY = 'fixitlab:small-screen-lab-ack'

export function useSmallScreenLabGate() {
  const isMobile = useIsMobile()
  const [pending, setPending] = useState(null)

  // Returns true when the caller should proceed immediately. When it returns false
  // the interstitial has been raised and will run `action` if the user continues.
  const guard = useCallback((action) => {
    if (!isMobile) return true
    try {
      if (sessionStorage.getItem(CONSENT_KEY) === '1') return true
    } catch {
      // Private browsing can throw on sessionStorage. Falling through to the
      // interstitial is the safe direction — worst case the user acknowledges twice.
    }
    setPending(() => action)
    return false
  }, [isMobile])

  const dismiss = useCallback(() => setPending(null), [])

  const proceed = useCallback(() => {
    try {
      // Per session, not forever: someone who switches to a laptop tomorrow should
      // not carry a decision they made on a phone.
      sessionStorage.setItem(CONSENT_KEY, '1')
    } catch { /* nothing to do; the warning simply shows again */ }
    const action = pending
    setPending(null)
    if (typeof action === 'function') action()
  }, [pending])

  return { guard, gateOpen: pending !== null, dismiss, proceed }
}

export default function SmallScreenLabGate({ open, onCancel, onProceed }) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in"
      onClick={onCancel}
      role="dialog"
      aria-modal="true"
      aria-labelledby="small-screen-lab-title"
    >
      <div
        className="glass-card p-6 max-w-md w-full relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 text-surface-500 hover:text-white transition-colors"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-xl bg-accent-amber/10 border border-accent-amber/20 flex items-center justify-center shrink-0">
            <Smartphone size={22} className="text-accent-amber" />
          </div>
          <div>
            <h3 id="small-screen-lab-title" className="text-lg font-bold text-white">
              This lab needs a bigger screen
            </h3>
            <p className="text-sm text-surface-400">You can continue, but it will be rough</p>
          </div>
        </div>

        <ul className="text-sm text-surface-400 space-y-1.5 mb-5 ml-4 list-disc">
          <li>The terminal needs a physical keyboard — including <code className="text-surface-300">Ctrl-C</code> and arrow keys</li>
          <li>Starting a lab uses one of your daily lab slots even if you stop straight away</li>
          <li>3D datacenter scenarios are heavy and may crash a mobile browser</li>
        </ul>

        <p className="text-xs text-surface-500 mb-5">
          Everything else — browsing scenarios, tutorials, blog and your progress —
          works fine here.
        </p>

        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="btn-secondary text-sm px-5 py-2">
            Not now
          </button>
          <button
            onClick={onProceed}
            className="btn-primary text-sm px-5 py-2 flex items-center gap-2"
          >
            <Monitor size={14} /> Start anyway
          </button>
        </div>
      </div>
    </div>
  )
}
