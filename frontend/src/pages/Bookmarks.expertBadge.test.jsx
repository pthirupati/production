// @vitest-environment jsdom
// Audit L2337: the difficulty badge map was keyed on easy/medium/hard only, with
// a `|| ''` fallback. Any scenario outside those three rendered a `badge` chip
// with no colour, border, or contrast — the tier was effectively invisible.
// The regression to guard is "styleless chip", not merely "text is present".
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const getBookmarks = vi.fn()
vi.mock('../api/scenarios', () => ({
  scenarioApi: {
    getBookmarks: (...a) => getBookmarks(...a),
    toggleBookmark: vi.fn(),
  },
}))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))

import Bookmarks from './Bookmarks'

const scenario = (difficulty) => ({
  id: 1,
  slug: 'gpu-nvlink-fabric-collapse',
  title: 'NVLink fabric collapse',
  difficulty,
  scenario_type: 'fix',
  time_limit: 900,
  technology: { name: 'GPU' },
})

const renderWith = async (difficulty) => {
  getBookmarks.mockResolvedValue([scenario(difficulty)])
  render(<MemoryRouter><Bookmarks /></MemoryRouter>)
  return waitFor(() => screen.getByText(difficulty))
}

describe('Bookmarks difficulty badge', () => {
  beforeEach(() => { cleanup(); getBookmarks.mockReset() })
  afterEach(() => cleanup())

  it('gives expert a styled badge, not a colourless chip', async () => {
    const badge = await renderWith('expert')
    const cls = badge.className
    // `badge` alone is just shape (padding + rounding). Colour is what was missing.
    expect(cls).toContain('badge')
    expect(cls).toMatch(/text-accent-purple/)
    expect(cls).toMatch(/bg-accent-purple/)
  })

  it('still styles the three original tiers', async () => {
    const badge = await renderWith('hard')
    expect(badge.className).toContain('badge-hard')
  })

  it('falls back to a legible chip for an unknown difficulty', async () => {
    const badge = await renderWith('impossible')
    // Regression guard for the old `|| ''`: some colour must always be applied.
    expect(badge.className).toMatch(/text-surface-300/)
  })
})
