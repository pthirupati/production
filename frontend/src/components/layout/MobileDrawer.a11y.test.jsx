// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { useState } from 'react'
import { useModalA11y } from '../ConfirmModal'

/** Same Escape / dialog contract as MainLayout / AdminLayout mobile drawers. */
function MobileDrawerHarness() {
  const [open, setOpen] = useState(true)
  const panelRef = useModalA11y(open, () => setOpen(false))
  if (!open) return <div>closed</div>
  return (
    <aside
      ref={panelRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label="Main navigation"
      className="outline-none"
    >
      <button type="button" onClick={() => setOpen(false)}>Close</button>
    </aside>
  )
}

describe('Layout mobile drawer accessibility', () => {
  afterEach(() => cleanup())

  it('exposes a dialog landmark closed by Escape', async () => {
    render(<MobileDrawerHarness />)
    expect(screen.getByRole('dialog', { name: 'Main navigation' }).getAttribute('aria-modal')).toBe('true')
    await act(async () => {
      fireEvent.keyDown(document, { key: 'Escape' })
    })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Main navigation' })).toBeNull()
    })
  })
})
