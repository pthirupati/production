// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'

vi.mock('../../api/admin', () => ({
  adminApi: {
    getTechnologies: vi.fn().mockResolvedValue([]),
    getTags: vi.fn().mockResolvedValue([]),
  },
}))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))

const AdminTechnologies = (await import('./AdminTechnologies')).default

describe('AdminTechnologies modal accessibility', () => {
  afterEach(() => cleanup())

  it('opens the tech form as a dialog with a named close control', async () => {
    render(<AdminTechnologies />)
    fireEvent.click(await screen.findByRole('button', { name: /Add Technology/i }))
    const dialog = screen.getByRole('dialog', { name: /New Technology/i })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(screen.getByRole('button', { name: 'Close technology form' })).toBeTruthy()
  })

  it('closes the tech form on Escape', async () => {
    render(<AdminTechnologies />)
    fireEvent.click(await screen.findByRole('button', { name: /Add Technology/i }))
    expect(screen.getByRole('dialog', { name: /New Technology/i })).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: /New Technology/i })).toBeNull()
  })
})
