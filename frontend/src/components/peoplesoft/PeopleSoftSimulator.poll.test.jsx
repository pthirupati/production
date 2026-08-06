// @vitest-environment jsdom
/**
 * Guards the visibility gate on the Process Monitor poll (audit L1423).
 *
 * The poll is what advances queued -> running -> success, so the two things
 * that matter are: (1) it stops entirely while the tab is hidden, and (2) it
 * fires an IMMEDIATE refetch on becoming visible rather than only restarting
 * the timer — otherwise a job that finished while hidden renders stale.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'

const getState = vi.fn()

vi.mock('../../api/peoplesoft', () => ({
  peoplesoftApi: {
    getState: (...a) => getState(...a),
    action: vi.fn(async () => ({ ok: true })),
  },
}))
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

let PeopleSoftSimulator

/** Drive document.visibilityState + dispatch the event React listens for. */
function setVisibility(value) {
  Object.defineProperty(document, 'visibilityState', {
    value, configurable: true, writable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('PeopleSoftSimulator process-monitor poll visibility gate', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    setVisibility('visible')
    getState.mockReset()
    // One queued run keeps the poll effect armed for the whole test.
    getState.mockResolvedValue({
      inventory: { session: { logged_in: true, oprid: 'PS' } },
      summary: { process_runs_running: 1, current_oprid: 'PS' },
      goal: {},
    })
    ;({ default: PeopleSoftSimulator } = await import('./PeopleSoftSimulator'))
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  async function mount() {
    await act(async () => {
      render(<PeopleSoftSimulator sessionId="s1" scenario={{ slug: 'peoplesoft-basic' }} />)
    })
  }

  it('stops polling while the tab is hidden', async () => {
    await mount()
    const afterMount = getState.mock.calls.length

    // Visible: the 3.5s timer fires.
    await act(async () => { await vi.advanceTimersByTimeAsync(3600) })
    const whileVisible = getState.mock.calls.length
    expect(whileVisible).toBeGreaterThan(afterMount)

    setVisibility('hidden')
    const atHide = getState.mock.calls.length
    // Three full intervals in the background must produce zero round-trips.
    await act(async () => { await vi.advanceTimersByTimeAsync(3500 * 3) })
    expect(getState.mock.calls.length).toBe(atHide)
  })

  it('refetches immediately on becoming visible, not one interval later', async () => {
    await mount()
    setVisibility('hidden')
    await act(async () => { await vi.advanceTimersByTimeAsync(3500 * 2) })
    const atHide = getState.mock.calls.length

    // Zero elapsed time between visible and the assertion: the only way the
    // count can move is the resume-refresh, not the restarted interval.
    await act(async () => { setVisibility('visible') })
    expect(getState.mock.calls.length).toBe(atHide + 1)
  })
})
