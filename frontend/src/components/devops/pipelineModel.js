/**
 * pipelineModel.js — normalized, framework-agnostic CI/CD pipeline shape.
 *
 * A single provider-neutral model that GitLab CI, GitHub Actions and Jenkins
 * pipelines all parse down to. Pure JS, no React, no external deps.
 *
 * Normalized shape:
 *   pipeline = {
 *     provider: 'gitlab' | 'github' | 'jenkins',
 *     name:     string,
 *     stages:   [{ id, name }],
 *     jobs: [{
 *       id, name,
 *       stage:        stageId,
 *       needs:        [jobId],           // explicit DAG deps (in addition to stage order)
 *       steps:        [{ id, name, run }],
 *       environment:  string | null,     // deploy target (e.g. 'production')
 *       when:         'on_success' | 'manual',
 *       allowFailure: boolean,
 *       protected:    boolean,           // requires approval before running
 *     }],
 *   }
 */

/** Job runs after its deps succeed (default). */
export const WHEN_ON_SUCCESS = 'on_success'
/** Job waits for a manual approval gate before running. */
export const WHEN_MANUAL = 'manual'

/** Provider identifiers used across model/parser/engine. */
export const PROVIDERS = Object.freeze({
  GITLAB: 'gitlab',
  GITHUB: 'github',
  JENKINS: 'jenkins',
})

/** Human labels for providers (for UI). */
export const PROVIDER_LABELS = Object.freeze({
  gitlab: 'GitLab CI',
  github: 'GitHub Actions',
  jenkins: 'Jenkins',
})

let _uid = 0
/** Deterministic-enough id generator for synthesized ids. */
function nextId(prefix = 'id') {
  _uid += 1
  return `${prefix}_${_uid}`
}

/** Normalize a raw stage into { id, name }. */
export function normalizeStage(raw, index = 0) {
  if (typeof raw === 'string') {
    const id = slugify(raw) || `stage_${index}`
    return { id, name: raw }
  }
  const name = raw?.name || raw?.id || `stage_${index}`
  const id = slugify(raw?.id || raw?.name || `stage_${index}`)
  return { id, name }
}

/** Normalize a raw step into { id, name, run }. */
export function normalizeStep(raw, index = 0) {
  if (typeof raw === 'string') {
    return { id: nextId('step'), name: raw, run: raw }
  }
  const run = raw?.run != null ? String(raw.run) : String(raw?.name || '')
  return {
    id: raw?.id || nextId('step'),
    name: raw?.name || firstLine(run) || `step ${index + 1}`,
    run,
  }
}

/** Normalize a raw job into the canonical job shape. */
export function normalizeJob(raw, index = 0) {
  const id = slugify(raw?.id || raw?.name || `job_${index}`)
  const when = raw?.when === WHEN_MANUAL ? WHEN_MANUAL : WHEN_ON_SUCCESS
  const steps = Array.isArray(raw?.steps) ? raw.steps.map((s, i) => normalizeStep(s, i)) : []
  return {
    id,
    name: raw?.name || raw?.id || `job ${index + 1}`,
    stage: raw?.stage ? slugify(raw.stage) : null,
    needs: Array.isArray(raw?.needs) ? raw.needs.map((n) => slugify(n)) : [],
    steps,
    environment: raw?.environment || null,
    when,
    allowFailure: Boolean(raw?.allowFailure),
    protected: Boolean(raw?.protected) || when === WHEN_MANUAL || isProtectedEnv(raw?.environment),
  }
}

/**
 * Build a normalized pipeline model from loosely-shaped input. Idempotent:
 * feeding an already-normalized model back in yields the same model.
 */
