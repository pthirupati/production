import { describe, it, expect } from 'vitest'
import { userHasTechAccess, canOpenCompanionConsole } from './techAccess'

describe('userHasTechAccess', () => {
  it('denies empty payload', () => {
    expect(userHasTechAccess(null, 'vmware')).toBe(false)
    expect(userHasTechAccess({}, 'vmware')).toBe(false)
  })

  it('allows complimentary_access', () => {
    expect(userHasTechAccess({ complimentary_access: true, subscriptions: [] }, 'vmware')).toBe(true)
  })

  it('allows has_access subscription for matching slug', () => {
    const payload = {
      complimentary_access: false,
      subscriptions: [
        { technology: { slug: 'linux' }, has_access: true },
        { technology: { slug: 'vmware' }, has_access: true },
      ],
    }
    expect(userHasTechAccess(payload, 'vmware')).toBe(true)
    expect(userHasTechAccess(payload, 'azure')).toBe(false)
  })

  it('falls back to is_active when has_access missing', () => {
    const payload = {
      subscriptions: [{ technology: { slug: 'vmware' }, is_active: true }],
    }
    expect(userHasTechAccess(payload, 'vmware')).toBe(true)
  })

  it('respects has_access false even if is_active true', () => {
    const payload = {
      subscriptions: [{ technology: { slug: 'vmware' }, is_active: true, has_access: false }],
    }
    expect(userHasTechAccess(payload, 'vmware')).toBe(false)
  })
})

describe('canOpenCompanionConsole', () => {
  const withVmware = {
    complimentary_access: false,
    subscriptions: [{ technology: { slug: 'vmware' }, has_access: true }],
  }

  it('requires both link flag and entitlement', () => {
    expect(canOpenCompanionConsole(withVmware, true, 'vmware')).toBe(true)
    expect(canOpenCompanionConsole(withVmware, false, 'vmware')).toBe(false)
    expect(canOpenCompanionConsole({ complimentary_access: false, subscriptions: [] }, true, 'vmware')).toBe(false)
  })
})
