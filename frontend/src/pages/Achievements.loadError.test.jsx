// @vitest-environment jsdom
// Audit W5: all three fetches were `.catch(() => [] / ({...}))`, so a backend
// blip rendered "0 of 0 achievements unlocked" and "No technology subscriptions
// yet" — byte-identical to what a brand-new user sees. Someone who had earned a
// certificate would see it silently gone with no indication anything broke.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

const getAchievements = vi.fn()
const getAchievementsCertificate = vi.fn()
const listCertificates = vi.fn()

vi.mock('../api/labs', () => ({
  labApi: {
    getAchievements: (...a) => getAchievements(...a),
    getAchievementsCertificate: (...a) => getAchievementsCertificate(...a),
  },
}))
vi.mock('../api/interviews', () => ({
  interviewsApi: { listCertificates: (...a) => listCertificates(...a) },
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({ user: { username: 'alice' } }),
}))
vi.mock('react-hot-toast', () => ({ default: { error: vi.fn(), success: vi.fn() } }))

import Achievements from './Achievements'

describe('Achievements fetch failure vs empty progress', () => {
  beforeEach(() => {
    cleanup()
    getAchievements.mockReset()
    getAchievementsCertificate.mockReset()
    listCertificates.mockReset()
  })
  afterEach(() => cleanup())

  it('surfaces an error instead of pretending the user has no achievements', async () => {
    getAchievements.mockRejectedValue(new Error('503'))
    getAchievementsCertificate.mockResolvedValue({ eligible_technologies: [] })
    listCertificates.mockResolvedValue({ certificates: [] })
    render(<Achievements />)

    await waitFor(() => expect(screen.getByTestId('achievements-load-error')).toBeTruthy())
    expect(screen.getByText(/not lost progress/i)).toBeTruthy()
  })

  it('flags a failed certificate fetch rather than showing the "subscribe" empty state alone', async () => {
    getAchievements.mockResolvedValue([])
    getAchievementsCertificate.mockRejectedValue(new Error('503'))
    listCertificates.mockResolvedValue({ certificates: [] })
    render(<Achievements />)

    await waitFor(() => expect(screen.getByTestId('achievements-load-error')).toBeTruthy())
  })

  it('stays quiet when every call succeeds, even with genuinely empty data', async () => {
    getAchievements.mockResolvedValue([])
    getAchievementsCertificate.mockResolvedValue({ eligible_technologies: [] })
    listCertificates.mockResolvedValue({ certificates: [] })
    render(<Achievements />)

    await waitFor(() => expect(getAchievements).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.getByText('No technology subscriptions yet')).toBeTruthy()
    )
    // A real empty account must not be mislabelled as an error either.
    expect(screen.queryByTestId('achievements-load-error')).toBeNull()
  })
})
