import { useEffect, useCallback } from 'react'

/**
 * Keyboard shortcut hook for the Lab Runner.
 *
 * Shortcuts:
 *   Ctrl+Enter  → Check Solution
 *   Ctrl+H      → Toggle hints sidebar
 *   Escape      → Toggle sidebar
 *
 * @param {Object} opts
 * @param {function} opts.onValidate   - Check solution callback
 * @param {function} opts.onToggleHints - Toggle hints tab
 * @param {function} opts.onToggleSidebar - Toggle sidebar
 * @param {boolean}  opts.disabled     - Disable all shortcuts
 */
export default function useLabShortcuts({ onValidate, onToggleHints, onToggleSidebar, disabled = false }) {
  const handler = useCallback((e) => {
    if (disabled) return

    // Don't capture when typing in regular inputs (terminal handles its own keys)
    const tag = e.target.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

    // Ctrl+Enter → validate
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      onValidate?.()
      return
    }

    // Ctrl+H → hints
    if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
      e.preventDefault()
      onToggleHints?.()
      return
    }

    // Escape → toggle sidebar
    if (e.key === 'Escape') {
      e.preventDefault()
      onToggleSidebar?.()
      return
    }
  }, [onValidate, onToggleHints, onToggleSidebar, disabled])

  useEffect(() => {
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handler])
}
