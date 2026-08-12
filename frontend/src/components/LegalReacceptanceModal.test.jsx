// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => { store.clear() },
  }
})

vi.mock('../api/auth', () => ({
  authApi: {
    getProfile: vi.fn(),
    acceptTerms: vi.fn(),
  },
}))

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))

import { authApi } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import LegalReacceptanceModal from './LegalReacceptanceModal'

describe('LegalReacceptanceModal', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: {
        email: 'a@b.com',
        needs_legal_reacceptance: true,
      },
      accessToken: 'a',
      refreshToken: 'r',
      isAuthenticated: true,
    })
    authApi.acceptTerms.mockReset()
    authApi.getProfile.mockReset()
  })

  it('opens when the profile needs reacceptance', () => {
    render(
      <MemoryRouter>
        <LegalReacceptanceModal />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Updated Terms & Privacy/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /I accept/i })).toBeTruthy()
  })

  it('stays closed when reacceptance is not needed', () => {
    useAuthStore.setState({
      user: { email: 'a@b.com', needs_legal_reacceptance: false },
      isAuthenticated: true,
    })
    render(
      <MemoryRouter>
        <LegalReacceptanceModal />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/Updated Terms & Privacy/i)).toBeNull()
  })

  it('records acceptance and clears the modal', async () => {
    authApi.acceptTerms.mockResolvedValue({ needs_legal_reacceptance: false })
    authApi.getProfile.mockResolvedValue({
      email: 'a@b.com',
      needs_legal_reacceptance: false,
    })
    render(
      <MemoryRouter>
        <LegalReacceptanceModal />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: /I accept/i }))
    await waitFor(() => {
      expect(authApi.acceptTerms).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.queryByText(/Updated Terms & Privacy/i)).toBeNull()
    })
    expect(useAuthStore.getState().user.needs_legal_reacceptance).toBe(false)
  })
})
