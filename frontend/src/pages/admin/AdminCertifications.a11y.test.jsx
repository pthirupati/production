// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../api/certifications', () => ({
  certAdminApi: {
    getTracks: vi.fn().mockResolvedValue({
      tracks: [{
        id: 1, code: 'RHCSA', slug: 'rhcsa', name: 'RHCSA', vendor: 'Red Hat',
        price: 0, addon_price: 0, is_free: true, coming_soon: false, is_active: true,
        passing_score: 70, exam_duration_minutes: 180, validity_months: 36,
        maintenance_enabled: false, maintenance_message: '',
        scenario_count: 0,
      }],
    }),
  },
}))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))

const AdminCertifications = (await import('./AdminCertifications')).default

describe('AdminCertifications modal accessibility', () => {
  afterEach(() => cleanup())

  it('opens the edit track dialog with a named close control', async () => {
    render(<AdminCertifications />)
    fireEvent.click(await screen.findByTitle('Edit'))
    const dialog = await screen.findByRole('dialog', { name: /Edit RHCSA/i })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(screen.getByRole('button', { name: 'Close certification editor' })).toBeTruthy()
  })

  it('closes the edit dialog on Escape', async () => {
    render(<AdminCertifications />)
    fireEvent.click(await screen.findByTitle('Edit'))
    expect(await screen.findByRole('dialog', { name: /Edit RHCSA/i })).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /Edit RHCSA/i })).toBeNull()
    })
  })
})
