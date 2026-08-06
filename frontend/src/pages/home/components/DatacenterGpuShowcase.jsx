import { Link } from 'react-router-dom'
import { Play, Thermometer, Zap, Boxes } from 'lucide-react'

/**
 * Animated marketing showcase for the 3D datacenter walk + GPU/AI-infra track.
 *
 * Deliberately CSS/SVG-only (no video file, no WebGL, no network asset) so it is
 * cheap on the marketing critical path and cannot repeat the CDN-HDRI failure
 * that took the real twin down. All motion is disabled under
 * prefers-reduced-motion via the shared block in index.css.
 */

/** Rack elevation — mix of healthy nodes, a GPU box, and one failed sled. */
const RACK_A = [
  { u: 'U42', label: 'ToR switch', tone: 'net' },
  { u: 'U38', label: 'gpu-node-01 · 8×H100', tone: 'gpu' },
  { u: 'U34', label: 'gpu-node-02 · 8×H100', tone: 'gpu' },
  { u: 'U30', label: 'esxi-04', tone: 'ok' },
  { u: 'U26', label: 'esxi-05 — PSU B failed', tone: 'fail' },
  { u: 'U22', label: 'ceph-osd-11', tone: 'ok' },
]

const TONE = {
  ok: { bar: '#56e0b0', led: '#56e0b0', bg: 'rgba(86,224,176,.09)' },
  gpu: { bar: '#76b900', led: '#9ae600', bg: 'rgba(118,185,0,.12)' },
  fail: { bar: '#f87171', led: '#f87171', bg: 'rgba(248,113,113,.13)' },
  net: { bar: '#7cc0f0', led: '#7cc0f0', bg: 'rgba(124,192,240,.1)' },
}

/** Per-GPU telemetry rows — mirrors what `nvidia-smi` actually prints. */
const GPUS = [
  { id: 0, util: 96, mem: 74, temp: 71, w: 612 },
  { id: 1, util: 91, mem: 71, temp: 69, w: 588 },
  { id: 2, util: 88, mem: 69, temp: 74, w: 601 },
  { id: 3, util: 43, mem: 22, temp: 58, w: 214, throttle: true },
]

export default function DatacenterGpuShowcase({ demoHref = '/register' }) {
  return (
    <Link
      to={demoHref}
      className="fx-vmware-showcase-wrap block no-underline group"
      aria-label="Open the 3D datacenter walk and GPU lab"
    >
      <div
        className="fx-vmware-showcase-glow"
        aria-hidden="true"
        style={{ background: 'linear-gradient(135deg, rgba(118,185,0,.20), rgba(249,115,22,.14))' }}
      />

      <div className="fx-vmware-showcase relative">
        <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/50 border border-white/15 text-[10px] font-semibold text-white/90 group-hover:bg-[#76b900]/90 transition-colors">
          <Play size={10} fill="currentColor" stroke="none" /> Enter 3D hall
        </div>

        <div
          className="fx-vmware-header"
          style={{ background: 'linear-gradient(90deg, #1d2a12, #16220f)' }}
        >
          <span className="fx-vmware-header-title">
            Data Hall A <em style={{ color: '#9ae600' }}>· 3D walk</em>
          </span>
          <span className="fx-vmware-header-sub">WASD · E to interact</span>
          <div className="fx-vmware-live">
            <span className="fx-pulse-dot" style={{ width: 6, height: 6, background: '#9ae600' }} />
            live
          </div>
        </div>

        {/* ── Isometric hall: two rack rows receding down the cold aisle ── */}
        <div className="fx-dc-hall" aria-hidden="true">
          <div className="fx-dc-floor" />
          <div className="fx-dc-aisle-glow" />

          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={`fx-dc-rack fx-dc-rack-l${i}`}>
              <span className="fx-dc-rack-led" style={{ background: i === 2 ? '#f87171' : '#56e0b0' }} />
            </div>
          ))}
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={`fx-dc-rack fx-dc-rack-r${i}`}>
              <span className="fx-dc-rack-led" style={{ background: i === 1 ? '#9ae600' : '#7cc0f0' }} />
            </div>
          ))}

          {/* Airflow particles rising through the perforated tiles */}
          {[12, 28, 44, 62, 78].map((left, i) => (
            <span key={left} className="fx-dc-airflow" style={{ left: `${left}%`, animationDelay: `${i * 0.7}s` }} />
          ))}

          <div className="fx-dc-crosshair">
            <span className="fx-dc-prompt">[E] Open rack RACK-03</span>
          </div>
        </div>

        {/* ── Facility strip: the physics the backend actually models ── */}
        <div className="fx-dc-strip">
          <div className="fx-dc-chip">
            <Thermometer size={11} style={{ color: '#fbbf24' }} />
            <span>Cold aisle 21.2°C</span>
            <em>·</em>
            <span style={{ color: '#f87171' }}>Hot 33.8°C</span>
          </div>
          <div className="fx-dc-chip">
            <Zap size={11} style={{ color: '#7cc0f0' }} />
            <span>PDU-A 18.4A</span>
            <em>/</em>
            <span>PDU-B 6.1A</span>
          </div>
          <div className="fx-dc-chip">
            <Boxes size={11} style={{ color: '#9ae600' }} />
            <span>PUE 1.42</span>
          </div>
        </div>

        {/* ── Rack elevation, real U positions ── */}
        <div className="fx-dc-elevation">
          {RACK_A.map((row) => {
            const tone = TONE[row.tone]
            return (
              <div key={row.u} className="fx-dc-u" style={{ background: tone.bg }}>
                <span className="fx-dc-u-num">{row.u}</span>
                <span className="fx-dc-u-bar" style={{ background: tone.bar }} />
                <span className="fx-dc-u-label">{row.label}</span>
                <span
                  className="fx-dc-u-led"
                  style={{ background: tone.led, boxShadow: `0 0 6px ${tone.led}` }}
                />
              </div>
            )
          })}
        </div>

        {/* ── nvidia-smi style GPU telemetry ── */}
        <div className="fx-dc-gpu-panel">
          <div className="fx-dc-gpu-head">
            <span>
              <strong style={{ color: '#9ae600' }}>nvidia-smi</strong> · gpu-node-01
            </span>
            <span className="fx-dc-gpu-driver">550.90 · CUDA 12.4</span>
          </div>
          {GPUS.map((g) => (
            <div key={g.id} className="fx-dc-gpu-row">
              <span className="fx-dc-gpu-id">GPU{g.id}</span>
              <span className="fx-dc-gpu-track">
                <span
                  className="fx-dc-gpu-fill"
                  style={{
                    width: `${g.util}%`,
                    background: g.throttle
                      ? 'linear-gradient(90deg,#f59e0b,#f87171)'
                      : 'linear-gradient(90deg,#76b900,#9ae600)',
                  }}
                />
              </span>
              <span className="fx-dc-gpu-num">{g.util}%</span>
              <span className="fx-dc-gpu-num" style={{ color: g.temp >= 73 ? '#fbbf24' : undefined }}>
                {g.temp}°C
              </span>
              <span className="fx-dc-gpu-num">{g.w}W</span>
              {g.throttle && <span className="fx-dc-gpu-flag">SW thermal slowdown</span>}
            </div>
          ))}
        </div>

        <div className="fx-vmware-scan" aria-hidden="true" style={{ background: 'linear-gradient(90deg, transparent, rgba(154,230,0,.10))' }} />
      </div>
    </Link>
  )
}
