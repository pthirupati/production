// @vitest-environment jsdom
// Audit W5: HomePage swallowed every fetch error. Technologies fall back to the
// static catalog so the page is never blank, but nothing told the visitor the
// per-technology lab counts were missing — a catalog-only render looked exactly
// like a live one.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

const getTechnologies = vi.fn()
const getPlatformStats = vi.fn()
const apiGet = vi.fn()

vi.mock('../../store/dataStore', () => ({
  useDataStore: (sel) => sel({ getTechnologies: () => getTechnologies() }),
}))
vi.mock('../../store/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: false }),
}))
vi.mock('../../api/scenarios', () => ({
  scenarioApi: { getPlatformStats: () => getPlatformStats() },
}))
vi.mock('../../api/client', () => ({ default: { get: (...a) => apiGet(...a) } }))
vi.mock('../../hooks/usePageTitle', () => ({ usePageTitle: () => {} }))
vi.mock('../../hooks/useStructuredData', () => ({
  useStructuredData: () => {},
  organizationSchema: {},
}))
vi.mock('../../hooks/useFxPage', () => ({
  useFxPage: () => ({
    progressRef: { current: null }, toTopRef: { current: null },
    navRef: { current: null }, spotRef: { current: null },
    initMagnetic: () => {},
  }),
}))
vi.mock('../../components/marketing', () => ({ FxPageChrome: () => null }))

// The marketing sections pull in framer-motion and the 3D datacenter; none of
// them are under test here, so stub them all to nothing.
const stub = { default: () => null }
for (const p of [
  './components/MarketingNav', './components/MarketingFooter',
  './sections/HeroSection', './sections/OnboardingSection', './sections/TechMarqueeSection',
  './sections/ChallengeModesSection', './sections/TechnologiesSection',
  './sections/CertificationsSection', './sections/InterviewSection', './sections/VMwareSection',
  './sections/DatacenterGpuSection', './sections/FeaturesSection', './sections/HowItWorksSection',
  './sections/TestimonialsSection', './sections/PricingCTASection',
]) vi.doMock(p, () => stub)

const { default: HomePage } = await import('./HomePage')

describe('HomePage technology fetch failure', () => {
  beforeEach(() => {
    cleanup()
    getTechnologies.mockReset()
    getPlatformStats.mockReset().mockResolvedValue({})
    apiGet.mockReset().mockResolvedValue({ data: {} })
  })
  afterEach(() => cleanup())

  it('flags the catalog-only fallback when the technology fetch fails', async () => {
    getTechnologies.mockRejectedValue(new Error('502'))
    render(<HomePage />)
    await waitFor(() => expect(screen.getByTestId('home-tech-stale')).toBeTruthy())
  })

  it('shows no notice when live technologies load', async () => {
    getTechnologies.mockResolvedValue([{ slug: 'linux', name: 'Linux', scenario_count: 40 }])
    render(<HomePage />)
    await waitFor(() => expect(getTechnologies).toHaveBeenCalled())
    expect(screen.queryByTestId('home-tech-stale')).toBeNull()
  })

  it('stays quiet when only stats and config fail', async () => {
    getTechnologies.mockResolvedValue([{ slug: 'linux', name: 'Linux', scenario_count: 40 }])
    getPlatformStats.mockRejectedValue(new Error('503'))
    apiGet.mockRejectedValue(new Error('503'))
    render(<HomePage />)
    await waitFor(() => expect(getTechnologies).toHaveBeenCalled())
    // Those two degrade to literal fallbacks / absent banners, not wrong data.
    expect(screen.queryByTestId('home-tech-stale')).toBeNull()
  })
})
