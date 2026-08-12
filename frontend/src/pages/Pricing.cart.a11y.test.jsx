// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useModalA11y } from '../components/ConfirmModal'
import { useState } from 'react'

/**
 * Pins the Pricing cart drawer a11y contract without mounting the full page
 * (gateway/coupon/Razorpay). Same hook + dialog landmark Pricing.jsx uses.
 */
function CartDrawerHarness() {
  const [open, setOpen] = useState(true)
  const panelRef = useModalA11y(open, () => setOpen(false))
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0" onClick={() => setOpen(false)} />
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Cart (1)"
        className="relative w-full max-w-md outline-none"
      >
        <button type="button" onClick={() => setOpen(false)} aria-label="Close cart">
          Close
        </button>
      </div>
    </div>
  )
}

describe('Pricing cart drawer accessibility', () => {
  afterEach(() => cleanup())

  it('exposes a dialog landmark closed by Escape', async () => {
    render(
      <MemoryRouter>
        <CartDrawerHarness />
      </MemoryRouter>,
    )
    expect(screen.getByRole('dialog', { name: 'Cart (1)' }).getAttribute('aria-modal')).toBe('true')
    expect(screen.getByRole('button', { name: 'Close cart' })).toBeTruthy()
    await act(async () => {
      fireEvent.keyDown(document, { key: 'Escape' })
    })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Cart (1)' })).toBeNull()
    })
  })
})
