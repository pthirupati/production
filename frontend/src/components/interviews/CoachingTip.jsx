/**
 * CoachingTip.jsx — instant coaching feedback shown after an answer in
 * practice mode (parity: interviewai.io practice mode).
 *
 * Props: coaching — { tip, all_tips, score, quality, signals }
 */
import React from 'react'
import { Lightbulb } from 'lucide-react'

export default function CoachingTip({ coaching }) {
  if (!coaching) return null
  const score = coaching.score || 0
  const tone =
    score >= 75 ? 'border-emerald-500/40 bg-emerald-500/10' :
    score >= 55 ? 'border-amber-500/40 bg-amber-500/10' :
    'border-red-500/40 bg-red-500/10'

  return (
    <div className={`rounded-xl border p-3 ${tone} animate-fade-in`}>
      <div className="flex items-start gap-2">
        <Lightbulb size={15} className="text-amber-300 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-white flex items-center gap-2">
            Coaching tip
            <span className="text-[10px] font-normal text-surface-400">· {Math.round(score)}/100 · {coaching.quality}</span>
          </p>
          {coaching.quoted_phrase && (
            <p className="text-[10px] text-indigo-300/90 mt-1">
              Thread: “{coaching.quoted_phrase}”
            </p>
          )}
          <ul className="mt-1 space-y-1">
            {(coaching.all_tips || [coaching.tip]).map((t, i) => (
              <li key={i} className="text-xs text-surface-300">• {t}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
