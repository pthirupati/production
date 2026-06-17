import { Target } from 'lucide-react'
import StickyPageToolbar from './StickyPageToolbar'
import { useScrollHideToolbar } from '../hooks/useScrollHideToolbar'

/**
 * Compact sticky page header — collapses fully on scroll down (no layout gap).
 */
export default function CompactPageHeader({
  title,
  subtitle,
  eyebrow = '',
  icon: Icon = Target,
  children,
  threshold = 72,
}) {
  const { hidden, anchorRef } = useScrollHideToolbar(threshold)

  return (
    <>
      <div ref={anchorRef} className="h-0 w-full" aria-hidden="true" />
      <StickyPageToolbar hidden={hidden} className="mb-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            {eyebrow && (
              <div className="flex items-center gap-1.5 mb-0.5">
                <Icon size={13} className="text-accent-cyan shrink-0" />
                <span className="text-[10px] font-semibold text-accent-cyan/80 uppercase tracking-widest">{eyebrow}</span>
              </div>
            )}
            <h1 className="font-display text-xl sm:text-2xl font-bold text-white tracking-tight leading-tight">{title}</h1>
            {subtitle && <p className="text-surface-500 text-xs mt-0.5">{subtitle}</p>}
          </div>
          {children}
        </div>
      </StickyPageToolbar>
    </>
  )
}
