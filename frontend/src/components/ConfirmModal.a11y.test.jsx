// @vitest-environment jsdom
//
// Audit line 1389. Modals across the app were plain divs with no focus trap, no
// Escape and no focus restore. ConfirmModal already had the pattern; it is now
// extracted as useModalA11y so themed product dialogs (MaaS, vSphere) can adopt
// the behaviour without adopting the glass-card markup.
//
// These tests pin the parts that silently rot: the trap wrapping in both
// directions, focus returning to the opener, and the refcounted body-scroll lock
// that a naive implementation breaks as soon as two dialogs overlap.
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { useState } from 'react'
import ConfirmModal from './ConfirmModal'

afterEach(() => {
  cleanup()
  document.body.style.overflow = ''
})

const noop = () => {}

describe('ConfirmModal accessibility', () => {
  it('moves focus into the dialog when it opens', () => {
    render(
      <ConfirmModal open onClose={noop} title="Danger">
        <button type="button">First</button>
        <button type="button">Second</button>
      </ConfirmModal>,
    )
    // The close button is the first focusable inside the panel.
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close dialog' }))
  })

  it('wraps Tab from the last control back to the first', () => {
    render(
      <ConfirmModal open onClose={noop} title="Danger">
        <button type="button">Only</button>
      </ConfirmModal>,
    )
    const close = screen.getByRole('button', { name: 'Close dialog' })
    const only = screen.getByRole('button', { name: 'Only' })

    only.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(close)
  })

  it('wraps Shift+Tab from the first control back to the last', () => {
    render(
      <ConfirmModal open onClose={noop} title="Danger">
        <button type="button">Only</button>
      </ConfirmModal>,
    )
    const close = screen.getByRole('button', { name: 'Close dialog' })
    const only = screen.getByRole('button', { name: 'Only' })

    close.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(only)
  })

  it('pulls focus back in if it has escaped the panel', () => {
    render(
      <>
        <button type="button">Outside</button>
        <ConfirmModal open onClose={noop} title="Danger">
          <button type="button">Inside</button>
        </ConfirmModal>
      </>,
    )
    const outside = screen.getByRole('button', { name: 'Outside' })
    outside.focus()
    expect(document.activeElement).toBe(outside)

    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close dialog' }))
  })

  it('closes on Escape', () => {
    let closed = false
    render(
      <ConfirmModal open onClose={() => { closed = true }} title="Danger">
        <button type="button">Only</button>
      </ConfirmModal>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(closed).toBe(true)
  })

  it('restores focus to whatever opened it', () => {
    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>Open</button>
          <ConfirmModal open={open} onClose={() => setOpen(false)} title="Danger">
            <button type="button">Inside</button>
          </ConfirmModal>
        </>
      )
    }
    render(<Harness />)
    const opener = screen.getByRole('button', { name: 'Open' })
    opener.focus()
    fireEvent.click(opener)
    expect(document.activeElement).not.toBe(opener)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(document.activeElement).toBe(opener)
  })
})

describe('stacked modal body-scroll lock', () => {
  it('keeps scroll locked until the last dialog closes', () => {
    function Stack({ outer, inner }) {
      return (
        <>
          <ConfirmModal open={outer} onClose={noop} title="Outer">
            <button type="button">Outer body</button>
          </ConfirmModal>
          <ConfirmModal open={inner} onClose={noop} title="Inner">
            <button type="button">Inner body</button>
          </ConfirmModal>
        </>
      )
    }
    const { rerender } = render(<Stack outer inner />)
    expect(document.body.style.overflow).toBe('hidden')

    // Inner closes first — the page must stay locked, the outer is still up.
    rerender(<Stack outer inner={false} />)
    expect(document.body.style.overflow).toBe('hidden')

    rerender(<Stack outer={false} inner={false} />)
    expect(document.body.style.overflow).toBe('')
  })
})
