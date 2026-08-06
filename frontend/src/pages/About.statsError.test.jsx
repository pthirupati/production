// @vitest-environment jsdom
// Audit W5: About seeded hardcoded stats (360 scenarios, 10k users) and then
// swallowed any /stats/ error, so a failed call published invented marketing
// numbers as if they were live. The regression to guard is "wrong numbers",
// not merely "no error banner".
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()
vi.mock('../api/client', () => ({ default: { get: (...a) => get(...a) } }))
vi.mock('../components/layout/PublicLayout', () => ({
  default: ({ children }) => <div>{children}</div>,
}))
vi.mock('../hooks/useRevealOnScroll', () => ({ useRevealOnScroll: () => {} }))

import About from './About'

const renderAbout = () => render(<MemoryRouter><About /></MemoryRouter>)

describe('About /stats/ failure', () => {
  beforeEach(() => { cleanup(); get.mockReset() })
  afterEach(() => cleanup())

  it('never publishes invented numbers when /stats/ fails', async () => {
    get.mockRejectedValue(new Error('503'))
    renderAbout()
    await waitFor(() => expect(screen.getByTestId('about-stats-error')).toBeTruthy())

    // The old hardcoded seeds rendered as "360+" scenarios and "10k+" users.
    expect(screen.queryByText('360+')).toBeNull()
    expect(screen.queryByText('10k+')).toBeNull()
    expect(screen.queryByText('50k+')).toBeNull()
    expect(screen.queryByText('18+')).toBeNull()
    // ...and a missing value must not degrade to a bogus "0+" either.
    expect(screen.queryByText('0+')).toBeNull()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('renders live numbers and no error note on success', async () => {
    get.mockResolvedValue({ data: { total_scenarios: 7280, total_technologies: 22, total_completions: 1234 } })
    renderAbout()
    await waitFor(() => expect(screen.getByText('7.3k+')).toBeTruthy())
    expect(screen.getByText('22+')).toBeTruthy()
    expect(screen.queryByTestId('about-stats-error')).toBeNull()
    expect(screen.queryByText('—')).toBeNull()
  })
})
