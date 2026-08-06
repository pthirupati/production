// @vitest-environment jsdom
/**
 * Guards the visibility gate on the live-job poll (audit L1420).
 *
 * Backup/restore jobs are long-running, so a hidden tab can otherwise burn a
 * round-trip every second for minutes. The resume path has to refetch
 * immediately — a job very often reaches a terminal status while hidden, and
 * restarting only the timer would leave a stale "Running" badge on screen.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'

const getState = vi.fn()

vi.mock('../../api/commvault', () => ({
  commvaultApi: {
    getState: (...a) => getState(...a),
    action: vi.fn(async () => ({ ok: true })),
    login: vi.fn(async () => ({ ok: true })),
  },
  default: {
    getState: (...a) => getState(...a),
    action: vi.fn(async () => ({ ok: true })),
    login: vi.fn(async () => ({ ok: true })),
  },
}))
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

let CommvaultSimulator

/** Drive document.visibilityState + dispatch the event React listens for. */
function setVisibility(value) {
  Object.defineProperty(document, 'visibilityState', {
    value, configurable: true, writable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('CommvaultSimulator live-job poll visibility gate', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    setVisibility('visible')
    getState.mockReset()
    // logged_in + a non-terminal job is what arms the poll effect.
    getState.mockResolvedValue({
      state: {
        session: { logged_in: true },
        jobs: [{ id: 1, client: 'vm-01', operation: 'Backup', status: 'running', progress: 20 }],
        clients: [],
        summary: { commcell: 'CommCell' },
        goal: {},
        broken: {},
      },
    })
    ;({ default: CommvaultSimulator } = await import('./CommvaultSimulator'))
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  async function mount() {
    await act(async () => {
      render(<CommvaultSimulator sessionId="s1" scenario={{ slug: 'commvault-basic' }} />)
    })
  }

  it('stops polling while the tab is hidden', async () => {
    await mount()
    const afterMount = getState.mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
    expect(getState.mock.calls.length).toBeGreaterThan(afterMount)

    setVisibility('hidden')
    const atHide = getState.mock.calls.length
    // Several intervals in the background must produce zero round-trips.
    await act(async () => { await vi.advanceTimersByTimeAsync(1000 * 5) })
    expect(getState.mock.calls.length).toBe(atHide)
  })

  it('refetches immediately on becoming visible, not one interval later', async () => {
    await mount()
    setVisibility('hidden')
    await act(async () => { await vi.advanceTimersByTimeAsync(1000 * 3) })
    const atHide = getState.mock.calls.length

    // No timers advance here, so only the resume-refresh can move the count.
    await act(async () => { setVisibility('visible') })
    expect(getState.mock.calls.length).toBe(atHide + 1)
  })

  it('tears the poll down once every job reaches a terminal status', async () => {
    await mount()
    // The visibility gate must not keep the timer alive past hasLiveJob=false.
    getState.mockResolvedValue({
      state: {
        session: { logged_in: true },
        jobs: [{ id: 1, client: 'vm-01', operation: 'Backup', status: 'completed', progress: 100 }],
        clients: [],
        summary: { commcell: 'CommCell' },
        goal: {},
        broken: {},
      },
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
    const atTerminal = getState.mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(1000 * 5) })
    expect(getState.mock.calls.length).toBe(atTerminal)
  })
})