export function createPipeline({ provider, name, stages, jobs } = {}) {
  const normStages = Array.isArray(stages) ? stages.map((s, i) => normalizeStage(s, i)) : []
  const normJobs = Array.isArray(jobs) ? jobs.map((j, i) => normalizeJob(j, i)) : []

  // If a job references a stage that isn't declared, synthesize it so the
  // engine still has a stage to bucket into (the parser flags this as an error
  // separately — the model stays tolerant).
  const known = new Set(normStages.map((s) => s.id))
  for (const job of normJobs) {
    if (job.stage && !known.has(job.stage)) {
      normStages.push({ id: job.stage, name: job.stage })
      known.add(job.stage)
    }
  }

  return {
    provider: provider || PROVIDERS.GITLAB,
    name: name || 'pipeline',
    stages: normStages,
    jobs: normJobs,
  }
}

/** Map of jobId -> job for quick lookup. */
export function jobMap(pipeline) {
  const m = new Map()
  for (const job of pipeline?.jobs || []) m.set(job.id, job)
  return m
}

/**
 * Full dependency set for a job: explicit `needs` plus implicit ordering from
 * the stage list (a job depends on every job in an earlier stage). Returns a
 * de-duplicated array of jobIds.
 *
 * GitHub Actions has no `stages:` concept — jobs run fully in parallel and order
 * is driven ONLY by `needs`. The GitHub parser synthesizes a 1:1 stage per job
 * purely so the graph can lay nodes out in columns; treating those synthetic
 * stages as sequential would invent phantom dependencies (e.g. an independent
 * `lint` job blocking `build`). So for GitHub we skip implicit stage ordering
 * and rely on `needs` alone, matching real Actions scheduling.
 */
export function resolveJobDeps(pipeline, job) {
  const deps = new Set(job.needs || [])
  const usesStageOrdering = pipeline?.provider !== PROVIDERS.GITHUB
  if (usesStageOrdering && job.stage) {
    const stageOrder = (pipeline.stages || []).map((s) => s.id)
    const myStageIdx = stageOrder.indexOf(job.stage)
    if (myStageIdx > 0) {
      const priorStages = new Set(stageOrder.slice(0, myStageIdx))
      for (const other of pipeline.jobs) {
        if (other.id !== job.id && priorStages.has(other.stage)) deps.add(other.id)
      }
    }
  }
  return [...deps].filter((d) => d !== job.id)
}

/**
 * Compute topological levels for concurrent execution. Returns an array of
 * "levels"; each level is an array of jobIds that can run in parallel once all
 * previous levels finish. Throws { code: 'cyclic', cycle } on a cycle.
 */
export function topoLevels(pipeline) {
  const jobs = pipeline?.jobs || []
  const ids = new Set(jobs.map((j) => j.id))
  const deps = new Map()
  for (const job of jobs) {
    deps.set(job.id, resolveJobDeps(pipeline, job).filter((d) => ids.has(d)))
  }

  const remaining = new Set(ids)
  const levels = []
  let guard = 0
  while (remaining.size) {
    guard += 1
    if (guard > jobs.length + 2) break
    const ready = []
    for (const id of remaining) {
      const d = deps.get(id) || []
      if (d.every((dep) => !remaining.has(dep))) ready.push(id)
    }
    if (ready.length === 0) {
      const err = new Error('Cyclic dependency detected in pipeline `needs`')
      err.code = 'cyclic'
      err.cycle = [...remaining]
      throw err
    }
    ready.sort()
    levels.push(ready)
    for (const id of ready) remaining.delete(id)
  }
  return levels
}

/** Detect a cycle without throwing. Returns the offending jobIds or null. */
export function findCycle(pipeline) {
  try {
    topoLevels(pipeline)
    return null
  } catch (e) {
    if (e.code === 'cyclic') return e.cycle
    throw e
  }
}

// ── helpers ────────────────────────────────────────────────────────────────

const PROTECTED_ENVS = /^(prod|production|prd|live)$/i

function isProtectedEnv(env) {
  return typeof env === 'string' && PROTECTED_ENVS.test(env.trim())
}

/** kebab/snake-safe slug for ids. Keeps existing valid ids stable. */
export function slugify(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function firstLine(str) {
  return String(str || '').split('\n')[0].trim()
}
