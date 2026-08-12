/**
 * Audit L1407 — the six heavy simulators must not feed `|| {}` / `|| []`
 * literals into memo dep arrays.
 *
 * The companion suite (monitoring/grafanaAlertingMemo.test.js) proves the rule
 * with a real `useMemo` recompute count. This one binds the rule to the actual
 * files, because the rule holding in the abstract does not stop someone
 * reintroducing a bare literal here. vitest cannot mount these consoles (each
 * pulls a session hook, a ~1MB 3D chunk or a live poll), so the source-level
 * contract is the honest alternative to not testing it at all — the same
 * technique datacenter3dParity.test.js already uses for the Twin3DSafe wiring.
 */
import { describe, expect, it } from 'vitest'
import { promises as fs } from 'fs'

const read = (rel) => fs.readFile(new URL(`../${rel}`, import.meta.url), 'utf8')

// Each entry names the file and an anchor line that opens the state block whose
// values feed that component's memos. Only that block is checked: a `|| []` in
// an unrelated helper or leaf child is harmless (nothing memoizes on it), and
// asserting over the whole file would be scope creep the audit item never asked
// for. `end` is the first memo/JSX line after the block.
const TARGETS = [
  { file: 'lxd/LxdConsole.jsx', from: 'const st = state?.state', to: 'const user =' },
  { file: 'datacenter/DatacenterSimulator.jsx', from: 'const st = state?.state', to: 'const currentRoomId' },
  { file: 'azure/AzureConsole.jsx', from: 'const st = state?.state', to: 'const chromeProps' },
  { file: 'gcp/GcpConsole.jsx', from: 'const st = state?.state', to: 'const chromeProps' },
  { file: 'monitoring/GrafanaAlertingPanel.jsx', from: 'const rules = Array.isArray', to: '// firing rules drive' },
  { file: 'aiml/AgentWorkflowSimulator.jsx', from: 'const graph = state?.graph', to: 'const validationPassed' },
  { file: 'baremetal/MaasNavPages.jsx', from: 'const fabrics = state?.maas', to: 'const tree = useMemo' },
]

const stateBlock = (src, from, to) => {
  const start = src.indexOf(from)
  const end = src.indexOf(to, start)
  expect(start, `anchor "${from}" moved`).toBeGreaterThan(-1)
  expect(end, `anchor "${to}" moved`).toBeGreaterThan(start)
  return src.slice(start, end)
}

describe('L1407 — hoisted empty fallbacks', () => {
  it.each(TARGETS.map((t) => t.file))('%s declares frozen EMPTY constants', async (file) => {
    const src = await read(file)
    expect(src).toMatch(/const EMPTY_(OBJ|ARR) = Object\.freeze\(/)
  })

  it.each(TARGETS)('$file binds no bare `|| {}` / `|| []` in its state block', async ({ file, from, to }) => {
    const src = await read(file)
    const offenders = stateBlock(src, from, to)
      .split('\n')
      .filter((line) => /\|\|\s*(\{\}|\[\])\s*$/.test(line) || /\?\s*[^:]+\s*:\s*(\{\}|\[\])\s*$/.test(line))
      .map((line) => line.trim())
    expect(offenders).toEqual([])
  })
})
