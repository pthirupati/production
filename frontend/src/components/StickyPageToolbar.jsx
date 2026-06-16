/**
 * Stays pinned below the main app header while the page content scrolls.
 */
export default function StickyPageToolbar({ children, className = '' }) {
  return (
    <div
      className={`sticky top-0 z-20 -mx-3 sm:-mx-6 lg:-mx-8 px-3 sm:px-6 lg:px-8 pt-1 pb-4 mb-2 bg-surface-950/92 backdrop-blur-xl border-b border-surface-800/50 space-y-4 ${className}`}
    >
      {children}
    </div>
  )
}
