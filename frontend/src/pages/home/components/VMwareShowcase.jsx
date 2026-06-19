import { Loader2, Check } from 'lucide-react'

const HOSTS = [
  { name: 'esxi-01', color: '#4c9be8', width: '52%' },
  { name: 'esxi-02', color: '#9b6bd6', width: '47%' },
  { name: 'ds-01', color: '#56e0b0', width: '61%', dot: '#56e0b0' },
]

export default function VMwareShowcase() {
  return (
    <div className="fx-vmware-showcase-wrap">
      <div className="fx-vmware-showcase-glow" aria-hidden="true" />
      <div className="fx-vmware-showcase">
        <div className="fx-vmware-header">
          <span className="fx-vmware-header-title">
            <em>vm</em>ware vSphere
          </span>
          <span className="fx-vmware-header-sub">Performance · esxi-01</span>
          <div className="fx-vmware-live">
            <span className="fx-pulse-dot" style={{ width: 6, height: 6, background: '#56e0b0' }} />
            live
          </div>
        </div>

        <div className="fx-vmware-chart-wrap">
          <div className="fx-vmware-chart-label">
            <span>CPU usage · last 60s</span>
            <span className="fx-vmware-chart-val">61%</span>
          </div>
          <div className="fx-vmware-chart">
            <svg viewBox="0 0 300 120" preserveAspectRatio="none" aria-hidden="true">
              <line x1="0" y1="30" x2="300" y2="30" stroke="rgba(255,255,255,.06)" />
              <line x1="0" y1="60" x2="300" y2="60" stroke="rgba(255,255,255,.06)" />
              <line x1="0" y1="90" x2="300" y2="90" stroke="rgba(255,255,255,.06)" />
              <polygon
                points="0,84 25,66 50,74 75,48 100,58 125,36 150,46 175,26 200,40 225,22 250,34 275,20 300,30 300,120 0,120"
                fill="url(#vmArea)"
                opacity="0.45"
              />
              <polyline
                className="fx-vmware-chart-line"
                points="0,84 25,66 50,74 75,48 100,58 125,36 150,46 175,26 200,40 225,22 250,34 275,20 300,30"
              />
              <defs>
                <linearGradient id="vmArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#5b9bd5" stopOpacity="0.5" />
                  <stop offset="1" stopColor="#5b9bd5" stopOpacity="0" />
                </linearGradient>
              </defs>
            </svg>
            <div className="fx-vmware-scan" aria-hidden="true" />
            <span className="absolute left-1 top-0.5 text-[9px] text-white/30">100</span>
            <span className="absolute left-1 bottom-0.5 text-[9px] text-white/30">0</span>
          </div>
        </div>

        <div className="fx-vmware-alerts">
          <div className="fx-vmware-alert fx-vmware-alert-critical">
            <span className="w-2 h-2 rounded-full bg-[#ec6a5e] shadow-[0_0_10px_#ec6a5e] shrink-0" />
            <span>Datastore alarm · ds-01 usage <strong className="text-white">94%</strong> · critical</span>
          </div>
          <div className="fx-vmware-alert fx-vmware-alert-warn">
            <Loader2 size={14} className="shrink-0 text-[#feb155]" style={{ animation: 'fxSpin 1s linear infinite' }} />
            <span>AI Copilot applying fix — expanding datastore…</span>
          </div>
          <div className="fx-vmware-alert fx-vmware-alert-ok">
            <Check size={14} className="shrink-0 text-[#56e0b0]" strokeWidth={2.6} />
            <span>Resolved · usage <strong className="text-white">61%</strong> · 0 active alarms</span>
          </div>
        </div>

        <div className="fx-vmware-hosts">
          {HOSTS.map(({ name, color, width, dot = '#2db52d' }) => (
            <div key={name} className="fx-vmware-host">
              <div className="fx-vmware-host-name">
                <span className="fx-vmware-host-dot" style={{ background: dot, color: dot }} />
                {name}
              </div>
              <div className="fx-vmware-host-bar">
                <div className="fx-vmware-host-fill" style={{ width, background: color }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
