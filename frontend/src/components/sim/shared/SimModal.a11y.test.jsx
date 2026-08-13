// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import SimModal from './SimModal'

describe('SimModal accessibility', () => {
  afterEach(() => cleanup())

  it('exposes a dialog landmark with Escape close', () => {
    const onClose = vi.fn()
    render(
      <SimModal open title="Create Job Template" onClose={onClose}>
        <p>body</p>
      </SimModal>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Create Job Template' })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(screen.getByRole('button', { name: 'Close' })).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('applies light portal theme from shellClass without body:has', () => {
    render(
      <SimModal open title="Create a virtual machine" onClose={() => {}} shellClass="az-shell">
        <p className="text-sm">Fluent create form</p>
      </SimModal>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Create a virtual machine' })
    expect(dialog.className).toContain('sim-modal--light')
    const portal = dialog.parentElement
    expect(portal?.getAttribute('data-sim-shell')).toBe('az')
    expect(portal?.className).toContain('az-shell')
  })
})
