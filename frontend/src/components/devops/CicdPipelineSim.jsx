import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Play, RotateCcw, GitBranch, GitPullRequest, Hand, CalendarClock, Workflow, FileCode,
  Server, History, CheckCircle2, XCircle, AlertTriangle, ThumbsUp, ThumbsDown,
  Download, Ban, ArrowUpCircle, Rocket, Zap, KeyRound, Variable, Settings2,
} from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { simPanelRoot } from '../../utils/simLayout'
import SimStatusBadge from '../sim/shared/SimStatusBadge'
import PipelineGraph from './PipelineGraph'
import JobConsole from './JobConsole'
import { createPipelineRun, JOB_STATUS } from './pipelineEngine'
import { parsePipeline } from './pipelineParser'
import { PROVIDERS, PROVIDER_LABELS } from './pipelineModel'
import {
  CICD_SEED_PIPELINES, CICD_SEED_PIPELINE_LIST, CICD_FAULTS_CATALOG,
  faultsForScenario, pipelineForScenario,
} from '../../simFixtures/cicd'
import { cicdApi } from '../../api/cicd'
import { renderCicdGitOpsPage } from '../sim/V3PlatformPanels'
import '../../styles/lab-chrome.css'
import '../../styles/sim-products.css'

const PROVIDER_ORDER = [PROVIDERS.GITLAB, PROVIDERS.GITHUB, PROVIDERS.JENKINS]

const TRIGGERS = [
  { id: 'push', label: 'Push', icon: GitBranch },
  { id: 'pr', label: 'Pull request', icon: GitPullRequest },
  { id: 'manual', label: 'Manual', icon: Hand },
  { id: 'schedule', label: 'Schedule', icon: CalendarClock },
]

const TABS = [
  { id: 'pipeline', label: 'Workflow', icon: Workflow },
  { id: 'argocd', label: 'Argo CD', icon: Rocket },
  { id: 'flux', label: 'Flux', icon: Zap },
  { id: 'github', label: 'GitHub', icon: GitPullRequest },
  { id: 'editor', label: 'YAML', icon: FileCode },
  { id: 'secrets', label: 'Secrets', icon: KeyRound },
  { id: 'variables', label: 'Variables', icon: Variable },
  { id: 'environments', label: 'Environments', icon: Server },
  { id: 'history', label: 'Runs', icon: History },
]

let _sha = 0xa1b2c3
function nextSha() {
  _sha = (_sha * 1103515245 + 12345) & 0xffffff
  return _sha.toString(16).padStart(6, '0')
}

