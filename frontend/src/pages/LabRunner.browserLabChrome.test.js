// @vitest-environment node
//
// Audit L445 / L450 / L453. The Coding IDE and Prompt Playground layouts return
// early from LabRunner, before the sidebar and the terminal action bar render,
// and neither header received simChromeProps. The result: no +30m and no way
// back to the scenario — Stop (which destroys the session) was the only exit.
//
// LabRunner is ~4000 lines with a very deep mount tree, so this asserts on the
// source of the two early-return blocks rather than rendering them. That is
// weaker than a render test, but it is targeted at the exact regression: a
// future edit that drops the shared controls out of either header.
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect, beforeAll } from 'vitest'

const HERE = path.dirname(fileURLToPath(import.meta.url))
let src = ''

beforeAll(async () => {
  src = await fs.readFile(path.join(HERE, 'LabRunner.jsx'), 'utf8')
})

/** Source of one early-return layout block, from its comment banner to the return. */
function layoutBlock(banner) {
  const start = src.indexOf(banner)
  expect(start, `layout banner not found: ${banner}`).toBeGreaterThan(-1)
  // Both blocks end at the next top-level layout comment or the main return.
  const rest = src.slice(start + banner.length)
  const end = rest.indexOf('\n  // ──')
  return rest.slice(0, end === -1 ? rest.indexOf('\n  return (') : end)
}

describe('browser-surface lab layouts have a full header', () => {
  it('defines the shared controls once, above both layouts', () => {
    const def = src.indexOf('const browserLabHeaderControls')
    expect(def).toBeGreaterThan(-1)
    expect(def).toBeLessThan(src.indexOf('// ── Prompt Engineering layout'))
  })

  it('renders them in the Prompt Playground header', () => {
    expect(layoutBlock('// ── Prompt Engineering layout')).toContain('{browserLabHeaderControls}')
  })

  it('renders them in the Coding IDE header', () => {
    expect(layoutBlock('// ── Coding IDE layout')).toContain('{browserLabHeaderControls}')
  })

  it('wires +30m to the real extend handler and its real disabled conditions', () => {
    const controls = src.slice(
      src.indexOf('const browserLabHeaderControls'),
      src.indexOf('// ── Prompt Engineering layout'),
    )
    expect(controls).toContain('onClick={handleExtendLab}')
    expect(controls).toContain('extensionsUsed >= 2')
  })

  it('routes Back through getLabExitPath, not a hardcoded path', () => {
    const controls = src.slice(
      src.indexOf('const browserLabHeaderControls'),
      src.indexOf('// ── Prompt Engineering layout'),
    )
    expect(controls).toMatch(/to=\{getLabExitPath\(/)
    expect(controls).not.toMatch(/to="\/(dashboard|scenarios)"/)
  })

  it('does NOT add a second grading path to either layout', () => {
    // PromptPlayground's "Complete Lesson" and CodingIDE's Run/Check already
    // grade on the backend and call onSolved. A header Check wired to
    // handleValidate would be a different grader racing the same session.
    const controls = src.slice(
      src.indexOf('const browserLabHeaderControls'),
      src.indexOf('// ── Prompt Engineering layout'),
    )
    expect(controls).not.toContain('handleValidate')
    for (const banner of ['// ── Prompt Engineering layout', '// ── Coding IDE layout']) {
      expect(layoutBlock(banner)).not.toContain('onCheck')
    }
  })

  it('does NOT offer Hints where the hints sidebar never mounts', () => {
    const controls = src.slice(
      src.indexOf('const browserLabHeaderControls'),
      src.indexOf('// ── Prompt Engineering layout'),
    )
    expect(controls).not.toContain("setSidebarTab('hints')")
  })
})

describe('Packer companion is crash-contained (L485)', () => {
  /** Source with // line comments stripped, so prose about the old code does not match. */
  const stripComments = (s) => s.replace(/^\s*\/\/.*$/gm, '')

  it('mounts through LazySimPanel, not a bare Suspense', () => {
    const start = src.indexOf('{showPackerLink && showPackerSim && (')
    expect(start).toBeGreaterThan(-1)
    const block = stripComments(src.slice(start, start + 1400))
    expect(block).toContain('<LazySimPanel')
    expect(block).not.toContain('<Suspense')
    // embedded=true would hide the Packer lab controls entirely.
    expect(block).not.toMatch(/\bembedded\b/)
    expect(block).toContain('showLabControls')
  })

  it('leaves no bare Suspense anywhere in the lab render tree', () => {
    // Every lazy console must go through LazySimPanel (Suspense + error
    // boundary). A bare <Suspense> means one crash blanks the whole lab.
    expect(stripComments(src)).not.toMatch(/<Suspense\b/)
  })
})
