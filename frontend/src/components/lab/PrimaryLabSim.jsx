import { Suspense } from 'react'
import { PRIMARY_SIM_COMPONENTS } from './labSimLoader'
import LabSimFallback from './LabSimFallback'

/**
 * Renders the correct primary lab simulator (lazy-loaded) for the active scenario type.
 */
export default function PrimaryLabSim({ kind, monitoringFlavor, ...props }) {
  const Sim = PRIMARY_SIM_COMPONENTS[kind]
  if (!Sim) return null
  const label = kind === 'aws' ? 'AWS Console' : `${kind} simulator`
  return (
    <Suspense fallback={<LabSimFallback label={`Loading ${label}…`} />}>
      {kind === 'monitoring' ? (
        <Sim {...props} flavor={monitoringFlavor} />
      ) : (
        <Sim {...props} />
      )}
    </Suspense>
  )
}
