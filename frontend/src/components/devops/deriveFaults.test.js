/**
 * Faults must follow the YAML the learner actually edited (audit L992).
 *
 * Before this, faults came straight from CICD_FAULTS_CATALOG keyed on the
 * scenario slug, so `parsed` changed on every keystroke but the fault set never
 * did — a lab graded on "job goes green" could not be passed by fixing the
 * pipeline. These tests drive the real parser over the real seed YAML so a
 * regression in either the parser or the derivation is caught.
 */
import { describe, it, expect } from 'vitest'
import { deriveFaults } from './CicdPipelineSim'
import { parsePipeline } from './pipelineParser'
import { PROVIDERS } from './pipelineModel'
import { CICD_FAULTS_CATALOG, GITLAB_BROKEN_CI } from '../../simFixtures/cicd'

/** Mirror of the component's own extractor input: { job: {image, script} }. */
function fieldsFor(jobs) {
  const out = {}
  for (const [id, f] of Object.entries(jobs)) out[id] = { image: null, script: [], ...f }
  return out
}

const parseGitlab = (src) => parsePipeline(src, PROVIDERS.GITLAB).pipeline

describe('deriveFaults — bad image tag', () => {
  const catalog = CICD_FAULTS_CATALOG['bad-image-tag'].faults
  const pipeline = parseGitlab(GITLAB_BROKEN_CI)

  it('keeps the fault while the broken tag is still in the YAML', () => {
    // GITLAB_BROKEN_CI ships `node:18-alpinee` (note the typo) on build.
    const faults = deriveFaults(catalog, {
      pipeline,
      jobFields: fieldsFor({ build: { image: 'node:18-alpinee' } }),
    })
    expect(faults.build).toBeTruthy()
    expect(faults.build.message).toMatch(/manifest/)
  })

  it('clears the fault once the tag is corrected to a pullable image', () => {
    const faults = deriveFaults(catalog, {
      pipeline,
      jobFields: fieldsFor({ build: { image: 'node:18-alpine' } }),
    })
    expect(faults.build).toBeUndefined()
    expect(Object.keys(faults)).toHaveLength(0)
  })

  it('does not accept an arbitrary made-up tag as a fix', () => {
    const faults = deriveFaults(catalog, {
      pipeline,
      jobFields: fieldsFor({ build: { image: 'node:totally-made-up' } }),
    })
    expect(faults.build).toBeTruthy()
  })
})

describe('deriveFaults — catalog entries for absent jobs', () => {
  it('drops fault keys for jobs this pipeline does not define', () => {
    // The oom catalog keys both `test` and `unit-test`; the broken seed only
    // has `test`, so `unit-test` must not leak into the engine's fault set.
    const pipeline = parseGitlab(GITLAB_BROKEN_CI)
    const faults = deriveFaults(CICD_FAULTS_CATALOG['oom-test'].faults, {
      pipeline,
      jobFields: fieldsFor({ test: { script: ['npm test'] } }),
    })
    expect(Object.keys(faults)).toEqual(['test'])
  })
})

describe('deriveFaults — OOM in tests', () => {
  const catalog = CICD_FAULTS_CATALOG['oom-test'].faults
  const pipeline = parseGitlab(GITLAB_BROKEN_CI)

  it('keeps the fault for an unchanged test script', () => {
    const faults = deriveFaults(catalog, {
      pipeline, jobFields: fieldsFor({ test: { script: ['npm test'] } }),
    })
    expect(faults.test?.exitCode).toBe(137)
  })

  it('clears the fault when parallelism is capped', () => {
    const faults = deriveFaults(catalog, {
      pipeline, jobFields: fieldsFor({ test: { script: ['npm test -- --runInBand'] } }),
    })
    expect(faults.test).toBeUndefined()
  })
})

describe('deriveFaults — missing secret', () => {
  const catalog = CICD_FAULTS_CATALOG['missing-secret'].faults
  const pipeline = parseGitlab(GITLAB_BROKEN_CI)

  it('keeps the fault until the job references the required variable', () => {
    const faults = deriveFaults(catalog, {
      pipeline, jobFields: fieldsFor({ build: { script: ['npm ci'] } }),
    })
    expect(faults.build).toBeTruthy()
  })

  it('clears the fault once the variable is wired into the script', () => {
    const faults = deriveFaults(catalog, {
      pipeline,
      jobFields: fieldsFor({
        build: { script: ['export REGISTRY_TOKEN=$CI_REGISTRY_TOKEN', 'npm ci'] },
        // deploy still lacks KUBE_TOKEN, so its fault must survive.
        deploy: { script: ['kubectl apply -f k8s/'] },
      }),
    })
    expect(faults.build).toBeUndefined()
    expect(faults.deploy).toBeTruthy()
  })
})

describe('deriveFaults — kubeconfig/RBAC on deploy', () => {
  const catalog = CICD_FAULTS_CATALOG['kubeconfig-unauthorized'].faults

  it('keeps the fault while deploy has no upstream dependency', () => {
    const faults = deriveFaults(catalog, {
      pipeline: parseGitlab(GITLAB_BROKEN_CI), jobFields: fieldsFor({}),
    })
    expect(faults.deploy).toBeTruthy()
  })

  it('clears the fault once `needs:` is added to deploy', () => {
    const withNeeds = GITLAB_BROKEN_CI.replace(
      'deploy:\n  stage: deploy\n',
      'deploy:\n  stage: deploy\n  needs:\n    - test\n',
    )
    const pipeline = parseGitlab(withNeeds)
    // Guard the fixture edit itself — if the parser stops seeing the needs
    // edge this test would pass for the wrong reason.
    expect(pipeline.jobs.find((j) => j.id === 'deploy').needs).toContain('test')
    const faults = deriveFaults(catalog, { pipeline, jobFields: fieldsFor({}) })
    expect(faults.deploy).toBeUndefined()
  })
})

describe('deriveFaults — non-derivable faults pass through', () => {
  it('keeps flaky/approvalTimeout faults so those labs stay failable', () => {
    const pipeline = parseGitlab(GITLAB_BROKEN_CI)
    const flaky = deriveFaults(CICD_FAULTS_CATALOG['flaky-test'].faults, {
      pipeline, jobFields: fieldsFor({ test: { script: ['npm test'] } }),
    })
    expect(flaky.test?.flaky).toBe(0.4)

    const approval = deriveFaults(CICD_FAULTS_CATALOG['approval-timeout'].faults, {
      pipeline, jobFields: fieldsFor({}),
    })
    expect(approval.deploy?.approvalTimeout).toBe(true)
  })

  it('returns an empty set for a scenario with no planted fault', () => {
    expect(deriveFaults(undefined, { pipeline: parseGitlab(GITLAB_BROKEN_CI), jobFields: {} }))
      .toEqual({})
  })
})
