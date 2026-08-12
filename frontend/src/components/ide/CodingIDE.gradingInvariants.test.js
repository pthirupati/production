// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/**
 * Structural guards on the client/server grading split.
 *
 * The client-side runners (Pyodide / JS worker) exist for instant feedback only.
 * Only the backend may mark a lab solved. These assertions are deliberately
 * source-level: the rule they protect is about which code path may call
 * setSolved, which is exactly the kind of thing a refactor silently breaks.
 */
const SRC = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'CodingIDE.jsx'),
  'utf8',
)

describe('grading stays server-authoritative', () => {
  it('marks the local visible-test run as a preview', () => {
    // The advisory result must be structurally distinct from the graded one.
    expect(SRC).toMatch(/preview:\s*true/)
    expect(SRC).toMatch(/preview:\s*false/)
  })

  it('never sets solved from the local preview branch', () => {
    const previewBlock = SRC.slice(
      SRC.indexOf('let localPreview = null'),
      SRC.indexOf('const result = await labApi.codeValidate'),
    )
    expect(previewBlock.length).toBeGreaterThan(0)
    expect(previewBlock).not.toContain('setSolved')
    expect(previewBlock).not.toContain('onSolved')
  })

  it('only calls onSolved behind the server result.passed check', () => {
    const idx = SRC.indexOf('onSolved?.(')
    expect(idx).toBeGreaterThan(-1)
    // The nearest preceding condition must be the server verdict.
    const before = SRC.slice(0, idx)
    expect(before.lastIndexOf('if (result.passed)')).toBeGreaterThan(
      before.lastIndexOf('localPreview'),
    )
  })

  it('routes Check Solution through the backend, not a local runner', () => {
    expect(SRC).toContain('labApi.codeValidate')
  })
})

describe('offline runtime is surfaced explicitly', () => {
  it('consumes the runtimeMissing flag the runner produces', () => {
    // Regression: pyodideRunner set runtimeMissing but nothing read it, so an
    // air-gapped learner only saw a generic stderr line.
    expect(SRC).toContain('setRuntimeMissing')
    expect(SRC).toMatch(/runtimeMissing &&/)
  })

  it('tells the learner server grading still works while offline', () => {
    expect(SRC).toMatch(/Check Solution still works/)
  })
})
