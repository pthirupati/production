import { describe, test, expect } from 'vitest'
import { applyOutput } from './cliFormat'

// Sample describe-instances-shaped payload for --query exercises.
const RES = JSON.stringify({
  Reservations: [
    { Instances: [{ InstanceId: 'i-1', InstanceType: 't2.micro', State: { Name: 'running' }, Placement: { AvailabilityZone: 'us-east-1a' }, Tags: [{ Key: 'Name', Value: 'web' }] }] },
    { Instances: [{ InstanceId: 'i-2', InstanceType: 't3.small', State: { Name: 'stopped' }, Placement: { AvailabilityZone: 'us-east-1b' }, Tags: [{ Key: 'Name', Value: 'db' }] }] },
  ],
})

const parse = (s, flags) => {
  const out = applyOutput(s, flags)
  try { return JSON.parse(out) } catch { return out }
}

describe('--query JMESPath subset', () => {
  test('single-field projection', () => {
    expect(parse(RES, { query: 'Reservations[].Instances[].InstanceId' })).toEqual(['i-1', 'i-2'])
  })

  test('multiselect-list projection -> list of lists', () => {
    expect(parse(RES, { query: 'Reservations[].Instances[].[InstanceId,InstanceType]' }))
      .toEqual([['i-1', 't2.micro'], ['i-2', 't3.small']])
  })

  test('multiselect-list with nested path element', () => {
    expect(parse(RES, { query: 'Reservations[].Instances[].[InstanceId,State.Name]' }))
      .toEqual([['i-1', 'running'], ['i-2', 'stopped']])
  })

  test('multiselect-hash projection -> list of objects', () => {
    expect(parse(RES, { query: 'Reservations[].Instances[].{Id:InstanceId,Az:Placement.AvailabilityZone}' }))
      .toEqual([{ Id: 'i-1', Az: 'us-east-1a' }, { Id: 'i-2', Az: 'us-east-1b' }])
  })

  test('filter projection still works', () => {
    expect(parse(RES, { query: "Reservations[].Instances[?State.Name==`running`][].InstanceId" }))
      .toEqual(['i-1'])
  })
})

describe('--output text', () => {
  test('flat scalar list -> one value per line', () => {
    expect(applyOutput(RES, { query: 'Reservations[].Instances[].InstanceId', output: 'text' }))
      .toBe('i-1\ni-2')
  })

  test('multiselect-list rows -> tab-joined lines', () => {
    expect(applyOutput(RES, { query: 'Reservations[].Instances[].[InstanceId,InstanceType]', output: 'text' }))
      .toBe('i-1\tt2.micro\ni-2\tt3.small')
  })
})

describe('--output table', () => {
  test('multiselect-list rows render as multi-column table', () => {
    const out = applyOutput(RES, { query: 'Reservations[].Instances[].[InstanceId,InstanceType]', output: 'table' })
    expect(out).toContain('| i-1 | t2.micro |')
    expect(out).toContain('| i-2 | t3.small |')
    // No JSON blob in a single cell.
    expect(out).not.toContain('["i-1"')
  })
})
