// @vitest-environment jsdom
// Audit L1324/L2317: Dashboard fired ten parallel fetches through Promise.all,
// each with its own `.catch(() => null / [] / ({...}))`, and only the first
// (getProgress) could ever set loadError. The other nine resolved to defaults
// byte-identical to a brand-new account, so a backend blip rendered a plausible
// empty dashboard. The two cases that cost the user something real:
//   - activeLabs failing hides a RUNNING lab, so they start a duplicate.
//   - subscriptions failing shows "No active subscriptions" + a Subscribe CTA
//     to someone who already paid.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// OnboardingChecklist reads localStorage during render, and jsdom 29 does not
// provide it here without --localstorage-file (same workaround as
// CodeEditor.docSwap.test.jsx).
vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => store.clear(),
  }
})

import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const getProgress = vi.fn()
const getAchievements = vi.fn()
const getActiveLabs = vi.fn()
const getMySubscriptions = vi.fn()
const getUserTickets = vi.fn()
const getBookmarks = vi.fn()
const apiGet = vi.fn()
const getEntitlement = vi.fn()
const getMyAnalytics = vi.fn()
const tutorialList = vi.fn()
const tutorialContinue = vi.fn()
const getNextJourney = vi.fn()

vi.mock('../api/labs', () => ({
  labApi: {
    getProgress: (...a) => getProgress(...a),
    getAchievements: (...a) => getAchievements(...a),
    getActiveLabs: (...a) => getActiveLabs(...a),
  },
}))
vi.mock('../api/scenarios', () => ({
  scenarioApi: { getBookmarks: (...a) => getBookmarks(...a) },
}))
vi.mock('../api/client', () => ({ default: { get: (...a) => apiGet(...a) } }))
vi.mock('../api/subscriptions', () => ({
  subscriptionApi: {
    getMySubscriptions: (...a) => getMySubscriptions(...a),
    cancelSubscription: vi.fn(),
  },
}))
vi.mock('../api/jira', () => ({
  jiraApi: { getUserTickets: (...a) => getUserTickets(...a) },
}))
vi.mock('../api/interviews', () => ({
  interviewsApi: {
    getEntitlement: (...a) => getEntitlement(...a),
    getMyAnalytics: (...a) => getMyAnalytics(...a),
  },
}))
vi.mock('../api/tutorials', () => ({
  tutorialApi: {
    list: (...a) => tutorialList(...a),
    getContinue: (...a) => tutorialContinue(...a),
  },
}))
vi.mock('../api/journeys', () => ({
  journeyApi: { getNext: (...a) => getNextJourney(...a) },
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({ user: { username: 'alice' }, isAuthenticated: true }),
}))
vi.mock('../utils/tutorialProgress', () => ({
  listLocalContinue: () => [],
  progressPct: () => 0,
}))
// Heavy/irrelevant children — this suite is about fetch failure, not chrome.
vi.mock('../components/OnboardingTour', () => ({ default: () => null }))
vi.mock('../components/MfaRecommendationBanner', () => ({ default: () => null }))
vi.mock('../components/ActivityHeatmap', () => ({ default: () => null }))
vi.mock('../components/certifications/CertDashboardPanel', () => ({ default: () => null }))
vi.mock('../components/engagement', () => ({
  DailyChallengeCard: () => null, StreakWidget: () => null, XpLevelCard: () => null,
}))
vi.mock('../components/JiraTicketLink', () => ({ default: () => null }))

import Dashboard from './Dashboard'

const renderDash = () => render(<MemoryRouter><Dashboard /></MemoryRouter>)

const PROGRESS = {
  summary: { completed: 3, total_attempts: 5, average_score: 80, completion_rate: 60 },
  technology_progress: {},
  difficulty_progress: {},
  recent_activity: [],
  recommended_scenarios: [],
}

