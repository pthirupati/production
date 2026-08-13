import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useModalA11y } from '../../ConfirmModal'

import '../../../styles/sim-products.css'  // modal theme (portal to body)

/** Light Fluent/Material portal shells — Create-VM etc. theme via data-sim-shell. */
const LIGHT_SHELLS = {
  'az-shell': 'az',
  'gcp-shell': 'gcp',
  'cv-shell': 'cv',
  'na-shell': 'na',
  'de-shell': 'de',
}

function detectLightSimShell() {
  if (typeof document === 'undefined') return null
  for (const [cls, key] of Object.entries(LIGHT_SHELLS)) {
    if (document.querySelector(`.${cls}`)) return { className: cls, key }
  }
  return null
}

export default function SimModal({
  open, onClose, title, children, footer, width = 'max-w-lg', danger = false,
  shellClass, light = false,
}) {
  // Shared product-sim chrome; borrow focus trap / Escape / focus restore.
  const panelRef = useModalA11y(open, onClose)

  if (!open) return null

  // Portals to document.body lose `.az-shell .sim-modal` ancestry after PR #173
  // dropped body:has — stamp shell on the portal root (or use sim-modal--light).
  const detected = shellClass ? null : detectLightSimShell()
  const resolvedShell = shellClass || detected?.className || ''
  const shellKey = LIGHT_SHELLS[resolvedShell]
    || (resolvedShell.endsWith('-shell') ? resolvedShell.replace(/-shell$/, '') : null)
  const useLight = Boolean(light || shellKey)

  return createPortal(
    <div
      className={`fixed inset-0 z-[200] flex items-center justify-center p-4${resolvedShell ? ` ${resolvedShell}` : ''}`}
      data-sim-shell={shellKey || undefined}
    >
      <button type="button" className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" onClick={onClose} aria-label="Close dialog" />
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`sim-modal relative w-full ${width} outline-none ${danger ? 'sim-modal-danger' : ''} ${useLight ? 'sim-modal--light' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sim-modal-head">
          <h3 className="sim-modal-title">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="sim-modal-close min-h-[44px] min-w-[44px] inline-flex items-center justify-center"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>
        <div className="sim-modal-body">{children}</div>
        {footer && <div className="sim-modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
