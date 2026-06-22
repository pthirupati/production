/**
 * CompetencyScorecard.jsx — per-competency ratings + overall hiring recommendation.
 *
 * Props:
 *   recommendation       — 'strong_hire' | 'hire' | 'maybe' | 'no_hire'
 *   recommendationLabel  — human label from the API
 *   competencies         — [{ name, score, rating, note }]
 */
import React from 'react'

const REC_STYLES = {
  strong_hire: { label: 'Strong hire', cls: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300' },
  hire: { label: 'Hire', cls: 'bg-green-500/15 border-green-500/40 text-green-300' },
  maybe: { label: 'Maybe / lean hire', cls: 'bg-amber-500/15 border-amber-500/40 text-amber-300' },
  no_hire: { label: 'No hire', cls: 'bg-red-500/15 border-red-500/40 text-red-300' },
}

function barColor(score) {
  return score >= 75 ? 'bg-emerald-500' : score >= 55 ? 'bg-amber-500' : 'bg-red-500'
}

export default function CompetencyScorecard({ recommendation, recommendationLabel, competencies = [] }) {
  const rec = REC_STYLES[recommendation]
  if (!rec && !competencies.length) return null

  return (
    <div className="glass-card p-5 border border-surface-800 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-white">Hiring scorecard</h3>
        {rec && (
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${rec.cls}`}>
            {recommendationLabel || rec.label}
          </span>
        )}
      </div>
      <div className="space-y-3">
        {competencies.map((c, i) => (
          <div key={i}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-surface-300 font-medium">{c.name}</span>
              <span className="text-surface-400">
                {Math.round(c.score || 0)} · <span className="capitalize">{c.rating}</span>
              </span>
            </div>
            <div className="bg-surface-800 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${barColor(c.score || 0)}`}
                style={{ width: `${Math.min(100, Math.max(0, c.score || 0))}%` }}
              />
            </div>
            {c.note && <p className="text-[11px] text-surface-500 mt-1">{c.note}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
