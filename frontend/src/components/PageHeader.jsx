/**
 * Overflow-safe page header — title, subtitle, and action buttons scroll horizontally on narrow screens.
 */
export default function PageHeader({ title, subtitle, icon: Icon, children, className = '' }) {
  return (
    <div className={`flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between ${className}`}>
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
