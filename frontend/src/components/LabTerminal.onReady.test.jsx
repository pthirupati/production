// @vitest-environment jsdom
//
// Regression test for the stale-closure risk flagged in
// docs/AUDIT_2026_08_TODO.md:1413 ("LabTerminal.jsx:598 missing `onReady` dep").
//
// The init effect is deliberately NOT keyed on `onReady`: every caller passes an
// inline arrow (LabRunner.jsx:3522/3544/3573, TerraformWorkspaceIde.jsx:336,
// PackerWorkspaceIde.jsx:453), so adding it to the dep array would tear down and
// remount xterm + the WebSocket on every parent render and drop the user's
// shell. The fix is the file's existing always-fresh-prop ref idiom, which this
// test pins: the effect must survive a re-render AND readiness must invoke the
// LATEST arrow, not the one captured when the effect first ran.
//
// Without onReadyRef this test fails on the second assertion — the terminal
// reports ready for the host that was active at mount time, so a queued command
// flushes into the wrong pane.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { createRef } from 'react'

// xterm is a heavy dynamic import with real canvas/DOM measurement; stub it down
// to the surface the init effect actually touches.
const termInstances = []
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    constructor(opts) {
      this.options = opts || {}
      this.cols = 80
      this.rows = 24
      this.loadAddon = vi.fn()
      this.open = vi.fn()
      this.write = vi.fn()
      this.writeln = vi.fn()
      this.focus = vi.fn()
      this.dispose = vi.fn()
      this.onData = vi.fn()
      this.onResize = vi.fn()
      this.attachCustomKeyEventHandler = vi.fn()
      termInstances.push(this)
    }
  },
}))
vi.mock('@xterm/addon-fit', () => ({
  FitAddon: class { fit = vi.fn(); activate = vi.fn(); dispose = vi.fn() },
}))
vi.mock('@xterm/addon-web-links', () => ({
  WebLinksAddon: class { activate = vi.fn(); dispose = vi.fn() },
}))
vi.mock('@xterm/xterm/css/xterm.css', () => ({ default: {} }))

vi.mock('../store/authStore', () => ({
  useAuthStore: Object.assign(
    (selector) => selector({ accessToken: 'test-token', user: { id: 1 } }),
    { getState: () => ({ accessToken: 'test-token', user: { id: 1 } }) },
  ),
}))

const sockets = []
class MockWebSocket {
  static OPEN = 1
  constructor(url) {
    this.url = url
    this.readyState = 1
    this.send = vi.fn()
    this.close = vi.fn()
    sockets.push(this)
  }
}

let LabTerminal

beforeEach(async () => {
  termInstances.length = 0
  sockets.length = 0
  vi.stubGlobal('WebSocket', MockWebSocket)
  if (!globalThis.ResizeObserver) {
    vi.stubGlobal('ResizeObserver', class {
      observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn()
    })
  }
  ;({ default: LabTerminal } = await import('./LabTerminal'))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const RUNNING_SIM_SESSION = {
  status: 'RUNNING',
  provider: 'simulation',
  container_id: null,
  instance_id: null,
}

/** Drive the mocked socket to the point where the component fires readiness. */
async function driveToReady() {
  await waitFor(() => expect(sockets.length).toBeGreaterThan(0))
  const ws = sockets[0]
  await waitFor(() => expect(typeof ws.onopen).toBe('function'))
  ws.onopen()
  ws.onmessage({ data: JSON.stringify({ type: 'shell_ready' }) })
}

describe('LabTerminal onReady freshness', () => {
  it('invokes the latest onReady prop, not the one captured at effect init', async () => {
    const first = vi.fn()
    const second = vi.fn()
    const ref = createRef()

    const { rerender } = render(
      <LabTerminal
        ref={ref}
        sessionId="sess-1"
        session={RUNNING_SIM_SESSION}
        hostKey="primary"
        onReady={first}
      />,
    )

    // Let the async init() land (dynamic imports + socket construction) BEFORE
    // swapping the prop, so the effect has genuinely closed over `first`.
    await waitFor(() => expect(sockets.length).toBeGreaterThan(0))

    // Same session identity => the init effect must NOT re-run. Only the arrow
    // changes, exactly as it does when a parent re-renders with a new inline fn.
    rerender(
      <LabTerminal
        ref={ref}
        sessionId="sess-1"
        session={RUNNING_SIM_SESSION}
        hostKey="primary"
        onReady={second}
      />,
    )

    // The terminal must not have been torn down and rebuilt by the re-render:
    // one xterm, one socket. This is the half that would break if `onReady`
    // were naively added to the dep array.
    expect(termInstances).toHaveLength(1)
    expect(sockets).toHaveLength(1)

    await driveToReady()

    // The half that breaks without the ref: readiness went to the stale arrow.
    await waitFor(() => expect(second).toHaveBeenCalledTimes(1))
    expect(first).not.toHaveBeenCalled()
  })

  it('fires readiness only once even if shell_ready repeats', async () => {
    const onReady = vi.fn()
    render(
      <LabTerminal
        sessionId="sess-2"
        session={RUNNING_SIM_SESSION}
        hostKey="primary"
        onReady={onReady}
      />,
    )

    await driveToReady()
    sockets[0].onmessage({ data: JSON.stringify({ type: 'shell_ready' }) })

    await waitFor(() => expect(onReady).toHaveBeenCalledTimes(1))
  })
})
