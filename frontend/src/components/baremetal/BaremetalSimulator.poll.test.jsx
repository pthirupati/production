// @vitest-environment jsdom
/**
 * Guards the visibility gate on the transient-machine poll (audit L1422).
 *
 * This 2s poll only arms while a machine is mid-commission/deploy AND the
 * WebSocket is down, but in that window it ran forever in a hidden tab. MAAS
 * advances commissioning server-side, so a background poll buys nothing — but
 * the resume path MUST refetch immediately, otherwise a machine that finished
 * while hidden keeps showing a stale "Commissioning" badge for up to 2s.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'

const getState = vi.fn()

vi.mock('../../api/baremetal', () => ({
  baremetalApi: {
    getState: (...a) => getState(...a),
    action: vi.fn(async () => ({ ok: true })),
  },
}))
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

let BaremetalSimulator

/** Drive document.visibilityState + dispatch the event React listens for. */
function setVisibility(value) {
  Object.defineProperty(document, 'visibilityState', {
    value, configurable: true, writable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('BaremetalSimulator transient poll visibility gate', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    setVisibility('visible')
    getState.mockReset()
    // logged_in + a machine in a TRANSIENT_STATUSES state is what arms the
    // poll. jsdom has no WebSocket constructor, so the WS effect's `new
    // WebSocket(...)` throws into its own try/catch and wsConnected stays
    // false — the same state as a real WS outage, which is the only time this
    // poll is supposed to run at all.
    getState.mockResolvedValue({
      state: {
        session: { logged_in: true, user: 'admin' },
        maas: {
          machines: [{
            id: 1, system_id: 'abc123', hostname: 'node-1', status: 'Commissioning',
          }],
          boot_resources: [],
        },
        goal: {},
      },
    })
    ;({ default: BaremetalSimulator } = await import('./BaremetalSimulator'))
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  async function mount() {
    await act(async () => {
      render(<BaremetalSimulator sessionId="s1" scenario={{ slug: 'maas-commission' }} />)
    })
  }

  // A SEPARATE ungated slow poll (line ~295) also runs while the WS is down.
  // It is out of scope for L1422, so both assertions below measure a window
  // short enough that the 8s timer cannot contribute a tick: 3 x 2s = 6s of
  // total elapsed fake time, versus 4 ticks the 2s poll would have fired.
  const WINDOW_MS = 2000 * 3

  it('stops polling while the tab is hidden', async () => {
    await mount()

    setVisibility('hidden')
    const atHide = getState.mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(WINDOW_MS) })
    expect(getState.mock.calls.length).toBe(atHide)
  })

  it('polls on an interval while the tab is visible', async () => {
    // Guards against the gate being "fixed" by disabling the poll outright,
    // which would make the hidden-tab test above pass vacuously.
    await mount()
    const afterMount = getState.mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(WINDOW_MS) })
    expect(getState.mock.calls.length).toBeGreaterThan(afterMount)
  })

  it('refetches immediately on becoming visible, not one interval later', async () => {
    await mount()
    setVisibility('hidden')
    await act(async () => { await vi.advanceTimersByTimeAsync(2000 * 3) })
    const atHide = getState.mock.calls.length

    // No timers advance here, so only the resume-refresh can move the count.
    await act(async () => { setVisibility('visible') })
    expect(getState.mock.calls.length).toBe(atHide + 1)
  })
})
