import { terraformApi } from '../../api/terraform'
import LabChromeBar from '../lab/LabChromeBar'
import { Cloud } from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { getIacProfile } from '../../utils/iacFlavor'
import { useSimSession } from '../sim/shared'
import TerraformCloudShell from './TerraformCloudShell'
import '../../styles/lab-chrome.css'
import '../../styles/sim-products.css'

export default function TerraformSimulator(props) {
  const {
    sessionId, scenario, embedded = false,
    terminalSession, terminalHost, blockedCommands, isMobile,
    onExit, onStop, onHints, onCheck, onExtend, hintsLabel, checkDisabled, extendDisabled,
    onToggleTerminal, simTerminalOpen,
  } = props
  const slug = scenario?.slug || ''
  const iac = getIacProfile()
  const { state, setState, loading, busy, refresh, run } = useSimSession(sessionId, slug, terraformApi)

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? undefined : onExit,
    hintsLabel, checkDisabled, extendDisabled,
  }

  if (loading) {
    return (
      <div className={simPanelRoot(embedded, 'tfc-shell flex items-center justify-center text-slate-400')}>
        <LabChromeBar icon={Cloud} title={iac.cloudTitle} subtitle={slug} accent={iac.accent} {...chromeProps} />
        <p className="p-8 text-sm">Loading {iac.label} workspace…</p>
      </div>
    )
  }

  return (
    <TerraformCloudShell
      sessionId={sessionId}
      scenario={scenario}
      embedded={embedded}
      chromeProps={chromeProps}
      terminalSession={terminalSession}
      terminalHost={terminalHost}
      blockedCommands={blockedCommands}
      isMobile={isMobile}
      state={state}
      setState={setState}
      refresh={refresh}
      busy={busy}
      run={run}
      onToggleTerminal={onToggleTerminal}
      simTerminalOpen={simTerminalOpen}
    />
  )
}
