// @vitest-environment jsdom
/**
 * Guards the visibility gate on the VyOS dashboard poll (audit L1421).
 *
 * The 2s poll is a getState round-trip plus a re-render of every panel, so a
 * hidden tab must go fully quiet. The resume path has to refetch immediately:
 * refresh() is the only writer of `dash`, so restarting just the timer would
 * leave a returning learner looking at stale config for a further 2s.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'

const getState = vi.fn()

vi.mock('../../api/vyos', () => ({
  vyosApi: {
    getState: (...a) => getState(...a),
    applyCli: vi.fn(async () => ({ output: '' })),
  },
}))

let VyosConsole

/** Drive document.visibilityState + dispatch the event React listens for. */
function setVisibility(value) {
  Object.defineProperty(document, 'visibilityState', {
    value, configurable: true, writable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('VyosConsole dashboard poll visibility gate', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    // jsdom ships no scrollIntoView; the CLI log auto-scroll effect calls it on
    // every mount and would throw before the poll assertions ever run.
    Element.prototype.scrollIntoView = vi.fn()
    setVisibility('visible')
    getState.mockReset()
    getState.mockResolvedValue({
      dashboard: {
        interfaces: [{ name: 'eth0', address: '10.0.0.1/24', state: 'up' }],
        routes: [],
        bgp: [],
        ospf: {},
        firewall: { rules: [], counters: {} },
        nat: {},
        vrrp: {},
        dhcp_leases: [],
        revisions: {},
        uncommitted: false,
        diff: '',
        configure_mode: false,
        edit_path: [],
      },
    })
    ;({ default: VyosConsole } = await import('./VyosConsole'))
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  async function mount() {
    await act(async () => {
      render(<VyosConsole sessionId="s1" scenario={{ slug: 'vyos-bgp' }} />)
    })
  }

  it('stops polling while the tab is hidden', async () => {
    await mount()
    const afterMount = getState.mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(getState.mock.calls.length).toBeGreaterThan(afterMount)

    setVisibility('hidden')
    const atHide = getState.mock.calls.length
    // Several intervals in the background must produce zero round-trips.
    await act(async () => { await vi.advanceTimersByTimeAsync(2000 * 5) })
    expect(getState.mock.calls.length).toBe(atHide)
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

  it('resumes the interval after becoming visible again', async () => {
    await mount()
    setVisibility('hidden')
    await act(async () => { await vi.advanceTimersByTimeAsync(2000 * 2) })
    await act(async () => { setVisibility('visible') })
    const atResume = getState.mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(getState.mock.calls.length).toBeGreaterThan(atResume)
  })
})
