import { Activity, CheckCircle2, Clock, Lightbulb, Server, StopCircle, Terminal, Timer } from 'lucide-react'
import { useLabStore } from '../../store/labStore'
import '../../styles/lab-chrome.css'

export function formatLabTime(seconds) {
  const s = Math.max(0, Number(seconds) || 0)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m.toString().padStart(2, '0')}:${r.toString().padStart(2, '0')}`
}

/** Timer pill for simulator overlays — reads lab store when timeRemaining omitted. */
export function LabChromeTimer({ timeRemaining, className = '' }) {
  const storeTime = useLabStore((st) => st.timeRemaining)
  const remaining = timeRemaining ?? storeTime
  const low = remaining < 120 && remaining > 0
  const critical = remaining < 60 && remaining > 0
  const cls = critical ? 'lab-chrome-timer-critical' : low ? 'lab-chrome-timer-low' : ''
  return (
    <span className={`lab-chrome-timer ${cls} ${className}`.trim()} title="Lab time remaining">
      <Timer size={12} />
      {formatLabTime(remaining)}
    </span>
  )
}

/** Lab control buttons only — for simulators with a custom brand row. */
export function LabChromeControls({
  onHints,
  onCheck,
  onExtend,
  onStop,
  onBackToTerminal,
  hintsLabel = 'Hints',
  checkDisabled = false,
  extendDisabled = false,
  backLabel = 'Back to terminal',
  showTimer = true,
  timeRemaining,
  buttonClass = 'lab-chrome-btn',
  primaryClass = 'lab-chrome-btn lab-chrome-btn-primary',
  vmwareHref = null,
  vmwareLabel = 'VMware Server',
}) {
  return (
    <>
      {showTimer && <LabChromeTimer timeRemaining={timeRemaining} />}
      {vmwareHref && (
        <a
          href={vmwareHref}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonClass}
          style={{ textDecoration: 'none', color: 'inherit' }}
          title="This server also lives in VMware. Open vCenter to perform hypervisor-side steps (add a disk, snapshot, reboot), then return here and rescan."
        >
          <Server size={13} className="text-[#4fa7e8]" /> {vmwareLabel}
        </a>
      )}
      {onHints && (
        <button type="button" className={buttonClass} onClick={onHints}>
          <Lightbulb size={13} className="text-[#F5A623]" /> {hintsLabel}
        </button>
      )}
      {onCheck && (
        <button type="button" className={buttonClass} onClick={onCheck} disabled={checkDisabled}>
          <CheckCircle2 size={13} className="text-[#56e0b0]" /> Check
        </button>
      )}
      {onExtend && (
        <button type="button" className={buttonClass} onClick={onExtend} disabled={extendDisabled}>
          <Clock size={13} /> +30m
        </button>
      )}
      {onStop && (
        <button type="button" className={buttonClass} onClick={onStop}>
          <StopCircle size={13} className="text-[#ff6b6b]" /> Stop
        </button>
      )}
      {onBackToTerminal && (
        <button type="button" className={primaryClass} onClick={onBackToTerminal}>
          <Terminal size={13} /> {backLabel}
        </button>
      )}
    </>
  )
}

/**
 * Canonical lab chrome bar — brand + timer + Hints / Check / +30m / Stop / Back to terminal.
 * Used on every simulator surface (login gate and running state).
 */
export default function LabChromeBar({
  icon: Icon = Activity,
  title = 'Console',
  subtitle = '',
  accent = '#0891b2',
  className = 'lab-chrome-bar',
  onHints,
  onCheck,
  onExtend,
  onStop,
  onBackToTerminal,
  onExit,
  hintsLabel,
  checkDisabled,
  extendDisabled,
  timeRemaining,
  showTimer = true,
  backLabel = 'Terminal',
  vmwareHref = null,
  vmwareLabel = 'VMware Server',
  children = null,
}) {
  const backHandler = onBackToTerminal || onExit
  return (
    <div className={className}>
      <div className="lab-chrome-brand">
        <Icon size={18} style={{ color: accent, flexShrink: 0 }} />
        <span className="lab-chrome-title">{title}</span>
        {subtitle ? <span className="lab-chrome-sub hidden sm:inline">{subtitle}</span> : null}
      </div>
      <div className="lab-chrome-actions">
        {children}
        <LabChromeControls
          onHints={onHints}
          onCheck={onCheck}
          onExtend={onExtend}
          onStop={onStop}
          onBackToTerminal={backHandler}
          hintsLabel={hintsLabel}
          checkDisabled={checkDisabled}
          extendDisabled={extendDisabled}
          timeRemaining={timeRemaining}
          showTimer={showTimer}
          backLabel={backLabel}
          vmwareHref={vmwareHref}
          vmwareLabel={vmwareLabel}
        />
      </div>
    </div>
  )
}
