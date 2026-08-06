import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Play, Thermometer, Zap, Activity, Cpu } from 'lucide-react'

/**
 * Continuous first-person "walk the data hall" animation for the marketing page.
 *
 * Deliberately CSS/SVG only — no video file, no WebGL, no network asset. The real
 * 3D twin is a ~1MB gzip chunk behind auth; putting WebGL on the landing page
 * would wreck LCP, and an HDRI/CDN dependency is exactly what broke the twin
 * (see docs/AUDIT_2026_08_TODO.md §X1b). This has to stay cheap.
 *
 * What it shows, cycling through four camera stops down a cold aisle:
 *   - rack bays receding into fog, sliding past as the camera advances
 *   - per-server status LEDs: healthy / warn / failed, each blinking off its own
 *     phase so the wall looks alive rather than strobing in unison
 *   - GPU trays called out on the AI rows (8x H100), with utilisation bars
 *   - patch-panel fibre runs with light pulses travelling along them
 *   - live-ish facility telemetry (inlet/exhaust temp, PDU A/B amps, PUE)
 *   - a first-person HUD: crosshair, interaction prompt, and the current bay
 *
 * All motion is suppressed under prefers-reduced-motion via index.css.
 */

/** Four stops. Each is a bay the camera walks up to. */
const BAYS = [
  {
    id: 'RACK-01',
    kind: 'compute',
    label: 'Compute row A',
    detail: '2× Xeon · 512 GB · ESXi 8',
    servers: ['ok', 'ok', 'ok', 'warn', 'ok', 'ok', 'ok', 'ok'],
    prompt: '[E] Open rack RACK-01',
  },
  {
    id: 'RACK-04',
    kind: 'gpu',
    label: 'GPU row — AI training',
    detail: '8× H100 SXM · NVLink · 700 W',
    servers: ['gpu', 'gpu', 'gpu', 'gpu', 'ok', 'ok', 'warn', 'gpu'],
    prompt: '[E] Inspect gpu-node-02',
  },
  {
    id: 'RACK-07',
    kind: 'storage',
    label: 'Storage row',
    detail: '24× NVMe · Ceph OSD',
    servers: ['ok', 'ok', 'fail', 'ok', 'ok', 'ok', 'ok', 'warn'],
    prompt: '[E] Replace failed drive',
  },
  {
    id: 'MDF-01',
    kind: 'network',
    label: 'MDF / spine',
    detail: '64× 400G QSFP-DD',
    servers: ['ok', 'ok', 'ok', 'ok', 'ok', 'ok', 'ok', 'ok'],
    prompt: '[E] Trace fibre to RACK-04',
  },
]

const LED = {
  ok: { color: '#56e0b0', glow: 'rgba(86,224,176,.85)' },
  warn: { color: '#fbbf24', glow: 'rgba(251,191,36,.85)' },
  fail: { color: '#f87171', glow: 'rgba(248,113,113,.9)' },
  gpu: { color: '#9ae600', glow: 'rgba(154,230,0,.9)' },
}

/** One rack: chassis, sled stack with per-sled LEDs, and an optional GPU badge. */
function Rack({ bay, depth, active }) {
  return (
    <div className={`fx-dcw-rack fx-dcw-depth-${depth} ${active ? 'is-active' : ''}`}>
      <div className="fx-dcw-rack-frame">
        <div className="fx-dcw-rack-top">{bay.id}</div>
        <div className="fx-dcw-sleds">
          {bay.servers.map((s, i) => {
            const led = LED[s] || LED.ok
            return (
              <div key={i} className="fx-dcw-sled">
                <span className="fx-dcw-sled-vents" />
                <span
                  className="fx-dcw-sled-led"
                  style={{
                    background: led.color,
                    boxShadow: `0 0 5px ${led.glow}, 0 0 10px ${led.glow}`,
                    animationDelay: `${(i % 5) * 0.37}s`,
                  }}
                />
                {s === 'gpu' && <span className="fx-dcw-sled-gpu">GPU</span>}
              </div>
            )
          })}
        </div>
        {bay.kind === 'gpu' && (
          <div className="fx-dcw-gpu-strip">
            {[92, 88, 95, 41].map((u, i) => (
              <span key={i} className="fx-dcw-gpu-bar">
                <span
                  className="fx-dcw-gpu-fill"
                  style={{
                    width: `${u}%`,
                    background: u < 50 ? 'linear-gradient(90deg,#f59e0b,#f87171)' : 'linear-gradient(90deg,#76b900,#9ae600)',
                    animationDelay: `${i * 0.4}s`,
                  }}
                />
              </span>
            ))}
          </div>
        )}
      </div>
      {/* Fibre / copper runs leaving the top of the rack toward the MDF */}
      <svg className="fx-dcw-cables" viewBox="0 0 60 40" preserveAspectRatio="none" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <path
            key={i}
            d={`M ${18 + i * 12} 40 C ${18 + i * 12} ${22 - i * 5}, ${44 - i * 7} ${16 - i * 4}, 60 ${6 + i * 5}`}
            className="fx-dcw-cable-path"
            style={{ stroke: ['#38bdf8', '#a78bfa', '#f59e0b'][i], animationDelay: `${i * 0.9}s` }}
          />
        ))}
      </svg>
    </div>
  )
}

