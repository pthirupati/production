import { motion } from 'framer-motion'
import { features } from '../data/homeContent'
import { blurIn, scaleIn, staggerContainer, viewportOnce } from '../../../ui/motion'

const colorMap = {
  cyan: { bg: 'rgba(73,181,255,.18)', border: 'rgba(73,181,255,.25)', text: '#49b5ff' },
  purple: { bg: 'rgba(178,102,224,.18)', border: 'rgba(178,102,224,.25)', text: '#d6a8ee' },
  amber: { bg: 'rgba(254,177,85,.18)', border: 'rgba(254,177,85,.25)', text: '#feb155' },
  green: { bg: 'rgba(86,224,176,.18)', border: 'rgba(86,224,176,.25)', text: '#56e0b0' },
}

export default function FeaturesSection() {
  return (
    <section id="features" className="fx-home-section">
      <div
        className="fx-parallax-orb absolute top-[8%] left-[4%] pointer-events-none"
        aria-hidden="true"
        data-parallax="0.2"
        style={{ width: 340, height: 340, background: 'radial-gradient(circle, var(--fx-ac2) 0%, transparent 70%)', opacity: 0.09, filter: 'blur(46px)' }}
      />

      <div className="fx-home-section-inner">
        <motion.div
          className="text-center max-w-[640px] mx-auto mb-[60px]"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={blurIn}
        >
          <div
            className="fx-home-eyebrow mx-auto"
            style={{ background: 'rgba(73,181,255,.1)', border: '1px solid rgba(73,181,255,.25)', color: '#7cc6ff' }}
          >
            Platform
          </div>
          <h2 className="fx-home-title">Built for serious engineers</h2>
          <p className="fx-home-sub mx-auto">
            Everything you need to master any technology — in one platform.
          </p>
        </motion.div>

        <motion.div
          className="fx-feature-grid"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
        >
          {features.map(({ icon: Icon, title, desc, color }) => {
            const c = colorMap[color] || colorMap.cyan
            return (
              <motion.div key={title} className="fx-feature-card" variants={scaleIn}>
                <div
                  className="fx-feature-icon"
                  style={{ background: c.bg, borderColor: c.border, color: c.text }}
                >
                  <Icon size={22} />
                </div>
                <h3>{title}</h3>
                <p>{desc}</p>
              </motion.div>
            )
          })}
        </motion.div>
      </div>
    </section>
  )
}
