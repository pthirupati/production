import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { blurIn, viewportOnce } from '../../../ui/motion'

export default function PricingCTASection() {
  return (
    <section id="pricing" className="fx-home-section overflow-hidden" style={{ paddingTop: 0, paddingBottom: 120 }}>
      <motion.div
        className="fx-pricing-cta"
        initial="hidden"
        whileInView="visible"
        viewport={viewportOnce}
        variants={blurIn}
      >
        <div className="fx-pricing-cta-grid" aria-hidden="true" />
        <div className="fx-pricing-cta-glow" aria-hidden="true" />

        <div className="relative">
          <div
            className="fx-home-eyebrow mx-auto"
            style={{ background: 'rgba(109,120,255,.14)', border: '1px solid rgba(109,120,255,.3)', color: '#aeb4ff' }}
          >
            Get started today
          </div>
          <h2 className="fx-home-title text-[clamp(2rem,5vw,52px)] mb-5">Ready to prove your skills?</h2>
          <p className="fx-home-sub mx-auto mb-10 max-w-[560px]">
            Free labs always available. Subscribe per technology at prices that keep hands-on practice affordable.
            Promo codes apply automatically at checkout. Your lab is yours alone — fully isolated from every other user.
          </p>

          <div className="flex gap-[14px] justify-center flex-wrap mb-9">
            <Link to="/register" data-magnetic className="fx-btn-primary text-[17px] px-8 py-[17px]">
              Start fixing free <ArrowRight size={17} />
            </Link>
            <Link to="/pricing" className="fx-btn-secondary text-[17px] px-[30px] py-[17px]">
              View pricing
            </Link>
          </div>

          <div className="flex justify-center gap-7 flex-wrap text-sm text-white/55">
            {[
              'Try free — no card required',
              'Isolated lab in 30 seconds',
              'Coupons auto-apply at checkout',
            ].map(text => (
              <span key={text} className="inline-flex items-center gap-[7px]">
                <CheckCircle2 size={15} className="text-[#56e0b0]" strokeWidth={2.4} />
                {text}
              </span>
            ))}
          </div>
        </div>
      </motion.div>
    </section>
  )
}
