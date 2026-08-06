// @vitest-environment jsdom
// Audit L2310: the unfiltered empty state read "No scenarios are available yet.
// Check back soon!" — a dead end with no next action. The catch here is that the
// scenario fetch used `.catch(console.error)` and fell through to that same
// empty state, so adding a cheerful CTA without an error branch would have
// permanently disguised an outage as an empty catalog.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// usePageTitle and the toolbar hook touch storage/observers during render.
vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => store.clear(),
  }
})

import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const getScenarios = vi.fn()
const getTags = vi.fn()
const getTechnologies = vi.fn()

vi.mock('../api/scenarios', () => ({
  scenarioApi: {
    getScenarios: (...a) => getScenarios(...a),
    getTags: (...a) => getTags(...a),
    toggleBookmark: vi.fn(),
  },
}))
vi.mock('../store/authStore', () => ({ useAuthStore: () => ({ isAuthenticated: false }) }))
vi.mock('../store/dataStore', () => ({
  useDataStore: (sel) => sel({ getTechnologies: (...a) => getTechnologies(...a) }),
}))
vi.mock('react-hot-toast', () => ({ default: { error: vi.fn(), success: vi.fn() } }))
vi.mock('../hooks/usePageTitle', () => ({ usePageTitle: () => {} }))
vi.mock('../hooks/useScrollHideToolbar', () => ({ useScrollHideToolbar: () => ({}) }))
vi.mock('../components/engagement', () => ({ ScenarioStatsChip: () => null }))

import Scenarios from './Scenarios'

const renderScenarios = () => render(<MemoryRouter><Scenarios /></MemoryRouter>)

describe('Scenarios empty state vs load failure', () => {
  beforeEach(() => {
    cleanup()
    getScenarios.mockReset().mockResolvedValue({ results: [], count: 0 })
    getTags.mockReset().mockResolvedValue([])
    getTechnologies.mockReset().mockResolvedValue([])
  })
  afterEach(() => cleanup())

  it('offers a next action instead of "check back soon" on a real empty catalog', async () => {
    renderScenarios()

    await waitFor(() => expect(screen.getByText('No scenarios found')).toBeTruthy())
    // The dead end the audit flagged must be gone, replaced by somewhere to go.
    expect(screen.queryByText(/Check back soon/i)).toBeNull()
    expect(screen.getByText('Browse technologies')).toBeTruthy()
    expect(screen.getByText('Guided tutorials')).toBeTruthy()
  })

  it('shows a load error, not the empty state, when the fetch fails', async () => {
    // Without this branch the failure renders as "No scenarios found" plus a
    // browse CTA — an outage permanently disguised as an empty catalog.
    getScenarios.mockRejectedValue(new Error('503'))
    renderScenarios()

    await waitFor(() => expect(screen.getByTestId('scenarios-load-error')).toBeTruthy())
    expect(screen.queryByText('No scenarios found')).toBeNull()
    expect(screen.queryByText('Browse technologies')).toBeNull()
    expect(screen.getByText(/isn't empty/i)).toBeTruthy()
  })

  it('does not leave the error state stuck after a later successful fetch', async () => {
    getScenarios.mockRejectedValueOnce(new Error('503'))
    const { unmount } = renderScenarios()
    await waitFor(() => expect(screen.getByTestId('scenarios-load-error')).toBeTruthy())
    unmount()

    getScenarios.mockResolvedValue({ results: [], count: 0 })
    renderScenarios()
    await waitFor(() => expect(screen.getByText('No scenarios found')).toBeTruthy())
    expect(screen.queryByTestId('scenarios-load-error')).toBeNull()
  })
})
