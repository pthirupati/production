// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'

vi.mock('../../api/admin', () => ({
  adminApi: {
    getUsers: vi.fn().mockResolvedValue([]),
  },
}))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))
vi.mock('../../components/Skeleton', () => ({
  SkeletonTable: () => null,
}))
vi.mock('../../components/JiraTicketLink', () => ({ default: () => null }))

const AdminUsers = (await import('./AdminUsers')).default

describe('AdminUsers modal accessibility', () => {
  afterEach(() => cleanup())

  it('opens create-user as a dialog with a named close control', async () => {
    render(<AdminUsers />)
    fireEvent.click(await screen.findByRole('button', { name: /Create User|Add User|New User/i }))
    const dialog = await screen.findByRole('dialog', { name: /Create User/i })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(screen.getByRole('button', { name: 'Close create user form' })).toBeTruthy()
  })

  it('closes create-user on Escape', async () => {
    render(<AdminUsers />)
    fireEvent.click(await screen.findByRole('button', { name: /Create User|Add User|New User/i }))
    expect(await screen.findByRole('dialog', { name: /Create User/i })).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: /Create User/i })).toBeNull()
  })
})
