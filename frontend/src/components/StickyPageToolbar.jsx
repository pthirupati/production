export default function StickyPageToolbar({ children, className = '', sticky = true, hidden = false, toolbarRef }) {
  if (hidden) {
    return null
  }

  return (
    <div
      ref={toolbarRef}
      className={`${sticky ? 'sticky top-0' : ''} z-20 -mx-3 sm:-mx-6 lg:-mx-8 px-3 sm:px-6 lg:px-8 py-2 mb-2 bg-surface-950/98 backdrop-blur-xl border-b border-surface-700/35 space-y-2 shadow-[0_4px_20px_rgba(0,0,0,0.15)] ${className}`}
    >
      {children}
    </div>
  )
}
