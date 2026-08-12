// @vitest-environment jsdom
// Audit W5: `orgApi.getAnalytics(slug).catch(() => null)` fed a block rendered
// under `{analytics && ...}`, so a failed analytics call made the entire team
// overview vanish with no explanation. It also backstops `pending_invites`
// (Team.jsx:302), so the silent failure could under-report outstanding invites.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const list = vi.fn()
const get = vi.fn()
const getAnalytics = vi.fn()

vi.mock('../api/org', () => ({
  orgApi: {
    list: (...a) => list(...a),
    get: (...a) => get(...a),
    getAnalytics: (...a) => getAnalytics(...a),
  },
}))
vi.mock('../api/subscriptions', () => ({ subscriptionApi: {} }))
vi.mock('../api/client', () => ({ default: { post: vi.fn(), get: vi.fn() } }))
vi.mock('react-hot-toast', () => ({ default: { error: vi.fn(), success: vi.fn() } }))
vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({ confirm: vi.fn(), ConfirmPortal: () => null }),
}))

import Team from './Team'

const ORG = { slug: 'acme', name: 'Acme', role: 'owner', seat_limit: 10, technologies: [] }

const renderTeam = () => render(<MemoryRouter><Team /></MemoryRouter>)

// Reach loadOrg the way a user does: click the org row in the sidebar list.
const selectOrg = async () => {
  await waitFor(() => expect(screen.getAllByText('Acme').length).toBeGreaterThan(0))
  fireEvent.click(screen.getAllByText('Acme')[0])
}

describe('Team analytics fetch failure', () => {
  beforeEach(() => {
    cleanup()
    list.mockReset().mockResolvedValue({ organizations: [ORG], can_create_team: false })
    get.mockReset().mockResolvedValue(ORG)
    getAnalytics.mockReset()
  })
  afterEach(() => cleanup())

  it('explains the missing overview instead of silently dropping it', async () => {
    getAnalytics.mockRejectedValue(new Error('503'))
    renderTeam()
    await selectOrg()

    await waitFor(() => expect(screen.getByTestId('team-analytics-error')).toBeTruthy())
    expect(screen.getByText(/may be incomplete/i)).toBeTruthy()
  })

  it('renders the real overview and no error when analytics load', async () => {
    getAnalytics.mockResolvedValue({
      total_completions: 12, total_labs: 30, member_count: 4, pending_invite_count: 1,
    })
    renderTeam()
    await selectOrg()

    await waitFor(() => expect(screen.getByText('Team overview')).toBeTruthy())
    expect(screen.queryByTestId('team-analytics-error')).toBeNull()
  })

  it('clears a stale error after a successful retry', async () => {
    getAnalytics.mockRejectedValueOnce(new Error('503')).mockResolvedValue({
      total_completions: 1, total_labs: 1, member_count: 1, pending_invite_count: 0,
    })
    renderTeam()
    await selectOrg()
    await waitFor(() => expect(screen.getByTestId('team-analytics-error')).toBeTruthy())

    fireEvent.click(screen.getByText('Retry'))
    await waitFor(() => expect(screen.queryByTestId('team-analytics-error')).toBeNull())
  })
})
