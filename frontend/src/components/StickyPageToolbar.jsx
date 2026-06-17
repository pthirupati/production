export default function StickyPageToolbar({ children, className = '', sticky = true }) {
  return (
    <div
      className={`${sticky ? 'sticky top-0' : ''} z-30 -mx-3 sm:-mx-6 lg:-mx-8 px-3 sm:px-6 lg:px-8 py-2 bg-surface-950/95 backdrop-blur-xl border-b border-surface-700/35 space-y-2 shadow-[0_4px_24px_rgba(0,0,0,0.18)] ${className}`}
    >
      {children}
    </div>
  )
}
