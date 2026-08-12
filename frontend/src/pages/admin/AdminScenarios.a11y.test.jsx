// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../api/admin', () => ({
  adminApi: {
    getScenarios: vi.fn().mockResolvedValue([]),
    getTechnologies: vi.fn().mockResolvedValue([]),
    getTags: vi.fn().mockResolvedValue([]),
    syncScenarios: vi.fn().mockResolvedValue({ message: 'ok' }),
  },
}))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))

const AdminScenarios = (await import('./AdminScenarios')).default

/**
 * Audit line 1383: the scenario editor rendered a visible <label> above each
 * control but never bound the two, so every field was anonymous to a screen
 * reader. The fix wires htmlFor/id, which is what getByLabelText resolves.
 */
async function openForm() {
  render(<AdminScenarios />)
  fireEvent.click(await screen.findByRole('button', { name: /Add Scenario/i }))
}

describe('AdminScenarios accessibility', () => {
  afterEach(() => cleanup())

  it('binds each scenario form label to its control', async () => {
    await openForm()
    for (const name of ['Title', 'Slug', 'Subtitle', 'Technology', 'Difficulty', 'Description']) {
      expect(screen.getByLabelText(name)).toBeTruthy()
    }
  })

  it('names the search box and the icon-only close button', async () => {
    render(<AdminScenarios />)
    expect(await screen.findByLabelText('Search scenarios')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Add Scenario/i }))
    expect(screen.getByRole('button', { name: 'Close scenario form' })).toBeTruthy()
  })

  it('points every htmlFor at an element that exists', async () => {
    await openForm()
    await waitFor(() => expect(document.querySelectorAll('label[for]').length).toBeGreaterThan(10))
    const dangling = [...document.querySelectorAll('label[for]')]
      .map(l => l.getAttribute('for'))
      .filter(id => !document.getElementById(id))
    expect(dangling).toEqual([])
  })

  it('exposes the scenario form as a dialog closed by Escape', async () => {
    await openForm()
    const dialog = screen.getByRole('dialog', { name: /New Scenario|Edit Scenario/i })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: /New Scenario|Edit Scenario/i })).toBeNull()
  })
})
