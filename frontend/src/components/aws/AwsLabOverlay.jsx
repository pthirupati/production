import { useEffect, useState } from 'react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Cloud } from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import AwsConsole from './AwsConsole'
import { useAwsStore } from './store/awsStore'
import { simPanelRoot } from '../../utils/simLayout'
import '../../styles/lab-chrome.css'

/**
 * AWS Console embedded in LabRunner with full lab chrome (Hints, Check, timer, Stop).
 * Terminal panel is toggled from LabRunner's SimWithTerminal wrapper — console is primary.
 */
export default function AwsLabOverlay({
  embedded = true,
  onToggleTerminal,
  onExit,
  scenario,
  sessionId,
  onHints,
  onCheck,
  onExtend,
  onStop,
  hintsLabel,
  checkDisabled,
  extendDisabled,
  vmwareHref,
}) {
  // Reset the lab console store to a clean seed BEFORE the console renders, not after.
  // Doing this in a lazy useState initializer means the very first paint is
  // driven by fresh seed state — never a rehydrated old/corrupt v2 blob — so a
  // returning user can't hit a stale-state render crash. The initializer runs
  // exactly once per mount (guarded so it can never throw the mount).
  useState(() => {
    try { useAwsStore.getState().resetSimulation() } catch { /* ignore */ }
    return true
  })

  // Re-seed again if this overlay is reused for a different lab session without
  // a full remount (defensive; the key on the parent boundary already remounts).
  // Also arm the server-side action sync so every mutating console click is
  // mirrored into the graded engine world. Disarm on unmount / session change so
  // a stray later click can't leak into a released session's log.
  useEffect(() => {
    if (!sessionId) return undefined
    try { useAwsStore.getState().resetSimulation() } catch { /* ignore */ }
    try { useAwsStore.getState().armLabSync(sessionId) } catch { /* ignore */ }
    try { useAwsStore.getState().setLabSessionId(sessionId) } catch { /* ignore */ }
    return () => {
      try { useAwsStore.getState().disarmLabSync() } catch { /* ignore */ }
      try { useAwsStore.getState().setLabSessionId(null) } catch { /* ignore */ }
    }
  }, [sessionId])

  // Defensive: never let a console render throw escape to the parent boundary
  // without a chance to remount. Key forces a clean MemoryRouter on session change.
  const routerKey = `aws-${sessionId || 'anon'}`

  return (
    <div className={simPanelRoot(embedded, 'bg-[#232f3e]')}>
      <LabChromeBar
        icon={Cloud}
        title="AWS Management Console"
        subtitle={scenario?.title || scenario?.slug || ''}
        accent="#ff9900"
        className="lab-chrome-bar !bg-[#232f3e] !border-b-[#37475a]"
        onExit={onToggleTerminal}
        onHints={onHints}
        onCheck={onCheck}
        onExtend={onExtend}
        onStop={onStop}
        hintsLabel={hintsLabel}
        checkDisabled={checkDisabled}
        extendDisabled={extendDisabled}
        backLabel="Terminal"
        vmwareHref={vmwareHref}
      />
      <div className="flex-1 min-h-0 overflow-hidden aws-embedded-host h-full w-full">
        <MemoryRouter key={routerKey} initialEntries={['/aws-sim/console/home']}>
          <Routes>
            <Route path="/aws-sim/*" element={<AwsConsole embedded />} />
          </Routes>
        </MemoryRouter>
      </div>
    </div>
  )
}
