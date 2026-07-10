import { describe, it, expect } from 'vitest'
import { usePageTitle } from './usePageTitle'

describe('usePageTitle', () => {
  it('is exported as a function', () => {
    expect(typeof usePageTitle).toBe('function')
  })
})

describe('awsSimStorageKey', () => {
  it('scopes storage by user id', async () => {
    const { awsSimStorageKey } = await import('../components/aws/store/awsStore')
    expect(awsSimStorageKey('user-1')).toBe('fixitlab-aws-sim:user-1')
    expect(awsSimStorageKey(null)).toBe('fixitlab-aws-sim:anon')
  })
})
