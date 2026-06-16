/**
 * Overflow-safe page header — title, subtitle, and action buttons scroll horizontally on narrow screens.
 * Stays visible while the page scrolls (below the main app search bar).
 */
export default function PageHeader({ title, subtitle, icon: Icon, children, className = '', sticky = true }) {
  const stickyClass = sticky
    ? 'sticky top-0 z-20 -mx-3 sm:-mx-6 lg:-mx-8 px-3 sm:px-6 lg:px-8 py-3 mb-4 bg-surface-950/92 backdrop-blur-xl border-b border-surface-800/50'
    : ''

  return (
    <div className={`flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between ${stickyClass} ${className}`}>
      <div className="min-w-0 shrink">
        {title && (
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            {Icon && <Icon className="text-accent-cyan shrink-0" size={24} />}
            <span className="truncate">{title}</span>
          </h1>
        )}
        {subtitle && <p className="text-sm text-surface-400 mt-1">{subtitle}</p>}
      </div>
      {children && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1 shrink-0 max-w-full">
          {children}
        </div>
      )}
    </div>
  )
}
