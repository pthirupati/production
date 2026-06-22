/**
 * ScoreTrendChart.jsx — line chart of overall score across attempts (pure SVG).
 *
 * Props:
 *   trend — [{ overall_score, passed, round_type, title, date }]
 */
import React from 'react'

export default function ScoreTrendChart({ trend = [], height = 180 }) {
  if (!trend.length) {
    return <p className="text-xs text-surface-500">No attempts yet — your score trend will appear here.</p>
  }
  const width = 520
  const padX = 32
  const padY = 20
  const innerW = width - padX * 2
  const innerH = height - padY * 2
  const n = trend.length
  const x = i => (n === 1 ? padX + innerW / 2 : padX + (innerW * i) / (n - 1))
  const y = v => padY + innerH - (innerH * Math.min(100, Math.max(0, v || 0))) / 100

  const linePath = trend
    .map((t, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(t.overall_score).toFixed(1)}`)
    .join(' ')

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {[0, 50, 100].map(g => (
        <g key={g}>
          <line x1={padX} y1={y(g)} x2={width - padX} y2={y(g)} stroke="#334155" strokeWidth={1} opacity={0.4} />
          <text x={4} y={y(g) + 3} fontSize={9} fill="#64748b">{g}</text>
        </g>
      ))}
      {/* Pass threshold guide at 65 */}
      <line x1={padX} y1={y(65)} x2={width - padX} y2={y(65)} stroke="#f59e0b" strokeWidth={1} strokeDasharray="4 3" opacity={0.5} />
      <path d={linePath} fill="none" stroke="#6366f1" strokeWidth={2.5} strokeLinejoin="round" />
      {trend.map((t, i) => (
        <g key={i}>
          <circle
            cx={x(i)}
            cy={y(t.overall_score)}
            r={4}
            fill={t.passed ? '#22c55e' : '#ef4444'}
            stroke="#0f172a"
            strokeWidth={1.5}
          >
            <title>{`${t.title || t.round_type}: ${Math.round(t.overall_score)}/100`}</title>
          </circle>
        </g>
      ))}
    </svg>
  )
}
