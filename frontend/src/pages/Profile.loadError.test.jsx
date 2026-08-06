// @vitest-environment jsdom
// Audit W5: Profile swallowed every billing fetch into an empty default, so a
// failed getMySubscriptions rendered "No active technology subscriptions" plus a
// "View Pricing" CTA to someone who had already paid — the one empty state on
// this page that can provoke a duplicate purchase. Separately, a failed
// getSocialConfig left socialConfig null, which made handleSocialLink report
// "not configured on this server" and send users chasing a phantom misconfig.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const getProfile = vi.fn()
const getSocialConfig = vi.fn()
const getUserPlan = vi.fn()
const getMySubscriptions = vi.fn()
const getMyInvoices = vi.fn()
const getUnifiedBilling = vi.fn()
const interviewGetProfile = vi.fn()
const apiGet = vi.fn()

vi.mock('../api/auth', () => ({
  authApi: {
    getProfile: (...a) => getProfile(...a),
    getSocialConfig: (...a) => getSocialConfig(...a),
    updateProfile: vi.fn(),
  },
}))
vi.mock('../api/labs', () => ({ labApi: { getUserPlan: (...a) => getUserPlan(...a) } }))
vi.mock('../api/subscriptions', () => ({
  subscriptionApi: {
    getMySubscriptions: (...a) => getMySubscriptions(...a),
    getMyInvoices: (...a) => getMyInvoices(...a),
    getUnifiedBilling: (...a) => getUnifiedBilling(...a),
  },
}))
vi.mock('../api/interviews', () => ({
  interviewsApi: { getProfile: (...a) => interviewGetProfile(...a) },
}))
vi.mock('../api/client', () => ({ default: { get: (...a) => apiGet(...a) } }))
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({ user: { username: 'alice' } }),
}))
vi.mock('react-hot-toast', () => ({ default: { error: vi.fn(), success: vi.fn() } }))
vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({ confirm: vi.fn(), ConfirmPortal: () => null }),
}))
vi.mock('../utils/oauth', () => ({ startOAuth: vi.fn() }))
vi.mock('../components/MfaSetupPanel', () => ({ default: () => null }))
vi.mock('../components/engagement', () => ({
  XpLevelCard: () => null, StreakWidget: () => null, BadgeWall: () => null,
}))

import Profile from './Profile'

const renderProfile = () => render(<MemoryRouter><Profile /></MemoryRouter>)

const PROFILE = { username: 'alice', social_accounts: [], has_usable_password: true }

describe('Profile billing fetch failure', () => {
  beforeEach(() => {
    cleanup()
    getProfile.mockReset().mockResolvedValue(PROFILE)
    getSocialConfig.mockReset().mockResolvedValue({ github: { enabled: true } })
    getUserPlan.mockReset().mockResolvedValue(null)
    getMySubscriptions.mockReset().mockResolvedValue({ subscriptions: [] })
    getMyInvoices.mockReset().mockResolvedValue({ invoices: [] })
    getUnifiedBilling.mockReset().mockResolvedValue(null)
    interviewGetProfile.mockReset().mockResolvedValue(null)
    apiGet.mockReset().mockResolvedValue({ data: null })
  })
  afterEach(() => cleanup())

  it('never tells a paying user to buy again when the subscriptions fetch fails', async () => {
    getMySubscriptions.mockRejectedValue(new Error('503'))
    renderProfile()

    await waitFor(() => expect(screen.getByTestId('profile-billing-error')).toBeTruthy())
    // The duplicate-purchase trap: the empty state and its CTA must be gone.
    expect(screen.queryByText('No active technology subscriptions')).toBeNull()
    expect(screen.getByText(/Don't purchase again/i)).toBeTruthy()
  })

  it('shows the genuine empty state for a user who really has no subscriptions', async () => {
    renderProfile()

    await waitFor(() =>
      expect(screen.getByText('No active technology subscriptions')).toBeTruthy()
    )
    expect(screen.queryByTestId('profile-billing-error')).toBeNull()
  })

  it('does not raise a billing error when only a non-billing call fails', async () => {
    // Notification prefs degrade to a default toggle — nothing misleading.
    apiGet.mockRejectedValue(new Error('503'))
    renderProfile()

    await waitFor(() => expect(getMySubscriptions).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.getByText('No active technology subscriptions')).toBeTruthy()
    )
    expect(screen.queryByTestId('profile-billing-error')).toBeNull()
  })

  it('still renders the profile when a billing call fails', async () => {
    getUnifiedBilling.mockRejectedValue(new Error('503'))
    renderProfile()

    // allSettled must not abort the sibling profile fields.
    await waitFor(() => expect(screen.getByDisplayValue('alice')).toBeTruthy())
    expect(screen.getByTestId('profile-billing-error')).toBeTruthy()
  })
})