export default function DatacenterWalkAnimation({ demoHref = '/register' }) {
  const [stop, setStop] = useState(0)
  const reduced = useRef(false)

  useEffect(() => {
    reduced.current =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced.current) return
    // Walk to the next bay every 4.2s. Interval is cheap; nothing re-renders
    // except this component's own bay index.
    const t = setInterval(() => setStop((s) => (s + 1) % BAYS.length), 4200)
    return () => clearInterval(t)
  }, [])

  const bay = BAYS[stop]

  // Telemetry drifts with the bay so the numbers feel connected to the walk.
  const telemetry = useMemo(() => {
    const hot = bay.kind === 'gpu'
    return {
      inlet: hot ? '22.8' : '21.2',
      exhaust: hot ? '41.6' : '33.8',
      pduA: hot ? '27.4' : '18.4',
      pduB: hot ? '9.2' : '6.1',
      pue: hot ? '1.51' : '1.42',
    }
  }, [bay.kind])

  return (
    <Link
      to={demoHref}
      className="fx-dcw-wrap block no-underline group"
      aria-label="Walk the 3D datacenter"
    >
      <div className="fx-dcw-glow" aria-hidden="true" />

      <div className="fx-dcw-frame">
        {/* ── window chrome ── */}
        <div className="fx-dcw-titlebar">
          <span className="fx-dcw-title">
            Data Hall A <em>· first-person walk</em>
          </span>
          <span className="fx-dcw-bay">{bay.label}</span>
          <span className="fx-dcw-live">
            <span className="fx-pulse-dot" style={{ width: 6, height: 6, background: '#9ae600' }} />
            live
          </span>
        </div>

        {/* ── the hall ── */}
        <div className="fx-dcw-hall" aria-hidden="true">
          <div className="fx-dcw-ceiling" />
          <div className="fx-dcw-floor" />
          <div className="fx-dcw-fog" />

          {/* Overhead luminaires streaking past as the camera advances */}
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className="fx-dcw-lamp" style={{ animationDelay: `${i * 0.84}s` }} />
          ))}

          {/* Two rack rows. key on stop so each walk re-triggers the slide-in. */}
          <div className="fx-dcw-row fx-dcw-row-left" key={`l${stop}`}>
            {[3, 2, 1, 0].map((d) => (
              <Rack key={d} bay={BAYS[(stop + d) % BAYS.length]} depth={d} active={d === 0} />
            ))}
          </div>
          <div className="fx-dcw-row fx-dcw-row-right" key={`r${stop}`}>
            {[3, 2, 1, 0].map((d) => (
              <Rack key={d} bay={BAYS[(stop + d + 2) % BAYS.length]} depth={d} active={false} />
            ))}
          </div>

          {/* Cold air rising through perforated tiles */}
          {[10, 24, 38, 56, 72, 88].map((left, i) => (
            <span
              key={left}
              className="fx-dcw-air"
              style={{ left: `${left}%`, animationDelay: `${i * 0.62}s` }}
            />
          ))}

          {/* First-person HUD */}
          <div className="fx-dcw-hud">
            <span className="fx-dcw-crosshair" />
            <span className="fx-dcw-prompt" key={bay.id}>{bay.prompt}</span>
          </div>
          <div className="fx-dcw-keys">
            <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd>
            <span>walk</span>
            <kbd>E</kbd><span>interact</span>
          </div>
          <div className="fx-dcw-badge">
            <Play size={9} fill="currentColor" stroke="none" /> Enter the hall
          </div>
        </div>

        {/* ── facility telemetry ── */}
        <div className="fx-dcw-telemetry">
          <span className="fx-dcw-chip">
            <Thermometer size={10} style={{ color: '#38bdf8' }} />
            inlet <b>{telemetry.inlet}°C</b>
            <em>/</em>
            <span style={{ color: '#f87171' }}>exhaust <b>{telemetry.exhaust}°C</b></span>
          </span>
          <span className="fx-dcw-chip">
            <Zap size={10} style={{ color: '#fbbf24' }} />
            PDU-A <b>{telemetry.pduA}A</b><em>/</em>B <b>{telemetry.pduB}A</b>
          </span>
          <span className="fx-dcw-chip">
            <Activity size={10} style={{ color: '#9ae600' }} />
            PUE <b>{telemetry.pue}</b>
          </span>
          <span className="fx-dcw-chip fx-dcw-chip-ctx">
            <Cpu size={10} style={{ color: '#a78bfa' }} />
            {bay.detail}
          </span>
        </div>
      </div>
    </Link>
  )
}
