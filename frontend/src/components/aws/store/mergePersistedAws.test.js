import { describe, it, expect } from 'vitest'
import { mergePersistedAws } from './awsStore'

describe('mergePersistedAws chrome + corrupt rows', () => {
  it('keeps string chrome arrays (favorites / recentServices / homeWidgets)', () => {
    const current = {}
    const persisted = {
      favorites: ['ec2', 's3'],
      recentServices: ['iam', 'vpc'],
      homeWidgets: ['recently-visited', 'resources'],
      instances: [{ id: 'i-1', region: 'us-east-1', state: 'running' }],
    }
    const merged = mergePersistedAws(persisted, current)
    expect(merged.favorites).toEqual(['ec2', 's3'])
    expect(merged.recentServices).toEqual(['iam', 'vpc'])
    expect(merged.homeWidgets).toEqual(['recently-visited', 'resources'])
    expect(merged.instances).toEqual([{ id: 'i-1', region: 'us-east-1', state: 'running' }])
  })

  it('drops null/non-string chrome entries without wiping the list', () => {
    const merged = mergePersistedAws({
      favorites: ['ec2', null, 12, ''],
      recentServices: ['s3', undefined],
      homeWidgets: ['welcome'],
    }, {})
    expect(merged.favorites).toEqual(['ec2'])
    expect(merged.recentServices).toEqual(['s3'])
    expect(merged.homeWidgets).toEqual(['welcome'])
  })

  it('drops null/non-object resource rows', () => {
    const merged = mergePersistedAws({
      instances: [{ id: 'i-ok' }, null, 'bad'],
      cwAlarms: [null, { name: 'A' }],
    }, {})
    expect(merged.instances).toEqual([{ id: 'i-ok' }])
    expect(merged.cwAlarms).toEqual([{ name: 'A' }])
  })

  it('filters nested genericResources arrays', () => {
    const merged = mergePersistedAws({
      genericResources: {
        lambda: { functions: [{ id: 'fn-1' }, null, 'x'] },
      },
    }, {})
    expect(merged.genericResources.lambda.functions).toEqual([{ id: 'fn-1' }])
  })
})
