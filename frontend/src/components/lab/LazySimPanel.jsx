import { Suspense } from 'react'
import LabSimFallback from './LabSimFallback'
import SimErrorBoundary from '../SimErrorBoundary'

/** Wraps any lazy simulator component with loading + error boundary. */
export default function LazySimPanel({ Sim, label = 'simulator', ...props }) {
  if (!Sim) return null
  return (
    <SimErrorBoundary name={label} title="Lab simulator error">
      <Suspense fallback={<LabSimFallback label={`Loading ${label}…`} />}>
        <Sim {...props} />
      </Suspense>
    </SimErrorBoundary>
  )
}
