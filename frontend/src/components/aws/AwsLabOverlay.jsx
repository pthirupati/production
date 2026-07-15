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
  // Reset the simulation to a clean seed BEFORE the console renders, not after.
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
  useEffect(() => {
    if (!sessionId) return
    try { useAwsStore.getState().resetSimulation() } catch { /* ignore */ }
  }, [sessionId])

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
        <MemoryRouter initialEntries={['/aws-sim/console/home']}>
          <Routes>
            <Route path="/aws-sim/*" element={<AwsConsole embedded />} />
          </Routes>
        </MemoryRouter>
      </div>
    </div>
  )
}
