import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Play } from 'lucide-react'
import InterviewShowcase from '../components/InterviewShowcase'
import { interviewBullets } from '../data/homeContent'
import { fadeLeft, fadeRight, viewportOnce } from '../../../ui/motion'

export default function InterviewSection({ isAuthenticated }) {
  return (
    <section id="interview" className="fx-home-section overflow-hidden">
      <div
        className="absolute inset-[-120px] pointer-events-none"
        aria-hidden="true"
        data-parallax="0.1"
        style={{ background: 'linear-gradient(135deg, rgba(88,28,135,.28) 0%, rgba(139,92,246,.12) 42%, rgba(12,10,28,0) 72%)' }}
      />
      <div
        className="absolute left-[-120px] top-[20%] w-[480px] h-[480px] rounded-full pointer-events-none"
        aria-hidden="true"
        style={{ background: 'radial-gradient(circle, var(--fx-ac2) 0%, transparent 65%)', opacity: 0.2, filter: 'blur(30px)', animation: 'fxFloat 15s ease-in-out infinite' }}
      />

      <div className="fx-home-section-inner grid lg:grid-cols-2 gap-[72px] items-center relative">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeLeft}
        >
          <div
            className="fx-home-eyebrow"
            style={{ background: 'rgba(178,102,224,.14)', border: '1px solid rgba(178,102,224,.3)', color: '#d6a8ee' }}
          >
            AI Interview Studio
          </div>
          <h2 className="fx-home-title">Get hired faster with face-to-face AI interviews</h2>
          <p className="fx-home-sub mb-9">
            Sit across from a live AI interviewer in a real video-call interface. Technical, behavioral, and system-design rounds — resume-aware questions, instant STAR scoring, and actionable feedback.
          </p>

          <div className="flex flex-col gap-5 mb-10">
            {interviewBullets.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-[15px]">
                <div
                  className="w-10 h-10 rounded-[11px] shrink-0 flex items-center justify-center"
                  style={{ background: 'rgba(178,102,224,.12)', border: '1px solid rgba(178,102,224,.25)', color: '#d6a8ee' }}
                >
                  <Icon size={17} />
                </div>
                <div>
                  <p className="font-semibold text-base text-white m-0 mb-0.5">{title}</p>
                  <p className="text-sm leading-relaxed text-white/52 m-0">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              to={isAuthenticated ? '/interviews' : '/register'}
              data-magnetic
              className="fx-btn-primary"
              style={{ background: 'linear-gradient(135deg, var(--fx-ac2), var(--fx-ac))', boxShadow: '0 10px 34px rgba(178,102,224,.38)' }}
            >
              Start a mock interview <ArrowRight size={16} />
            </Link>
            <Link to="/mock-interviews" className="fx-btn-secondary">
              <Play size={14} fill="currentColor" stroke="none" /> Watch Demo
            </Link>
          </div>
        </motion.div>

        <motion.div
          className="hidden lg:block"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeRight}
        >
          <InterviewShowcase />
        </motion.div>
      </div>

      <div className="lg:hidden mt-14 px-8">
        <InterviewShowcase />
      </div>
    </section>
  )
}
