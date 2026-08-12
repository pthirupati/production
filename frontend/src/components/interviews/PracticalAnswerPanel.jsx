import { useCallback, useEffect, useRef, useState } from 'react'
import { Terminal, CheckCircle2, XCircle, Loader2, Play, Code2, ExternalLink } from 'lucide-react'
import CodeEditor from '../ide/CodeEditor'
import LabTerminal from '../LabTerminal'
import VsCodeWorkbench, { VscPanelTab } from '../ide/VsCodeWorkbench'
import '../../styles/vscode-workbench.css'
import { labApi } from '../../api/labs'

/**
 * Inline practical command/code workspace for the interview (P2.4 / WS6).
 *
 * Instead of a bare textarea, the candidate works in a REAL environment inline:
 *   * practical_config.kind === 'code'    → an embedded CodeEditor (CodeMirror)
 *     with language-aware highlighting; Ctrl/⌘+Enter (or "Check answer") grades
 *     it via the same free, deterministic sandbox the coding-IDE labs use.
 *   * practical_config.kind === 'command' → an embedded LabTerminal wired to the
 *     interview's practical-lab session, so the candidate types and runs real
 *     commands inline. A compact "command to grade" field feeds "Check answer".
 *
 * "Check answer" POSTs to the existing /practical-validate/ endpoint for BOTH
 * kinds (no paid API). The verdict + feedback render right here so the bot can
 * probe deeper or move on. "Open full lab in a new tab" stays as a secondary
 * affordance for candidates who prefer the standalone lab UI.
 *
 * Props:
 *   onValidate(answer) -> Promise<{ validated, method, feedback }>
 *   onValidated(result, answer)        optional — parent reacts to a pass
 *   practicalConfig                    { kind:'code'|'command', language?, ... } | null
 *   labSession                         { session_id, lab_url, scenario_title } | null
 *   onStartLab()  -> Promise<labInfo>  start the practical lab session inline
 *   onOpenLab()                        open the full lab in a new tab (secondary)
 *   disabled
 */
