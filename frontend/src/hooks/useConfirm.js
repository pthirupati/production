import { useState, useCallback, createElement } from 'react'
import { ConfirmDialog } from '../components/ConfirmModal'

/**
 * Promise-based confirm dialog — drop-in replacement for window.confirm.
 */
export function useConfirm() {
  const [config, setConfig] = useState(null)

  const confirm = useCallback((opts) => {
    const message = typeof opts === 'string' ? opts : opts.message
    const title = typeof opts === 'string' ? 'Confirm' : (opts.title || 'Confirm')
    const danger = Boolean(typeof opts === 'object' && opts.danger)
    const confirmLabel = (typeof opts === 'object' && opts.confirmLabel) || 'Confirm'
    return new Promise((resolve) => {
      setConfig({ message, title, danger, confirmLabel, resolve })
    })
  }, [])

  const finish = (value) => {
    config?.resolve?.(value)
    setConfig(null)
  }

  function ConfirmPortal() {
    if (!config) return null
    return createElement(ConfirmDialog, {
      open: true,
      onClose: () => finish(false),
      onConfirm: () => finish(true),
      title: config.title,
      message: config.message,
      danger: config.danger,
      confirmLabel: config.confirmLabel,
    })
  }

  return { confirm, ConfirmPortal }
}
