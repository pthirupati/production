/**
 * pipelineParser.js — forgiving, hand-rolled CI/CD config parsers.
 *
 * NO js-yaml dependency. Each parser converts a provider's config text into the
 * normalized model (see pipelineModel.js) plus a list of structured validation
 * errors — modeled on GitLab's CI Lint output.
 *
 *   parseGitlab(yaml)        -> { pipeline, errors }
 *   parseGithubActions(yaml) -> { pipeline, errors }
 *   parseJenkinsfile(text)   -> { pipeline, errors }
 *   parsePipeline(text, provider) -> dispatch by provider
 *
 * Validation error shape:
 *   { code, message, job?, stage?, line? }
 * codes: 'unknown-stage' | 'job-without-stage' | 'duplicate-id' |
 *        'cyclic-needs' | 'unknown-need' | 'empty' | 'no-jobs' | 'parse'
 */

import { createPipeline, findCycle, slugify, PROVIDERS, WHEN_MANUAL, WHEN_ON_SUCCESS } from './pipelineModel'

// GitLab reserved top-level keys that are not jobs.
const GITLAB_RESERVED = new Set([
  'stages', 'variables', 'default', 'include', 'workflow', 'image', 'services',
  'before_script', 'after_script', 'cache', 'pages',
])

/** Public dispatch by provider slug. */
export function parsePipeline(text, provider) {
  switch (provider) {
    case PROVIDERS.GITHUB: return parseGithubActions(text)
    case PROVIDERS.JENKINS: return parseJenkinsfile(text)
    case PROVIDERS.GITLAB:
    default: return parseGitlab(text)
  }
}

/**
 * Common validation across all providers once a raw model has been assembled.
 * Mutates nothing; returns an errors array.
 */
export function validateModel(pipeline, { rawJobs = [], declaredStageIds = null } = {}) {
  const errors = []
  // Validate stage refs against what the author actually declared (if the
  // parser passed it) — createPipeline synthesizes missing stages, so relying
  // on pipeline.stages would hide `unknown-stage`. Fall back to the model's
  // stages when a provider has no explicit stage list (GitHub/Jenkins).
  const stageIds = declaredStageIds ? new Set(declaredStageIds) : new Set(pipeline.stages.map((s) => s.id))
  const seen = new Set()

  if (!pipeline.jobs.length) {
    errors.push({ code: 'no-jobs', message: 'No jobs found in pipeline definition.' })
  }

  for (const job of pipeline.jobs) {
    if (seen.has(job.id)) {
      errors.push({ code: 'duplicate-id', job: job.id, message: `Duplicate job id "${job.id}".` })
    }
    seen.add(job.id)

    // job-without-stage: only flag when the provider uses stages at all.
    if (pipeline.stages.length && !job.stage) {
      errors.push({ code: 'job-without-stage', job: job.id, message: `Job "${job.id}" is not assigned to a stage.` })
    }

    // unknown-stage: job references a stage not declared in `stages`.
    const declared = rawJobs.find((r) => slugify(r.id || r.name) === job.id)
    const declaredStage = declared?.stage ? slugify(declared.stage) : job.stage
    if (declaredStage && !stageIds.has(declaredStage)) {
      errors.push({ code: 'unknown-stage', job: job.id, stage: declaredStage, message: `Job "${job.id}" references undeclared stage "${declaredStage}".` })
    }

    for (const need of job.needs) {
      if (!pipeline.jobs.some((j) => j.id === need)) {
        errors.push({ code: 'unknown-need', job: job.id, message: `Job "${job.id}" needs unknown job "${need}".` })
      }
    }
  }

  const cycle = findCycle(pipeline)
  if (cycle && cycle.length) {
    errors.push({ code: 'cyclic-needs', message: `Cyclic dependency in \`needs\`: ${cycle.join(' -> ')}.`, jobs: cycle })
  }

  return errors
}

// ─────────────────────────────────────────────────────────────────────────────
// GitLab CI
// ─────────────────────────────────────────────────────────────────────────────

