import { useEffect, useRef, useState } from 'react'
import { FxPageChrome } from '../../components/marketing'
import { useFxPage } from '../../hooks/useFxPage'
import { useDataStore } from '../../store/dataStore'
import { scenarioApi } from '../../api/scenarios'
import api from '../../api/client'
import { mergeTechnologies } from '../../constants/techCatalog'
import { useAuthStore } from '../../store/authStore'
import MarketingNav from './components/MarketingNav'
import MarketingFooter from './components/MarketingFooter'
import HeroSection from './sections/HeroSection'
import TechMarqueeSection from './sections/TechMarqueeSection'
import ChallengeModesSection from './sections/ChallengeModesSection'
import TechnologiesSection from './sections/TechnologiesSection'
import InterviewSection from './sections/InterviewSection'
import VMwareSection from './sections/VMwareSection'
import FeaturesSection from './sections/FeaturesSection'
import HowItWorksSection from './sections/HowItWorksSection'
import TestimonialsSection from './sections/TestimonialsSection'
import PricingCTASection from './sections/PricingCTASection'

export default function HomePage() {
  const { isAuthenticated } = useAuthStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [technologies, setTechnologies] = useState([])
  const [stats, setStats] = useState({})
  const [platformConfig, setPlatformConfig] = useState(null)
  const rootRef = useRef(null)
  const { progressRef, toTopRef, navRef, spotRef, initMagnetic } = useFxPage()

  useEffect(() => {
    getTechnologies()
      .then(data => setTechnologies(mergeTechnologies(data)))
      .catch(() => setTechnologies(mergeTechnologies([])))
    scenarioApi.getPlatformStats().then(setStats).catch(() => {})
    api.get('/config/').then(res => {
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
      <ChallengeModesSection />
      <TechnologiesSection technologies={technologies} isAuthenticated={isAuthenticated} />
      <InterviewSection isAuthenticated={isAuthenticated} />
      <VMwareSection isAuthenticated={isAuthenticated} />
      <FeaturesSection />
      <HowItWorksSection />
      <TestimonialsSection />
      <PricingCTASection />

      <MarketingFooter />
    </div>
  )
}
