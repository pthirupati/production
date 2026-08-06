// @vitest-environment jsdom
// Audit W5: both fetches were `.catch(() => null)`, so a failed replay fetch
// rendered the identical "No terminal recording available for this session"
// copy as a session that genuinely recorded nothing. A user whose lab work was
// fine could conclude it had been lost. The regression to guard is that the two
// cases stay *distinguishable* — not merely that some banner exists.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const getSessionReplay = vi.fn()
const getCommandHistory = vi.fn()
const getAiReview = vi.fn()

vi.mock('../api/labs', () => ({
  labApi: {
    getSessionReplay: (...a) => getSessionReplay(...a),
    getCommandHistory: (...a) => getCommandHistory(...a),
    getAiReview: (...a) => getAiReview(...a),
    generateAiReview: vi.fn(),
  },
}))
vi.mock('react-hot-toast', () => ({ default: { error: vi.fn(), success: vi.fn() } }))
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ sessionId: 's1' }) }
})

import SessionReplay from './SessionReplay'

const renderPage = () => render(<MemoryRouter><SessionReplay /></MemoryRouter>)

describe('SessionReplay fetch failure vs empty recording', () => {
  beforeEach(() => {
    cleanup()
    getSessionReplay.mockReset()
    getCommandHistory.mockReset()
    getAiReview.mockReset()
  })
  afterEach(() => cleanup())

  it('does not claim "no recording" when the replay fetch fails', async () => {
    getSessionReplay.mockRejectedValue(new Error('503'))
    getCommandHistory.mockResolvedValue({ commands: [], total_commands: 0 })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('replay-load-error')).toBeTruthy())
    // The dangerous copy must NOT appear — that is the whole point of the fix.
    expect(screen.queryByText('No terminal recording available for this session')).toBeNull()
    expect(screen.getByText(/your session data is safe/i)).toBeTruthy()
  })

  it('still shows the genuine empty state when the session really recorded nothing', async () => {
    // Backend answered successfully with "no recording" — that is real data.
    getSessionReplay.mockResolvedValue(null)
    getCommandHistory.mockResolvedValue({ commands: [], total_commands: 0 })
    renderPage()

    await waitFor(() =>
      expect(screen.getByText('No terminal recording available for this session')).toBeTruthy()
    )
    expect(screen.queryByTestId('replay-load-error')).toBeNull()
  })

  it('flags only the failing tab when the two calls disagree', async () => {
    getSessionReplay.mockResolvedValue({ events: [[0, 'o', 'hi']], total_duration: 1 })
    getCommandHistory.mockRejectedValue(new Error('503'))
    renderPage()

    await waitFor(() => expect(getCommandHistory).toHaveBeenCalled())
    // Replay tab is healthy, so no replay error even though a sibling failed.
    expect(screen.queryByTestId('replay-load-error')).toBeNull()
  })

  it('shows no error markers when both calls succeed', async () => {
    getSessionReplay.mockResolvedValue({ events: [[0, 'o', 'hi']], total_duration: 1 })
    getCommandHistory.mockResolvedValue({ commands: [{ command: 'ls', timestamp: Date.now() }], total_commands: 1 })
    renderPage()

    await waitFor(() => expect(getSessionReplay).toHaveBeenCalled())
    expect(screen.queryByTestId('replay-load-error')).toBeNull()
    expect(screen.queryByTestId('commands-load-error')).toBeNull()
  })
})
