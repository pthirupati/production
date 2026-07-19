import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Play } from 'lucide-react'
import { HeroShowcase } from '../../../components/marketing'
import { fadeUp, staggerContainer } from '../../../ui/motion'

export default function HeroSection({ technologies, stats = {} }) {
  const techCount = technologies.filter(t => !t.coming_soon).length || stats.total_technologies || 8

  return (
    <section id="top" className="fx-hero">
      <div className="fx-hero-bg" aria-hidden="true" />
      <div className="fx-hero-grid-bg" aria-hidden="true" data-parallax="0.06" />
      <div
        className="fx-hero-orb"
        aria-hidden="true"
        style={{ top: '-180px', left: '8%', width: 560, height: 560, background: 'radial-gradient(circle, var(--fx-ac3) 0%, transparent 65%)', opacity: 0.3, animation: 'fxFloat 13s ease-in-out infinite' }}
      />
      <div
        className="fx-hero-orb"
        aria-hidden="true"
        style={{ top: 80, right: -100, width: 520, height: 520, background: 'radial-gradient(circle, var(--fx-ac2) 0%, transparent 65%)', opacity: 0.26, animation: 'fxFloatX 16s ease-in-out infinite' }}
      />
      <div
        className="fx-hero-orb"
        aria-hidden="true"
        style={{ bottom: -220, left: '38%', width: 480, height: 480, background: 'radial-gradient(circle, var(--fx-ac) 0%, transparent 65%)', opacity: 0.22, animation: 'fxMorph 18s ease-in-out infinite' }}
      />

      <motion.div
        className="fx-hero-inner"
        initial="hidden"
        animate="visible"
        variants={staggerContainer}
      >
        <div>
          <motion.div className="fx-hero-eyebrow" variants={fadeUp}>
            <span className="fx-pulse-dot" style={{ background: '#56e0b0' }} />
            Production-grade labs · Jira tickets · AI interviews
          </motion.div>
          <motion.h1 className="fx-hero-h1" variants={fadeUp}>
            Break things.<br />
            <span className="fx-hero-gradient-text">Fix them.</span> Get hired.
          </motion.h1>
          <motion.p className="fx-hero-lead" variants={fadeUp}>
            Train like your whole platform team is on call — isolated break-fix labs across 30+ technologies
            (Linux, cloud, containers, networking, databases, VMware, Ansible, security, and more).
            Pick up a Jira incident, SSH into a real environment, fix it under time pressure, and prove it with
            instant validation. Then sit a voice AI interview and earn verifiable certificates — all at a
            price that makes serious hands-on practice affordable.
          </motion.p>
          <motion.div className="fx-hero-cta-row" variants={fadeUp}>
            <Link to="/register" data-magnetic className="fx-btn-primary">
              Start fixing free <ArrowRight size={17} />
            </Link>
            <Link to="/register" className="fx-btn-secondary">
              <Play size={16} fill="currentColor" stroke="none" /> Browse challenges
            </Link>
          </motion.div>
          <motion.div className="fx-hero-stats" variants={fadeUp}>
            <div>
              <div className="fx-hero-stat-val">{stats.total_technologies || techCount}</div>
              <div className="fx-hero-stat-label">Technologies</div>
            </div>
            <div>
              <div className="fx-hero-stat-val">{stats.total_scenarios ? `${stats.total_scenarios}+` : '5,000+'}</div>
              <div className="fx-hero-stat-label">Hands-on scenarios</div>
            </div>
            <div>
              <div className="fx-hero-stat-val">Per-user isolated</div>
              <div className="fx-hero-stat-label">Isolated lab environments</div>
            </div>
          </motion.div>
        </div>

        <motion.div variants={fadeUp} className="order-first lg:order-none">
          <HeroShowcase />
        </motion.div>
      </motion.div>
    </section>
  )
}