export default function PracticalAnswerPanel({
  onValidate,
  onValidated,
  practicalConfig,
  labSession,
  onStartLab,
  onOpenLab,
  disabled,
}) {
  const kind = practicalConfig?.kind === 'command' ? 'command' : 'code'
  const language = practicalConfig?.language || 'python'

  const [value, setValue] = useState('')
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState(null)

  // --- command-mode lab session (xterm needs a full RUNNING session object) ---
  const [session, setSession] = useState(null)   // full LabSession status object
  const [labStarting, setLabStarting] = useState(false)
  const [labError, setLabError] = useState('')
  const pollRef = useRef(null)
  const sessionId = labSession?.session_id || null

  // Reset the workspace whenever the practical question (kind/language) changes,
  // so a fresh question never inherits a previous answer or stale verdict.
  useEffect(() => {
    setValue('')
    setResult(null)
  }, [kind, language])

  // Fetch + poll the lab session status so LabTerminal can attach once RUNNING.
  // Only relevant in command mode; code mode never touches a terminal session.
  const refreshSession = useCallback(async (id) => {
    if (!id) return null
    try {
      const s = await labApi.getSessionStatus(id)
      setSession(s)
      setLabError('')
      return s
    } catch {
      setLabError('Could not load the lab session — retry or open it in a new tab.')
      return null
    }
  }, [])

  const clearPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  useEffect(() => {
    clearPoll()
    setSession(null)
    if (kind !== 'command' || !sessionId) return
    let cancelled = false
    refreshSession(sessionId).then((s) => {
      if (cancelled || !s) return
      // Keep polling until the environment is RUNNING (provisioning can lag).
      if (s.status !== 'RUNNING') {
        pollRef.current = setInterval(async () => {
          const next = await refreshSession(sessionId)
          if (next?.status === 'RUNNING') clearPoll()
        }, 4000)
      }
    })
    return () => { cancelled = true; clearPoll() }
  }, [kind, sessionId, refreshSession])

  // Start the practical-lab session inline when we don't have one yet.
  const startLab = async () => {
    if (labStarting || disabled || typeof onStartLab !== 'function') return
    setLabStarting(true)
    setLabError('')
    try {
      const info = await onStartLab()
      if (info?.error) {
        setLabError(info.error)
      } else if (info?.session_id) {
        await refreshSession(info.session_id)
      }
    } catch {
      setLabError('Could not start the lab environment — try again or open the full lab.')
    } finally {
      setLabStarting(false)
    }
  }

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

  // Ctrl/Cmd+Enter submits in both modes (CodeEditor binds it via onRun; the
  // command field binds it directly). Plain Enter inserts a newline.
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      check()
    }
  }

  const isCommand = kind === 'command'

  return (
    <div className="p-3 border-t border-surface-800 bg-surface-950/40 space-y-2" data-interview-answer="1">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-cyan-400 flex items-center gap-1">
          {isCommand ? <Terminal size={12} /> : <Code2 size={12} />}
          {isCommand
            ? 'Run real commands in the lab below — then check the command you used'
            : `Write your ${language} solution — I'll grade it`}
        </p>
        {typeof onOpenLab === 'function' && (
          <button
            type="button"
            onClick={onOpenLab}
            className="text-[10px] text-surface-400 hover:text-white inline-flex items-center gap-1 shrink-0"
            title="Open the full lab in a new tab"
          >
            <ExternalLink size={11} /> Open in new tab
          </button>
        )}
      </div>

      {isCommand ? (
        <>
          {/* Embedded real terminal (xterm + ws) wired to the interview lab. */}
          <div className="h-56 rounded-lg overflow-hidden border border-surface-800 bg-[#020617]">
            {sessionId && session?.status === 'RUNNING' ? (
              <LabTerminal
                sessionId={sessionId}
                session={session}
                className="h-full"
                welcomeHint="Interview practical — run your commands here, then check the one that fixes it."
              />
            ) : (
              <div className="h-full flex flex-col items-center justify-center gap-2 text-center px-4">
                {labError ? (
                  <p className="text-xs text-amber-300">{labError}</p>
                ) : sessionId ? (
                  <p className="text-xs text-surface-400 inline-flex items-center gap-1.5">
                    <Loader2 size={13} className="animate-spin" />
                    Starting your lab environment…
                  </p>
                ) : (
                  <p className="text-xs text-surface-400">
                    Start the lab to run commands inline.
                  </p>
                )}
                {(!sessionId || labError) && (
                  <button
                    type="button"
                    onClick={startLab}
                    disabled={labStarting || disabled}
                    className="btn-primary text-xs py-1.5 px-3 inline-flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {labStarting ? <Loader2 size={12} className="animate-spin" /> : <Terminal size={12} />}
                    {labStarting ? 'Starting…' : sessionId ? 'Retry' : 'Start lab'}
                  </button>
                )}
              </div>
            )}
          </div>
          {/* Compact field to submit the exact command for grading. */}
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={disabled || checking}
            spellCheck={false}
            placeholder={'Command to grade — e.g. systemctl start sshd'}
            className="input-field w-full text-xs font-mono"
          />
        </>
      ) : (
        <div className="h-72 rounded-lg overflow-hidden border border-surface-800">
          <VsCodeWorkbench
            theme="app"
            className="h-full"
            title={`${language} workspace`}
            subtitle="Interview practical"
            showSidebar={false}
            editor={(
              <CodeEditor value={value} onChange={setValue} language={language} onRun={check} readOnly={disabled || checking} />
            )}
            bottomPanel={{
              height: 48,
              tabs: <VscPanelTab active>Output</VscPanelTab>,
              content: result ? (
                <span className={result.validated ? 'text-emerald-400' : 'text-amber-300'}>{result.feedback}</span>
              ) : (
                <span className="text-[var(--vsc-muted)]">Ctrl/⌘+Enter to check your answer.</span>
              ),
            }}
            statusBar={{ left: 'solution' + (language === 'python' ? '.py' : '.js'), center: language, right: checking ? 'Checking…' : 'Ready' }}
          />
        </div>
      )}

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
