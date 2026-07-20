import { ChevronRight } from 'lucide-react'

/** Breadcrumb trail — each item: { label, onClick? }. Theme via parent shell CSS. */
export default function SimBreadcrumbs({ items = [], className = '' }) {
  if (!items.length) return null
  return (
    <nav aria-label="Breadcrumb" className={`sim-breadcrumbs flex items-center gap-1 text-xs min-w-0 ${className}`.trim()}>
      {items.map((item, i) => (
        <span key={`${item.label}-${i}`} className="flex items-center gap-1 min-w-0">
          {i > 0 && <ChevronRight size={12} className="sim-bc-sep shrink-0" />}
          {item.onClick ? (
            <button type="button" onClick={item.onClick}
              className="sim-bc-link truncate max-w-[180px]">
              {item.label}
            </button>
          ) : (
            <span className="sim-bc-current font-medium truncate max-w-[220px]">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
