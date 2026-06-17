import { useState, useId } from 'react'
import { Info } from 'lucide-react'

/**
 * Info icon with accessible tooltip — use beside form labels across the app.
 */
export default function FieldHint({ text, className = '' }) {
  const [open, setOpen] = useState(false)
  const tipId = useId()
  if (!text) return null

  return (
    <span className={`relative inline-flex align-middle ${className}`}>
      <button
        type="button"
        className="inline-flex items-center justify-center w-4 h-4 rounded-full text-surface-400 hover:text-accent-cyan hover:bg-accent-cyan/10 transition-colors"
        aria-label="Field help"
        aria-describedby={open ? tipId : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <Info size={12} strokeWidth={2.5} />
      </button>
      {open && (
        <span
          id={tipId}
          role="tooltip"
          className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-56 px-3 py-2 text-xs leading-relaxed text-surface-100 bg-surface-800 border border-surface-600/80 rounded-lg shadow-xl pointer-events-none"
        >
          {text}
        </span>
      )}
    </span>
  )
}

export function LabelWithHint({ label, hint, htmlFor, required, className = '' }) {
  return (
    <label htmlFor={htmlFor} className={`flex items-center gap-1.5 text-sm font-medium text-surface-200 ${className}`}>
      <span>
        {label}
        {required && <span className="text-accent-red ml-0.5" aria-hidden="true">*</span>}
      </span>
      {hint && <FieldHint text={hint} />}
    </label>
  )
}
