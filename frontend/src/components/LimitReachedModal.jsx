import { Link } from 'react-router-dom'
import { X, Zap, Clock, AlertCircle } from 'lucide-react'

/**
 * Daily-limit popup. Shown as a centered modal window (not an inline banner) so
 * the user clearly understands they've hit the Free-plan cap and what to do.
 */
export default function LimitReachedModal({ info, onClose }) {
  if (!info) return null
  const used = info.usage?.labs_today
  const max = info.plan?.max_labs_per_day
  const planName = info.plan?.name || 'Free'

  return (
    <div
      className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="glass-card relative w-full max-w-md p-6 border-accent-amber/30 bg-surface-900/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-surface-500 hover:text-white transition-colors"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-11 h-11 rounded-xl bg-accent-amber/15 flex items-center justify-center shrink-0">
            <AlertCircle size={22} className="text-accent-amber" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white leading-tight">Daily Limit Reached</h3>
            <p className="text-xs text-surface-400">{planName} plan</p>
          </div>
        </div>

        <p className="text-sm text-surface-300 mb-4">
          You've used <span className="font-semibold text-white">{used} of {max}</span> labs today.
          Upgrade for unlimited daily labs across every technology.
        </p>

        <div className="flex items-center gap-2 text-xs text-surface-400 mb-5 px-3 py-2 rounded-lg bg-surface-800/60">
          <Clock size={14} className="text-surface-500 shrink-0" />
          Your free labs reset at <span className="text-surface-200">midnight UTC</span>.
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <Link
            to="/pricing"
            className="btn-primary flex-1 px-4 py-2.5 text-sm flex items-center justify-center gap-1.5"
          >
            <Zap size={15} /> Upgrade to Pro
          </Link>
          <button
            onClick={onClose}
            className="btn-secondary flex-1 px-4 py-2.5 text-sm"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  )
}