export function parseGitlab(yaml) {
  const text = String(yaml || '')
  if (!text.trim()) return emptyResult(PROVIDERS.GITLAB)

  const lines = stripComments(text.split('\n'))
  const top = parseTopLevelBlocks(lines)

  const stages = Array.isArray(top.__stages) ? top.__stages : []
  const rawJobs = []

  for (const [key, block] of Object.entries(top.blocks)) {
    if (GITLAB_RESERVED.has(key)) continue
    if (key.startsWith('.')) continue // hidden/template job

    const props = block.props
    const script = block.lists.script || block.lists.run || []
    const rules = block.lists.rules || []
    const whenManual = /manual/i.test(props.when || '') || rules.some((r) => /when:\s*manual/i.test(r))

    rawJobs.push({
      id: key,
      name: key,
      stage: props.stage || null,
      needs: normalizeNeeds(block.lists.needs, props.needs),
      steps: script.map((s) => ({ name: firstToken(s), run: s })),
      environment: extractEnvName(props.environment, block.blocks?.environment),
      when: whenManual ? WHEN_MANUAL : WHEN_ON_SUCCESS,
      allowFailure: /true/i.test(props.allow_failure || ''),
    })
  }

  const pipeline = createPipeline({
    provider: PROVIDERS.GITLAB,
    name: '.gitlab-ci.yml',
    stages: stages.length ? stages : uniqueStages(rawJobs),
    jobs: rawJobs,
  })
  // Only enforce unknown-stage when the author declared an explicit `stages:`
  // list; otherwise GitLab derives stages from jobs and any ref is valid.
  const declaredStageIds = stages.length ? stages.map((s) => s.id) : null
  const errors = validateModel(pipeline, { rawJobs, declaredStageIds })
  return { pipeline, errors }
}

// ─────────────────────────────────────────────────────────────────────────────
// GitHub Actions
// ─────────────────────────────────────────────────────────────────────────────

export function parseGithubActions(yaml) {
  const text = String(yaml || '')
  if (!text.trim()) return emptyResult(PROVIDERS.GITHUB)

  const lines = stripComments(text.split('\n'))
  const name = matchValue(lines, /^name:\s*(.+)$/) || 'workflow'

  // Find the `jobs:` block and parse each 2-space-indented job key.
  const jobsStart = lines.findIndex((l) => /^jobs:\s*$/.test(l))
  const rawJobs = []
  if (jobsStart !== -1) {
    const jobBlocks = splitIndentedBlocks(lines.slice(jobsStart + 1), 2)
    for (const jb of jobBlocks) {
      const props = collectScalarProps(jb.body, jb.indent + 2)
      const steps = parseGithubSteps(jb.body)
      const needs = normalizeNeeds(null, props.needs)
      const envName = props.environment || extractGithubEnvBlock(jb.body)
      const isManual = props.if && /manual|workflow_dispatch/i.test(props.if)
      rawJobs.push({
        id: jb.key,
        name: props.name || jb.key,
        // GitHub has no stages; we synthesize one stage per job so ordering
        // comes purely from `needs`.
        stage: jb.key,
        needs,
        steps,
        environment: envName,
        when: isManual ? WHEN_MANUAL : WHEN_ON_SUCCESS,
        allowFailure: /true/i.test(props['continue-on-error'] || ''),
      })
    }
  }

  const pipeline = createPipeline({
    provider: PROVIDERS.GITHUB,
    name,
    stages: uniqueStages(rawJobs),
    jobs: rawJobs,
  })
  const errors = validateModel(pipeline, { rawJobs })
  return { pipeline, errors }
}

// ─────────────────────────────────────────────────────────────────────────────
// Jenkinsfile (declarative pipeline)
// ─────────────────────────────────────────────────────────────────────────────

