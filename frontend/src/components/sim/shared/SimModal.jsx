import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

import '../../styles/sim-products.css'  // modal theme (portal to body)

export default function SimModal({
  open, onClose, title, children, footer, width = 'max-w-lg', danger = false,
}) {
  const panelRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', onKey)
    panelRef.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <button type="button" className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" onClick={onClose} aria-label="Close dialog" />
      <div ref={panelRef} tabIndex={-1}
        className={`sim-modal relative w-full ${width} outline-none ${danger ? 'sim-modal-danger' : ''}`}
        onClick={(e) => e.stopPropagation()}>
        <div className="sim-modal-head">
          <h3 className="sim-modal-title">{title}</h3>
          <button type="button" onClick={onClose} className="sim-modal-close" aria-label="Close">
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
