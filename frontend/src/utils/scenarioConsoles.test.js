// @vitest-environment node
import { describe, it, expect } from 'vitest'
import {
  resolvePrimarySimFromConsoles,
  consolesInclude,
  normalizeConsoles,
  companionChipsFromConsoles,
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

  it('does not promote baremetal/maas when vyos is listed', () => {
    expect(resolvePrimarySimFromConsoles(['vyos', 'terminal', 'baremetal'])).toBeNull()
    expect(resolvePrimarySimFromConsoles(['vyos', 'maas', 'terminal'])).toBeNull()
    expect(resolvePrimarySimFromConsoles(['baremetal', 'terminal'])).toBe('baremetal')
    expect(resolvePrimarySimFromConsoles(['maas', 'terminal'])).toBe('baremetal')
  })

  it('builds companion chips including ai-infra defaults', () => {
    expect(companionChipsFromConsoles(['vyos', 'terminal', 'baremetal'])).toEqual(
      expect.arrayContaining(['vyos', 'baremetal']),
    )
    const ai = companionChipsFromConsoles(['terminal'], { techSlug: 'ai-infra' })
    expect(ai).toEqual(expect.arrayContaining(['baremetal', 'lxd', 'awx', 'datacenter']))
  })
})
