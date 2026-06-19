import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { TechCardGrid } from '../../../components/marketing'
import { blurIn, scaleIn, staggerContainer, viewportOnce } from '../../../ui/motion'

export default function TechnologiesSection({ technologies, isAuthenticated }) {
  return (
    <section id="tech" className="fx-home-section" style={{ paddingTop: 0 }}>
      <div className="fx-home-section-inner">
        <motion.div
          className="text-center max-w-[640px] mx-auto mb-14"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={blurIn}
        >
          <div
            className="fx-home-eyebrow mx-auto"
            style={{ background: 'rgba(86,224,176,.1)', border: '1px solid rgba(86,224,176,.25)', color: '#56e0b0' }}
          >
            Technologies
          </div>
          <h2 className="fx-home-title">Choose your battleground</h2>
          <p className="fx-home-sub mx-auto">
            Subscribe per technology. Cancel anytime. Live scenario counts straight from the platform.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
        >
          <TechCardGrid
            technologies={technologies}
            linkTo={(tech) => {
              if (tech.coming_soon) return '#'
              return isAuthenticated ? `/technologies/${tech.slug}` : '/register'
            }}
          />
        </motion.div>

        <motion.div
          className="fx-cta-strip mt-10"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={scaleIn}
        >
          <div className="fx-cta-strip-glow" aria-hidden="true" />
          <div className="relative">
            <h2>Not sure where to start?</h2>
            <p>Browse the full challenge library and filter by technology, difficulty, and type.</p>
          </div>
          <Link to="/register" data-magnetic className="fx-btn-primary relative shrink-0">
            Get started free <ArrowRight size={15} />
          </Link>
        </motion.div>
      </div>
    </section>
  )
}
