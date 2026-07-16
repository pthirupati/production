/** Lightweight placeholder while a lazy lab simulator chunk loads. */
export default function LabSimFallback({ label = 'Loading lab console…' }) {
  return (
    <div className="flex flex-1 min-h-[200px] items-center justify-center bg-surface-950 text-surface-400 text-sm">
      <div className="flex flex-col items-center gap-3">
        <div
          className="h-8 w-8 rounded-full border-2 border-accent-cyan/30 border-t-accent-cyan animate-spin"
          role="status"
          aria-label={label}
        />
        <span>{label}</span>
      </div>
    </div>
  )
}
