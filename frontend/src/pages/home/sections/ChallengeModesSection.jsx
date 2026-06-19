import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { scenarioTypes } from '../data/homeContent'
import { fadeLeft, fadeRight, scaleIn, blurIn, viewportOnce } from '../../../ui/motion'

const cardVariants = [fadeLeft, scaleIn, fadeRight]

export default function ChallengeModesSection() {
  return (
    <section id="modes" className="fx-home-section">
      <div
        className="fx-parallax-orb absolute top-[4%] right-[5%] pointer-events-none"
        aria-hidden="true"
        data-parallax="0.24"
        style={{ width: 320, height: 320, background: 'radial-gradient(circle, var(--fx-ac3) 0%, transparent 70%)', opacity: 0.1, filter: 'blur(44px)' }}
      />

      <div className="fx-home-section-inner">
        <motion.div
          className="text-center max-w-[640px] mx-auto mb-16"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={blurIn}
        >
          <div
            className="fx-home-eyebrow mx-auto"
            style={{ background: 'rgba(109,120,255,.1)', border: '1px solid rgba(109,120,255,.25)', color: '#aeb4ff' }}
          >
            Challenge modes
          </div>
          <h2 className="fx-home-title">Three ways to prove yourself</h2>
          <p className="fx-home-sub mx-auto">
            Each scenario type tests a different depth of skill — from rapid triage to offensive thinking.
          </p>
        </motion.div>

        <div className="fx-challenge-grid">
          {scenarioTypes.map((item, i) => {
            const Icon = item.icon
            const Variant = cardVariants[i]
            return (
              <motion.div
                key={item.type}
                initial="hidden"
                whileInView="visible"
                viewport={viewportOnce}
                variants={Variant}
                transition={{ delay: i * 0.08 }}
              >
                <Link
                  to={`/scenarios?type=${item.type}`}
                  className="fx-challenge-card"
                  style={{ background: item.bg }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = item.hoverBorder
                    e.currentTarget.style.boxShadow = item.hoverShadow
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,.09)'
                    e.currentTarget.style.boxShadow = 'none'
                  }}
                >
                  <div
                    className="fx-challenge-icon"
                    style={{ background: item.iconBg, borderColor: item.border, color: item.accent }}
                  >
                    <Icon size={28} fill={item.type === 'do' ? 'currentColor' : 'none'} stroke={item.type === 'do' ? 'none' : 'currentColor'} />
                  </div>
                  <h3>{item.label}</h3>
                  <p>{item.desc}</p>
                </Link>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
