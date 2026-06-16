/**
 * AIScorecard.jsx
 *
 * Rich post-interview AI scorecard component.
 * Displays after end_round() completes and report is available.
 *
 * Props:
 *   report   — InterviewReport object from API
 *   round    — InterviewRound object
 *   extras   — { confidence_signals, time_management_note, benchmark_comparison }
 *              (only present when LLM scorecard is active)
 */

import React, { useMemo } from 'react'

// ---------------------------------------------------------------------------
// Score gauge (circular SVG)
// ---------------------------------------------------------------------------

function ScoreGauge({ score, label, size = 80 }) {
  const pct = Math.min(100, Math.max(0, score || 0))
  const r = (size / 2) - 8
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  const color = pct >= 75 ? '#22c55e' : pct >= 55 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="#1e293b" strokeWidth="6"
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
      </svg>
      <span className="text-lg font-bold text-white -mt-[52px] mb-[28px] z-10 relative">
        {Math.round(pct)}
      </span>
      <span className="text-[11px] text-slate-400 text-center leading-tight">{label}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Horizontal score bar
// ---------------------------------------------------------------------------

function ScoreBar({ label, score, benchmark }) {
  const pct = Math.min(100, Math.max(0, score || 0))
  const color = pct >= 75 ? 'bg-green-500' : pct >= 55 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="flex items-center gap-3 py-1">
      <span className="text-slate-300 text-sm w-44 shrink-0">{label}</span>
      <div className="flex-1 bg-slate-800 rounded-full h-2 relative overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
        {benchmark != null && (
          <div
            className="absolute top-0 h-full w-0.5 bg-blue-400 opacity-60"
            style={{ left: `${benchmark}%` }}
            title={`Benchmark: ${benchmark}`}
          />
        )}
      </div>
      <span className="text-white font-semibold text-sm w-10 text-right">{Math.round(pct)}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// STAR badge
// ---------------------------------------------------------------------------

function StarBadge({ starData }) {
  if (!starData) return null
  const { star_score = 0, missing_components = [], coaching_note } = starData
  const labels = { 0: 'No STAR', 1: 'Weak', 2: 'Partial', 3: 'Good STAR', 4: 'Full STAR' }
  const colors = {
    0: 'bg-red-900 text-red-300',
    1: 'bg-orange-900 text-orange-300',
    2: 'bg-amber-900 text-amber-300',
    3: 'bg-green-900 text-green-300',
    4: 'bg-emerald-900 text-emerald-300',
  }

  return (
    <div className={`inline-flex items-center gap-2 px-2 py-1 rounded text-xs font-medium ${colors[star_score] || colors[0]}`}>
      <span>STAR {star_score}/4</span>
      <span>{labels[star_score]}</span>
      {missing_components.length > 0 && (
        <span className="opacity-70">missing: {missing_components.join(', ')}</span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AIScorecard({ report, round, extras = {} }) {
  if (!report) return null

  const {
    overall_score = 0,
    technical_score = 0,
    communication_score = 0,
    problem_solving_score = 0,
    practical_score = 0,
    presence_score = 0,
    resume_alignment_score = 0,
    passed = false,
    summary = '',
    strengths = [],
    improvements = [],
    question_breakdown = [],
    study_plan = [],
  } = report

  const {
    confidence_signals = '',
    time_management_note = '',
    benchmark_comparison = '',
  } = extras

  // Benchmarks by dimension (typical mid-level DevOps/SRE scores)
  const BENCHMARKS = {
    technical: 68,
    communication: 72,
    problem_solving: 65,
    practical: 60,
    presence: 70,
    resume_alignment: 65,
  }

  const dimensions = useMemo(() => [
    { label: 'Technical Depth', score: technical_score, benchmark: BENCHMARKS.technical },
    { label: 'Communication', score: communication_score, benchmark: BENCHMARKS.communication },
    { label: 'Problem Solving', score: problem_solving_score, benchmark: BENCHMARKS.problem_solving },
    { label: 'Practical / Tooling', score: practical_score, benchmark: BENCHMARKS.practical },
    { label: 'Presence & Confidence', score: presence_score, benchmark: BENCHMARKS.presence },
    { label: 'Resume Alignment', score: resume_alignment_score, benchmark: BENCHMARKS.resume_alignment },
  ], [report])

  const passColor = passed ? 'text-green-400' : 'text-red-400'
  const passBg = passed ? 'bg-green-950 border-green-700' : 'bg-red-950 border-red-700'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={`rounded-xl border p-5 ${passBg}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">
              {passed ? 'Round Passed' : 'Round Not Passed'}
            </h2>
            <p className="text-slate-300 text-sm leading-relaxed max-w-xl">{summary}</p>
          </div>
          <div className="shrink-0">
            <ScoreGauge score={overall_score} label="Overall" size={90} />
          </div>
        </div>
      </div>

      {/* Dimension gauges */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
        <h3 className="text-white font-semibold mb-4">Score Breakdown</h3>
        <div className="space-y-2">
          {dimensions.map(d => (
            <ScoreBar
              key={d.label}
              label={d.label}
              score={d.score}
              benchmark={d.benchmark}
            />
          ))}
        </div>
        <p className="text-slate-500 text-xs mt-3">
          Blue line = benchmark score for {round?.campaign?.experience_level || 'mid'}-level candidates
        </p>
      </div>

      {/* AI insights row */}
      {(confidence_signals || time_management_note || benchmark_comparison) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {confidence_signals && (
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-1">Confidence</p>
              <p className="text-slate-300 text-sm">{confidence_signals}</p>
            </div>
          )}
          {time_management_note && (
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-1">Pacing</p>
              <p className="text-slate-300 text-sm">{time_management_note}</p>
            </div>
          )}
          {benchmark_comparison && (
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-1">vs. Peers</p>
              <p className="text-slate-300 text-sm">{benchmark_comparison}</p>
            </div>
          )}
        </div>
      )}

      {/* Strengths + Improvements */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {strengths.length > 0 && (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
            <h3 className="text-green-400 font-semibold mb-3 flex items-center gap-2">
              <span>Strengths</span>
            </h3>
            <ul className="space-y-2">
              {strengths.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-300 text-sm">
                  <span className="text-green-500 mt-0.5">+</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {improvements.length > 0 && (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
            <h3 className="text-amber-400 font-semibold mb-3 flex items-center gap-2">
              <span>Areas to Improve</span>
            </h3>
            <ul className="space-y-2">
              {improvements.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-300 text-sm">
                  <span className="text-amber-500 mt-0.5">!</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Per-question breakdown */}
      {question_breakdown.length > 0 && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <h3 className="text-white font-semibold mb-3">Question Breakdown</h3>
          <div className="space-y-3">
            {question_breakdown.slice(0, 10).map((q, i) => {
              const score = q.score || 0
              const quality = q.metadata?.quality || (score >= 75 ? 'strong' : score >= 50 ? 'adequate' : 'weak')
              const qualityColor = {
                strong: 'text-green-400',
                adequate: 'text-amber-400',
                weak: 'text-red-400',
                brief: 'text-orange-400',
                skipped: 'text-slate-500',
              }[quality] || 'text-slate-400'
              const starData = q.metadata?.star_analysis

              return (
                <div key={i} className="border border-slate-800 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-400 text-xs">Answer {i + 1}</span>
                    <div className="flex items-center gap-2">
                      {starData && <StarBadge starData={starData} />}
                      <span className={`text-sm font-semibold ${qualityColor}`}>
                        {Math.round(score)}/100
                      </span>
                    </div>
                  </div>
                  <p className="text-slate-300 text-sm line-clamp-2">{q.content}</p>
                  {q.metadata?.feedback && (
                    <p className="text-slate-500 text-xs mt-1 italic">{q.metadata.feedback}</p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Study plan */}
      {study_plan.length > 0 && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <h3 className="text-white font-semibold mb-3">Recommended Next Steps</h3>
          <div className="flex flex-wrap gap-2">
            {study_plan.map((item, i) => (
              <a
                key={i}
                href={item.url}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600
                           rounded-lg text-slate-300 text-sm transition-colors"
              >
                {item.title}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
