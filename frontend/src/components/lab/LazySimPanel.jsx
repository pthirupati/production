import { Suspense, useState } from 'react'
import LabSimFallback from './LabSimFallback'
import SimErrorBoundary from '../SimErrorBoundary'

/**
 * Wraps any lazy simulator with Suspense + SimErrorBoundary.
 * Pass AWS reset props so companion overlays (Terraform → Open AWS) recover
 * from corrupt Zustand the same way the primary AWS lab boundary does.
 */
export default function LazySimPanel({
  Sim,
  label = 'lab console',
  name,
  title = 'Lab environment error',
  message,
  resetStorageKey,
  onResetStorage,
  onReset,
  autoResetStorageOnError = false,
  remountKey,
  ...props
}) {
  const [localNonce, setLocalNonce] = useState(0)
  if (!Sim) return null

  const bump = () => {
    setLocalNonce((n) => n + 1)
    try { onReset?.() } catch { /* ignore */ }
  }
  const resetStorage = () => {
    try { onResetStorage?.() } catch { /* ignore */ }
    bump()
  }

  const boundaryName = name || label
  const key = remountKey != null ? `${remountKey}:${localNonce}` : `${boundaryName}:${localNonce}`

  return (
    <div className="flex-1 min-h-0 flex flex-col h-full w-full">
      <SimErrorBoundary
        key={key}
        name={boundaryName}
        title={title}
        message={message}
        resetStorageKey={resetStorageKey}
        onResetStorage={onResetStorage ? resetStorage : undefined}
        onReset={bump}
        autoResetStorageOnError={autoResetStorageOnError}
      >
        <Suspense fallback={<LabSimFallback label={`Loading ${label}…`} />}>
          <div className="flex-1 min-h-0 h-full w-full flex flex-col">
            <Sim {...props} />
          </div>
        </Suspense>
      </SimErrorBoundary>
    </div>
  )
}
