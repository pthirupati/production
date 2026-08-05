import { useCallback, useEffect, useRef, useState } from 'react'
import {
  CheckCircle2, Circle, Loader2, XCircle, Play, RotateCcw, ChevronRight, Upload,
} from 'lucide-react'
import { packerApi } from '../../api/packer'

const MATRIX = ['H100', 'H200', 'B300', 'MI300']

const STATUS_ICON = {
  success: CheckCircle2,
  failure: XCircle,
  in_progress: Loader2,
  queued: Circle,
  pending: Circle,
}

function statusColor(status) {
  if (status === 'success') return '#3fb950'
  if (status === 'failure') return '#f85149'
  if (status === 'in_progress') return '#02A8EF'
  return '#858585'
}

/**
 * GitHub Actions–style Image Factory CI panel for PackerWorkspaceIde.
 * Advances jobs via API on a timer; supports re-run failed + gated publish.
 */
export default function PackerCiPipelinePanel({
  sessionId,
  sku = 'h100',
  files = {},
  buildSucceeded = false,
  onFactoryUpdate,
  onPublishSuggest,
  className = '',
}) {
  const [factory, setFactory] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [autoAdvance, setAutoAdvance] = useState(false)
  const timerRef = useRef(null)
  const advancingRef = useRef(false)

  const activeRun = factory?.active_run || (factory?.packer_factory?.runs || [])[0] || null
  const jobs = activeRun?.jobs || []
  const selectedJob = jobs.find((j) => j.id === selectedJobId) || jobs.find((j) => j.status === 'in_progress' || j.status === 'failure') || jobs[0]
  const matrixActive = (activeRun?.sku || sku || 'h100').toUpperCase()
  const checks = activeRun?.checks || factory?.checks || []
  const publishEnabled = Boolean(activeRun?.publish_enabled || factory?.publish_enabled)
  const artifactReady = Boolean(activeRun?.artifact_ready || factory?.artifact_ready)
  const bootResource = activeRun?.boot_resource || factory?.suggested_boot_resource || `custom/${sku}-jammy`

  const applyResult = useCallback((res) => {
    if (!res) return
    const next = {
      ...res,
      packer_factory: res.packer_factory,
      active_run: res.active_run || res.run,
      build_succeeded: res.build_succeeded,
      artifact_ready: res.artifact_ready,
      suggested_boot_resource: res.suggested_boot_resource,
      publish_enabled: res.publish_enabled,
      checks: res.checks,
    }
    setFactory(next)
    onFactoryUpdate?.(next)
    if (next.artifact_ready) onPublishSuggest?.(next.suggested_boot_resource || bootResource)
  }, [bootResource, onFactoryUpdate, onPublishSuggest])

  const refresh = useCallback(async () => {
    if (!sessionId) return
    try {
      const res = await packerApi.getFactoryState(sessionId)
      applyResult(res)
    } catch { /* session may not exist yet */ }
  }, [sessionId, applyResult])

  useEffect(() => { refresh() }, [refresh])

  const startPipeline = useCallback(async () => {
    if (!sessionId || busy) return
    setBusy(true)
    try {
      const res = await packerApi.startPipeline(sessionId, { sku, files, template: Object.values(files).join('\n') })
      applyResult(res)
      setAutoAdvance(true)
      setSelectedJobId('packer-init')
    } catch (err) {
      console.warn('Image Factory start failed', err)
    } finally {
      setBusy(false)
    }
  }, [sessionId, busy, sku, files, applyResult])

  const advanceOnce = useCallback(async () => {
    if (!sessionId || advancingRef.current) return null
    advancingRef.current = true
    try {
      const res = await packerApi.advanceJob(sessionId, {})
      applyResult(res)
      const run = res?.active_run || res?.run
      const failed = (run?.jobs || []).find((j) => j.status === 'failure')
      if (failed) {
        setSelectedJobId(failed.id)
        setAutoAdvance(false)
      } else {
        const running = (run?.jobs || []).find((j) => j.status === 'in_progress')
        const nextQueued = (run?.jobs || []).find((j) => j.status === 'queued')
        setSelectedJobId((running || nextQueued)?.id || selectedJobId)
        if (run?.status === 'success') setAutoAdvance(false)
      }
      return res
    } catch {
      setAutoAdvance(false)
      return null
    } finally {
      advancingRef.current = false
    }
  }, [sessionId, applyResult, selectedJobId])

  useEffect(() => {
    if (!autoAdvance || !activeRun || activeRun.status === 'success') return undefined
    if (activeRun.status === 'failure') return undefined
    timerRef.current = setInterval(() => { advanceOnce() }, 900)
    return () => clearInterval(timerRef.current)
  }, [autoAdvance, activeRun?.status, activeRun?.id, advanceOnce])

  const rerunFailed = useCallback(async () => {
    const failed = jobs.find((j) => j.status === 'failure')
    if (!failed || !sessionId) return
    setBusy(true)
    try {
      const res = await packerApi.rerunJob(sessionId, failed.id, { files, template: Object.values(files).join('\n') })
      applyResult(res)
      setSelectedJobId(failed.id)
      setAutoAdvance(true)
    } finally {
      setBusy(false)
    }
  }, [jobs, sessionId, files, applyResult])

  const publishNow = useCallback(async () => {
    if (!sessionId || !publishEnabled) return
    setBusy(true)
    try {
      // Advance through publish job if still queued
      const pubJob = jobs.find((j) => j.id === 'publish')
      if (pubJob && pubJob.status !== 'success') {
        let res = await packerApi.advanceJob(sessionId, {})
        applyResult(res)
        // publish may need two advances (queued → in_progress → done); advance_job completes publish in one when in_progress
        if ((res?.active_run || res?.run)?.jobs?.find((j) => j.id === 'publish')?.status === 'in_progress') {
          res = await packerApi.advanceJob(sessionId, {})
          applyResult(res)
        }
      } else {
        const res = await packerApi.publishArtifact(sessionId, { sku, boot_resource: bootResource })
        applyResult(res)
      }
    } finally {
      setBusy(false)
    }
  }, [sessionId, publishEnabled, jobs, sku, bootResource, applyResult])

  const logs = selectedJob?.logs || []

  return (
    <div className={`packer-ci-panel flex flex-col min-h-0 h-full ${className}`}>
      <div className="flex items-center gap-2 px-2 py-1.5 border-b border-[var(--vsc-border)] shrink-0">
        <span className="text-[11px] font-semibold text-[#02A8EF]">Image Factory</span>
        <span className="text-[10px] text-[var(--vsc-muted)]">workflow runs</span>
        <div className="ml-auto flex items-center gap-1">
          {MATRIX.map((m) => (
            <span
              key={m}
              className="text-[9px] px-1.5 py-0.5 rounded border"
              style={{
                borderColor: matrixActive === m ? '#02A8EF' : 'var(--vsc-border)',
                color: matrixActive === m ? '#02A8EF' : 'var(--vsc-muted)',
                background: matrixActive === m ? 'rgba(2,168,239,0.12)' : 'transparent',
              }}
            >
              {m}
            </span>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-1.5 px-2 py-1.5 border-b border-[var(--vsc-border)] shrink-0 flex-wrap">
        <button
          type="button"
          disabled={!sessionId || busy || (!buildSucceeded && !factory?.build_succeeded)}
          onClick={startPipeline}
          className="vsc-btn vsc-btn-primary text-[10px] inline-flex items-center gap-1 disabled:opacity-40"
          style={{ background: '#02A8EF', borderColor: '#02A8EF' }}
          title={buildSucceeded || factory?.build_succeeded ? 'Start Image Factory pipeline' : 'Run packer build successfully first'}
        >
          <Play size={10} /> Run Image Factory pipeline
        </button>
        {jobs.some((j) => j.status === 'failure') && (
          <button type="button" disabled={busy} onClick={rerunFailed} className="vsc-btn text-[10px] inline-flex items-center gap-1">
            <RotateCcw size={10} /> Re-run failed job
          </button>
        )}
        <button
          type="button"
          disabled={!publishEnabled || busy}
          onClick={publishNow}
          className="vsc-btn text-[10px] inline-flex items-center gap-1 disabled:opacity-40"
          title={publishEnabled ? `Publish ${bootResource}` : 'PR status checks must pass first'}
        >
          <Upload size={10} /> Publish
        </button>
        {artifactReady && (
          <span className="text-[10px] text-emerald-400">Artifact ready → {bootResource}</span>
        )}
      </div>

      {/* Runs list */}
      <div className="px-2 py-1 border-b border-[var(--vsc-border)] shrink-0">
        {activeRun ? (
          <div className="flex items-center gap-2 text-[11px]">
            <ChevronRight size={11} className="text-[#02A8EF]" />
            <span className="font-medium">#{activeRun.id}</span>
            <span className="text-[var(--vsc-muted)]">{activeRun.name}</span>
            <span style={{ color: statusColor(activeRun.status) }} className="text-[10px] uppercase tracking-wide">
              {activeRun.conclusion || activeRun.status}
            </span>
            <span className="text-[10px] text-[var(--vsc-muted)] ml-auto">{activeRun.event || 'workflow_dispatch'}</span>
          </div>
        ) : (
          <p className="text-[10px] text-[var(--vsc-muted)] py-1">No workflow runs yet. Complete a packer build, then start the pipeline.</p>
        )}
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Jobs column */}
        <div className="w-[42%] min-w-[140px] border-r border-[var(--vsc-border)] overflow-auto shrink-0">
          {jobs.length === 0 && (
            <p className="text-[10px] text-[var(--vsc-muted)] p-2">Jobs appear after the pipeline starts.</p>
          )}
          {jobs.map((job) => {
            const Icon = STATUS_ICON[job.status] || Circle
            const active = selectedJob?.id === job.id
            return (
              <button
                key={job.id}
                type="button"
                onClick={() => setSelectedJobId(job.id)}
                className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left text-[11px] border-b border-[var(--vsc-border)]/50 hover:bg-white/5 ${active ? 'bg-[rgba(2,168,239,0.1)]' : ''}`}
              >
                <Icon
                  size={12}
                  className={job.status === 'in_progress' ? 'animate-spin shrink-0' : 'shrink-0'}
                  style={{ color: statusColor(job.status) }}
                />
                <span className="truncate">{job.name}</span>
              </button>
            )
          })}
          {checks.length > 0 && (
            <div className="p-2 mt-1">
              <div className="text-[9px] uppercase tracking-wider text-[var(--vsc-muted)] mb-1">PR status checks</div>
              {checks.map((c) => (
                <div key={c.name} className="flex items-center gap-1 text-[10px] py-0.5">
                  <span style={{ color: statusColor(c.status) }}>●</span>
                  <span className="truncate text-[var(--vsc-text)]">{c.name.replace('Image Factory / ', '')}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Log viewer */}
        <div className="flex-1 min-w-0 flex flex-col bg-[var(--vsc-panel,#181818)]">
          <div className="px-2 py-1 text-[10px] text-[var(--vsc-muted)] border-b border-[var(--vsc-border)] shrink-0">
            {selectedJob ? `${selectedJob.name} · ${selectedJob.status}` : 'Select a job'}
          </div>
          <pre className="flex-1 overflow-auto p-2 text-[10px] font-mono leading-relaxed text-[var(--vsc-text)] whitespace-pre-wrap break-words">
            {logs.length ? logs.join('\n') : 'No log output yet.'}
          </pre>
        </div>
      </div>
    </div>
  )
}
