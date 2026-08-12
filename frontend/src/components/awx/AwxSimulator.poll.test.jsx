// @vitest-environment jsdom
/**
 * Guards the visibility gate on the live-job poll (audit L1419).
 *
 * At 1.2s this is the most aggressive poll in the simulator set, so the
 * background tab must go fully quiet. The resume path has to refetch
 * immediately — a job can hit a terminal status while hidden, and restarting
 * only the timer would leave a stale "running" badge on screen for 1.2s.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'

const getState = vi.fn()

vi.mock('../../api/awx', () => ({
  awxApi: {
    getState: (...a) => getState(...a),
    action: vi.fn(async () => ({ ok: true })),
  },
}))
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

let AwxSimulator

/** Drive document.visibilityState + dispatch the event React listens for. */
function setVisibility(value) {
  Object.defineProperty(document, 'visibilityState', {
    value, configurable: true, writable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('AwxSimulator live-job poll visibility gate', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    setVisibility('visible')
    getState.mockReset()
    // logged_in + a non-terminal job is what arms the poll effect.
    getState.mockResolvedValue({
      inventory: {
        session: { logged_in: true },
        jobs: [{ id: 1, name: 'deploy', status: 'running', stdout: '' }],
        summary: { organization: 'Default' },
      },
      goal: {},
    })
    ;({ default: AwxSimulator } = await import('./AwxSimulator'))
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  async function mount() {
    await act(async () => {
      render(<AwxSimulator sessionId="s1" scenario={{ slug: 'awx-basic' }} />)
    })
  }

  it('stops polling while the tab is hidden', async () => {
    await mount()
    const afterMount = getState.mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(1300) })
    expect(getState.mock.calls.length).toBeGreaterThan(afterMount)

    setVisibility('hidden')
    const atHide = getState.mock.calls.length
    // Several intervals in the background must produce zero round-trips.
    await act(async () => { await vi.advanceTimersByTimeAsync(1200 * 5) })
    expect(getState.mock.calls.length).toBe(atHide)
  })

  it('refetches immediately on becoming visible, not one interval later', async () => {
    await mount()
    setVisibility('hidden')
    await act(async () => { await vi.advanceTimersByTimeAsync(1200 * 3) })
    const atHide = getState.mock.calls.length

    // No timers advance here, so only the resume-refresh can move the count.
    await act(async () => { setVisibility('visible') })
    expect(getState.mock.calls.length).toBe(atHide + 1)
  })
})
