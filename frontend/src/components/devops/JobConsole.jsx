import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronRight, ChevronDown, Loader2, Terminal } from 'lucide-react'
import SimTerminalLog from '../sim/shared/SimTerminalLog'

/**
 * JobConsole — renders the selected job's steps as collapsible ::group:: sections
 * (GitLab/GitHub Actions style). Each section header shows a per-step status dot,
 * the step name and an elapsed timer; the body renders that step's streamed log
 * lines through SimTerminalLog (ANSI-aware). The running step shows a spinner and
 * the whole console auto-scrolls as lines arrive.
 *
 * props:
 *   job       normalized job { id, name, steps: [{id,name,run}] } | null
 *   stepState Map<stepId, { status, lines: string[], durationMs, startedAt }>
 *             (owned by CicdPipelineSim, fed from engine step:log / step:done)
 *   jobStatus 'queued'|'running'|'awaiting_approval'|'success'|'failed'|'skipped'
 *   nowTick   number — a monotonically-updating value so running timers re-render
 */

function fmtElapsed(ms) {
  if (!ms || ms < 0) return ''
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`
}

const DOT_CLS = {
  queued: 'cicd-dot-queued',
  running: 'cicd-dot-running',
  success: 'cicd-dot-success',
  failed: 'cicd-dot-failed',
  skipped: 'cicd-dot-skipped',
}

export default function JobConsole({ job, stepState, jobStatus, nowTick }) {
  const scrollRef = useRef(null)
  const [collapsed, setCollapsed] = useState({})

  const steps = useMemo(() => {
    if (!job) return []
    return job.steps?.length ? job.steps : [{ id: `${job.id}_step`, name: job.name, run: job.name }]
  }, [job])

  // Auto-scroll to the bottom whenever new lines land (tracked by total line count).
  const totalLines = useMemo(() => {
    let n = 0
    for (const s of steps) n += stepState?.get(s.id)?.lines?.length || 0
    return n
  }, [steps, stepState])

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [totalLines])

  const toggle = (id) => setCollapsed((c) => ({ ...c, [id]: !c[id] }))

  if (!job) {
    return (
      <div className="cicd-console p-6 text-center text-[13px] flex flex-col items-center gap-2" style={{ color: 'var(--cicd-muted)' }}>
        <Terminal size={20} />
        Select a job in the graph to view its console output.
      </div>
    )
  }

  const runningStepId = (() => {
    for (const s of steps) {
      const st = stepState?.get(s.id)
      if (st && st.status === 'running') return s.id
    }
    return null
  })()

  return (
    <div className="cicd-console flex flex-col min-h-0 overflow-hidden">
      <div className="px-3 py-2 flex items-center gap-2 border-b" style={{ borderColor: 'var(--cicd-border-soft)' }}>
        <Terminal size={13} style={{ color: 'var(--cicd-accent)' }} />
        <span className="text-[13px] font-semibold" style={{ color: 'var(--cicd-text)' }}>{job.name}</span>
        <span className="text-[11px]" style={{ color: 'var(--cicd-muted)' }}>
          {steps.length} step{steps.length > 1 ? 's' : ''} · {jobStatus?.replace('_', ' ') || 'queued'}
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 min-h-[220px] overflow-auto">
        {steps.map((step, i) => {
          const st = stepState?.get(step.id)
          const status = st?.status || 'queued'
          const isRunning = step.id === runningStepId
          const isCollapsed = collapsed[step.id] ?? false
          // nowTick is referenced so a running step's elapsed timer re-renders each tick.
          const elapsed = st?.startedAt && status === 'running'
            ? Date.now() - st.startedAt + (nowTick && 0)
            : st?.durationMs
          const cmd = (step.run || step.name || '').split('\n')[0]
          return (
            <div key={step.id}>
              <button type="button" className="cicd-step-head" onClick={() => toggle(step.id)}>
                {isCollapsed ? <ChevronRight size={13} className="shrink-0" /> : <ChevronDown size={13} className="shrink-0" />}
                <span className={`cicd-dot ${DOT_CLS[status] || DOT_CLS.queued}`} />
                <span className="font-medium truncate">{i + 1}. {step.name}</span>
                {cmd && cmd !== step.name ? (
                  <span className="truncate text-[11px] font-mono" style={{ color: 'var(--cicd-muted)' }}>{cmd}</span>
                ) : null}
                <span className="ml-auto flex items-center gap-1.5 shrink-0">
                  {isRunning && <Loader2 size={12} className="animate-spin" style={{ color: 'var(--cicd-accent)' }} />}
                  <span className="text-[11px] font-mono" style={{ color: 'var(--cicd-muted)' }}>{fmtElapsed(elapsed)}</span>
                </span>
              </button>
              {!isCollapsed && (st?.lines?.length ? (
                <SimTerminalLog lines={st.lines} title={null} className="border-b" />
              ) : (
                <div className="px-4 py-2 text-[11px] font-mono border-b" style={{ color: 'var(--cicd-muted)', borderColor: 'var(--cicd-border-soft)' }}>
                  {status === 'queued' ? 'Waiting…' : status === 'skipped' ? 'Skipped (upstream failed).' : '(no output)'}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
