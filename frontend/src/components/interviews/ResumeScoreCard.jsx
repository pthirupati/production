/**
 * ResumeScoreCard.jsx — resume score display (only when a resume was uploaded).
 */

import React from 'react'
import { FileText, Lightbulb, Loader2, Upload } from 'lucide-react'

const SUBSCORE_LABELS = {
  skills_match: 'Skills match',
  experience: 'Experience fit',
  clarity: 'Clarity & structure',
  keywords: 'Impact & keywords',
}

const SUBSCORE_ORDER = ['skills_match', 'experience', 'clarity', 'keywords']

function barColor(pct) {
  return pct >= 75 ? 'bg-green-500' : pct >= 55 ? 'bg-amber-500' : 'bg-red-500'
}

function gaugeColor(pct) {
  return pct >= 75 ? '#22c55e' : pct >= 55 ? '#f59e0b' : '#ef4444'
}

function ScoreGauge({ score }) {
  const pct = Math.min(100, Math.max(0, Math.round(score || 0)))
  const size = 84
  const r = size / 2 - 7
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1e293b" strokeWidth="6" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={gaugeColor(pct)}
          strokeWidth="6"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-bold text-white leading-none">{pct}</span>
        <span className="text-[10px] text-surface-400">/ 100</span>
      </div>
    </div>
  )
}

function SubBar({ label, score }) {
  const pct = Math.min(100, Math.max(0, Math.round(score || 0)))
  return (
    <div className="flex items-center gap-3">
      <span className="text-surface-300 text-xs w-32 shrink-0">{label}</span>
      <div className="flex-1 bg-surface-800 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barColor(pct)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-white font-semibold text-xs w-8 text-right">{pct}</span>
    </div>
  )
}

export function NoResumeUploaded() {
  return (
    <div className="rounded-xl border border-dashed border-surface-700 bg-surface-900/30 p-4 flex items-start gap-3">
      <div className="w-10 h-10 rounded-lg bg-surface-800 border border-surface-700 flex items-center justify-center shrink-0">
        <Upload size={18} className="text-surface-500" />
      </div>
      <div>
        <p className="text-sm font-medium text-surface-300">No resume uploaded</p>
        <p className="text-xs text-surface-500 mt-1 leading-relaxed">
          You skipped the resume — that&apos;s fine. We&apos;ll personalize questions from your career fields.
          Upload a PDF or DOCX above to see a resume score and improvement tips.
        </p>
      </div>
    </div>
  )
}

export default function ResumeScoreCard({ score, loading = false }) {
  if (loading) {
    return (
      <div className="rounded-xl border border-surface-800 bg-surface-900/40 p-4 flex items-center gap-2 text-surface-400 text-sm">
        <Loader2 size={16} className="animate-spin" /> Scoring your resume…
      </div>
    )
  }

  if (!score || score.has_resume === false || score.overall_score == null) {
    return <NoResumeUploaded />
  }

  const subs = score.subscores || {}
  const tips = Array.isArray(score.tips) ? score.tips : []
  const matched = Array.isArray(score.matched_keywords) ? score.matched_keywords : []
  const overall = Math.round(score.overall_score)
  const headline =
    overall >= 75 ? 'Strong resume for this role' : overall >= 55 ? 'Decent — a few tweaks will help' : 'Needs work for this role'

  return (
    <div className="rounded-xl border border-surface-800 bg-surface-900/40 p-4 space-y-4 animate-fade-in">
      <div className="flex items-center gap-4">
        <ScoreGauge score={overall} />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white flex items-center gap-2">
            <FileText size={15} className="text-indigo-400" /> Resume score
          </p>
          <p className="text-xs text-surface-400 mt-0.5">{headline}</p>
        </div>
      </div>

      <div className="space-y-2">
        {SUBSCORE_ORDER.filter(k => k in subs).map(k => (
          <SubBar key={k} label={SUBSCORE_LABELS[k] || k} score={subs[k]} />
        ))}
      </div>

      {matched.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {matched.slice(0, 10).map(kw => (
            <span
              key={kw}
              className="px-2 py-0.5 rounded text-[11px] border border-green-500/30 bg-green-500/10 text-green-300"
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      {tips.length > 0 && (
        <div className="rounded-lg bg-indigo-500/5 border border-indigo-500/20 p-3">
          <p className="text-xs font-medium text-indigo-300 flex items-center gap-1.5 mb-2">
            <Lightbulb size={13} /> Improvement tips
          </p>
          <ul className="space-y-1.5">
            {tips.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-surface-300 leading-relaxed">
                <span className="text-indigo-400 mt-0.5">→</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
