/**
 * SkillRadar.jsx — competency radar chart (pure SVG, no chart library).
 *
 * Props:
 *   data — [{ dimension, key, score }]  (scores 0–100)
 *   size — px (default 260)
 */
import React from 'react'

export default function SkillRadar({ data = [], size = 260 }) {
  const axes = data.filter(d => d && d.dimension)
  if (axes.length < 3) {
    return (
      <p className="text-xs text-surface-500">Complete at least one interview to see your skill radar.</p>
    )
  }

  const cx = size / 2
  const cy = size / 2
  const radius = size / 2 - 36
  const n = axes.length
  const angle = i => (Math.PI * 2 * i) / n - Math.PI / 2

  const point = (i, r) => [cx + r * Math.cos(angle(i)), cy + r * Math.sin(angle(i))]

  // Concentric grid rings at 25/50/75/100.
  const rings = [0.25, 0.5, 0.75, 1].map(frac =>
    axes.map((_, i) => point(i, radius * frac).join(',')).join(' ')
  )

  const valuePoints = axes
    .map((d, i) => point(i, radius * (Math.min(100, Math.max(0, d.score || 0)) / 100)).join(','))
    .join(' ')

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="mx-auto">
      {rings.map((pts, idx) => (
        <polygon key={idx} points={pts} fill="none" stroke="#334155" strokeWidth={1} opacity={0.5} />
      ))}
      {axes.map((_, i) => {
        const [x, y] = point(i, radius)
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="#334155" strokeWidth={1} opacity={0.4} />
      })}
      <polygon points={valuePoints} fill="rgba(99,102,241,0.35)" stroke="#6366f1" strokeWidth={2} />
      {axes.map((d, i) => {
        const [x, y] = point(i, radius * (Math.min(100, Math.max(0, d.score || 0)) / 100))
        return <circle key={i} cx={x} cy={y} r={3} fill="#818cf8" />
      })}
      {axes.map((d, i) => {
        const [lx, ly] = point(i, radius + 18)
        const anchor = Math.abs(lx - cx) < 12 ? 'middle' : lx > cx ? 'start' : 'end'
        return (
          <text
            key={i}
            x={lx}
            y={ly}
            textAnchor={anchor}
            dominantBaseline="middle"
            fontSize={10}
            fill="#94a3b8"
          >
            {d.dimension}
          </text>
        )
      })}
    </svg>
  )
}
