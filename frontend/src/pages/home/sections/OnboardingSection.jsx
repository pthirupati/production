import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Terminal, BookOpen, Sparkles } from '../../../ui/eagerIcons'
import { blurIn, fadeUp, staggerContainer, viewportOnce } from '../../../ui/motion'

/**
 * Absolute-beginner on-ramp ("start here"). Gives newcomers one unambiguous
 * first step instead of dropping them into 7,000+ scenarios.
 *
 * This used to be titled "Start with Linux Basics" and every step pointed at
 * Linux, with the sub-copy asking "Brand new to DevOps and SRE?". The platform
 * spans 46 technologies including a GPU/AI-infrastructure track, LLM and agent
 * labs, data science, cloud, VMware and Windows — so a visitor arriving for any
 * of those was told, on the home page, that this product is for Linux/DevOps
 * people. Now the learner picks a track and the three steps follow it.
 */
const TRACKS = [
  {
    id: 'linux',
    label: 'Linux & Cloud Ops',
    tutorial: '/tutorials/linux-command-line-basics',
    firstLab: 'academy-linux-001-learn-users-groups',
    tech: 'linux',
    basics: 'the Linux command line',
    path: 'Linux',
  },
  {
    id: 'ai',
    label: 'AI Infra & GPUs',
    tutorial: '/tutorials/gpu-nvidia-zero-hero',
    firstLab: 'academy-gpu-001-learn-drivers',
    tech: 'gpu',
    basics: 'GPUs, drivers and CUDA',
    path: 'GPU & AI infrastructure',
  },
  {
    id: 'data',
    label: 'Data & ML',
    tutorial: '/tutorials/data-science-zero-hero',
    firstLab: 'academy-data-science-001-learn-cleaning',
    tech: 'data-science',
    basics: 'pandas, SQL and real datasets',
    path: 'data science',
  },
  {
    id: 'k8s',
    label: 'Containers & K8s',
    tutorial: '/tutorials/docker-containers-zero-hero',
    firstLab: 'academy-kubernetes-001-learn-pods',
    tech: 'kubernetes',
    basics: 'containers and Kubernetes',
    path: 'container platform',
  },
]

export default function OnboardingSection({ isAuthenticated }) {
  const [trackId, setTrackId] = useState(TRACKS[0].id)
  const track = TRACKS.find((t) => t.id === trackId) || TRACKS[0]

  const steps = [
    {
      icon: BookOpen,
      title: 'Learn the basics',
      desc: `A short, plain-English tutorial on ${track.basics} — no prior experience needed.`,
      to: track.tutorial,
      cta: 'Read the tutorial',
    },
    {
      icon: Terminal,
      title: 'Fix your first lab',
      desc: 'Jump into a real environment and solve a guided beginner task. We walk you through it.',
      to: isAuthenticated ? `/scenarios/${track.firstLab}` : '/register',
      cta: 'Open the lab',
    },
    {
      icon: Sparkles,
      title: 'Build a streak',
      desc: `Follow the curated ${track.path} path, earn XP, and unlock harder break/fix scenarios.`,
      to: `/technologies/${track.tech}`,
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
          <h2 className="fx-home-title">Start from zero — pick your track</h2>
          <p className="fx-home-sub mx-auto">
            Whether you are heading for cloud ops, GPUs and AI infrastructure, data and ML, or
            container platforms — three short steps from zero to your first solved lab.
          </p>

          <div className="flex flex-wrap justify-center gap-2 mt-7">
            {TRACKS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTrackId(t.id)}
                aria-pressed={t.id === trackId}
                className="px-3.5 py-2 rounded-full text-xs font-semibold transition-colors"
                style={
                  t.id === trackId
                    ? { background: 'rgba(6,182,212,.16)', border: '1px solid rgba(6,182,212,.5)', color: '#67e8f9' }
                    : { background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.1)', color: 'rgba(255,255,255,.62)' }
                }
              >
                {t.label}
              </button>
            ))}
          </div>
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
