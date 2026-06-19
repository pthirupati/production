import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Layers, ArrowRight } from 'lucide-react'
import toast from 'react-hot-toast'
import { useDataStore } from '../store/dataStore'
import { mergeTechnologies } from '../constants/techCatalog'
import { useFxPage } from '../hooks/useFxPage'
import { FxPageChrome, TechCardGrid } from '../components/marketing'

export default function Technologies() {
  const rootRef = useRef(null)
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [technologies, setTechnologies] = useState([])
  const [loading, setLoading] = useState(true)
  const { progressRef, toTopRef, spotRef, initMagnetic } = useFxPage()

  useEffect(() => {
    getTechnologies()
      .then(data => setTechnologies(mergeTechnologies(data)))
      .catch(() => {
        setTechnologies(mergeTechnologies([]))
        toast.error('Could not load technologies — showing catalog')
      })
      .finally(() => setLoading(false))
  }, [getTechnologies])

  useEffect(() => {
    initMagnetic(rootRef.current)
  }, [loading, technologies, initMagnetic])

  const linkTo = (tech) => {
    if (tech.coming_soon) return '#'
    return `/technologies/${tech.slug}`
  }

  return (
    <div id="top" ref={rootRef} className="fx-marketing-page">
      <FxPageChrome progressRef={progressRef} toTopRef={toTopRef} spotRef={spotRef} />

      <div aria-hidden="true" className="fx-parallax-bg">
        <div
          data-parallax="0.18"
          className="fx-parallax-orb"
          style={{
            top: '10%', left: '8%', width: 400, height: 400,
            background: 'radial-gradient(circle, var(--fx-ac3) 0%, transparent 68%)',
            opacity: 0.08,
          }}
        />
        <div
          data-parallax="0.24"
          className="fx-parallax-orb"
          style={{
            bottom: '8%', right: '8%', width: 380, height: 380,
            background: 'radial-gradient(circle, var(--fx-ac2) 0%, transparent 68%)',
            opacity: 0.08,
            animationDelay: '2s',
          }}
        />
      </div>

      <div className="fx-section-inner">
        <div className="fx-section-header">
          <div>
            <div className="fx-section-eyebrow">
              <Layers size={13} stroke="var(--fx-ac3)" />
              Learning paths
            </div>
            <h1 className="fx-section-title">Technologies</h1>
            <p className="fx-section-sub">Choose a technology to explore its challenges.</p>
          </div>
          <Link
            to="/scenarios"
            className="text-sm font-semibold text-white/60 hover:text-[var(--fx-ac3)] transition-colors inline-flex items-center gap-1.5 shrink-0"
          >
            View all scenarios <ArrowRight size={14} />
          </Link>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-10 h-10 border-2 border-[var(--fx-ac)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <TechCardGrid technologies={technologies} linkTo={linkTo} />
        )}

        <div className="fx-cta-strip">
          <div className="fx-cta-strip-glow" aria-hidden="true" />
          <div className="relative">
            <h2>Not sure where to start?</h2>
            <p>Browse the full challenge library and filter by technology, difficulty, and type.</p>
          </div>
          <Link to="/scenarios" data-magnetic className="fx-btn-primary relative shrink-0">
            Browse scenarios <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </div>
  )
}
