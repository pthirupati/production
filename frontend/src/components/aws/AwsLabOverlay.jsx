import { useEffect } from 'react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Cloud } from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import AwsConsole from './AwsConsole'
import { useAwsStore } from './store/awsStore'
import { simPanelRoot } from '../../utils/simLayout'
import '../../styles/lab-chrome.css'

/**
 * AWS Console embedded in LabRunner with full lab chrome (Hints, Check, timer, Stop).
 * Uses MemoryRouter so routing works without an iframe (fixes clipped layout / hidden sidebar).
 */
export default function AwsLabOverlay({
  embedded = true,
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
  useEffect(() => {
    if (!sessionId) return
    const key = `fixitlab-aws-lab-seeded:${sessionId}`
    try {
      if (!sessionStorage.getItem(key)) {
        useAwsStore.getState().resetSimulation()
        sessionStorage.setItem(key, '1')
      }
    } catch { /* storage unavailable */ }
  }, [sessionId])

  return (
    <div className={simPanelRoot(embedded, 'bg-[#232f3e]')}>
      <LabChromeBar
        icon={Cloud}
        title="AWS Management Console"
        subtitle={scenario?.title || scenario?.slug || ''}
        accent="#ff9900"
        className="lab-chrome-bar !bg-[#232f3e] !border-b-[#37475a]"
        onExit={onExit}
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
      <div className="flex-1 min-h-0 overflow-hidden aws-embedded-host">
        <MemoryRouter initialEntries={['/aws-sim/console/home']}>
          <Routes>
            <Route path="/aws-sim/*" element={<AwsConsole embedded />} />
          </Routes>
        </MemoryRouter>
      </div>
    </div>
  )
}
