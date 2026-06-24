import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

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
        className={`relative w-full ${width} bg-[#1a1d2e] border border-slate-600 rounded-lg shadow-2xl outline-none`}
        onClick={(e) => e.stopPropagation()}>
        <div className={`flex items-center justify-between px-4 py-3 border-b ${danger ? 'border-red-500/30' : 'border-slate-700'}`}>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          <button type="button" onClick={onClose} className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/10" aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <div className="px-4 py-4 max-h-[70vh] overflow-y-auto">{children}</div>
        {footer && <div className="px-4 py-3 border-t border-slate-700 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
