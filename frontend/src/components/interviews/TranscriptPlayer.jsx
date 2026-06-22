/**
 * TranscriptPlayer.jsx — timestamped transcript + conversation playback, plus
 * résumé highlights mapped to the topics they were probed by.
 *
 * "Playback" here is a synchronized text walk-through (optionally re-speaking
 * each line with the browser SpeechSynthesis — 100% free, no media file needed).
 *
 * Props:
 *   data — { transcript:[{role,content,offset_seconds,topic,score}],
 *            resume_highlights:[{skill,mapped_topic,covered,question_count}],
 *            duration_seconds }
 */
import React, { useEffect, useRef, useState } from 'react'
import { Play, Pause, FileText, CheckCircle2, Circle, User, Bot } from 'lucide-react'

function fmt(sec) {
  if (sec == null) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function TranscriptPlayer({ data }) {
  const [playingIdx, setPlayingIdx] = useState(-1)
  const timerRef = useRef(null)
  const transcript = data?.transcript || []
  const highlights = data?.resume_highlights || []

  const stop = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = null
    try { window.speechSynthesis?.cancel() } catch { /* ignore */ }
    setPlayingIdx(-1)
  }

  useEffect(() => () => stop(), [])

  // Walk the transcript line by line, pacing roughly to content length.
  const playFrom = (start) => {
    if (timerRef.current) clearTimeout(timerRef.current)
    const step = (i) => {
      if (i >= transcript.length) { stop(); return }
      setPlayingIdx(i)
      const line = transcript[i]
      const el = document.getElementById(`tx-line-${i}`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Optional free re-speak of interviewer lines.
      try {
        if (line.role === 'interviewer' && window.speechSynthesis) {
          const u = new SpeechSynthesisUtterance((line.content || '').slice(0, 240))
          u.rate = 1.05
          window.speechSynthesis.cancel()
          window.speechSynthesis.speak(u)
        }
      } catch { /* ignore */ }
      const words = (line.content || '').split(/\s+/).length
      const dwell = Math.min(6000, Math.max(1400, words * 60))
      timerRef.current = setTimeout(() => step(i + 1), dwell)
    }
    step(start)
  }

  if (!transcript.length) {
    return <p className="text-xs text-surface-500">No transcript recorded for this round.</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <FileText size={15} className="text-indigo-400" /> Transcript & playback
          {data?.duration_seconds != null && (
            <span className="text-xs text-surface-500 font-normal">· {fmt(data.duration_seconds)}</span>
          )}
        </h3>
        <button
          type="button"
          onClick={() => (playingIdx >= 0 ? stop() : playFrom(0))}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/10"
        >
          {playingIdx >= 0 ? <><Pause size={12} /> Stop</> : <><Play size={12} /> Play conversation</>}
        </button>
      </div>

      {highlights.length > 0 && (
        <div className="glass-card p-3 border border-surface-800">
          <p className="text-xs font-semibold text-surface-300 mb-2">Résumé skills covered</p>
          <div className="flex flex-wrap gap-1.5">
            {highlights.map((h, i) => (
              <span
                key={i}
                title={h.covered ? `Probed in ${h.question_count} question(s)` : 'Not covered this round'}
                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] border ${
                  h.covered
                    ? 'border-emerald-500/30 text-emerald-300 bg-emerald-500/5'
                    : 'border-surface-700 text-surface-500'
                }`}
              >
                {h.covered ? <CheckCircle2 size={11} /> : <Circle size={11} />}
                {h.skill}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="max-h-96 overflow-y-auto space-y-2 pr-1">
        {transcript.map((m, i) => {
          if (m.role === 'system') return null
          const mine = m.role === 'candidate'
          return (
            <div
              id={`tx-line-${i}`}
              key={m.id || i}
              className={`flex gap-2 ${mine ? 'flex-row-reverse' : ''} ${playingIdx === i ? 'opacity-100' : 'opacity-90'}`}
            >
              <div className={`shrink-0 mt-1 ${mine ? 'text-cyan-400' : 'text-indigo-400'}`}>
                {mine ? <User size={14} /> : <Bot size={14} />}
              </div>
              <div
                className={`rounded-xl px-3 py-2 max-w-[80%] text-xs border ${
                  playingIdx === i ? 'ring-1 ring-indigo-400' : ''
                } ${mine ? 'bg-cyan-500/10 border-cyan-500/20 text-surface-200' : 'bg-surface-800/60 border-surface-700 text-surface-300'}`}
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[10px] text-surface-500">{fmt(m.offset_seconds)}</span>
                  {m.topic && <span className="text-[10px] text-indigo-400">{m.topic}</span>}
                  {mine && m.score != null && (
                    <span className="text-[10px] text-surface-400">· {Math.round(m.score)}/100</span>
                  )}
                </div>
                {m.content}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