describe('Dashboard fetch failure vs empty data', () => {
  beforeEach(() => {
    cleanup()
    localStorage.setItem('onboarding_dismissed', '1')
    getProgress.mockReset().mockResolvedValue(PROGRESS)
    getAchievements.mockReset().mockResolvedValue([])
    getActiveLabs.mockReset().mockResolvedValue([])
    getMySubscriptions.mockReset().mockResolvedValue({ subscriptions: [] })
    getUserTickets.mockReset().mockResolvedValue({ data: { tickets: [] } })
    getBookmarks.mockReset().mockResolvedValue([])
    apiGet.mockReset().mockResolvedValue({ data: { notifications: [] } })
    getEntitlement.mockReset().mockResolvedValue({ platform_enabled: false })
    getMyAnalytics.mockReset().mockResolvedValue(null)
    tutorialList.mockReset().mockResolvedValue({ tutorials: [] })
    tutorialContinue.mockReset().mockResolvedValue([])
    getNextJourney.mockReset().mockResolvedValue({ journey: null, next_step: null })
  })
  afterEach(() => cleanup())

  it('warns about possibly-running labs when getActiveLabs fails', async () => {
    // The duplicate-lab trap: silence here makes the user think nothing is running.
    getActiveLabs.mockRejectedValue(new Error('503'))
    renderDash()

    await waitFor(() =>
      expect(screen.getByTestId('dashboard-active-labs-error')).toBeTruthy()
    )
    expect(screen.getByText(/Don't start a new one/i)).toBeTruthy()
  })

  it('never shows the Subscribe CTA when the subscriptions fetch fails', async () => {
    getMySubscriptions.mockRejectedValue(new Error('503'))
    renderDash()

    await waitFor(() =>
      expect(screen.getByTestId('dashboard-subscriptions-error')).toBeTruthy()
    )
    // The duplicate-purchase trap must be gone, not merely accompanied by a banner.
    expect(screen.queryByText('No active subscriptions')).toBeNull()
    expect(screen.queryByText(/Subscribe to a Technology/i)).toBeNull()
    expect(screen.getByText(/Don't purchase again/i)).toBeTruthy()
  })

  it('raises a partial-failure banner for a subscriptions fetch failure', async () => {
    // Banner is reserved for activeLabs / subscriptions — not every flaky side panel.
    getMySubscriptions.mockRejectedValue(new Error('503'))
    renderDash()

    await waitFor(() =>
      expect(screen.getByTestId('dashboard-partial-error')).toBeTruthy()
    )
  })

  it('does not raise the page banner for bookmarks or jira-list blips', async () => {
    getBookmarks.mockRejectedValue(new Error('503'))
    getUserTickets.mockRejectedValue(new Error('503'))
    renderDash()

    await waitFor(() => expect(screen.getByText('No active subscriptions')).toBeTruthy())
    expect(screen.queryByTestId('dashboard-partial-error')).toBeNull()
  })

  it('stays silent for a genuinely empty but healthy account', async () => {
    renderDash()

    await waitFor(() => expect(screen.getByText('No active subscriptions')).toBeTruthy())
    // A real empty account must not be mislabelled as an outage.
    expect(screen.queryByTestId('dashboard-partial-error')).toBeNull()
    expect(screen.queryByTestId('dashboard-active-labs-error')).toBeNull()
    expect(screen.queryByTestId('dashboard-subscriptions-error')).toBeNull()
  })

  it('does not raise the banner when only the silentError notifications call fails', async () => {
    // That call opts into silentError on purpose; a failed unread badge is not
    // worth a page-level alarm.
    apiGet.mockRejectedValue(new Error('503'))
    renderDash()

    await waitFor(() => expect(screen.getByText('No active subscriptions')).toBeTruthy())
    expect(screen.queryByTestId('dashboard-partial-error')).toBeNull()
  })

  it('suppresses the onboarding checklist when its inputs failed to load', async () => {
    // The checklist infers "new user" from empty data — with a failed
    // subscriptions fetch it would tell a paying user to go pick a technology.
    localStorage.removeItem('onboarding_dismissed')
    getMySubscriptions.mockRejectedValue(new Error('503'))
    renderDash()

    await waitFor(() =>
      expect(screen.getByTestId('dashboard-subscriptions-error')).toBeTruthy()
    )
    expect(screen.queryByText('Pick a technology')).toBeNull()
  })
})

describe('Dashboard weakest competency', () => {
  beforeEach(() => {
    cleanup()
    localStorage.setItem('onboarding_dismissed', '1')
    getProgress.mockReset().mockResolvedValue(PROGRESS)
    getAchievements.mockReset().mockResolvedValue([])
    getActiveLabs.mockReset().mockResolvedValue([])
    getMySubscriptions.mockReset().mockResolvedValue({ subscriptions: [] })
    getUserTickets.mockReset().mockResolvedValue({ data: { tickets: [] } })
    getBookmarks.mockReset().mockResolvedValue([])
    apiGet.mockReset().mockResolvedValue({ data: { notifications: [] } })
    getEntitlement.mockReset().mockResolvedValue({ platform_enabled: false })
    tutorialList.mockReset().mockResolvedValue({ tutorials: [] })
    tutorialContinue.mockReset().mockResolvedValue([])
    getMyAnalytics.mockReset().mockResolvedValue(null)
    getNextJourney.mockReset().mockResolvedValue({ journey: null, next_step: null })
  })
  afterEach(() => cleanup())

  it('names the lowest-scoring radar dimension', async () => {
    getMyAnalytics.mockResolvedValue({
      attempts: 3,
      radar: [
        { dimension: 'Communication', key: 'communication', score: 72 },
        { dimension: 'System Design', key: 'system_design', score: 41 },
        { dimension: 'Technical Depth', key: 'technical_depth', score: 65 },
      ],
    })
    renderDash()

    await waitFor(() =>
      expect(screen.getByText(/Weakest area: System Design/)).toBeTruthy()
    )
    expect(screen.getByText(/41\/100 across 3 graded attempts/)).toBeTruthy()
  })

  it('shows nothing when the user has no graded attempts', async () => {
    // Every dimension is 0 before the first report — picking a "weakest" one
    // would be an arbitrary label on an empty radar.
    getMyAnalytics.mockResolvedValue({
      attempts: 0,
      radar: [
        { dimension: 'Communication', key: 'communication', score: 0 },
        { dimension: 'System Design', key: 'system_design', score: 0 },
      ],
    })
    renderDash()

    await waitFor(() => expect(screen.getByText('No active subscriptions')).toBeTruthy())
    expect(screen.queryByText(/Weakest area/)).toBeNull()
  })
})

describe('Dashboard next journey step', () => {
  const JOURNEY = {
    journey: {
      slug: 'junior-linux-admin-rhcsa',
      title: 'Junior Linux Admin → RHCSA',
      role_label: 'Junior Linux Admin',
      level: 'beginner',
      completed_steps: 2,
      total_steps: 5,
    },
    next_step: {
      order: 2,
      kind: 'scenarios',
      title: 'Level up: networking & firewalld hardening',
      slug: 'academy-linux-006-security-networking-firewalld',
      target_title: 'Secure the box with firewalld',
      link: '/scenarios/academy-linux-006-security-networking-firewalld',
      items_completed: 0,
      items_total: 1,
    },
  }

  beforeEach(() => {
    cleanup()
    localStorage.setItem('onboarding_dismissed', '1')
    getProgress.mockReset().mockResolvedValue(PROGRESS)
    getAchievements.mockReset().mockResolvedValue([])
    getActiveLabs.mockReset().mockResolvedValue([])
    getMySubscriptions.mockReset().mockResolvedValue({ subscriptions: [] })
    getUserTickets.mockReset().mockResolvedValue({ data: { tickets: [] } })
    getBookmarks.mockReset().mockResolvedValue([])
    apiGet.mockReset().mockResolvedValue({ data: { notifications: [] } })
    getEntitlement.mockReset().mockResolvedValue({ platform_enabled: false })
    getMyAnalytics.mockReset().mockResolvedValue(null)
    tutorialList.mockReset().mockResolvedValue({ tutorials: [] })
    tutorialContinue.mockReset().mockResolvedValue([])
    getNextJourney.mockReset().mockResolvedValue({ journey: null, next_step: null })
  })
  afterEach(() => cleanup())

  it('renders the next step with a link straight into the content', async () => {
    getNextJourney.mockResolvedValue(JOURNEY)
    renderDash()

    await waitFor(() =>
      expect(screen.getByTestId('dashboard-journey-card')).toBeTruthy()
    )
    // The content title, not the step's generic label — that is the thing the
    // user actually opens.
    expect(screen.getByText('Secure the box with firewalld')).toBeTruthy()
    expect(screen.getByText(/step 3 of 5/)).toBeTruthy()

    const resume = screen.getByRole('link', { name: 'Resume' })
    expect(resume.getAttribute('href')).toBe(
      '/scenarios/academy-linux-006-security-networking-firewalld'
    )
  })

  it('does not render a failed journey fetch as "no journey"', async () => {
    // The bug this audit item is about: a rejected fetch that degrades to an
    // empty default is indistinguishable from a user who never started one.
    getNextJourney.mockRejectedValue(new Error('503'))
    renderDash()

    await waitFor(() =>
      expect(screen.getByTestId('dashboard-journey-error')).toBeTruthy()
    )
    expect(screen.queryByTestId('dashboard-journey-card')).toBeNull()
    expect(screen.getByText(/your progress is intact/i)).toBeTruthy()
    // Journey failures get a dedicated card — not the page-level partial banner
    // (that banner is reserved for primary cards: labs/subs/jira/bookmarks/etc.).
    expect(screen.queryByTestId('dashboard-partial-error')).toBeNull()
  })

  it('shows neither card nor error when the user has not started a journey', async () => {
    renderDash()

    await waitFor(() => expect(screen.getByText('No active subscriptions')).toBeTruthy())
    expect(screen.queryByTestId('dashboard-journey-card')).toBeNull()
    expect(screen.queryByTestId('dashboard-journey-error')).toBeNull()
    expect(screen.queryByTestId('dashboard-partial-error')).toBeNull()
  })

  it('renders a capstone with no route as text instead of a dead link', async () => {
    // The SPA has no /projects/<slug> page, so the backend sends link: null.
    getNextJourney.mockResolvedValue({
      ...JOURNEY,
      next_step: {
        ...JOURNEY.next_step,
        kind: 'project',
        slug: 'linux-fundamentals-first-server',
        target_title: 'Build a real server from zero',
        link: null,
      },
    })
    renderDash()

    await waitFor(() =>
      expect(screen.getByText('Build a real server from zero')).toBeTruthy()
    )
    expect(screen.queryByRole('link', { name: 'Resume' })).toBeNull()
    expect(screen.getByText('Up next')).toBeTruthy()
  })

  it('shows per-item progress only for a multi-item step', async () => {
    getNextJourney.mockResolvedValue({
      ...JOURNEY,
      next_step: { ...JOURNEY.next_step, items_completed: 2, items_total: 3 },
    })
    renderDash()

    await waitFor(() => expect(screen.getByText(/2\/3 done/)).toBeTruthy())
  })
})
