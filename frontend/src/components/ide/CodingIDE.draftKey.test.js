// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest'

// jsdom 29 only exposes localStorage when node is started with
// --localstorage-file, so stand up a minimal in-memory store. vi.hoisted runs
// before the ESM imports below, which matters because zustand's persist
// middleware captures the storage object at module-evaluation time.
vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => store.clear(),
  }
})

// CodingIDE pulls in CodeMirror/Pyodide-adjacent modules; we only exercise the
// pure draft-key helpers, so stub the heavy leaves that touch browser APIs.
vi.mock('../../utils/ide/pyodideRunner', () => ({ runPython: vi.fn(), runPythonTests: vi.fn() }))
vi.mock('../../utils/ide/jsRunner', () => ({ runJavaScript: vi.fn(), runJavaScriptTests: vi.fn() }))
vi.mock('../../api/labs', () => ({ labApi: {} }))

import { draftKey, DRAFT_TTL_MS } from './CodingIDE'
import { useAuthStore } from '../../store/authStore'

describe('IDE draft storage key', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ user: null, isAuthenticated: false })
  })

  it('scopes the draft key to the logged-in user', () => {
    useAuthStore.setState({ user: { id: 7 }, isAuthenticated: true })
    const a = draftKey('sess-1')

    useAuthStore.setState({ user: { id: 9 }, isAuthenticated: true })
    const b = draftKey('sess-1')

    // Same lab session, two accounts on one browser => two distinct buckets.
    expect(a).not.toBe(b)
    expect(a).toContain('7')
    expect(b).toContain('9')
  })

  it('falls back to an anon bucket when logged out', () => {
    expect(draftKey('sess-1')).toBe('fixitlab:ide-draft:sess-1:anon')
  })

  it('keeps the session id so two labs never share a draft', () => {
    useAuthStore.setState({ user: { id: 7 }, isAuthenticated: true })
    expect(draftKey('sess-1')).not.toBe(draftKey('sess-2'))
  })

  it('uses a TTL generous enough to survive a long break', () => {
    // Guards against someone "tidying" this down to a few days and silently
    // deleting a learner's in-progress code.
    expect(DRAFT_TTL_MS).toBeGreaterThanOrEqual(30 * 24 * 60 * 60 * 1000)
  })
})
