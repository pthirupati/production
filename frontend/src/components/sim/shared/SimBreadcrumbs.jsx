import { ChevronRight } from 'lucide-react'

/** Breadcrumb trail — each item: { label, onClick? } */
export default function SimBreadcrumbs({ items = [], className = '' }) {
  if (!items.length) return null
  return (
    <nav aria-label="Breadcrumb" className={`flex items-center gap-1 text-xs min-w-0 ${className}`.trim()}>
      {items.map((item, i) => (
        <span key={`${item.label}-${i}`} className="flex items-center gap-1 min-w-0">
          {i > 0 && <ChevronRight size={12} className="text-slate-500 shrink-0" />}
          {item.onClick ? (
            <button type="button" onClick={item.onClick}
              className="text-slate-400 hover:text-white truncate max-w-[180px]">
              {item.label}
            </button>
          ) : (
            <span className="text-slate-200 font-medium truncate max-w-[220px]">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
