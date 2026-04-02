import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

/**
 * Accessible modal with focus trapping, Escape to close, and backdrop click.
 *
 * Props:
 *   open      - boolean
 *   onClose   - () => void
 *   title     - string (optional)
 *   maxWidth  - tailwind max-w class (default 'max-w-md')
 *   children  - modal body
 */
export default function ConfirmModal({ open, onClose, title, maxWidth = 'max-w-md', children }) {
  const dialogRef = useRef(null)
  const previousFocus = useRef(null)

  // Trap focus & handle Escape
  useEffect(() => {
    if (!open) return

    previousFocus.current = document.activeElement
    const dialog = dialogRef.current
    if (dialog) dialog.focus()

    const handleKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
        return
      }
      // Focus trap
      if (e.key === 'Tab' && dialog) {
        const focusable = dialog.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKey)
    // Prevent body scroll
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = ''
      previousFocus.current?.focus()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className={`glass-card p-6 w-full ${maxWidth} mx-4 max-h-[85vh] overflow-y-auto outline-none animate-fade-in`}
      >
        {title && (
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-white">{title}</h2>
            <button
              onClick={onClose}
              className="p-1.5 text-surface-500 hover:text-white transition-colors rounded-lg hover:bg-surface-800"
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  )
}

/**
 * Pre-built confirm/cancel dialog.
 *
 * Props:
 *   open, onClose, title,
 *   message    - string or ReactNode
 *   confirmLabel - string (default 'Confirm')
 *   danger     - boolean (red button style)
 *   onConfirm  - () => void
 *   loading    - boolean
 */
export function ConfirmDialog({ open, onClose, title = 'Confirm', message, confirmLabel = 'Confirm', danger = false, onConfirm, loading = false }) {
  return (
    <ConfirmModal open={open} onClose={onClose} title={title} maxWidth="max-w-sm">
      <p className="text-sm text-surface-300 mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="btn-secondary text-sm" disabled={loading}>Cancel</button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className={`text-sm px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
            danger
              ? 'bg-accent-red/10 text-accent-red border border-accent-red/20 hover:bg-accent-red/20'
              : 'btn-primary'
          }`}
        >
          {loading && <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />}
          {confirmLabel}
        </button>
      </div>
    </ConfirmModal>
  )
}
