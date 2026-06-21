import { useState } from 'react'
import { Terminal, CheckCircle2, XCircle, Loader2, Play } from 'lucide-react'

/**
 * Inline practical command/code input for the interview (P2.4).
 *
 * For a practical question the candidate can type the exact command(s) or code
 * they'd run; we POST it to the backend validate endpoint, which grades it with
 * the SAME free, deterministic engines the labs use (no paid API). The verdict
 * + feedback render right here so the bot can probe deeper or move on.
 *
 * Props:
 *   onValidate(answer) -> Promise<{ validated, method, feedback }>
 *   onValidated(result, answer)  optional — parent reacts to a successful check
 *   disabled
 */
export default function PracticalAnswerPanel({ onValidate, onValidated, disabled }) {
  const [value, setValue] = useState('')
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState(null)

  const check = async () => {
    const answer = value.trim()
    if (!answer || checking || disabled) return
    setChecking(true)
    setResult(null)
    try {
      const res = await onValidate(answer)
      setResult(res)
      if (res?.validated && typeof onValidated === 'function') {
        onValidated(res, answer)
      }
    } catch {
      setResult({
        validated: false,
        feedback: "Couldn't check that just now — try again or describe your approach in the answer box.",
      })
    } finally {
      setChecking(false)
    }
  }

  // Ctrl/Cmd+Enter submits; plain Enter inserts a newline (this is a code box).
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      check()
    }
  }

  return (
    <div className="p-3 border-t border-surface-800 bg-surface-950/40 space-y-2">
      <p className="text-xs text-cyan-400 flex items-center gap-1">
        <Terminal size={12} /> Type the command or code you'd run — I'll check it
      </p>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled || checking}
        rows={3}
        spellCheck={false}
        placeholder={'e.g. systemctl status sshd && systemctl start sshd'}
        className="input-field w-full text-xs font-mono leading-relaxed resize-y min-h-[64px]"
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={check}
          disabled={disabled || checking || !value.trim()}
          className="btn-primary text-xs py-1.5 px-3 inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          {checking ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          {checking ? 'Checking…' : 'Check answer'}
        </button>
        <span className="text-[10px] text-surface-500">Ctrl/⌘+Enter to check</span>
      </div>

      {result && (
        <div
          className={`text-xs rounded-lg p-2 flex items-start gap-2 ${
            result.validated
              ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-200'
              : 'bg-amber-500/10 border border-amber-500/30 text-amber-100'
          }`}
        >
          {result.validated ? (
            <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
          ) : (
            <XCircle size={14} className="mt-0.5 shrink-0" />
          )}
          <span className="whitespace-pre-wrap">{result.feedback}</span>
        </div>
      )}
    </div>
  )
}
