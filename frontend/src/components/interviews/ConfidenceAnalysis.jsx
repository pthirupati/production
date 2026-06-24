/**
 * ConfidenceAnalysis.jsx — heuristic confidence/communication read-out.
 *
 * Clearly labelled as a heuristic estimate (derived from free signals: filler
 * words, answer length, pace, skips). No paid vision/NLP.
 *
 * Props: analysis — confidence_analysis object from the report.
 */
import React from 'react'
import { Activity, Info } from 'lucide-react'

function Stat({ label, value, suffix = '' }) {
  if (value == null) return null
  return (
    <div className="text-center">
      <p className="text-lg font-bold text-white">{value}{suffix}</p>
      <p className="text-[10px] text-surface-500 uppercase tracking-wide">{label}</p>
    </div>
  )
}

export default function ConfidenceAnalysis({ analysis }) {
  if (!analysis) return null
  const phraseCoach = analysis.phrase_coaching
  const hasScore = analysis.confidence_score != null

  if (!hasScore && !phraseCoach && !analysis.round_narrative) return null

  const score = analysis.confidence_score
  const color = score == null ? 'text-surface-400' : score >= 75 ? 'text-emerald-400' : score >= 58 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="glass-card p-5 border border-surface-800 space-y-4">
      {hasScore && (
        <>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity size={15} className="text-indigo-400" /> Communication & confidence
            </h3>
            <span className={`text-2xl font-bold ${color}`}>{score}<span className="text-sm text-surface-500">/100</span></span>
          </div>
          <p className="text-xs text-surface-400">{analysis.summary}</p>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 pt-2 border-t border-surface-800">
            <Stat label="Avg words" value={analysis.avg_answer_words} />
            <Stat label="Fillers/100w" value={analysis.filler_per_100_words} />
            <Stat label="Words/min" value={analysis.words_per_minute} />
            <Stat label="Attempted" value={analysis.answers_attempted} />
            <Stat label="Skipped" value={analysis.answers_skipped} />
          </div>
        </>
      )}
      {analysis.round_narrative && (
        <div className={hasScore ? 'pt-2 border-t border-surface-800' : ''}>
          <p className="text-[10px] uppercase tracking-wide text-surface-500 mb-1">Round narrative</p>
          <p className="text-xs text-surface-300 leading-relaxed">{analysis.round_narrative}</p>
        </div>
      )}
      {phraseCoach?.phrases_referenced?.length > 0 && (
        <div className="pt-2 border-t border-surface-800">
          <p className="text-[10px] uppercase tracking-wide text-surface-500 mb-2">Phrases from your answers</p>
          <div className="flex flex-wrap gap-1.5">
            {phraseCoach.phrases_referenced.map((p, i) => (
              <span key={i} className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                {p}
              </span>
            ))}
          </div>
          {phraseCoach.summary_line && (
            <p className="text-xs text-surface-400 mt-2">{phraseCoach.summary_line}</p>
          )}
        </div>
      )}
      <p className="text-[10px] text-surface-600 flex items-start gap-1.5">
        <Info size={11} className="shrink-0 mt-0.5" />
        Heuristic estimate from your transcript and timing — not a clinical or vision-based measure.
      </p>
    </div>
  )
}
