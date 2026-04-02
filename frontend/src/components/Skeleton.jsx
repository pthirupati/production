/**
 * Reusable skeleton loader components for perceived performance.
 * Replace spinners with these for content-aware loading states.
 */

export function SkeletonLine({ width = 'w-full', className = '' }) {
  return (
    <div className={`h-4 ${width} bg-surface-800 rounded animate-pulse ${className}`} />
  )
}

export function SkeletonCircle({ size = 'w-10 h-10' }) {
  return <div className={`${size} rounded-full bg-surface-800 animate-pulse shrink-0`} />
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="glass-card p-5 space-y-3">
      <SkeletonLine width="w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} width={i === lines - 1 ? 'w-2/3' : 'w-full'} />
      ))}
    </div>
  )
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 p-4 border-b border-surface-800/50">
      <SkeletonCircle size="w-8 h-8" />
      <div className="flex-1 space-y-2">
        <SkeletonLine width="w-1/4" />
        <SkeletonLine width="w-1/2" className="h-3" />
      </div>
      <SkeletonLine width="w-16" className="h-6" />
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="flex gap-4 px-4 py-3 border-b border-surface-700/50">
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonLine key={i} width="w-20" className="h-3" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-surface-800/30">
          {Array.from({ length: cols }).map((_, j) => (
            <SkeletonLine key={j} width={j === 0 ? 'w-32' : 'w-20'} className="h-4" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonStats({ count = 4 }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="glass-card p-5 space-y-3">
          <div className="w-10 h-10 rounded-xl bg-surface-800 animate-pulse" />
          <SkeletonLine width="w-12" className="h-6" />
          <SkeletonLine width="w-20" className="h-3" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonScenarioCard() {
  return (
    <div className="glass-card p-5 space-y-3">
      <div className="flex items-center gap-2">
        <SkeletonLine width="w-16" className="h-5 rounded-full" />
        <SkeletonLine width="w-12" className="h-5 rounded-full" />
      </div>
      <SkeletonLine width="w-3/4" className="h-5" />
      <SkeletonLine width="w-full" />
      <SkeletonLine width="w-2/3" />
      <div className="flex justify-between items-center pt-2">
        <SkeletonLine width="w-20" className="h-3" />
        <SkeletonLine width="w-24" className="h-8 rounded-lg" />
      </div>
    </div>
  )
}
