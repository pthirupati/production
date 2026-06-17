export default function StickyPageToolbar({ children, className = '', sticky = true, hidden = false }) {
  return (
    <div
      className={`${sticky ? 'sticky top-0' : ''} z-30 -mx-3 sm:-mx-6 lg:-mx-8 px-3 sm:px-6 lg:px-8 bg-surface-950/95 backdrop-blur-xl border-b border-surface-700/35 space-y-2 shadow-[0_4px_24px_rgba(0,0,0,0.18)] transition-all duration-300 ease-out ${
        hidden
          ? '!max-h-0 !py-0 !mb-0 opacity-0 pointer-events-none overflow-hidden border-transparent shadow-none'
          : 'py-2 mb-0'
      } ${className}`}
    >
      {children}
    </div>
  )
}
