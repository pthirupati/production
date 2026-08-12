// @vitest-environment jsdom
//
// Audit line 1389. The MaaS machines dialog was a bare `role="dialog"` div: no
// focus trap, no Escape, no focus restore, and no accessible name. It keeps its
// own maas-* chrome (swapping in ConfirmModal's glass-card would break the
// emulated MaaS UI the lab teaches), so it adopts the shared useModalA11y hook
// instead.
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import MachinesTable from './MachinesTable'

afterEach(() => {
  cleanup()
  document.body.style.overflow = ''
})

const openAddDialog = () => {
  const trigger = screen.getByRole('button', { name: /Add hardware/ })
  trigger.focus()
  fireEvent.click(trigger)
  return trigger
}

describe('MaaS machines dialog accessibility', () => {
  it('exposes an accessible name matching the MaaS wording', () => {
    render(<MachinesTable machines={[]} />)
    openAddDialog()
    // Wording must stay the product's own, not a paraphrase.
    expect(screen.getByRole('dialog', { name: 'Add hardware' })).toBeTruthy()
  })

  it('moves focus into the dialog on open', () => {
    render(<MachinesTable machines={[]} />)
    openAddDialog()
    const hostname = screen.getByPlaceholderText('node-04')
    expect(document.activeElement).toBe(hostname)
  })

  it('traps Tab inside the dialog', () => {
    render(<MachinesTable machines={[]} />)
    openAddDialog()
    const dialog = screen.getByRole('dialog')
    const confirm = screen.getByRole('button', { name: 'Confirm' })
    const hostname = screen.getByPlaceholderText('node-04')

    // Forward from the last control wraps to the first.
    confirm.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(dialog.contains(document.activeElement)).toBe(true)
    expect(document.activeElement).toBe(hostname)

    // Backward from the first control wraps to the last.
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(confirm)
  })

  it('closes on Escape and restores focus to the trigger', () => {
    render(<MachinesTable machines={[]} />)
    const trigger = openAddDialog()
    expect(screen.queryByRole('dialog')).toBeTruthy()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it('locks body scroll only while the dialog is open', () => {
    render(<MachinesTable machines={[]} />)
    expect(document.body.style.overflow).toBe('')
    openAddDialog()
    expect(document.body.style.overflow).toBe('hidden')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(document.body.style.overflow).toBe('')
  })
})