function fmtDur(ms) {
  if (!ms) return '—'
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`
}

/** Extract per-job image + script from GitLab / GitHub-ish YAML for lab-server sync. */
function extractPipelineJobFields(source) {
  const reserved = new Set([
    'stages', 'variables', 'default', 'include', 'workflow', 'image', 'services',
    'before_script', 'after_script', 'cache', 'pages', 'name', 'on', 'env', 'jobs',
  ])
  const out = {}
  let current = null
  let inScript = false
  for (const raw of String(source || '').split('\n')) {
    const line = raw.replace(/\t/g, '  ')
    const top = line.match(/^([A-Za-z0-9_.-]+):\s*(.*)$/)
    if (top && !line.startsWith(' ') && !line.startsWith('\t')) {
      const key = top[1]
      inScript = false
      if (reserved.has(key) || key.startsWith('.')) {
        current = null
        continue
      }
      current = key
      out[current] = out[current] || { image: null, script: [] }
      const inline = (top[2] || '').trim()
      if (inline && !inline.startsWith('|') && !inline.startsWith('>')) {
        // ignore inline maps; job body continues below
      }
      continue
    }
    if (!current) continue
    if (/^\S/.test(line) && line.includes(':')) {
      current = null
      inScript = false
      continue
    }
    const img = line.match(/^\s{2,}image:\s*(.+?)\s*$/)
    if (img) {
      out[current].image = img[1].replace(/^['"]|['"]$/g, '').trim()
      inScript = false
      continue
    }
    if (/^\s{2,}(?:script|run):\s*$/.test(line)) {
      inScript = true
      out[current].script = []
      continue
    }
    if (inScript) {
      const step = line.match(/^\s{2,}-\s+(.+)$/)
      if (step) {
        out[current].script.push(step[1].replace(/^['"]|['"]$/g, '').trim())
        continue
      }
      if (/^\s{2,}\w[\w-]*:\s*/.test(line)) inScript = false
    }
  }
  return out
}

/**
 * Registry images the runner can actually pull. Mirrors `_VALID_IMAGES` in
 * backend/apps/vmware_sim/cicd_engine.py — that module is authoritative for
 * grading, so the local run must agree with it or the learner sees a green
 * pipeline and a failing Check (or vice-versa).
 */
const VALID_IMAGES = new Set([
  'node:20', 'node:18', 'python:3.12', 'python:3.11', 'golang:1.22',
  'docker:24', 'docker:25', 'alpine:3.19', 'ubuntu:22.04',
  'maven:3.9-eclipse-temurin-21', 'registry.fixitlab.local/ci/base:1.4.0',
  // Seed pipelines also ship these; they are pullable in the sim registry.
  'node:18-alpine', 'alpine/k8s:1.28.0', 'golang:1.22-alpine',
])

/**
 * Decide whether a catalog fault is STILL live against the pipeline the learner
 * is actually looking at.
 *
 * The catalog entry says which fault was planted; this says whether the edit
 * fixed it. Previously the catalog faults were fed to the engine verbatim, so
 * correcting `image:` or adding `needs:` changed the parsed model but not the
 * fault set and the job stayed red forever (audit L992). Faults we cannot yet
 * express in terms of the YAML (flaky, approvalTimeout) are passed through
 * unchanged so their labs keep behaving as before.
 *
 * Returns a faults object in the engine's shape: { [jobId]: fault }.
 */
export function deriveFaults(catalogFaults, { pipeline, jobFields }) {
  const out = {}
  const jobIds = new Set((pipeline?.jobs || []).map((j) => j.id))
  for (const [jobId, fault] of Object.entries(catalogFaults || {})) {
    // The catalog is keyed by conventional job names across several seed
    // pipelines; entries for jobs this pipeline does not define never applied.
    if (!jobIds.has(jobId)) continue
    const job = pipeline.jobs.find((j) => j.id === jobId)
    const fields = jobFields[jobId] || {}

    // Bad image tag: cleared as soon as `image:` names a pullable tag.
    if (/manifest|not found/i.test(fault.message || '') || fault.imageFault) {
      if (fields.image && VALID_IMAGES.has(fields.image)) continue
      out[jobId] = fault
      continue
    }

    // Missing secret/variable: the job must reference the variable it needs.
    // Declaring it in the script (export/`--set`/env) is the learner's fix.
    if (/required variable/i.test(fault.message || '')) {
      const want = (fault.message.match(/variable ([A-Z0-9_]+)/) || [])[1]
      const script = (fields.script || []).join('\n')
      if (want && script.includes(want)) continue
      out[jobId] = fault
      continue
    }

    // OOM in tests: cleared by reducing parallelism or raising the memory the
    // job asks for — both show up as an edit to the job's script.
    if (fault.exitCode === 137) {
      const script = (fields.script || []).join('\n')
      if (/--max-workers|--maxWorkers|-p 1|NODE_OPTIONS|max-old-space-size|--runInBand/i.test(script)) continue
      out[jobId] = fault
      continue
    }

    // kubeconfig/RBAC on deploy: the fix is to make the deploy job depend on a
    // successful upstream (so credentials are provisioned) — i.e. add `needs:`.
    if (/Unauthorized|forbidden|RBAC/i.test(fault.message || '')) {
      if ((job?.needs || []).length) continue
      out[jobId] = fault
      continue
    }

    // Not yet derivable from the YAML (flaky, approvalTimeout): keep as-is
    // rather than silently making those labs unfailable.
    out[jobId] = fault
  }
  return out
}

export default function CicdPipelineSim({
  scenario,
  sessionId,
  onExit,
  onHints,
  onCheck,
  onExtend,
  onStop,
  hintsLabel,
  checkDisabled,
  extendDisabled,
  embedded = true,
  vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const techSlug = (scenario?.technology?.slug || '').toLowerCase()
  const isGitOpsLab = techSlug === 'gitops'
    || /gitops|argocd|flux|academy-gitops|github|gh-actions/.test(slug.toLowerCase())

  // Fault set derived from the lab scenario slug (gates the old cheat button).
  const scenarioFault = useMemo(() => faultsForScenario(slug), [slug])
  const [activeFaultKey, setActiveFaultKey] = useState(() => {
    const entry = faultsForScenario(slug)
    if (!entry) return ''
    return Object.keys(CICD_FAULTS_CATALOG).find((k) => CICD_FAULTS_CATALOG[k] === entry) || ''
  })
  const activeFault = activeFaultKey ? CICD_FAULTS_CATALOG[activeFaultKey] : null

  // Provider + seed selection, seeded from the scenario on mount.
  const initialSeed = useMemo(() => pipelineForScenario(slug), [slug])
  const [provider, setProvider] = useState(() => (
    isGitOpsLab ? PROVIDERS.GITHUB : initialSeed.provider
  ))
  const [seedSlug, setSeedSlug] = useState(() => (
    isGitOpsLab ? CICD_SEED_PIPELINES[PROVIDERS.GITHUB][0].slug : initialSeed.slug
  ))
  const [source, setSource] = useState(() => (
    isGitOpsLab ? CICD_SEED_PIPELINES[PROVIDERS.GITHUB][0].source : initialSeed.source
  ))

  const [tab, setTab] = useState('pipeline')
  const [trigger, setTrigger] = useState('push')
  const [branch, setBranch] = useState('main')

  // Parse the current source into a normalized model + lint errors on every edit.
  const parsed = useMemo(() => parsePipeline(source, provider), [source, provider])
  const { pipeline, errors } = parsed
  const hasBlockingErrors = errors.some((e) => e.code !== 'empty' && e.code !== 'job-without-stage')

  // ── run state ──────────────────────────────────────────────────────────────
  const [running, setRunning] = useState(false)
  const [statuses, setStatuses] = useState(() => new Map()) // jobId -> status
  const [durations, setDurations] = useState(() => new Map())
  const [liveMs, setLiveMs] = useState(() => new Map())
  const [stepState, setStepState] = useState(() => new Map()) // stepId -> {status,lines,startedAt,durationMs}
  const [awaiting, setAwaiting] = useState(() => new Set()) // jobIds awaiting approval
  const [selectedJob, setSelectedJob] = useState(null)
  const [nowTick, setNowTick] = useState(0)
  const [runHistory, setRunHistory] = useState([])
  const [environments, setEnvironments] = useState({}) // env -> {sha, at, status, runId}
  const [secrets, setSecrets] = useState(() => ([
    { name: 'GITHUB_TOKEN', scope: 'repository', updated: '2d ago' },
    { name: 'REGISTRY_TOKEN', scope: 'repository', updated: '5d ago', empty: true },
    { name: 'KUBE_TOKEN', scope: 'environment:production', updated: '1w ago' },
  ]))
  const [variables, setVariables] = useState(() => ([
    { name: 'NODE_VERSION', value: '18', scope: 'repository' },
    { name: 'DEPLOY_REGION', value: 'us-east-1', scope: 'repository' },
    { name: 'IMAGE_TAG', value: 'main', scope: 'environment:staging' },
  ]))
  const [artifacts, setArtifacts] = useState({}) // jobId -> [names]

  const runnerRef = useRef(null)
  const jobStartRef = useRef(new Map())

  // Tick while running so live timers advance (1s, matches store lifecycle cadence).
  useEffect(() => {
    if (!running && awaiting.size === 0) return undefined
    const id = setInterval(() => setNowTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [running, awaiting.size])

  // Recompute liveMs for running jobs each tick.
  useEffect(() => {
    if (!running && awaiting.size === 0) return
    setLiveMs(() => {
      const m = new Map()
      for (const [jobId, started] of jobStartRef.current) m.set(jobId, Date.now() - started)
      return m
    })
  }, [nowTick, running, awaiting.size])

  const resetRunState = useCallback(() => {
    setStatuses(new Map())
    setDurations(new Map())
    setLiveMs(new Map())
    setStepState(new Map())
    setAwaiting(new Set())
    jobStartRef.current = new Map()
  }, [])

  const artifactsForJob = useCallback((job) => {
    const hay = `${job.name} ${job.stage || ''}`.toLowerCase()
    if (/build|compile|package|image/.test(hay)) return [`app-${branch}.tar.gz`, 'build.log']
    if (/test|lint|qa/.test(hay)) return ['junit.xml', 'coverage.xml']
    if (/scan|sonar|security/.test(hay)) return ['scan-report.json']
    return []
  }, [branch])

  const handleEvent = useCallback((evt) => {
    switch (evt.type) {
      case 'run:started': {
        setSelectedJob((prev) => prev || evt.order?.[0]?.[0] || null)
        break
      }
      case 'job:queued':
        setStatuses((m) => new Map(m).set(evt.jobId, JOB_STATUS.QUEUED))
        break
      case 'job:running':
        jobStartRef.current.set(evt.jobId, Date.now())
        setStatuses((m) => new Map(m).set(evt.jobId, JOB_STATUS.RUNNING))
        setSelectedJob((prev) => prev || evt.jobId)
        break
      case 'job:awaiting_approval':
        setStatuses((m) => new Map(m).set(evt.jobId, JOB_STATUS.AWAITING_APPROVAL))
        setAwaiting((s) => new Set(s).add(evt.jobId))
        setSelectedJob(evt.jobId)
        break
      case 'step:log':
        setStepState((m) => {
          const next = new Map(m)
          const cur = next.get(evt.stepId) || { status: 'running', lines: [], startedAt: Date.now() }
          next.set(evt.stepId, { ...cur, status: 'running', startedAt: cur.startedAt || Date.now(), lines: [...cur.lines, evt.line] })
          return next
        })
        break
      case 'step:done':
        setStepState((m) => {
          const next = new Map(m)
          const cur = next.get(evt.stepId) || { lines: [] }
          next.set(evt.stepId, { ...cur, status: evt.status, durationMs: evt.durationMs })
          return next
        })
        break
      case 'job:done': {
        jobStartRef.current.delete(evt.jobId)
        setStatuses((m) => new Map(m).set(evt.jobId, evt.status))
        setDurations((m) => new Map(m).set(evt.jobId, evt.durationMs || 0))
        setAwaiting((s) => { if (!s.has(evt.jobId)) return s; const n = new Set(s); n.delete(evt.jobId); return n })
        setLiveMs((m) => { if (!m.has(evt.jobId)) return m; const n = new Map(m); n.delete(evt.jobId); return n })
        // Mark queued steps of a skipped job so the console reads correctly.
        if (evt.status === JOB_STATUS.SKIPPED) {
          const job = pipeline.jobs.find((j) => j.id === evt.jobId)
          if (job) {
            setStepState((m) => {
              const next = new Map(m)
              for (const s of job.steps.length ? job.steps : [{ id: `${job.id}_step` }]) {
                if (!next.has(s.id)) next.set(s.id, { status: 'skipped', lines: [] })
              }
              return next
            })
          }
        }
        break
      }
      case 'run:done':
        break
      default:
        break
    }
  }, [pipeline])

  const finalizeRun = useCallback((result, meta) => {
    const perJob = new Map(result.jobs?.map((j) => [j.id, j]) || [])
    // Capture the full graph+step snapshot so history can reload a past run.
    const snapshot = {
      statuses: Object.fromEntries([...(runnerRef.current?.getState().jobs || result.jobs || []).map((j) => [j.id, j.status])]),
      durations: Object.fromEntries((result.jobs || []).map((j) => [j.id, j.durationMs])),
    }
    const entry = {
      runId: meta.runId,
      sha: meta.sha,
      trigger: meta.trigger,
      branch: meta.branch,
      provider: meta.provider,
      seedSlug: meta.seedSlug,
      source: meta.source,
      status: result.status,
      durationMs: result.durationMs,
      at: new Date().toISOString(),
      snapshot,
      // capture step logs so re-loading a past run shows its console
      stepLogs: Object.fromEntries([...stepStateRef.current].map(([k, v]) => [k, { status: v.status, lines: v.lines, durationMs: v.durationMs }])),
      failedJobs: (result.jobs || []).filter((j) => j.status === JOB_STATUS.FAILED || j.status === JOB_STATUS.SKIPPED).map((j) => j.id),
      artifacts: meta.artifacts,
    }
    setRunHistory((h) => [entry, ...h].slice(0, 12))

    // Update deployed environments for successful deploy jobs.
    if (result.status === JOB_STATUS.SUCCESS) {
      const envUpdates = {}
      for (const job of pipeline.jobs) {
        if (job.environment && perJob.get(job.id)?.status === JOB_STATUS.SUCCESS) {
          envUpdates[job.environment] = { sha: meta.sha, at: entry.at, status: 'success', runId: meta.runId, jobId: job.id }
        }
      }
      if (Object.keys(envUpdates).length) {
        setEnvironments((e) => ({ ...e, ...envUpdates }))
        if (sessionId) {
          for (const [name, dep] of Object.entries(envUpdates)) {
            cicdApi.upsertEnvironment(sessionId, { name, deployment: dep }).catch(() => {})
          }
        }
      }
    }
  }, [pipeline, sessionId])

  // Keep a ref of stepState for the finalize snapshot (avoids stale closure).
  const stepStateRef = useRef(stepState)
  useEffect(() => { stepStateRef.current = stepState }, [stepState])

  const startRun = useCallback(async ({ onlyFailedFrom = null } = {}) => {
    if (running || hasBlockingErrors || !pipeline.jobs.length) return
    resetRunState()
    setRunning(true)

    // Per-job image/script as currently written. Drives both the lab-server
    // sync below and the local fault derivation, so the two cannot disagree.
    const fields = extractPipelineJobFields(source)

    // Mirror YAML image/script edits to the lab server before the grading run.
    if (sessionId) {
      await Promise.all(Object.entries(fields).map(async ([id, f]) => {
        if (f.image) await cicdApi.setImage(sessionId, id, f.image).catch(() => {})
        if (f.script?.length) await cicdApi.fixJob(sessionId, id, f.script).catch(() => {})
      }))
    }

    // Compute artifacts up front for the graph/history.
    const runArtifacts = {}
    for (const job of pipeline.jobs) {
      const a = artifactsForJob(job)
      if (a.length) runArtifacts[job.id] = a
    }
    setArtifacts(runArtifacts)

    // Re-evaluate the planted fault against the YAML as currently edited, so a
    // correct fix actually turns the job green.
    let faults = deriveFaults(activeFault?.faults, { pipeline, jobFields: fields })
    // Restrict faults to only the failed jobs when re-running failed only.
    if (onlyFailedFrom) {
      const allow = new Set(onlyFailedFrom)
      faults = Object.fromEntries(Object.entries(faults).filter(([jobId]) => allow.has(jobId)))
    }

    const meta = {
      runId: `#${1024 + runHistory.length}`,
      sha: nextSha(),
      trigger,
      branch,
      provider,
      seedSlug,
      source,
      artifacts: runArtifacts,
    }

    const runner = createPipelineRun(pipeline, { faults, onEvent: handleEvent })
    runnerRef.current = runner
    const result = await runner.start()
    finalizeRun(result, meta)
    runnerRef.current = null
    setRunning(false)
    if (sessionId) {
      cicdApi.runPipeline(sessionId).catch(() => {})
    }
  }, [running, hasBlockingErrors, pipeline, resetRunState, artifactsForJob, activeFault, runHistory.length, trigger, branch, provider, seedSlug, source, handleEvent, finalizeRun, sessionId])

  const cancelRun = useCallback(() => {
    runnerRef.current?.cancel()
  }, [])

  const approve = useCallback((jobId) => {
    runnerRef.current?.approve(jobId)
    if (sessionId) {
      cicdApi.approveJob(sessionId, jobId).catch(() => {})
    }
  }, [sessionId])
  const reject = useCallback((jobId) => {
    runnerRef.current?.reject(jobId)
    if (sessionId) {
      cicdApi.rejectJob(sessionId, jobId).catch(() => {})
    }
  }, [sessionId])

  const [serverState, setServerState] = useState(null)
  const [gitopsBusy, setGitopsBusy] = useState(false)
  const [yamlBusy, setYamlBusy] = useState(false)
  const reloadServer = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await cicdApi.getState(sessionId, slug)
      setServerState(data)
      if (Array.isArray(data?.pipeline_secrets) && data.pipeline_secrets.length) {
        setSecrets(data.pipeline_secrets)
      }
      if (Array.isArray(data?.pipeline_variables) && data.pipeline_variables.length) {
        setVariables(data.pipeline_variables)
      }
      if (Array.isArray(data?.pipeline_environments) && data.pipeline_environments.length) {
        const mapped = {}
        for (const env of data.pipeline_environments) {
          if (env.deployment) {
            mapped[env.name] = {
              sha: env.deployment.sha,
              at: env.deployment.at,
              status: env.deployment.status || 'success',
              runId: env.deployment.runId,
            }
          }
        }
        if (Object.keys(mapped).length) setEnvironments((prev) => ({ ...prev, ...mapped }))
      }
    } catch { /* grading sync is best-effort */ }
  }, [sessionId, slug])
  useEffect(() => { reloadServer() }, [reloadServer])
  const runGitops = useCallback(async (fn, _msg) => {
    setGitopsBusy(true)
    try {
      await fn()
      await reloadServer()
    } finally {
      setGitopsBusy(false)
    }
  }, [reloadServer])

  const applyYamlToLab = useCallback(async () => {
    if (!sessionId || hasBlockingErrors) return
    setYamlBusy(true)
    try {
      const fields = extractPipelineJobFields(source)
      await Promise.all(Object.entries(fields).map(async ([id, f]) => {
        if (f.image) await cicdApi.setImage(sessionId, id, f.image).catch(() => {})
        if (f.script?.length) await cicdApi.fixJob(sessionId, id, f.script).catch(() => {})
      }))
      await reloadServer()
    } finally {
      setYamlBusy(false)
    }
  }, [sessionId, hasBlockingErrors, source, reloadServer])

  // Re-load a past run's captured event log into the graph/console (read-only view).
  const loadHistory = useCallback((entry) => {
    setProvider(entry.provider)
    setSeedSlug(entry.seedSlug)
    setSource(entry.source)
    setStatuses(new Map(Object.entries(entry.snapshot.statuses)))
    setDurations(new Map(Object.entries(entry.snapshot.durations)))
    setStepState(new Map(Object.entries(entry.stepLogs || {})))
    setArtifacts(entry.artifacts || {})
    setLiveMs(new Map())
    setAwaiting(new Set())
    setTab('pipeline')
  }, [])

  const selectProvider = useCallback((p) => {
    const first = CICD_SEED_PIPELINES[p][0]
    setProvider(p)
    setSeedSlug(first.slug)
    setSource(first.source)
    resetRunState()
    setSelectedJob(null)
  }, [resetRunState])

  const selectSeed = useCallback((s) => {
    const seed = CICD_SEED_PIPELINE_LIST.find((x) => x.slug === s)
    if (!seed) return
    setSeedSlug(s)
    setSource(seed.source)
    resetRunState()
    setSelectedJob(null)
  }, [resetRunState])

  const selectedJobModel = useMemo(
    () => pipeline.jobs.find((j) => j.id === selectedJob) || null,
    [pipeline, selectedJob],
  )

  const anyFailed = [...statuses.values()].some((s) => s === JOB_STATUS.FAILED)
  const allGreen = pipeline.jobs.length > 0 && pipeline.jobs.every((j) => statuses.get(j.id) === JOB_STATUS.SUCCESS)
  const providerSeeds = CICD_SEED_PIPELINES[provider] || []

  // At-a-glance pipeline status pill for the header — mirrors the badge every
  // real CI/CD tool shows next to the project/branch name.
  const headerStatus = running
    ? 'running'
    : allGreen ? 'success'
      : anyFailed ? 'failed'
        : runHistory[0]?.status || null

  return (
    <div
      className={simPanelRoot(embedded, `cicd-sim text-sm${isGitOpsLab || provider === PROVIDERS.GITHUB ? ' cicd-github' : ''}`)}
      style={{ background: 'var(--cicd-bg)', color: 'var(--cicd-text)' }}
    >
      <LabChromeBar
        icon={GitBranch}
        title={isGitOpsLab || provider === PROVIDERS.GITHUB ? 'GitHub Actions' : 'CI/CD Pipeline'}
        subtitle={scenario?.title || (isGitOpsLab ? 'GitOps lab' : 'DevOps lab')}
        accent="#238636"
        className="lab-chrome-bar"
        onExit={onExit}
        onHints={onHints}
        onCheck={onCheck}
        onExtend={onExtend}
        onStop={onStop}
        hintsLabel={hintsLabel}
        checkDisabled={checkDisabled}
        extendDisabled={extendDisabled}
        backLabel="Terminal"
        vmwareHref={vmwareHref}
      >
        {headerStatus && (
          <span className={`cicd-status-pill cicd-status-pill-${headerStatus === 'running' ? 'running' : headerStatus === 'success' ? 'success' : headerStatus === 'failed' ? 'failed' : ''}`.trim()}>
            <span className="cicd-status-dot" />
            {headerStatus === 'running' ? 'Running' : headerStatus === 'success' ? 'Passing' : headerStatus === 'failed' ? 'Failed' : headerStatus}
          </span>
        )}
      </LabChromeBar>

      {/* Provider + trigger toolbar */}
      <div className="cicd-toolbar flex flex-wrap items-center gap-2 px-4 py-2 shrink-0">
        <label className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--cicd-muted)' }}>
          Provider
          <select
            className="cicd-select"
            value={provider}
            disabled={isGitOpsLab}
            onChange={(e) => selectProvider(e.target.value)}
          >
            {(isGitOpsLab ? [PROVIDERS.GITHUB] : PROVIDER_ORDER).map((p) => (
              <option key={p} value={p}>{PROVIDER_LABELS[p]}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--cicd-muted)' }}>
          Definition
          <select className="cicd-select max-w-[240px]" value={seedSlug} onChange={(e) => selectSeed(e.target.value)}>
            {providerSeeds.map((s) => <option key={s.slug} value={s.slug}>{s.title}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--cicd-muted)' }}>
          <GitBranch size={12} />
          <select className="cicd-select" value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="main">main</option>
            <option value="develop">develop</option>
            <option value="release/1.x">release/1.x</option>
            <option value="feature/fix-pipeline">feature/fix-pipeline</option>
          </select>
        </label>

        <div className="cicd-trigger ml-auto">
          {TRIGGERS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`cicd-trigger-btn ${trigger === t.id ? 'cicd-trigger-active' : ''}`}
              onClick={() => setTrigger(t.id)}
            >
              <t.icon size={12} /> <span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </div>

        {running ? (
          <button type="button" className="cicd-btn cicd-btn-danger" onClick={cancelRun}>
            <Ban size={13} /> Cancel
          </button>
        ) : (
          <button
            type="button"
            className="cicd-btn cicd-btn-primary"
            onClick={() => startRun()}
            disabled={hasBlockingErrors || !pipeline.jobs.length}
            title={hasBlockingErrors ? 'Fix definition errors first' : 'Run pipeline'}
          >
            <Play size={13} /> {isGitOpsLab || provider === PROVIDERS.GITHUB ? 'Run workflow' : 'Run pipeline'}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-4 py-1.5 border-b overflow-x-auto shrink-0" style={{ borderColor: 'var(--cicd-border-soft)' }}>
        {TABS.map((t) => (
          <button key={t.id} type="button" className={`cicd-tab ${tab === t.id ? 'cicd-tab-active' : ''}`} onClick={() => setTab(t.id)}>
            <t.icon size={12} /> {t.label}
            {t.id === 'history' && runHistory.length > 0 && (
              <span className="ml-1 opacity-70">({runHistory.length})</span>
            )}
          </button>
        ))}
        {scenarioFault && (
          <label className="ml-auto flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--cicd-amber)' }} title="Fault injected into this run, seeded from the lab scenario">
            <Zap size={12} /> Fault
            <select className="cicd-select" value={activeFaultKey} onChange={(e) => setActiveFaultKey(e.target.value)} disabled={running}>
              <option value="">None</option>
              {Object.entries(CICD_FAULTS_CATALOG).map(([key, f]) => (
                <option key={key} value={key}>{f.label}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-auto p-4">
        {(tab === 'argocd' || tab === 'flux' || tab === 'github') && renderCicdGitOpsPage({
          nav: tab, st: serverState || {}, sessionId, busy: gitopsBusy, run: runGitops,
        })}
        {tab === 'pipeline' && (
          <div className="max-w-6xl mx-auto space-y-4">
            {allGreen && !running && (
              <div className="cicd-card p-3 flex items-center gap-2 text-[13px]" style={{ borderColor: 'rgba(63,185,80,.35)', color: 'var(--cicd-green)' }}>
                <CheckCircle2 size={16} /> Pipeline green — return to the lab and click <strong>Check</strong> to validate.
              </div>
            )}
            {anyFailed && !running && (
              <div className="cicd-card p-3 flex items-center gap-2 text-[13px]" style={{ borderColor: 'rgba(248,81,73,.35)', color: 'var(--cicd-red)' }}>
                <XCircle size={16} /> A job failed. Inspect its console, fix the definition or variables, then re-run.
              </div>
            )}

            <PipelineGraph
              pipeline={pipeline}
              statuses={statuses}
              durations={durations}
              liveMs={liveMs}
              selectedId={selectedJob}
              onSelect={setSelectedJob}
            />

            {/* Approval gate controls */}
            {awaiting.size > 0 && (
              <div className="cicd-card p-3 space-y-2">
                <div className="flex items-center gap-2 text-[12px] font-semibold" style={{ color: 'var(--cicd-amber)' }}>
                  <AlertTriangle size={14} /> Awaiting manual approval
                </div>
                {[...awaiting].map((jobId) => {
                  const job = pipeline.jobs.find((j) => j.id === jobId)
                  return (
                    <div key={jobId} className="flex items-center gap-2">
                      <span className="text-[12px] flex-1">{job?.name || jobId}{job?.environment ? ` → ${job.environment}` : ''}</span>
                      <button type="button" className="cicd-btn cicd-btn-approve" onClick={() => approve(jobId)}>
                        <ThumbsUp size={12} /> Approve
                      </button>
                      <button type="button" className="cicd-btn cicd-btn-danger" onClick={() => reject(jobId)}>
                        <ThumbsDown size={12} /> Reject
                      </button>
                    </div>
                  )
                })}
              </div>
            )}

            <JobConsole
              job={selectedJobModel}
              stepState={stepState}
              jobStatus={selectedJob ? statuses.get(selectedJob) : null}
              nowTick={nowTick}
            />

            {selectedJobModel && artifacts[selectedJobModel.id]?.length > 0 && (
              <div className="cicd-card p-3">
                <div className="text-[11px] uppercase tracking-wide mb-2" style={{ color: 'var(--cicd-muted)' }}>Artifacts</div>
                <div className="flex flex-wrap gap-2">
                  {artifacts[selectedJobModel.id].map((a) => (
                    <span key={a} className="cicd-artifact"><Download size={11} /> {a}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'editor' && (
          <div className="max-w-5xl mx-auto space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="text-[12px]" style={{ color: 'var(--cicd-muted)' }}>
                Editing <code style={{ color: 'var(--cicd-accent)' }}>{providerSeeds.find((s) => s.slug === seedSlug)?.file || 'pipeline'}</code>
                {' '}— the parsed model drives the graph live.
              </span>
              <div className="flex items-center gap-2 flex-wrap">
                {errors.length === 0 ? (
                  <span className="cicd-lint-ok flex items-center gap-1.5 text-[12px]"><CheckCircle2 size={14} /> Pipeline is valid</span>
                ) : (
                  <span className="flex items-center gap-1.5 text-[12px]" style={{ color: 'var(--cicd-red)' }}>
                    <XCircle size={14} /> {errors.length} problem{errors.length > 1 ? 's' : ''}
                  </span>
                )}
                {sessionId && (
                  <button
                    type="button"
                    className="cicd-btn cicd-btn-sm"
                    disabled={yamlBusy || hasBlockingErrors}
                    onClick={applyYamlToLab}
                    title="Sync image and script edits to the lab server"
                  >
                    {yamlBusy ? 'Applying…' : 'Apply to lab'}
                  </button>
                )}
              </div>
            </div>

            {errors.length > 0 && (
              <div className="space-y-1.5">
                {errors.map((e, i) => (
                  <div key={i} className="cicd-lint-err">
                    <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                    <span><span className="font-mono opacity-70">[{e.code}]</span> {e.message}</span>
                  </div>
                ))}
              </div>
            )}

            <textarea
              className="cicd-editor"
              value={source}
              onChange={(e) => { setSource(e.target.value); resetRunState() }}
              spellCheck={false}
            />
          </div>
        )}

        {tab === 'secrets' && (
          <div className="max-w-4xl mx-auto space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="text-[14px] font-semibold flex items-center gap-2">
                  <KeyRound size={15} style={{ color: 'var(--cicd-accent)' }} /> Actions secrets
                </div>
                <p className="text-[12px] mt-1" style={{ color: 'var(--cicd-muted)' }}>
                  Repository and environment secrets available to workflow jobs (GitHub Actions style).
                </p>
              </div>
              <button
                type="button"
                className="cicd-btn cicd-btn-primary"
                disabled={gitopsBusy}
                onClick={() => {
                  const name = `NEW_SECRET_${secrets.length + 1}`
                  if (sessionId) {
                    runGitops(() => cicdApi.upsertSecret(sessionId, { name, scope: 'repository' }), 'Secret created')
                  } else {
                    setSecrets((s) => [...s, { name, scope: 'repository', updated: 'just now', empty: false }])
                  }
                }}
              >
                <Settings2 size={12} /> New secret
              </button>
            </div>
            <div className="cicd-card overflow-hidden">
              <table className="w-full text-[12px]">
                <thead>
                  <tr style={{ color: 'var(--cicd-muted)' }} className="text-left">
                    <th className="p-2.5 font-medium">Name</th>
                    <th className="p-2.5 font-medium">Scope</th>
                    <th className="p-2.5 font-medium">Last updated</th>
                    <th className="p-2.5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {secrets.map((sec) => (
                    <tr key={sec.name} className="cicd-row">
                      <td className="p-2.5 font-mono">
                        {sec.name}
                        {sec.empty && (
                          <span className="ml-2 text-[10px] uppercase" style={{ color: 'var(--cicd-amber)' }}>unset</span>
                        )}
                      </td>
                      <td className="p-2.5" style={{ color: 'var(--cicd-muted)' }}>{sec.scope}</td>
                      <td className="p-2.5" style={{ color: 'var(--cicd-muted)' }}>{sec.updated}</td>
                      <td className="p-2.5 text-right">
                        <button
                          type="button"
                          className="cicd-btn"
                          disabled={gitopsBusy}
                          onClick={() => {
                            if (sessionId) {
                              runGitops(() => cicdApi.upsertSecret(sessionId, { name: sec.name, scope: sec.scope, empty: false }), 'Secret updated')
                            } else {
                              setSecrets((rows) => rows.map((r) => (
                                r.name === sec.name ? { ...r, empty: false, updated: 'just now' } : r
                              )))
                            }
                          }}
                        >
                          Update
                        </button>
                        <button
                          type="button"
                          className="cicd-btn cicd-btn-danger ml-1"
                          disabled={gitopsBusy}
                          onClick={() => {
                            if (sessionId) {
                              runGitops(() => cicdApi.deleteSecret(sessionId, sec.name), 'Secret deleted')
                            } else {
                              setSecrets((rows) => rows.filter((r) => r.name !== sec.name))
                            }
                          }}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === 'variables' && (
          <div className="max-w-4xl mx-auto space-y-3">
            <div className="text-[14px] font-semibold flex items-center gap-2">
              <Variable size={15} style={{ color: 'var(--cicd-accent)' }} /> Variables
            </div>
            <p className="text-[12px]" style={{ color: 'var(--cicd-muted)' }}>
              Configuration variables injected into workflow steps (visible in job logs as env).
            </p>
            <div className="cicd-card overflow-hidden">
              <table className="w-full text-[12px]">
                <thead>
                  <tr style={{ color: 'var(--cicd-muted)' }} className="text-left">
                    <th className="p-2.5 font-medium">Name</th>
                    <th className="p-2.5 font-medium">Value</th>
                    <th className="p-2.5 font-medium">Scope</th>
                    <th className="p-2.5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {variables.map((v) => (
                    <tr key={v.name} className="cicd-row">
                      <td className="p-2.5 font-mono">{v.name}</td>
                      <td className="p-2.5">
                        <input
                          className="cicd-select w-full max-w-[220px]"
                          value={v.value}
                          onChange={(e) => setVariables((rows) => rows.map((r) => (
                            r.name === v.name ? { ...r, value: e.target.value } : r
                          )))}
                          onBlur={(e) => {
                            if (sessionId) {
                              cicdApi.upsertVariable(sessionId, { name: v.name, value: e.target.value, scope: v.scope }).then(reloadServer).catch(() => {})
                            }
                          }}
                        />
                      </td>
                      <td className="p-2.5" style={{ color: 'var(--cicd-muted)' }}>{v.scope}</td>
                      <td className="p-2.5 text-right">
                        <button
                          type="button"
                          className="cicd-btn cicd-btn-danger"
                          disabled={gitopsBusy}
                          onClick={() => {
                            if (sessionId) {
                              runGitops(() => cicdApi.deleteVariable(sessionId, v.name), 'Variable removed')
                            } else {
                              setVariables((rows) => rows.filter((r) => r.name !== v.name))
                            }
                          }}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button
              type="button"
              className="cicd-btn"
              disabled={gitopsBusy}
              onClick={() => {
                const name = `VAR_${variables.length + 1}`
                if (sessionId) {
                  runGitops(() => cicdApi.upsertVariable(sessionId, { name, value: '', scope: 'repository' }), 'Variable added')
                } else {
                  setVariables((rows) => [...rows, { name, value: '', scope: 'repository' }])
                }
              }}
            >
              Add variable
            </button>
          </div>
        )}

        {tab === 'environments' && (
          <div className="max-w-4xl mx-auto grid sm:grid-cols-2 gap-3">
            {['staging', 'production'].map((env) => {
              const info = environments[env]
              const isProd = env === 'production'
              return (
                <div key={env} className={`cicd-env-card p-4 ${isProd ? 'cicd-env-prod' : 'cicd-env-staging'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Rocket size={15} style={{ color: isProd ? 'var(--cicd-amber)' : 'var(--cicd-accent)' }} />
                    <span className="text-[14px] font-semibold capitalize">{env}</span>
                    {info && <SimStatusBadge status="success" label="deployed" className="ml-auto" />}
                  </div>
                  {info ? (
                    <div className="text-[12px] space-y-1" style={{ color: 'var(--cicd-muted)' }}>
                      <div>Revision <span className="cicd-sha">{info.sha}</span></div>
                      <div>Run {info.runId} · {new Date(info.at).toLocaleTimeString()}</div>
                      <button
                        type="button"
                        className="cicd-btn mt-2"
                        onClick={() => {
                          if (sessionId) {
                            runGitops(() => cicdApi.clearEnvironmentDeployment(sessionId, env), 'Rolled back')
                          }
                          setEnvironments((e) => {
                            const n = { ...e }; delete n[env]; return n
                          })
                        }}
                        title="Roll back deployment (removes the deployed revision)"
                      >
                        <ArrowUpCircle size={12} /> Rollback
                      </button>
                    </div>
                  ) : (
                    <div className="text-[12px]" style={{ color: 'var(--cicd-muted)' }}>No deployment yet.</div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {tab === 'history' && (
          <div className="max-w-5xl mx-auto">
            {runHistory.length === 0 ? (
              <div className="cicd-card p-6 text-center text-[13px]" style={{ color: 'var(--cicd-muted)' }}>
                No runs yet — click <strong>Run workflow</strong>.
              </div>
            ) : (
              <div className="cicd-card overflow-hidden">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr style={{ color: 'var(--cicd-muted)' }} className="text-left">
                      <th className="p-2.5 font-medium">Run</th>
                      <th className="p-2.5 font-medium">Commit</th>
                      <th className="p-2.5 font-medium">Trigger</th>
                      <th className="p-2.5 font-medium">Duration</th>
                      <th className="p-2.5 font-medium">Status</th>
                      <th className="p-2.5 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runHistory.map((r) => (
                      <tr key={r.runId} className="cicd-row">
                        <td className="p-2.5 font-mono">{r.runId}</td>
                        <td className="p-2.5"><span className="cicd-sha">{r.sha}</span> <span style={{ color: 'var(--cicd-muted)' }}>{r.branch}</span></td>
                        <td className="p-2.5 capitalize">{r.trigger}</td>
                        <td className="p-2.5 font-mono">{fmtDur(r.durationMs)}</td>
                        <td className="p-2.5"><SimStatusBadge status={r.status} /></td>
                        <td className="p-2.5">
                          <div className="flex items-center gap-1.5 justify-end flex-wrap">
                            <button type="button" className="cicd-btn" onClick={() => loadHistory(r)} title="Reload this run into the graph">
                              <History size={11} /> View
                            </button>
                            <button
                              type="button"
                              className="cicd-btn"
                              disabled={running}
                              onClick={() => { setProvider(r.provider); setSeedSlug(r.seedSlug); setSource(r.source); startRun() }}
                              title="Re-run all jobs"
                            >
                              <RotateCcw size={11} /> Re-run all
                            </button>
                            {r.failedJobs?.length > 0 && (
                              <button
                                type="button"
                                className="cicd-btn cicd-btn-danger"
                                disabled={running}
                                onClick={() => { setProvider(r.provider); setSeedSlug(r.seedSlug); setSource(r.source); startRun({ onlyFailedFrom: r.failedJobs }) }}
                                title="Re-run only the jobs that failed or were skipped"
                              >
                                <RotateCcw size={11} /> Re-run failed
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
