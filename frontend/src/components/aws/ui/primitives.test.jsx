import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

// jsdom 29 only exposes localStorage when node is started with
// --localstorage-file, so stand one up before the ESM imports below. Mirrors
// the shim in utils/userScopedStorage.test.js.
vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => store.clear(),
  }
})

import { DataTable, readColumnPrefs, COLUMN_PREFS_VERSION } from './primitives'
import { useAuthStore } from '../../../store/authStore'

const COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'state', label: 'State' },
  { key: 'zone', label: 'Zone' },
]
const ROWS = [{ id: 'i-1', name: 'web', state: 'running', zone: 'us-east-1a' }]
const TABLE_ID = 'instances'

const prefKey = (uid) => `aws-sim-table-columns:${TABLE_ID}:${uid}`

function renderTable() {
  return render(
    <DataTable columns={COLUMNS} rows={ROWS} getRowKey={(r) => r.id} tableId={TABLE_ID} />,
  )
}

const headerTexts = () =>
  screen.getAllByRole('columnheader').map((th) => th.textContent.replace(/[▲▼\s]+$/, ''))

describe('DataTable column preferences', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ user: { id: 7 }, isAuthenticated: true })
  })
  afterEach(cleanup)

  // The bug this file was written for. The restore-time reader and the
  // reconcile effect disagreed: the effect appended every column missing from
  // the saved list, so a user who hid "state" got it forced back on the next
  // mount. Hiding a column has to survive a reload or the picker is decorative.
  it('keeps a hidden column hidden across a remount', () => {
    // Shaped like a real write: `known` lists every column that existed when
    // the user hid "state", which is what marks it hidden-not-new.
    localStorage.setItem(
      prefKey(7),
      JSON.stringify({
        v: COLUMN_PREFS_VERSION,
        keys: ['name', 'zone'],
        known: ['name', 'state', 'zone'],
      }),
    )

    renderTable()

    expect(headerTexts()).toEqual(['Name', 'Zone'])
  })

  // Round-trip through the component's own writer rather than a hand-built
  // fixture, so the persisted shape and the reader cannot drift apart.
  it('persists a version-stamped payload the reader accepts', () => {
    renderTable()

    const written = JSON.parse(localStorage.getItem(prefKey(7)))
    expect(written.v).toBe(COLUMN_PREFS_VERSION)
    expect(readColumnPrefs(JSON.stringify(written), ['name', 'state', 'zone']))
      .toEqual({ visible: ['name', 'state', 'zone'], known: ['name', 'state', 'zone'] })
  })

  // Column prefs are user-scoped, so a second account on a shared browser must
  // not inherit the first account's hidden columns.
  it('does not leak one user\'s hidden columns to another', () => {
    localStorage.setItem(
      prefKey(7),
      JSON.stringify({
        v: COLUMN_PREFS_VERSION,
        keys: ['name'],
        known: ['name', 'state', 'zone'],
      }),
    )
    useAuthStore.setState({ user: { id: 8 }, isAuthenticated: true })

    renderTable()

    expect(headerTexts()).toEqual(['Name', 'State', 'Zone'])
  })

  it('adds a genuinely new column without resurrecting hidden ones', () => {
    // Saved before "zone" existed: unknown keys are additive, known-hidden
    // keys stay hidden.
    localStorage.setItem(
      prefKey(7),
      JSON.stringify({ v: COLUMN_PREFS_VERSION, keys: ['name'], known: ['name', 'state'] }),
    )

    renderTable()

    expect(headerTexts()).toEqual(['Name', 'Zone'])
  })
})

describe('readColumnPrefs', () => {
  const keys = ['name', 'state', 'zone']

  it('ignores a payload from a future schema version', () => {
    expect(readColumnPrefs(JSON.stringify({ v: COLUMN_PREFS_VERSION + 1, keys: ['name'] }), keys))
      .toBeNull()
  })

  it('ignores unversioned legacy payloads rather than trusting their shape', () => {
    // The pre-versioning format was a bare array. It carried no record of which
    // columns existed when it was written, so it cannot be reconciled without
    // guessing — dropping it costs one re-hide and is self-correcting.
    expect(readColumnPrefs(JSON.stringify(['name']), keys)).toBeNull()
  })

  it.each([
    ['malformed json', '{not json'],
    ['null', 'null'],
    ['a bare string', '"name"'],
    ['non-string elements', JSON.stringify({ v: COLUMN_PREFS_VERSION, keys: [{}, 3] })],
    ['keys that match no column', JSON.stringify({ v: COLUMN_PREFS_VERSION, keys: ['gone'] })],
    ['an empty key list', JSON.stringify({ v: COLUMN_PREFS_VERSION, keys: [] })],
  ])('falls back to all columns for %s', (_label, raw) => {
    expect(readColumnPrefs(raw, keys)).toBeNull()
  })

  it('drops keys for columns that no longer exist', () => {
    expect(readColumnPrefs(
      JSON.stringify({ v: COLUMN_PREFS_VERSION, keys: ['name', 'retired'] }),
      keys,
    )).toEqual({ visible: ['name'], known: ['name'] })
  })
})
