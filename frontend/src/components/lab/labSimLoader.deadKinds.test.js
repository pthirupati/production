// @vitest-environment node
//
// Audit L493. PRIMARY_SIM_COMPONENTS had 25 keys but only ~22 were reachable:
// `kubernetes` and `openshift` were aliases for a kind nothing ever emits.
// This suite pins BOTH directions so the map and the two things that index into
// it cannot drift apart again:
//
//   1. every kind CONSOLE_TO_KIND can emit has a component  (drift → blank lab)
//   2. every key in the map is emitted by something         (drift → dead code)
//
// Direction 1 is the load-bearing one. The audit item originally proposed
// deleting `datadashboard` and `agent` as well; they are NOT dead (LabRunner
// sets isDataDashboardLab / isAgentLab from simulation_type and slug prefixes),
// and deleting them would have blanked the primary pane for those scenarios.
// That is exactly the failure this test exists to catch.
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { PRIMARY_SIM_COMPONENTS } from './labSimLoader'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '../..')

/**
 * Kinds LabRunner's primarySimKind ternary chain can produce. Read from source
 * rather than hardcoded so adding a branch to the chain without adding a
 * component fails here instead of at runtime.
 */
async function kindsFromLabRunner() {
  const src = await fs.readFile(path.join(SRC, 'pages/LabRunner.jsx'), 'utf8')
  const start = src.indexOf('const primarySimKind =')
  expect(start).toBeGreaterThan(-1)
  const chain = src.slice(start, src.indexOf('\n  const solved =', start))
  return new Set([...chain.matchAll(/\?\s*'([a-z0-9]+)'/g)].map((m) => m[1]))
}

/** Kinds scenarioConsoles CONSOLE_TO_KIND maps YAML console keys onto. */
async function kindsFromConsoleMap() {
  const src = await fs.readFile(path.join(SRC, 'utils/scenarioConsoles.js'), 'utf8')
  const start = src.indexOf('const CONSOLE_TO_KIND = {')
  expect(start).toBeGreaterThan(-1)
  const body = src.slice(start, src.indexOf('\n}', start))
  return new Set([...body.matchAll(/:\s*'([a-z0-9-]+)'/g)].map((m) => m[1]))
}

describe('PRIMARY_SIM_COMPONENTS reachability', () => {
  it('has a component for every kind LabRunner can select', async () => {
    const kinds = await kindsFromLabRunner()
    expect(kinds.size).toBeGreaterThan(15) // sanity: the regex actually matched
    for (const kind of kinds) {
      expect(PRIMARY_SIM_COMPONENTS[kind], `no component for kind '${kind}'`).toBeTruthy()
    }
  })

  it('has a component for every kind a YAML consoles: list can resolve to', async () => {
    const kinds = await kindsFromConsoleMap()
    expect(kinds.size).toBeGreaterThan(15)
    for (const kind of kinds) {
      expect(PRIMARY_SIM_COMPONENTS[kind], `no component for console kind '${kind}'`).toBeTruthy()
    }
  })

  it('carries no keys that nothing can emit', async () => {
    const reachable = new Set([
      ...(await kindsFromLabRunner()),
      ...(await kindsFromConsoleMap()),
      // Companion-only overlay; LabRunner mounts it directly, not via primarySimKind.
      'lxd',
    ])
    const dead = Object.keys(PRIMARY_SIM_COMPONENTS).filter((k) => !reachable.has(k))
    expect(dead).toEqual([])
  })

  it('keeps datadashboard and agent — few scenarios is not dead', () => {
    // Guards against re-litigating the audit's incorrect half.
    expect(PRIMARY_SIM_COMPONENTS.datadashboard).toBeTruthy()
    expect(PRIMARY_SIM_COMPONENTS.agent).toBeTruthy()
  })
})
