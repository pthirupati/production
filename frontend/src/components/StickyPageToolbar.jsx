/**
 * Stays pinned at the top of the scroll area while page content scrolls beneath.
 * Background is intentionally near-opaque so scrolled content is fully hidden.
 */
export default function StickyPageToolbar({ children, className = '' }) {
  return (
    <div
      className={`sticky top-0 z-30 -mx-3 sm:-mx-6 lg:-mx-8 px-3 sm:px-6 lg:px-8 pt-2 pb-3 bg-surface-950 backdrop-blur-xl border-b border-surface-800/60 space-y-3 ${className}`}
    >
      {children}
    </div>
  )
}
