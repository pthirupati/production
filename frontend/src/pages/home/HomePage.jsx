import { useEffect, useRef, useState } from 'react'
import { FxPageChrome } from '../../components/marketing'
import { useFxPage } from '../../hooks/useFxPage'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useStructuredData, organizationSchema } from '../../hooks/useStructuredData'
import { useDataStore } from '../../store/dataStore'
import { scenarioApi } from '../../api/scenarios'
import api from '../../api/client'
import { mergeTechnologies } from '../../constants/techCatalog'
import { useAuthStore } from '../../store/authStore'
import MarketingNav from './components/MarketingNav'
import MarketingFooter from './components/MarketingFooter'
import HeroSection from './sections/HeroSection'
import OnboardingSection from './sections/OnboardingSection'
import TechMarqueeSection from './sections/TechMarqueeSection'
import ChallengeModesSection from './sections/ChallengeModesSection'
import TechnologiesSection from './sections/TechnologiesSection'
import CertificationsSection from './sections/CertificationsSection'
import InterviewSection from './sections/InterviewSection'
import VMwareSection from './sections/VMwareSection'
import DatacenterGpuSection from './sections/DatacenterGpuSection'
import FeaturesSection from './sections/FeaturesSection'
import HowItWorksSection from './sections/HowItWorksSection'
import TestimonialsSection from './sections/TestimonialsSection'
import PricingCTASection from './sections/PricingCTASection'

export default function HomePage() {
  const { isAuthenticated } = useAuthStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [technologies, setTechnologies] = useState([])
  const [stats, setStats] = useState({})
  const [techLoadFailed, setTechLoadFailed] = useState(false)
  const [platformConfig, setPlatformConfig] = useState(null)
  const rootRef = useRef(null)
  const { progressRef, toTopRef, navRef, spotRef, initMagnetic } = useFxPage()

  usePageTitle(
    'Hands-on DevOps, Cloud, GPU & AI Infrastructure Labs',
    'Fix broken production systems in real environments — Linux, AWS, Azure, GCP, Kubernetes, VMware, Terraform, security, plus GPU/NVIDIA and AI-infrastructure labs, a walkable 3D datacenter, portfolio projects and voice AI interviews.',
    { canonical: `${typeof window !== 'undefined' ? window.location.origin : ''}/` },
  )

  // Audit Z6-7: Organization markup on the home page is what lets Google attach
  // the name and logo to the brand rather than guessing from page copy.
  useStructuredData('organization', organizationSchema)

  useEffect(() => {
    // Audit W5: every fetch here used to swallow its error. Technologies fall
    // back to the static catalog (mergeTechnologies([])), so the page is never
    // blank — but nothing downstream could tell a catalog-only render from a
    // live one, which is why per-tech scenario counts silently vanish. Record
    // the failure so the technology sections can degrade honestly.
    getTechnologies()
      .then(data => {
        setTechnologies(mergeTechnologies(data))
        setTechLoadFailed(false)
      })
      .catch(() => {
        setTechnologies(mergeTechnologies([]))
        setTechLoadFailed(true)
      })
    // stats and /config/ stay quiet on failure by design: HeroSection has its
    // own literal fallbacks and the config only drives optional banners, so a
    // blip degrades to a complete page rather than an empty or wrong one.
    scenarioApi.getPlatformStats().then(setStats).catch(() => {})
    api.get('/config/', { silentError: true }).then(res => {
      setPlatformConfig(res.data)
      if (res.data?.platform_stats) {
        setStats(prev => ({ ...res.data.platform_stats, ...prev }))
      }
    }).catch(() => {})
  }, [getTechnologies])

  useEffect(() => {
    initMagnetic(rootRef.current)
  }, [initMagnetic, technologies])

  return (
    <div id="top" ref={rootRef} className="min-h-screen bg-[#080a16] fx-marketing-page">
      <FxPageChrome progressRef={progressRef} toTopRef={toTopRef} spotRef={spotRef} showSpotlight />

      <MarketingNav navRef={navRef} platformConfig={platformConfig} />

      <HeroSection technologies={technologies} stats={stats} />
      <TechMarqueeSection technologies={technologies} />
      <OnboardingSection isAuthenticated={isAuthenticated} />
      <ChallengeModesSection />
      <TechnologiesSection technologies={technologies} isAuthenticated={isAuthenticated} />
      {techLoadFailed && (
        <p
          data-testid="home-tech-stale"
          className="text-center text-xs text-surface-500 px-6 -mt-6 mb-10"
        >
          Showing our standard technology list — live lab counts are unavailable right now.
        </p>
      )}
      <CertificationsSection isAuthenticated={isAuthenticated} />
      <InterviewSection isAuthenticated={isAuthenticated} />
      <VMwareSection isAuthenticated={isAuthenticated} />
      <DatacenterGpuSection isAuthenticated={isAuthenticated} />
      <FeaturesSection />
      <HowItWorksSection />
      <TestimonialsSection />
      <PricingCTASection />

      <MarketingFooter />
    </div>
  )
}
