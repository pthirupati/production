export default function StickyPageToolbar({ children, className = '', sticky = true }) {
  return (
    <div
      className={`${sticky ? 'sticky top-0' : ''} z-30 -mx-3 sm:-mx-6 lg:-mx-8 px-3 sm:px-6 lg:px-8 py-3 bg-surface-950/92 backdrop-blur-2xl border-b border-surface-700/40 space-y-3 shadow-[0_8px_32px_rgba(0,0,0,0.25)] ${className}`}
    >
      {children}
    </div>
  )
}
