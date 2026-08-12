// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LimitReachedModal from './LimitReachedModal'

const info = {
  usage: { labs_today: 3 },
  plan: { max_labs_per_day: 3, name: 'Free' },
}

describe('LimitReachedModal accessibility', () => {
  afterEach(() => cleanup())

  it('is a dialog closed by Escape', async () => {
    const onClose = vi.fn()
    render(
      <MemoryRouter>
        <LimitReachedModal info={info} onClose={onClose} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('dialog', { name: 'Daily Limit Reached' })).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})
