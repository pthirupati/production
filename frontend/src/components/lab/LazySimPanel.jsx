import { Suspense } from 'react'
import LabSimFallback from './LabSimFallback'

/** Wraps any lazy simulator component with a consistent loading state. */
export default function LazySimPanel({ Sim, label = 'simulator', ...props }) {
  if (!Sim) return null
  return (
    <Suspense fallback={<LabSimFallback label={`Loading ${label}…`} />}>
      <Sim {...props} />
    </Suspense>
  )
}
