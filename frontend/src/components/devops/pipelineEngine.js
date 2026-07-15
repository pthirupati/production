/**
 * pipelineEngine.js — pure-JS CI/CD run engine.
 *
 * Drives a normalized pipeline model (see pipelineModel.js) through a realistic
 * run: topological levels run concurrently (Promise.all per level), each job
 * streams ANSI-tagged log lines with per-line delays, and a scriptable faults
 * map lets labs inject failures / flakiness / manual-approval gates.
 *
 * No React, no timers you can't control — fully unit-testable by passing a
 * deterministic `clock`/`sleep` and reading emitted events.
 *
 * Events (via onEvent):
 *   { type: 'run:started',  runId, order }                       levels = jobIds[][]
 *   { type: 'job:queued',   runId, jobId, name }
 *   { type: 'job:running',  runId, jobId, name }
 *   { type: 'job:awaiting_approval', runId, jobId, name }        manual/protected gate
 *   { type: 'step:log',     runId, jobId, stepId, line }         ANSI-tagged
 *   { type: 'step:done',    runId, jobId, stepId, status, durationMs }
 *   { type: 'job:done',     runId, jobId, status, durationMs }   status: success|failed|skipped|canceled
 *   { type: 'run:done',     runId, status, durationMs }
 */

import { topoLevels, jobMap, resolveJobDeps, WHEN_MANUAL } from './pipelineModel'

export const JOB_STATUS = Object.freeze({
  QUEUED: 'queued',
  RUNNING: 'running',
  AWAITING_APPROVAL: 'awaiting_approval',
  SUCCESS: 'success',
  FAILED: 'failed',
  SKIPPED: 'skipped',
  CANCELED: 'canceled',
})

// ANSI SGR codes matching sim/shared/SimTerminalLog.jsx palette.
const ANSI = { reset: '\x1b[0m', green: '\x1b[32m', red: '\x1b[31m', yellow: '\x1b[33m', cyan: '\x1b[36m', bold: '\x1b[1m' }

/** Wrap text in an ANSI color+reset. */
export function ansi(color, text) {
  const code = ANSI[color] || ''
  return `${code}${text}${ANSI.reset}`
}

const DEFAULT_LINE_DELAY = [60, 140] // ms per streamed log line
const DEFAULT_STEP_PAD = [120, 260] // extra ms after a step's lines

let _runSeq = 0

/**
 * createPipelineRun(pipeline, opts) -> controller
 *
 * opts:
 *   faults:    { [jobId]: { failAtStep?: number|stepName, message?, flaky?: number(0..1), exitCode? } }
 *   onEvent:   (event) => void
 *   runId:     string (optional; auto-generated otherwise)
 *   sleep:     (ms) => Promise (injectable; defaults to setTimeout)
 *   rng:       () => number in [0,1) (injectable; defaults to Math.random)
 *   lineDelay: [min,max] ms per log line
 *   autoApprove: boolean — if true, manual/protected gates resolve immediately
 *
 * controller:
 *   start()      -> Promise<{ status, durationMs, jobs }>
 *   cancel()     -> flips abort flag; in-flight run resolves 'canceled'
 *   approve(id)  -> release a job waiting at an approval gate
 *   reject(id)   -> fail a job waiting at an approval gate
 *   isAwaiting(id), getState()
 */
