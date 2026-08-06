// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest'

// jsdom 29 only exposes localStorage when node is started with
// --localstorage-file. vi.hoisted runs before the ESM imports below, which
// matters because zustand's persist middleware captures the storage object at
// module-evaluation time.
vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => store.clear(),
  }
})

import { userScopedKey, currentUserScopedKey, migrateUnscopedKey } from './userScopedStorage'
import { useAuthStore } from '../store/authStore'

const BASE = 'fixitlab_changelog_dismissed'

describe('userScopedKey', () => {
  it('buckets by user id and falls back to anon', () => {
    expect(userScopedKey('k', 42)).toBe('k:42')
    expect(userScopedKey('k', null)).toBe('k:anon')
    expect(userScopedKey('k', '')).toBe('k:anon')
  })
})

describe('currentUserScopedKey', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ user: null, isAuthenticated: false })
  })

  it('tracks the logged-in user rather than binding once at import', () => {
    useAuthStore.setState({ user: { id: 1 }, isAuthenticated: true })
    expect(currentUserScopedKey(BASE)).toBe(`${BASE}:1`)

    // A later login on the same page must not keep writing to user 1's bucket.
    useAuthStore.setState({ user: { id: 2 }, isAuthenticated: true })
    expect(currentUserScopedKey(BASE)).toBe(`${BASE}:2`)
  })
})

describe('migrateUnscopedKey', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ user: null, isAuthenticated: false })
  })

  it('adopts a pre-scoping value so existing dismissals survive deploy', () => {
    localStorage.setItem(BASE, 'v1.2.3')
    useAuthStore.setState({ user: { id: 1 }, isAuthenticated: true })

    const key = migrateUnscopedKey(BASE)

    expect(key).toBe(`${BASE}:1`)
    expect(localStorage.getItem(key)).toBe('v1.2.3')
  })

  it('does not leak the migrated value to a second account on the same browser', () => {
    localStorage.setItem(BASE, 'v1.2.3')
    useAuthStore.setState({ user: { id: 1 }, isAuthenticated: true })
    migrateUnscopedKey(BASE)

    // User 2 signs in on the shared browser: the legacy key is gone, so they
    // get a clean slate instead of inheriting user 1's dismissal.
    useAuthStore.setState({ user: { id: 2 }, isAuthenticated: true })
    const key2 = migrateUnscopedKey(BASE)

    expect(localStorage.getItem(BASE)).toBeNull()
    expect(localStorage.getItem(key2)).toBeNull()
  })

  it('never clobbers a value already written under the scoped key', () => {
    useAuthStore.setState({ user: { id: 1 }, isAuthenticated: true })
    localStorage.setItem(`${BASE}:1`, 'current')
    localStorage.setItem(BASE, 'stale-legacy')

    const key = migrateUnscopedKey(BASE)

    expect(localStorage.getItem(key)).toBe('current')
    expect(localStorage.getItem(BASE)).toBeNull()
  })
})
