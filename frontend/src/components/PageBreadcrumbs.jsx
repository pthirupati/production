import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

/**
 * Learner-facing breadcrumb trail for detail pages (X7a residual).
 * items: [{ label, to? }] — omit `to` on the current page crumb.
 */
export default function PageBreadcrumbs({ items = [], className = '' }) {
  if (!items.length) return null
  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex items-center gap-1 text-xs text-surface-500 min-w-0 mb-3 ${className}`.trim()}
    >
      {items.map((item, i) => {
        const isLast = i === items.length - 1
        return (
          <span key={`${item.label}-${i}`} className="flex items-center gap-1 min-w-0">
            {i > 0 && <ChevronRight size={12} className="shrink-0 text-surface-600" aria-hidden="true" />}
            {item.to && !isLast ? (
              <Link
                to={item.to}
                className="truncate max-w-[160px] hover:text-accent-cyan transition-colors"
              >
                {item.label}
              </Link>
            ) : (
              <span
                className="truncate max-w-[220px] font-medium text-surface-300"
                aria-current={isLast ? 'page' : undefined}
              >
                {item.label}
              </span>
            )}
          </span>
        )
      })}
    </nav>
  )
}
