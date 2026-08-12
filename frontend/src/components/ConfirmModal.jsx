import { useEffect, useRef } from 'react'
import { X } from '../ui/eagerIcons'

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

// Modals can stack (a confirm raised from inside another dialog). Body scroll is
// therefore refcounted: the last modal to close is the one that restores
// scrolling, otherwise the first to unmount frees the page while a dialog is
// still up.
let scrollLockCount = 0

function lockBodyScroll() {
  if (scrollLockCount === 0) document.body.style.overflow = 'hidden'
  scrollLockCount += 1
  return () => {
    scrollLockCount = Math.max(0, scrollLockCount - 1)
    if (scrollLockCount === 0) document.body.style.overflow = ''
  }
}

/**
 * Modal a11y behaviour, reusable by dialogs that cannot adopt ConfirmModal's
 * markup (product simulators render their own themed chrome — MaaS, vSphere —
 * where swapping in the glass-card shell would break the emulated UI they teach).
 *
 * Attach the returned ref to the dialog panel. Handles: focus move-in, Tab focus
 * trap, Escape to close, refcounted body-scroll lock, and focus restore to
 * whatever was focused before the dialog opened.
 */
export function useModalA11y(open, onClose) {
  const dialogRef = useRef(null)
  const previousFocus = useRef(null)
  // Kept in a ref so a caller passing an inline arrow does not tear down and
  // reinstall the listener on every render (which would also re-run focus move-in).
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return

    previousFocus.current = document.activeElement
    const dialog = dialogRef.current
    // Prefer the first real control so keyboard users land on something
    // actionable; fall back to the panel itself when the dialog is text-only.
    const initial = dialog?.querySelector(FOCUSABLE)
    if (initial) initial.focus()
    else if (dialog) dialog.focus()

    const handleKey = (e) => {
      if (e.key === 'Escape') {
        // Only the top-most dialog reacts, so Escape does not collapse a whole
        // stack at once.
        e.stopPropagation()
        onCloseRef.current?.()
        return
      }
      if (e.key === 'Tab' && dialog) {
        const focusable = dialog.querySelectorAll(FOCUSABLE)
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        // Focus can sit outside the panel (backdrop click, programmatic blur);
        // pull it back in rather than letting Tab escape to the page behind.
        if (!dialog.contains(document.activeElement)) {
          e.preventDefault()
          ;(e.shiftKey ? last : first).focus()
        } else if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKey)
    const releaseScroll = lockBodyScroll()

    return () => {
      document.removeEventListener('keydown', handleKey)
      releaseScroll()
      previousFocus.current?.focus?.()
    }
  }, [open])

  return dialogRef
}

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
  const dialogRef = useModalA11y(open, onClose)

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
              type="button"
              onClick={onClose}
              className="p-1.5 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-white transition-colors rounded-lg hover:bg-surface-800"
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
