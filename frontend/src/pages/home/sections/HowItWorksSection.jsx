import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { howItWorksSteps } from '../data/homeContent'
import { blurIn, fadeUp, staggerContainer, viewportOnce } from '../../../ui/motion'

export default function HowItWorksSection() {
  return (
    <section className="fx-home-section overflow-hidden" style={{ paddingTop: 0 }}>
      <div className="fx-home-section-inner max-w-[1100px]">
        <motion.div
          className="text-center max-w-[640px] mx-auto mb-16"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={blurIn}
        >
          <div
            className="fx-home-eyebrow mx-auto"
            style={{ background: 'rgba(254,177,85,.1)', border: '1px solid rgba(254,177,85,.25)', color: '#feb155' }}
          >
            How it works
          </div>
          <h2 className="fx-home-title">Up and running in 30 seconds</h2>
          <p className="fx-home-sub mx-auto">
            No setup. No SSH keys. No VMs to configure. Just click and fix.
          </p>
        </motion.div>

        <motion.div
          className="fx-how-grid"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
        >
          <div className="fx-how-line" aria-hidden="true" />

          {howItWorksSteps.map(({ step, title, desc, icon: Icon, color, bg, border, delay }) => (
            <motion.div key={step} className="fx-how-step text-center relative z-[1]" variants={fadeUp}>
              <div
                className="fx-how-step-icon"
                style={{ background: bg, border: `1px solid ${border}`, color, animationDelay: delay }}
              >
                <Icon size={30} strokeWidth={1.6} />
              </div>
              <div
                className="fx-how-step-pill"
                style={{ color, background: `${bg}`, borderColor: border }}
              >
                Step {step}
              </div>
              <h3>{title}</h3>
              <p>{desc}</p>
            </motion.div>
          ))}
        </motion.div>

        <motion.div
          className="mt-16 text-center"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
        >
          <Link to="/register" data-magnetic className="fx-btn-primary inline-flex">
            Try Your First Challenge Free <ArrowRight size={17} />
          </Link>
        </motion.div>
      </div>
    </section>
  )
}
