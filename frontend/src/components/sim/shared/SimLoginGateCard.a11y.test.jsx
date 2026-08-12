// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import SimLoginGateCard from './SimLoginGateCard'

describe('SimLoginGateCard accessibility', () => {
  afterEach(() => cleanup())

  it('exposes a dialog landmark and closes on Escape', () => {
    const onClose = vi.fn()
    render(
      <SimLoginGateCard title="Sign in to Ansible AWX" onClose={onClose}>
        <button type="button">Sign In</button>
      </SimLoginGateCard>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Sign in to Ansible AWX' })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
