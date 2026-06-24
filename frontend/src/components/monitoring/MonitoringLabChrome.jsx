import { Activity, ArrowLeft, StopCircle, Lightbulb, CheckCircle2, Clock, Terminal } from 'lucide-react'
import '../../styles/monitoring-sim.css'

/**
 * MonitoringLabChrome — the consistent top chrome bar shared across every
 * monitoring-sim surface (login gate + the running simulator). It mirrors the
 * VMware / Nmap / Wireshark sims: a product brand on the left and the
 * Hints / Stop / Back-to-lab lab controls on the right, each wired to the
 * matching callback. Every button is optional — it only renders when its
 * handler is supplied, so the bar degrades gracefully when a sim surface is
 * shown outside the lab runner.
 *
 * Props:
 *   product   — 'Grafana' | 'Prometheus' (drives label + accent)
 *   accent    — accent color for the brand mark
 *   subtitle  — optional scenario title shown next to the product name
 *   onExit    — return to the lab terminal/scenario  (Back to terminal)
 *   onStop    — stop the lab session                 (Stop)
 *   onHints   — open the scenario hints              (Hints)
 *   onCheck   — run Check Solution
 *   onExtend  — add +30m lab time
 *   hintsLabel — e.g. "Hints (1/3)"
 *   children  — optional extra controls injected before the lab controls
 */
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
  children = null,
}) {
  return (
    <div className="mon-topbar">
      <div className="flex items-center gap-3 min-w-0">
        <Activity size={18} style={{ color: accent }} />
        <span className="font-semibold text-white truncate">{product} simulator</span>
        {subtitle && <span className="mon-panel-sub hidden sm:inline truncate">{subtitle}</span>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {children}
        {/* Lab chrome — mirrors the VMware / Nmap sims (hints / stop / back to lab). */}
        {onHints && (
          <button type="button" className="mon-btn" onClick={onHints}>
            <Lightbulb size={13} className="text-[#F5A623]" /> {hintsLabel}
          </button>
        )}
        {onCheck && (
          <button type="button" className="mon-btn" onClick={onCheck} disabled={checkDisabled}>
            <CheckCircle2 size={13} className="text-[#56e0b0]" /> Check
          </button>
        )}
        {onExtend && (
          <button type="button" className="mon-btn" onClick={onExtend}>
            <Clock size={13} /> +30m
          </button>
        )}
        {onStop && (
          <button type="button" className="mon-btn" onClick={onStop}>
            <StopCircle size={13} className="text-[#ff6b6b]" /> Stop
          </button>
        )}
        {onExit && (
          <button type="button" className="mon-btn mon-btn-primary" onClick={onExit}>
            <Terminal size={13} /> Back to terminal
          </button>
        )}
      </div>
    </div>
  )
}
