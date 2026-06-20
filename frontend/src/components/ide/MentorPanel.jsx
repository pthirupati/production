import { useState } from 'react'
import {
  Sparkles, AlertCircle, FlaskConical, BookOpen, Wand2, ShieldAlert,
  Info, Loader2, Lock, Unlock, ChevronRight, RefreshCw,
} from 'lucide-react'

/**
 * AI Mentor side panel — rule-based, FREE (no paid LLM). It renders the
 * structured guidance returned by the backend /mentor/ endpoint (see
 * apps/labs/ide_mentor.py): error explanations, conceptual failing-test
 * explanations, concept teaching, and style/complexity/security suggestions.
 *
 * The reference solution is NEVER shown inline. It lives behind an explicit
 * "Unlock reference solution" button gated by a confirm step; only after the
 * user confirms does the parent re-request the mentor with unlock_reference and
 * pass the unlocked reference down here.
 *
 * Props:
 *   report        mentor response { summary, notes:[{kind,title,detail,line}], reference }
 *   loading       boolean
 *   onAsk         (requested) => void   — request analysis ('all'|'error'|'tests'|'improve'|'concept')
 *   onUnlock      () => void            — confirmed unlock of the reference solution
 *   disabled      boolean               — no run/test context yet
 */

const KIND_META = {
  error: { icon: AlertCircle, color: 'text-accent-red', label: 'Error' },
  test: { icon: FlaskConical, color: 'text-accent-amber', label: 'Test' },
  concept: { icon: BookOpen, color: 'text-accent-cyan', label: 'Concept' },
  style: { icon: Wand2, color: 'text-accent-purple', label: 'Improve' },
  security: { icon: ShieldAlert, color: 'text-accent-red', label: 'Security' },
  info: { icon: Info, color: 'text-surface-400', label: 'Info' },
}

function NoteCard({ note }) {
  const meta = KIND_META[note.kind] || KIND_META.info
  const Icon = meta.icon
  return (
    <div className="rounded-lg border border-surface-800 bg-surface-900/60 p-3">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={13} className={`${meta.color} shrink-0`} />
        <span className="text-xs font-semibold text-surface-200">{note.title}</span>
        {typeof note.line === 'number' && (
          <span className="ml-auto text-[10px] font-mono text-surface-500 px-1.5 py-0.5 rounded bg-surface-800">
            line {note.line}
          </span>
        )}
      </div>
      <p className="text-[12px] leading-relaxed text-surface-400 whitespace-pre-wrap">{note.detail}</p>
    </div>
  )
}

const ASK_BUTTONS = [
  { key: 'error', label: 'Explain error', icon: AlertCircle },
  { key: 'tests', label: 'Explain tests', icon: FlaskConical },
  { key: 'concept', label: 'Teach concept', icon: BookOpen },
  { key: 'improve', label: 'Improve code', icon: Wand2 },
]

export default function MentorPanel({ report, loading, onAsk, onUnlock, disabled }) {
  const [confirmUnlock, setConfirmUnlock] = useState(false)
  const reference = report?.reference
  const referenceUnlocked = reference?.unlocked
  const referenceAvailable = referenceUnlocked || reference?.reference_available

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="shrink-0 flex items-center gap-1.5 px-3 py-2 border-b border-surface-800 bg-surface-900/60">
        <Sparkles size={14} className="text-accent-purple" />
        <span className="text-xs font-semibold text-surface-200">AI Mentor</span>
        <span className="text-[10px] text-surface-500 px-1.5 py-0.5 rounded bg-surface-800">rule-based · free</span>
        <button
          onClick={() => onAsk('all')}
          disabled={loading || disabled}
          className="ml-auto p-1 rounded text-surface-400 hover:text-accent-cyan disabled:opacity-40"
          title="Re-analyze with the latest run/test output"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Quick-ask buttons */}
      <div className="shrink-0 grid grid-cols-2 gap-1.5 p-2 border-b border-surface-800">
        {ASK_BUTTONS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => onAsk(key)}
            disabled={loading || disabled}
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-[11px] font-medium border border-surface-700 text-surface-300 hover:border-accent-purple hover:text-accent-purple disabled:opacity-40 transition-colors"
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto p-2 space-y-2">
        {disabled && !report && (
          <p className="text-[12px] text-surface-500 p-2 leading-relaxed">
            Run your code or click Check Solution, then ask the mentor to explain what happened.
            It explains errors, stack traces, and what failing tests check — without giving away
            the answer.
          </p>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-surface-400 text-xs p-2">
            <Loader2 size={13} className="animate-spin" /> Analyzing your code…
          </div>
        )}

        {report?.summary && !loading && (
          <p className="text-[12px] text-surface-300 px-1 leading-relaxed">{report.summary}</p>
        )}

        {!loading && (report?.notes || []).map((note, i) => <NoteCard key={i} note={note} />)}
      </div>

      {/* Reference solution — gated reveal */}
      <div className="shrink-0 border-t border-surface-800 p-2">
        {referenceUnlocked ? (
          <div className="rounded-lg border border-accent-amber/30 bg-accent-amber/5 p-3 space-y-2 max-h-56 overflow-auto">
            <div className="flex items-center gap-1.5">
              <Unlock size={13} className="text-accent-amber" />
              <span className="text-xs font-semibold text-accent-amber">Reference solution</span>
            </div>
            {reference.solution_explanation && (
              <p className="text-[12px] text-surface-300 whitespace-pre-wrap leading-relaxed">
                {reference.solution_explanation}
              </p>
            )}
            {reference.reference && (
              <pre className="text-[11px] font-mono text-surface-200 whitespace-pre-wrap break-words bg-surface-950 rounded p-2 border border-surface-800">
                {reference.reference}
              </pre>
            )}
          </div>
        ) : confirmUnlock ? (
          <div className="rounded-lg border border-accent-amber/30 bg-accent-amber/5 p-3 space-y-2">
            <p className="text-[11px] text-surface-300 leading-relaxed">
              This reveals the reference solution and explanation. Try the mentor's hints first —
              you learn more by solving it yourself. Reveal anyway?
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => { setConfirmUnlock(false); onUnlock() }}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-semibold bg-accent-amber/20 text-accent-amber border border-accent-amber/40 hover:bg-accent-amber/30"
              >
                <Unlock size={12} /> Yes, reveal it
              </button>
              <button
                onClick={() => setConfirmUnlock(false)}
                className="px-2.5 py-1.5 rounded-md text-[11px] font-medium border border-surface-700 text-surface-300 hover:text-surface-100"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setConfirmUnlock(true)}
            disabled={!referenceAvailable}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[11px] font-medium border border-surface-700 text-surface-400 hover:border-accent-amber hover:text-accent-amber disabled:opacity-40 transition-colors"
            title={referenceAvailable ? 'Reveal the reference solution (confirm required)' : 'No reference solution provided for this scenario'}
          >
            <Lock size={12} /> Unlock reference solution
            <ChevronRight size={12} className="ml-auto opacity-60" />
          </button>
        )}
      </div>
    </div>
  )
}
