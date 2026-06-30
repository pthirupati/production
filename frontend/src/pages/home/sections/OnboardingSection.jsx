import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Terminal, BookOpen, Sparkles } from 'lucide-react'
import { blurIn, fadeUp, staggerContainer, viewportOnce } from '../../../ui/motion'

// Absolute-beginner on-ramp ("start here"). Gives newcomers a single,
// unambiguous first step instead of dropping them into 5,000 scenarios.
export default function OnboardingSection({ isAuthenticated }) {
  const steps = [
    {
      icon: BookOpen,
      title: 'Learn the basics',
      desc: 'A short, plain-English tutorial on the Linux command line — no prior experience needed.',
      to: '/tutorials/linux-command-line-basics',
      cta: 'Read the tutorial',
    },
    {
      icon: Terminal,
      title: 'Fix your first lab',
      desc: 'Jump into a real terminal and solve a guided beginner task. We walk you through it.',
      to: isAuthenticated ? '/scenarios/academy-linux-001-learn-users-groups' : '/register',
      cta: 'Open the lab',
    },
    {
      icon: Sparkles,
      title: 'Build a streak',
      desc: 'Follow the curated Linux path, earn XP, and unlock harder break/fix scenarios.',
      to: '/technologies/linux',
      cta: 'See the path',
    },
  ]

  return (
    <section className="fx-home-section overflow-hidden">
      <div className="fx-home-section-inner max-w-[1100px]">
        <motion.div
          className="text-center max-w-[640px] mx-auto mb-12"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={blurIn}
        >
          <div
            className="fx-home-eyebrow mx-auto"
            style={{ background: 'rgba(6,182,212,.1)', border: '1px solid rgba(6,182,212,.25)', color: '#22d3ee' }}
          >
            New here?
          </div>
          <h2 className="fx-home-title">Start with Linux Basics</h2>
          <p className="fx-home-sub mx-auto">
            Brand new to DevOps and SRE? Take the absolute-beginner path — three short steps from zero to your first solved lab.
          </p>
        </motion.div>

        <motion.div
          className="grid gap-4 sm:grid-cols-3"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
        >
          {steps.map(({ icon: Icon, title, desc, to, cta }, i) => (
            <motion.div key={title} variants={fadeUp}>
              <Link
                to={to}
                data-magnetic
                className="group flex h-full flex-col rounded-2xl p-6 transition-colors"
                style={{ background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.08)' }}
              >
                <div className="flex items-center gap-3 mb-3">
                  <span
                    className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: 'rgba(6,182,212,.12)', border: '1px solid rgba(6,182,212,.25)', color: '#22d3ee' }}
                  >
                    <Icon size={18} strokeWidth={1.8} />
                  </span>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-white/40">
                    Step {i + 1}
                  </span>
                </div>
                <h3 className="text-base font-bold text-white mb-1.5">{title}</h3>
                <p className="text-sm text-white/55 leading-relaxed flex-1">{desc}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-accent-cyan group-hover:gap-2 transition-all">
                  {cta} <ArrowRight size={15} />
                </span>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
