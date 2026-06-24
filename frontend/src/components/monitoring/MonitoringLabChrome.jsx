import LabChromeBar from '../lab/LabChromeBar'
import { Activity } from 'lucide-react'
import '../../styles/monitoring-sim.css'

/** @deprecated Use LabChromeBar directly — thin wrapper for monitoring sim CSS class. */
export default function MonitoringLabChrome({
  product = 'Grafana',
  accent = '#f7913b',
  subtitle = '',
  onExit,
  onStop,
  onHints,
  onCheck,
  onExtend,
  hintsLabel = 'Hints',
  checkDisabled = false,
  extendDisabled = false,
  children = null,
}) {
  return (
    <LabChromeBar
      className="mon-topbar"
      icon={Activity}
      title={`${product} simulator`}
      subtitle={subtitle}
      accent={accent}
      onExit={onExit}
      onStop={onStop}
      onHints={onHints}
      onCheck={onCheck}
      onExtend={onExtend}
      hintsLabel={hintsLabel}
      checkDisabled={checkDisabled}
      extendDisabled={extendDisabled}
    >
      {children}
    </LabChromeBar>
  )
}