export function parseJenkinsfile(text) {
  const src = String(text || '')
  if (!src.trim()) return emptyResult(PROVIDERS.JENKINS)

  const rawJobs = []
  const stageNames = []
  // Match `stage('Name') { ... }` blocks by brace-balancing.
  const stageRe = /stage\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\{/g
  let m
  let prevStageId = null
  while ((m = stageRe.exec(src))) {
    const stageName = m[1]
    const stageId = slugify(stageName)
    const bodyStart = m.index + m[0].length
    const body = extractBraceBlock(src, bodyStart - 1) // include opening brace
    stageNames.push(stageName)

    const steps = parseJenkinsSteps(body)
    const isManual = /input\s*(\(|\{|\s+message)/.test(body)
    const envName = matchJenkinsEnv(body)
    const needs = prevStageId ? [prevStageId] : []

    rawJobs.push({
      id: stageId,
      name: stageName,
      stage: stageId,
      needs,
      steps,
      environment: envName,
      when: isManual ? WHEN_MANUAL : WHEN_ON_SUCCESS,
      allowFailure: false,
    })
    prevStageId = stageId
  }

  const pipeline = createPipeline({
    provider: PROVIDERS.JENKINS,
    name: 'Jenkinsfile',
    stages: stageNames.map((n) => ({ id: slugify(n), name: n })),
    jobs: rawJobs,
  })
  const errors = validateModel(pipeline, { rawJobs })
  return { pipeline, errors }
}

// ─────────────────────────────────────────────────────────────────────────────
// Low-level YAML-ish helpers (indent-based, forgiving)
// ─────────────────────────────────────────────────────────────────────────────

function emptyResult(provider) {
  return {
    pipeline: createPipeline({ provider, name: provider, stages: [], jobs: [] }),
    errors: [{ code: 'empty', message: 'Pipeline definition is empty.' }],
  }
}

/** Drop full-line and trailing `#` comments and trailing whitespace. */
function stripComments(lines) {
  return lines.map((raw) => {
    let line = raw.replace(/\s+$/, '')
    // Remove trailing comments that are not inside quotes (best-effort).
    const hash = line.indexOf(' #')
    if (hash !== -1 && !/['"][^'"]*#/.test(line.slice(0, hash))) {
      line = line.slice(0, hash).replace(/\s+$/, '')
    }
    return line
  })
}

function indentOf(line) {
  const m = line.match(/^(\s*)/)
  return m ? m[1].length : 0
}

/**
 * Parse the GitLab top-level: returns { __stages: [...], blocks: { key: {props, lists, blocks} } }.
 * A "block" is a top-level (indent 0) mapping key whose nested keys are collected.
 */
function parseTopLevelBlocks(lines) {
  const result = { __stages: null, blocks: {} }
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i += 1; continue }
    if (indentOf(line) !== 0) { i += 1; continue }

    const keyMatch = line.match(/^([A-Za-z0-9_.\-/]+):\s*(.*)$/)
    if (!keyMatch) { i += 1; continue }
    const key = keyMatch[1]
    const inline = keyMatch[2]

    // Gather nested lines (indent > 0) until next indent-0 key.
    const bodyStart = i + 1
    let j = bodyStart
    while (j < lines.length && (!lines[j].trim() || indentOf(lines[j]) > 0)) j += 1
    const body = lines.slice(bodyStart, j)

    if (key === 'stages') {
      result.__stages = parseYamlList(inline, body).map((s) => ({ id: slugify(s), name: s }))
    } else {
      result.blocks[key] = parseBlockBody(body)
    }
    i = j
  }
  return result
}

/** Parse a block body into scalar props, named lists, and nested blocks. */
function parseBlockBody(body) {
  const props = {}
  const lists = {}
  const blocks = {}
  const base = body.length ? Math.min(...body.filter((l) => l.trim()).map(indentOf)) : 0

  let i = 0
  while (i < body.length) {
    const line = body[i]
    if (!line.trim()) { i += 1; continue }
    if (indentOf(line) !== base) { i += 1; continue }

    const listItem = line.match(/^\s*-\s+(.*)$/)
    if (listItem) { i += 1; continue } // stray list item at block base — ignore

    const kv = line.match(/^\s*([A-Za-z0-9_.\-]+):\s*(.*)$/)
    if (!kv) { i += 1; continue }
    const key = kv[1]
    const val = kv[2]

    // Collect nested lines under this key.
    let j = i + 1
    while (j < body.length && (!body[j].trim() || indentOf(body[j]) > base)) j += 1
    const nested = body.slice(i + 1, j)

    if (val && !isListMarker(val)) {
      props[key] = stripQuotes(val)
    } else if (nested.some((l) => /^\s*-\s+/.test(l))) {
      lists[key] = parseYamlList(val, nested)
    } else if (nested.length) {
      blocks[key] = parseBlockBody(nested)
    } else if (val) {
      props[key] = stripQuotes(val)
    }
    i = j
  }
  return { props, lists, blocks }
}

/** Parse a YAML list from either inline `[a, b]` or block `- a\n- b` form. */
function parseYamlList(inline, body = []) {
  const items = []
  const trimmed = (inline || '').trim()
  if (trimmed.startsWith('[')) {
    return trimmed.replace(/^\[|\]$/g, '')
      .split(',')
      .map((s) => stripQuotes(s.trim()))
      .filter(Boolean)
  }
  for (const line of body) {
    const m = line.match(/^\s*-\s+(.*)$/)
    if (m) items.push(stripQuotes(m[1].trim()))
  }
  return items
}

/** Split a body into indented blocks keyed by `key:` lines at exactly `indent`. */
function splitIndentedBlocks(body, indent) {
  const blocks = []
  let i = 0
  while (i < body.length) {
    const line = body[i]
    if (!line.trim()) { i += 1; continue }
    if (indentOf(line) !== indent) { i += 1; continue }
    const km = line.match(/^\s*([A-Za-z0-9_.\-]+):\s*$/)
    if (!km) { i += 1; continue }
    const key = km[1]
    let j = i + 1
    while (j < body.length && (!body[j].trim() || indentOf(body[j]) > indent)) j += 1
    blocks.push({ key, indent, body: body.slice(i + 1, j) })
    i = j
  }
  return blocks
}

/** Collect scalar `key: value` props at a given indent from a body. */
function collectScalarProps(body, indent) {
  const props = {}
  for (const line of body) {
    if (indentOf(line) !== indent) continue
    const m = line.match(/^\s*([A-Za-z0-9_.\-]+):\s*(.+)$/)
    if (m && !isListMarker(m[2])) props[m[1]] = stripQuotes(m[2])
  }
  return props
}

/** Parse GitHub Actions `steps:` (list of `- name:/run:/uses:`). */
function parseGithubSteps(body) {
  const stepsStart = body.findIndex((l) => /^\s*steps:\s*$/.test(l))
  if (stepsStart === -1) return []
  const stepsIndent = indentOf(body[stepsStart])
  const region = body.slice(stepsStart + 1)
  const steps = []
  let cur = null
  for (const line of region) {
    if (!line.trim()) continue
    if (indentOf(line) <= stepsIndent && !/^\s*-/.test(line)) break
    const itemStart = line.match(/^\s*-\s+(.*)$/)
    if (itemStart) {
      if (cur) steps.push(cur)
      cur = { name: '', run: '' }
      applyStepKv(cur, itemStart[1])
      continue
    }
    if (cur) applyStepKv(cur, line.trim())
  }
  if (cur) steps.push(cur)
  return steps.map((s) => ({ name: s.name || firstToken(s.run) || 'step', run: s.run || s.name }))
}

function applyStepKv(step, fragment) {
  const kv = fragment.match(/^([A-Za-z0-9_.\-]+):\s*(.*)$/)
  if (!kv) return
  const [, key, value] = kv
  if (key === 'name') step.name = stripQuotes(value)
  else if (key === 'run') step.run = stripQuotes(value.replace(/^\|>?-?\s*/, ''))
  else if (key === 'uses') step.run = `uses ${stripQuotes(value)}`
}

/** Parse Jenkins `steps { sh '...'; sh '...' }` inside a stage body. */
function parseJenkinsSteps(body) {
  const steps = []
  const stepRe = /(sh|bat|echo)\s+(?:'''([\s\S]*?)'''|"""([\s\S]*?)"""|'([^']*)'|"([^"]*)")/g
  let m
  while ((m = stepRe.exec(body))) {
    const cmd = (m[2] || m[3] || m[4] || m[5] || '').trim()
    for (const part of cmd.split('\n').map((s) => s.trim()).filter(Boolean)) {
      steps.push({ name: firstToken(part), run: part })
    }
  }
  return steps
}

function matchJenkinsEnv(body) {
  const m = body.match(/environment\s*['"]?\s*[:=]?\s*['"]([^'"]+)['"]/i)
    || body.match(/deploy(?:ing)?\s+to\s+['"]?([A-Za-z0-9_-]+)/i)
  return m ? m[1] : null
}

// ── small scalar helpers ─────────────────────────────────────────────────────

function normalizeNeeds(listForm, scalarForm) {
  if (Array.isArray(listForm) && listForm.length) return listForm.map(cleanNeed)
  if (typeof scalarForm === 'string' && scalarForm.trim()) {
    const t = scalarForm.trim()
    if (t.startsWith('[')) {
      return t.replace(/^\[|\]$/g, '').split(',').map((s) => cleanNeed(stripQuotes(s.trim()))).filter(Boolean)
    }
    return [cleanNeed(t)]
  }
  return []
}

function cleanNeed(need) {
  // GitLab `needs:` items may be `{ job: build }` maps flattened to text.
  const m = String(need).match(/job:\s*([A-Za-z0-9_.\-]+)/)
  return slugify(m ? m[1] : need)
}

function extractEnvName(scalar, block) {
  if (typeof scalar === 'string' && scalar.trim()) return stripQuotes(scalar).replace(/name:\s*/, '')
  if (block?.props?.name) return block.props.name
  return null
}

function extractGithubEnvBlock(body) {
  for (const line of body) {
    const m = line.match(/^\s*environment:\s*(.+)$/)
    if (m && !isListMarker(m[1])) return stripQuotes(m[1])
    const nameM = line.match(/^\s*name:\s*(.+)$/)
    if (nameM && body.some((l) => /^\s*environment:\s*$/.test(l))) return stripQuotes(nameM[1])
  }
  return null
}

function uniqueStages(rawJobs) {
  const seen = new Map()
  for (const j of rawJobs) {
    const id = j.stage ? slugify(j.stage) : slugify(j.id)
    if (!seen.has(id)) seen.set(id, { id, name: j.stage || j.name || id })
  }
  return [...seen.values()]
}

function isListMarker(val) {
  const t = (val || '').trim()
  return t === '' || t === '|' || t === '>' || t === '|-' || t === '>-'
}

function stripQuotes(val) {
  return String(val || '').trim().replace(/^['"]|['"]$/g, '')
}

function firstToken(str) {
  return String(str || '').trim().split(/\s+/)[0] || ''
}

function matchValue(lines, re) {
  for (const line of lines) {
    const m = line.match(re)
    if (m) return stripQuotes(m[1])
  }
  return null
}

/** Extract a brace-balanced block starting at the `{` at or after `openIdx`. */
function extractBraceBlock(src, openIdx) {
  let i = openIdx
  while (i < src.length && src[i] !== '{') i += 1
  if (src[i] !== '{') return ''
  let depth = 0
  const start = i
  for (; i < src.length; i += 1) {
    if (src[i] === '{') depth += 1
    else if (src[i] === '}') {
      depth -= 1
      if (depth === 0) return src.slice(start + 1, i)
    }
  }
  return src.slice(start + 1)
}
