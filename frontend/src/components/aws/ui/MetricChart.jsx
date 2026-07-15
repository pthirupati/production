import { useMemo, useState } from 'react'

// Lightweight offline SVG time-series chart (CloudWatch-style). Generates a
// deterministic-ish 168-point (7d x 24h) series with a hover tooltip. Avoids
// pulling a chart lib so the sim stays 100% offline.
export default function MetricChart({ title, unit = '%', color = '#0073bb', base = 20, variance = 40, points = 168, threshold = null }) {
  const data = useMemo(() => {
    const arr = []
    let v = base
    for (let i = 0; i < points; i += 1) {
      v += (Math.random() - 0.5) * (variance / 6)
      v = Math.max(0, Math.min(base + variance, v))
      // diurnal bump
      const hour = i % 24
      const bump = Math.sin((hour / 24) * Math.PI * 2) * (variance / 8)
      arr.push(Math.max(0, v + bump))
    }
    return arr
  }, [base, variance, points])

  const [hover, setHover] = useState(null)
  const W = 320
  const H = 120
  const pad = 24
  const max = Math.max(...data, base + variance, threshold != null ? threshold : 0) * 1.1
  const thresholdY = threshold != null && max > 0 ? H - pad - (threshold / max) * (H - pad * 2) : null
  const stepX = (W - pad * 2) / (data.length - 1)
  const path = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${pad + i * stepX} ${H - pad - (d / max) * (H - pad * 2)}`).join(' ')

  return (
    <div className="aws-card" style={{ padding: 12 }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{title}</div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const x = ((e.clientX - rect.left) / rect.width) * W
          const idx = Math.round((x - pad) / stepX)
          if (idx >= 0 && idx < data.length) setHover({ idx, v: data[idx] })
        }}
        onMouseLeave={() => setHover(null)}>
        {[0, 0.5, 1].map((g) => (
          <line key={g} x1={pad} x2={W - pad} y1={pad + g * (H - pad * 2)} y2={pad + g * (H - pad * 2)} stroke="#e9eaea" strokeWidth="1" />
        ))}
        <path d={`${path} L ${pad + (data.length - 1) * stepX} ${H - pad} L ${pad} ${H - pad} Z`} fill={color} opacity="0.08" />
        <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
        {thresholdY != null && (
          <>
            <line x1={pad} x2={W - pad} y1={thresholdY} y2={thresholdY} stroke="#d13212" strokeWidth="1" strokeDasharray="4 3" />
            <text x={W - pad} y={thresholdY - 3} fontSize="9" fill="#d13212" textAnchor="end">Threshold {threshold}{unit}</text>
          </>
        )}
        {hover && (
          <>
            <line x1={pad + hover.idx * stepX} x2={pad + hover.idx * stepX} y1={pad} y2={H - pad} stroke={color} strokeDasharray="3 3" opacity="0.5" />
            <circle cx={pad + hover.idx * stepX} cy={H - pad - (hover.v / max) * (H - pad * 2)} r="3" fill={color} />
          </>
        )}
        <text x={pad} y={14} fontSize="10" fill="#879596">{max.toFixed(0)}{unit}</text>
        <text x={pad} y={H - pad + 12} fontSize="10" fill="#879596">7 days ago</text>
        <text x={W - pad - 20} y={H - pad + 12} fontSize="10" fill="#879596">now</text>
      </svg>
      {hover && <div style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>Value: <strong>{hover.v.toFixed(2)}{unit}</strong></div>}
    </div>
  )
}
