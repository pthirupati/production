import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  Hammer, FlaskConical, ShieldCheck, Rocket, GitBranch, Package, Boxes, CircleDot,
} from 'lucide-react'
import SimStatusBadge from '../sim/shared/SimStatusBadge'
import { resolveJobDeps } from './pipelineModel'

/**
 * PipelineGraph — jobs grouped into stage columns with SVG connector lines for
 * `needs` edges. Each node = icon + name + live duration + SimStatusBadge.
 * Clicking a node selects it (drives JobConsole).
 *
 * props:
 *   pipeline    normalized model { stages, jobs }
 *   statuses    Map<jobId, status>  (engine job status; falls back to 'queued')
 *   durations   Map<jobId, ms>      (final durations)
 *   liveMs      Map<jobId, ms>      (elapsed ms for currently-running jobs)
 *   selectedId  string | null
 *   onSelect    (jobId) => void
 */

const STAGE_ICONS = [
  [/build|compile|image|docker/i, Hammer],
  [/test|lint|check|qa/i, FlaskConical],
  [/scan|sonar|security|sast|audit/i, ShieldCheck],
  [/deploy|release|sync|ship|prod|stag/i, Rocket],
  [/checkout|clone|fetch|prepare/i, GitBranch],
  [/publish|push|artifact|package/i, Package],
]

function jobIcon(job) {
  const hay = `${job.name} ${job.stage || ''} ${job.environment || ''}`
  for (const [re, Icon] of STAGE_ICONS) if (re.test(hay)) return Icon
  return Boxes
}

function fmtMs(ms) {
  if (!ms || ms < 0) return '—'
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`
}

/** Build ordered stage columns; each column holds its jobs. */
function buildColumns(pipeline) {
  const jobs = pipeline?.jobs || []
  const stages = pipeline?.stages || []
  const cols = []
  const seenStages = new Set()

  for (const stage of stages) {
    const stageJobs = jobs.filter((j) => j.stage === stage.id)
    if (!stageJobs.length) continue
    cols.push({ id: stage.id, name: stage.name, jobs: stageJobs })
    seenStages.add(stage.id)
  }
  // Jobs with no (or an unknown) stage: bucket by their needs depth so the DAG
  // still reads left-to-right.
  const orphan = jobs.filter((j) => !j.stage || !seenStages.has(j.stage))
  if (orphan.length) cols.push({ id: '__misc', name: 'Jobs', jobs: orphan })
  return cols
}

export default function PipelineGraph({
  pipeline,
  statuses,
  durations,
  liveMs,
  selectedId,
  onSelect,
}) {
  const columns = useMemo(() => buildColumns(pipeline), [pipeline])
  const containerRef = useRef(null)
  const nodeRefs = useRef(new Map())
  const [edges, setEdges] = useState([])
  const [size, setSize] = useState({ w: 0, h: 0 })

  const edgeDefs = useMemo(() => {
    const jobs = pipeline?.jobs || []
    const byId = new Set(jobs.map((j) => j.id))
    const list = []
    for (const job of jobs) {
      for (const need of job.needs || []) {
        if (byId.has(need)) list.push({ from: need, to: job.id })
      }
    }
    return list
  }, [pipeline])

  // Measure node centers and derive SVG edge paths after layout.
  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) return
    const cRect = container.getBoundingClientRect()
    setSize({ w: container.scrollWidth, h: container.scrollHeight })
    const center = (id, side) => {
      const el = nodeRefs.current.get(id)
      if (!el) return null
      const r = el.getBoundingClientRect()
      return {
        x: (side === 'right' ? r.right : r.left) - cRect.left + container.scrollLeft,
        y: r.top + r.height / 2 - cRect.top + container.scrollTop,
      }
    }
    const next = []
    for (const e of edgeDefs) {
      const a = center(e.from, 'right')
      const b = center(e.to, 'left')
      if (!a || !b) continue
      const midX = (a.x + b.x) / 2
      next.push({
        ...e,
        d: `M ${a.x} ${a.y} C ${midX} ${a.y}, ${midX} ${b.y}, ${b.x} ${b.y}`,
      })
    }
    setEdges(next)
  }, [edgeDefs, columns, statuses, liveMs])

  if (!columns.length) {
    return (
      <div className="cicd-card p-6 text-center text-[13px]" style={{ color: 'var(--cicd-muted)' }}>
        No jobs to display. Fix the definition errors in the editor to render the graph.
      </div>
    )
  }

  const statusOf = (id) => statuses?.get(id) || 'queued'
  const durOf = (id) => {
    const live = liveMs?.get(id)
    if (live != null) return live
    return durations?.get(id) || 0
  }

  return (
    <div ref={containerRef} className="cicd-graph p-3">
      <svg
        className="absolute inset-0 pointer-events-none"
        width={size.w || '100%'}
        height={size.h || '100%'}
        style={{ zIndex: 0 }}
      >
        {edges.map((e, i) => {
          const active = statusOf(e.from) === 'success' && statusOf(e.to) !== 'queued'
          return <path key={i} d={e.d} className={`cicd-edge${active ? ' cicd-edge-active' : ''}`} />
        })}
      </svg>

      <div className="relative flex gap-8 min-w-max" style={{ zIndex: 1 }}>
        {columns.map((col) => (
          <div key={col.id} className="flex flex-col gap-3 min-w-[176px]">
            <div className="cicd-graph-stage-title">{col.name}</div>
            {col.jobs.map((job) => {
              const st = statusOf(job.id)
              const Icon = jobIcon(job)
              const depCount = resolveJobDeps(pipeline, job).length
              const selected = job.id === selectedId
              const stateCls =
                st === 'running' || st === 'awaiting_approval' ? (st === 'awaiting_approval' ? 'cicd-node-awaiting' : 'cicd-node-running')
                  : st === 'failed' ? 'cicd-node-failed'
                    : st === 'success' ? 'cicd-node-success'
                      : ''
              return (
                <button
                  key={job.id}
                  type="button"
                  ref={(el) => { if (el) nodeRefs.current.set(job.id, el); else nodeRefs.current.delete(job.id) }}
                  onClick={() => onSelect?.(job.id)}
                  className={`cicd-node text-left ${stateCls} ${selected ? 'cicd-node-selected' : ''}`.trim()}
                  aria-pressed={selected}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Icon size={14} style={{ color: 'var(--cicd-accent)' }} className="shrink-0" />
                    <span className="cicd-node-name truncate">{job.name}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <SimStatusBadge status={st === 'awaiting_approval' ? 'pending' : st} label={st.replace('_', ' ')} />
                    <span className="cicd-node-meta">{fmtMs(durOf(job.id))}</span>
                  </div>
                  {(job.needs?.length || job.environment) ? (
                    <div className="cicd-node-meta mt-1 flex items-center gap-2">
                      {depCount > 0 && (
                        <span className="inline-flex items-center gap-0.5">
                          <CircleDot size={9} /> {depCount} dep{depCount > 1 ? 's' : ''}
                        </span>
                      )}
                      {job.environment && <span className="truncate">→ {job.environment}</span>}
                    </div>
                  ) : null}
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