export function createPipelineRun(pipeline, opts = {}) {
  const {
    faults = {},
    onEvent = () => {},
    sleep = defaultSleep,
    rng = Math.random,
    lineDelay = DEFAULT_LINE_DELAY,
    autoApprove = false,
  } = opts

  _runSeq += 1
  const runId = opts.runId || `run-${Date.now()}-${_runSeq}`

  const jobs = jobMap(pipeline)
  const state = {
    runId,
    status: JOB_STATUS.QUEUED,
    aborted: false,
    startedAt: 0,
    jobStatus: new Map(), // jobId -> status
    jobDuration: new Map(), // jobId -> ms
  }

  // Pending manual-approval gates: jobId -> { resolve } (resolve('approved'|'rejected'))
  const gates = new Map()

  function emit(evt) {
    try {
      onEvent({ runId, ...evt })
    } catch {
      /* listener errors never break the run */
    }
  }

  function rand(range) {
    const [min, max] = range
    return Math.round(min + rng() * (max - min))
  }

  function cancel() {
    state.aborted = true
    // Release any open gates so awaiters unblock as canceled.
    for (const [, gate] of gates) gate.resolve('canceled')
    gates.clear()
  }

  function approve(jobId) {
    const gate = gates.get(jobId)
    if (gate) {
      gates.delete(jobId)
      gate.resolve('approved')
      return true
    }
    return false
  }

  function reject(jobId) {
    const gate = gates.get(jobId)
    if (gate) {
      gates.delete(jobId)
      gate.resolve('rejected')
      return true
    }
    return false
  }

  function isAwaiting(jobId) {
    return gates.has(jobId)
  }

  function getState() {
    return {
      runId: state.runId,
      status: state.status,
      aborted: state.aborted,
      jobs: [...state.jobStatus.entries()].map(([id, status]) => ({
        id,
        status,
        durationMs: state.jobDuration.get(id) || 0,
      })),
    }
  }

  /** Wait at a manual/protected approval gate. Resolves to a verdict string. */
  function waitForApproval(job) {
    if (autoApprove) return Promise.resolve('approved')
    return new Promise((resolve) => {
      gates.set(job.id, { resolve })
      emit({ type: 'job:awaiting_approval', jobId: job.id, name: job.name })
    })
  }

  /** Run one step: stream lines, honor faults, return { status, durationMs }. */
  async function runStep(job, step, stepIndex, fault) {
    const start = now()
    const lines = buildStepLog(job, step)

    for (const line of lines) {
      if (state.aborted) return { status: JOB_STATUS.CANCELED, durationMs: now() - start }
      emit({ type: 'step:log', jobId: job.id, stepId: step.id, line })
      await sleep(rand(lineDelay))
    }
    await sleep(rand(DEFAULT_STEP_PAD))

    if (state.aborted) return { status: JOB_STATUS.CANCELED, durationMs: now() - start }

    if (stepFails(fault, step, stepIndex, rng)) {
      const msg = fault?.message || `Command exited with code ${fault?.exitCode ?? 1}`
      emit({ type: 'step:log', jobId: job.id, stepId: step.id, line: ansi('red', `ERROR: ${msg}`) })
      emit({ type: 'step:log', jobId: job.id, stepId: step.id, line: ansi('red', `Job failed: exit code ${fault?.exitCode ?? 1}`) })
      const durationMs = now() - start
      emit({ type: 'step:done', jobId: job.id, stepId: step.id, status: JOB_STATUS.FAILED, durationMs })
      return { status: JOB_STATUS.FAILED, durationMs }
    }

    const durationMs = now() - start
    emit({ type: 'step:done', jobId: job.id, stepId: step.id, status: JOB_STATUS.SUCCESS, durationMs })
    return { status: JOB_STATUS.SUCCESS, durationMs }
  }

  /** Run a single job (all steps sequentially). Returns final job status. */
  async function runJob(job) {
    const fault = faults[job.id] || null
    state.jobStatus.set(job.id, JOB_STATUS.QUEUED)
    emit({ type: 'job:queued', jobId: job.id, name: job.name })

    // Skip if an upstream dependency failed (unless this job allows failure upstream).
    const deps = resolveJobDeps(pipeline, job).filter((d) => jobs.has(d))
    const anyDepFailed = deps.some((d) => {
      const s = state.jobStatus.get(d)
      const depJob = jobs.get(d)
      return (s === JOB_STATUS.FAILED || s === JOB_STATUS.CANCELED) && !(depJob && depJob.allowFailure)
    })
    if (anyDepFailed) {
      state.jobStatus.set(job.id, JOB_STATUS.SKIPPED)
      emit({ type: 'job:done', jobId: job.id, status: JOB_STATUS.SKIPPED, durationMs: 0 })
      return JOB_STATUS.SKIPPED
    }

    if (state.aborted) {
      state.jobStatus.set(job.id, JOB_STATUS.CANCELED)
      emit({ type: 'job:done', jobId: job.id, status: JOB_STATUS.CANCELED, durationMs: 0 })
      return JOB_STATUS.CANCELED
    }

    // Manual / protected approval gate.
    if (job.when === WHEN_MANUAL || job.protected) {
      const verdict = await waitForApproval(job)
      if (verdict === 'rejected') {
        state.jobStatus.set(job.id, JOB_STATUS.FAILED)
        emit({ type: 'step:log', jobId: job.id, stepId: null, line: ansi('red', 'Approval rejected — job canceled') })
        emit({ type: 'job:done', jobId: job.id, status: JOB_STATUS.FAILED, durationMs: 0 })
        return JOB_STATUS.FAILED
      }
      if (verdict === 'canceled' || state.aborted) {
        state.jobStatus.set(job.id, JOB_STATUS.CANCELED)
        emit({ type: 'job:done', jobId: job.id, status: JOB_STATUS.CANCELED, durationMs: 0 })
        return JOB_STATUS.CANCELED
      }
    }

    // If the fault says this whole job never starts (approval timeout), bail.
    if (fault?.approvalTimeout) {
      state.jobStatus.set(job.id, JOB_STATUS.FAILED)
      emit({ type: 'step:log', jobId: job.id, stepId: null, line: ansi('yellow', 'Timed out waiting for manual approval') })
      emit({ type: 'job:done', jobId: job.id, status: JOB_STATUS.FAILED, durationMs: 0 })
      return JOB_STATUS.FAILED
    }

    state.jobStatus.set(job.id, JOB_STATUS.RUNNING)
    emit({ type: 'job:running', jobId: job.id, name: job.name })

    const jobStart = now()
    let finalStatus = JOB_STATUS.SUCCESS
    const steps = job.steps.length ? job.steps : [{ id: `${job.id}_step`, name: job.name, run: job.name }]

    for (let i = 0; i < steps.length; i += 1) {
      const res = await runStep(job, steps[i], i, fault)
      if (res.status === JOB_STATUS.CANCELED) {
        finalStatus = JOB_STATUS.CANCELED
        break
      }
      if (res.status === JOB_STATUS.FAILED) {
        finalStatus = job.allowFailure ? JOB_STATUS.SUCCESS : JOB_STATUS.FAILED
        break
      }
    }

    const durationMs = now() - jobStart
    state.jobStatus.set(job.id, finalStatus)
    state.jobDuration.set(job.id, durationMs)
    emit({ type: 'job:done', jobId: job.id, status: finalStatus, durationMs })
    return finalStatus
  }

  async function start() {
    let levels
    try {
      levels = topoLevels(pipeline)
    } catch (e) {
      state.status = JOB_STATUS.FAILED
      emit({ type: 'run:done', status: JOB_STATUS.FAILED, durationMs: 0, error: e.code || 'invalid', cycle: e.cycle })
      return { status: JOB_STATUS.FAILED, durationMs: 0, error: e.code || 'invalid', jobs: [] }
    }

    state.status = JOB_STATUS.RUNNING
    state.startedAt = now()
    emit({ type: 'run:started', order: levels })

    for (const level of levels) {
      if (state.aborted) break
      // Jobs within a level are independent → run concurrently.
      await Promise.all(level.map((jobId) => {
        const job = jobs.get(jobId)
        return job ? runJob(job) : Promise.resolve(JOB_STATUS.SKIPPED)
      }))
    }

    const statuses = [...state.jobStatus.values()]
    let runStatus = JOB_STATUS.SUCCESS
    if (state.aborted) runStatus = JOB_STATUS.CANCELED
    else if (statuses.includes(JOB_STATUS.FAILED)) runStatus = JOB_STATUS.FAILED

    const durationMs = now() - state.startedAt
    state.status = runStatus
    emit({ type: 'run:done', status: runStatus, durationMs })
    return { status: runStatus, durationMs, jobs: getState().jobs }
  }

  return { runId, start, cancel, approve, reject, isAwaiting, getState }
}

