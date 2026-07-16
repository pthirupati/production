// @vitest-environment jsdom
/**
 * REPRODUCTION harness for BUG A: AWS labs show "Lab environment error /
 * Something went wrong loading this simulator" on load.
 *
 * This renders the REAL mount path a returning learner hits:
 *   AwsLabOverlay -> MemoryRouter -> AwsConsole -> TopNav + ConsoleHome
 * off the persisted zustand store, across three localStorage states:
 *   1. fresh (no persisted blob)
 *   2. an OLD-shape / v2 persisted blob (returning user from a prior deploy)
 *   3. garbage under the aws sim key
 *
 * We wrap the overlay in the SAME SimErrorBoundary LabRunner uses, and assert
 * the boundary's fallback text never appears. If the console throws on mount,
 * the boundary renders "Something went wrong loading this simulator" — which is
 * exactly the reported symptom — and we capture the thrown error + stack.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

// jsdom in this Node build does not wire up window.localStorage (needs the
// --localstorage-file flag). Install a minimal in-memory Storage polyfill so
// the persisted-blob scenarios below have a real store to read/write. This is
// test-harness plumbing only — the bug under test is in the app code, not here.
if (typeof globalThis.localStorage === 'undefined' || !globalThis.localStorage) {
  const mem = new Map()
  const storage = {
    getItem: (k) => (mem.has(k) ? mem.get(k) : null),
    setItem: (k, v) => { mem.set(k, String(v)) },
    removeItem: (k) => { mem.delete(k) },
    clear: () => { mem.clear() },
    key: (i) => Array.from(mem.keys())[i] ?? null,
    get length() { return mem.size },
  }
  Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true })
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'localStorage', { value: storage, configurable: true })
  }
}

import SimErrorBoundary from '../SimErrorBoundary'
import AwsLabOverlay from './AwsLabOverlay'
import { awsSimStorageKey } from './store/awsStore'

// Mock the axios client so awsSimApi never touches the network.
vi.mock('../../api/client', () => ({
  default: {
    get: () => Promise.resolve({ data: {} }),
    post: () => Promise.resolve({ data: {} }),
  },
}))

// Capture anything the boundary catches so we can print the real stack.
const caught = []
vi.spyOn(console, 'error').mockImplementation((...args) => {
  caught.push(args)
})

const KEY = awsSimStorageKey(undefined) // anon user -> 'fixitlab-aws-sim:anon'

function renderOverlay() {
  return render(
    <SimErrorBoundary
      name="aws"
      title="Lab console error"
      message="Something went wrong loading this lab console. Try resetting or reload the page."
      resetStorageKey={KEY}
    >
      <AwsLabOverlay
        embedded
        sessionId="test-session"
        scenario={{ slug: 'ec2-launch-basics', title: 'Launch an EC2 instance' }}
        onExit={() => {}}
      />
    </SimErrorBoundary>,
  )
}

function expectNoBoundaryError() {
  // The SimErrorBoundary fallback heading is "Lab console error".
  const errored = screen.queryByText('Something went wrong loading this lab console. Try resetting or reload the page.')
  if (errored) {
    // Surface the real stack that the boundary swallowed.
    console.warn('CAUGHT BY BOUNDARY:\n', caught.map((a) => a.map(String).join(' ')).join('\n'))
  }
  expect(errored, 'SimErrorBoundary fallback should NOT render (console threw on mount)').toBeNull()
  // Positive assertion: the AWS console chrome mounted (Console Home heading).
  expect(screen.getAllByText('Console Home').length).toBeGreaterThan(0)
}

describe('AwsLabOverlay mount (BUG A reproduction)', () => {
  beforeEach(() => {
    localStorage.clear()
    caught.length = 0
  })

  afterEach(() => {
    cleanup()
  })

  it('1) FRESH localStorage — mounts without hitting the error boundary', () => {
    renderOverlay()
    expectNoBoundaryError()
  })

  it('2) OLD-SHAPE / v2 persisted blob — mounts without hitting the error boundary', () => {
    // A realistic pre-v3 payload: zustand persist wrapper { state, version }.
    // Old shape: many current fields absent, some fields the WRONG type.
    const oldBlob = {
      state: {
        region: 'us-east-1',
        account: { id: '123456789012', alias: 'legacy-alias' },
        instances: [
          { id: 'i-legacy0001', region: 'us-east-1', name: 'legacy', state: 'running' },
        ],
        // v2 had these as objects/missing that v3 code reads as arrays, etc.
        s3Buckets: [{ name: 'legacy-bucket', region: 'us-east-1', objects: [] }],
        cwAlarms: [{ name: 'A', region: 'us-east-1', state: 'OK' }],
        // Chrome fields that TopNav/ConsoleHome read:
        favorites: ['ec2'],
        recentServices: ['ec2', 's3'],
        homeWidgets: ['recently-visited', 'resources', 'cost-and-usage'],
        settings: { region: 'us-east-1' },
        // genericResources present but partial (missing many services)
        genericResources: { lambda: { functions: [] } },
      },
      version: 2,
    }
    localStorage.setItem(KEY, JSON.stringify(oldBlob))
    renderOverlay()
    expectNoBoundaryError()
  })

  it('3) GARBAGE persisted blob — mounts without hitting the error boundary', () => {
    localStorage.setItem(KEY, '{"state": "not-an-object", "version": 3}')
    renderOverlay()
    expectNoBoundaryError()
  })

  it('4) GARBAGE non-JSON blob — mounts without hitting the error boundary', () => {
    localStorage.setItem(KEY, 'total-garbage-not-json{{{')
    renderOverlay()
    expectNoBoundaryError()
  })

  it('5) MALFORMED ROWS blob (arrays present but rows missing fields the render reads) — mounts without hitting the error boundary', () => {
    // Arrays pass Array.isArray in mergePersistedAws so the malformed rows flow
    // straight into the render. TopNav/ConsoleHome read row.tags, row.name, etc.
    const blob = {
      state: {
        region: 'us-east-1',
        instances: [{ id: 'i-broken' }, null, 'not-an-object'],
        s3Buckets: [{ /* no name, no objects */ }],
        cwAlarms: [{}],
        vpcs: [{ id: 'vpc-x' }],
        securityGroups: [{ id: 'sg-x' }],
        iamUsers: [{}],
        iamRoles: [{}],
        favorites: ['ec2', 'nonexistent-service'],
        recentServices: ['ec2', null, 'also-missing'],
        homeWidgets: ['recently-visited', 'resources', 'unknown-widget'],
        // genericResources with rows missing tags/name that useResourceIndex reads:
        genericResources: { lambda: { functions: [{ id: 'fn-x' }, null] } },
      },
      version: 3,
    }
    localStorage.setItem(KEY, JSON.stringify(blob))
    renderOverlay()
    expectNoBoundaryError()
  })
})
