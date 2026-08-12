// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { useState } from 'react'
import { useModalA11y } from '../components/ConfirmModal'

/** Same Escape / dialog contract as LabRunner keyboard-shortcuts overlay. */
function ShortcutsHarness() {
  const [open, setOpen] = useState(true)
  const panelRef = useModalA11y(open, () => setOpen(false))
  if (!open) return null
  return (
    <div className="fixed inset-0" onClick={() => setOpen(false)}>
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="lab-shortcuts-title"
        className="outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="lab-shortcuts-title">Keyboard Shortcuts</h3>
        <button type="button" onClick={() => setOpen(false)}>Close</button>
      </div>
    </div>
  )
}

describe('LabRunner shortcuts overlay accessibility', () => {
  afterEach(() => cleanup())

  it('exposes a dialog landmark closed by Escape', async () => {
    render(<ShortcutsHarness />)
    expect(screen.getByRole('dialog', { name: 'Keyboard Shortcuts' }).getAttribute('aria-modal')).toBe('true')
    await act(async () => {
      fireEvent.keyDown(document, { key: 'Escape' })
    })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Keyboard Shortcuts' })).toBeNull()
    })
  })
})