// ── log synthesis ────────────────────────────────────────────────────────────

/** Build realistic ANSI-tagged log lines for a step. */
function buildStepLog(job, step) {
  const cmd = (step.run || step.name || '').trim()
  const lines = []
  lines.push(ansi('cyan', `$ ${cmd}`))

  if (/npm ci|npm install|yarn/i.test(cmd)) {
    lines.push('added 842 packages in 6s')
  } else if (/npm run build|mvn .*package|gradle .*build|go build/i.test(cmd)) {
    lines.push(ansi('green', 'BUILD SUCCESS'))
  } else if (/npm test|pytest|go test|mvn .*test|jest/i.test(cmd)) {
    lines.push(ansi('green', 'Tests run: 42, Failures: 0'))
    lines.push('Coverage: 78%')
  } else if (/docker (build|pull|push)/i.test(cmd)) {
    lines.push('Successfully tagged image')
  } else if (/kubectl apply|argocd app sync|helm (upgrade|install)|flux/i.test(cmd)) {
    lines.push(ansi('green', 'Sync status: Synced'))
    lines.push(ansi('green', 'Health: Healthy'))
  } else if (/sonar/i.test(cmd)) {
    lines.push(ansi('green', 'Quality Gate PASSED'))
  } else {
    lines.push('done')
  }

  if (job.environment) lines.push(`Deploying to environment: ${job.environment}`)
  return lines
}

/** Decide whether a step fails given its fault descriptor. */
function stepFails(fault, step, stepIndex, rng = Math.random) {
  if (!fault) return false
  if (typeof fault.flaky === 'number' && fault.flaky > 0) {
    if (rng() < fault.flaky) return true
  }
  if (fault.failAtStep == null) return Boolean(fault.always)
  if (typeof fault.failAtStep === 'number') return stepIndex === fault.failAtStep
  // string → match against step name or run command
  const target = String(fault.failAtStep).toLowerCase()
  return (
    String(step.name || '').toLowerCase().includes(target)
    || String(step.run || '').toLowerCase().includes(target)
  )
}

// ── injectable primitives ────────────────────────────────────────────────────

function now() {
  return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()
}

function defaultSleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
