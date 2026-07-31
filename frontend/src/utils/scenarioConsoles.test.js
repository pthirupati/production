// @vitest-environment node
import { describe, it, expect } from 'vitest'
import {
  resolvePrimarySimFromConsoles,
  consolesInclude,
  normalizeConsoles,
} from './scenarioConsoles'

describe('scenarioConsoles', () => {
  it('returns null for empty consoles so heuristics stay in control', () => {
    expect(resolvePrimarySimFromConsoles([])).toBeNull()
    expect(resolvePrimarySimFromConsoles(null)).toBeNull()
    expect(resolvePrimarySimFromConsoles(undefined)).toBeNull()
  })

  it('picks the first primary console, skipping terminal/bmc/vmware', () => {
    expect(resolvePrimarySimFromConsoles(['terminal', 'soc'])).toBe('soc')
    expect(resolvePrimarySimFromConsoles(['azure', 'terminal'])).toBe('azure')
    expect(resolvePrimarySimFromConsoles(['datacenter', 'terminal', 'bmc'])).toBe('datacenter')
    expect(resolvePrimarySimFromConsoles(['vmware', 'terminal'])).toBeNull()
    expect(resolvePrimarySimFromConsoles(['commvault', 'vmware', 'terminal'])).toBe('commvault')
  })

  it('detects companion console membership', () => {
    expect(consolesInclude(['commvault', 'vmware', 'terminal'], 'vmware')).toBe(true)
    expect(consolesInclude(['azure', 'terminal'], 'vmware')).toBe(false)
    expect(normalizeConsoles([' Azure ', 'TERMINAL'])).toEqual(['azure', 'terminal'])
  })
})
