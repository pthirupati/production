// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../api/admin', () => ({
  adminApi: {
    getSalesInquiries: vi.fn().mockResolvedValue({
      inquiries: [{
        id: 1,
        organization: 'Acme',
        full_name: 'Ada',
        work_email: 'ada@acme.test',
        status: 'new',
        message: 'hello',
        created_at: '2026-01-01T00:00:00Z',
      }],
      counts: { new: 1 },
    }),
    updateSalesInquiry: vi.fn().mockResolvedValue({}),
  },
}))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))

const AdminSales = (await import('./AdminSales')).default

describe('AdminSales modal accessibility', () => {
  afterEach(() => cleanup())

  it('opens the inquiry editor as a dialog closed by Escape', async () => {
    render(<AdminSales />)
    fireEvent.click(await screen.findByRole('button', { name: /^Quote$/i }))
    const dialog = await screen.findByRole('dialog', { name: /Edit inquiry Acme/i })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /Edit inquiry Acme/i })).toBeNull()
    })
  })
})
