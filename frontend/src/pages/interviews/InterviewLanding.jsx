import { useState } from 'react'
import { Link } from 'react-router-dom'
import PublicLayout from '../../components/layout/PublicLayout'
import { PageHeader } from '../../components/design'
import { useAuthStore } from '../../store/authStore'
import { usePageTitle } from '../../hooks/usePageTitle'
import {
  Mic, Video, Calendar, Award, CheckCircle2, ArrowRight, Sparkles, Shield,
  Star, Users, TrendingUp, ChevronRight, Play, Linkedin,
} from 'lucide-react'

const FEATURE_PILLS = [
  { label: 'Voice-based', color: 'text-accent-cyan border-accent-cyan/30 bg-accent-cyan/10' },
  { label: 'Face-to-face', color: 'text-accent-purple border-accent-purple/30 bg-accent-purple/10' },
  { label: 'STAR scoring', color: 'text-accent-green border-accent-green/30 bg-accent-green/10' },
  { label: '3–5 rounds', color: 'text-accent-amber border-accent-amber/30 bg-accent-amber/10' },
  { label: 'LinkedIn certificate', color: 'text-accent-blue border-accent-blue/30 bg-accent-blue/10' },
  { label: 'Resume-aware', color: 'text-accent-pink border-accent-pink/30 bg-accent-pink/10' },
]

const HOW_IT_WORKS = [
  {
    step: '01',
    icon: Calendar,
    title: 'Setup',
    desc: 'Upload your resume, pick a role and schedule a 3–5 round cycle within 48 hours. The AI tailors questions to your experience.',
    color: 'text-accent-cyan',
    bg: 'bg-accent-cyan/10',
    border: 'border-accent-cyan/20',
  },
  {
    step: '02',
    icon: Video,
    title: 'Live Interview',
    desc: 'Join your face-to-face AI video session. Camera and mic required. Voice-based, real-time questions across Technical, HR, Manager, and Leadership rounds.',
    color: 'text-accent-purple',
    bg: 'bg-accent-purple/10',
    border: 'border-accent-purple/20',
  },
  {
    step: '03',
    icon: Award,
    title: 'Score + Certificate',
    desc: 'Get a detailed STAR-scored feedback report, study plan links, and — if you clear all rounds — a verifiable FIXIT-INT LinkedIn certificate.',
    color: 'text-accent-green',
    bg: 'bg-accent-green/10',
    border: 'border-accent-green/20',
  },
]

const PLANS = [
  {
    name: 'Free Sample',
    price: '₹0',
    detail: '10 min · one-time preview',
    features: ['1 mini-round sample', 'Voice interview', 'Basic feedback'],
    highlight: false,
  },
  {
    name: 'Interview Pro',
    price: '₹999',
    period: '/yr',
    detail: '10 attempts · 3 rounds each',
    features: ['10 full attempts/yr', 'Technical, HR & Manager rounds', 'STAR-scored reports', 'Study plan links'],
    highlight: true,
  },
  {
    name: 'Premium',
    price: '₹2,499',
    period: '/yr',
    detail: '10 attempts · 5 rounds · certificate',
    features: ['10 full attempts/yr', 'All 5 round types incl. Leadership', 'STAR-scored reports + study plan', 'FIXIT-INT LinkedIn certificate'],
    highlight: false,
  },
]

const TESTIMONIALS = [
  {
    name: 'Priya S.',
    role: 'SRE at Flipkart',
    quote: 'The face-to-face format was surprisingly close to the real thing. STAR scoring feedback helped me fix my answers before the actual loop.',
    rating: 5,
  },
  {
    name: 'Arjun M.',
    role: 'DevOps Engineer at Razorpay',
    quote: 'I loved that it adapted to my Linux answers with harder follow-ups. The LinkedIn certificate was a great addition to my profile.',
    rating: 5,
  },
  {
    name: 'Sneha T.',
    role: 'Cloud Architect at TCS',
    quote: 'Scheduled my 5-round cycle in under 2 minutes. The post-round feedback report with links was actionable and specific.',
    rating: 5,
  },
]

const CHECKLIST_ITEMS = [
  'Resume upload for personalized technical & HR questions',
  'Adaptive difficulty after strong answers',
  'Hands-on troubleshooting segments in the answer panel',
  'Post-round feedback report with study plan links',
  'Public certificate verification (FIXIT-INT-*)',
  'Indian, UK, and US accent voice options',
]

export default function InterviewLanding() {
  const { isAuthenticated } = useAuthStore()
  const [activeTestimonial, setActiveTestimonial] = useState(0)

  usePageTitle(
    'AI Mock Interview Studio',
    'Multi-round face-to-face AI video interviews with resume-aware questions, voice, STAR scoring, scheduling, and LinkedIn certificates.',
  )

  const ctaTo = isAuthenticated ? '/interviews' : '/register'

  return (
    <PublicLayout>
      <div className="relative overflow-hidden bg-surface-950">
        {/* Background glows */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 right-1/4 w-[500px] h-[500px] bg-indigo-500/[0.06] rounded-full blur-[120px]" />
          <div className="absolute bottom-40 left-1/4 w-[400px] h-[400px] bg-purple-500/[0.05] rounded-full blur-[100px]" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[300px] bg-cyan-500/[0.03] rounded-full blur-[150px]" />
        </div>

        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 relative">

          {/* HERO */}
          <div className="text-center mb-16 animate-fade-in">
            <PageHeader
              eyebrow="AI Interview Studio · Now in Beta"
              title="Face-to-Face AI Video Interviews"
              subtitle="Not a chatbot. A real video call with an AI interviewer — camera on, mic live, multi-round, STAR-scored, with a verifiable certificate at the end."
              className="text-center [&_.flex]:justify-center [&_h1]:mx-auto [&_p]:mx-auto [&_h1]:text-4xl [&_h1]:sm:text-5xl [&_h1]:lg:text-6xl"
            />

            {/* Feature pills */}
            <div className="flex flex-wrap justify-center gap-2 mb-8">
              {FEATURE_PILLS.map(({ label, color }) => (
                <span key={label} className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${color}`}>
                  {label}
                </span>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                to={ctaTo}
                className="btn-primary inline-flex items-center justify-center gap-2 px-8 py-3 text-base animate-pulse-glow"
              >
                {isAuthenticated ? 'Start free sample' : 'Sign up & try free'} <ArrowRight size={18} />
              </Link>
              <a
                href="#interview-plans"
                className="btn-secondary inline-flex items-center justify-center gap-2 px-8 py-3 text-base"
              >
                View plans
              </a>
            </div>

            <p className="text-xs text-emerald-400 mt-5 flex items-center justify-center gap-1.5">
              <Shield size={12} /> Browser-based &middot; Privacy-first &middot; No app install needed
            </p>
          </div>

          {/* MOCK VIDEO CALL UI */}
          <div className="mb-20 animate-slide-up">
            <div className="relative max-w-3xl mx-auto">
              {/* Outer glow frame */}
              <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-indigo-500/30 via-purple-500/20 to-pink-500/30 blur-sm" />
              <div className="relative bg-surface-900 border border-surface-700/60 rounded-2xl overflow-hidden shadow-2xl">
                {/* Simulated browser chrome */}
                <div className="flex items-center gap-2 px-4 py-3 bg-surface-800/80 border-b border-surface-700/50">
                  <div className="w-3 h-3 rounded-full bg-red-400/70" />
                  <div className="w-3 h-3 rounded-full bg-amber-400/70" />
                  <div className="w-3 h-3 rounded-full bg-emerald-400/70" />
                  <div className="flex-1 mx-4 bg-surface-700/60 rounded px-3 py-1 text-[10px] text-surface-400 text-center">
                    app.fixitlab.com/interviews/session/INT-1042
                  </div>
                  <div className="w-6 h-6 rounded-full bg-red-500/20 border border-red-500/30 flex items-center justify-center">
                    <div className="w-2 h-2 rounded-full bg-red-400/80 animate-pulse" />
                  </div>
                </div>

                {/* Video tiles */}
                <div className="grid grid-cols-2 gap-2 p-3 bg-surface-950">
                  {/* AI Interviewer tile */}
                  <div className="relative aspect-video rounded-xl bg-gradient-to-br from-indigo-900/60 to-surface-900 border border-indigo-500/20 overflow-hidden flex items-center justify-center">
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                    <div className="relative flex flex-col items-center gap-2">
                      <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                        <Sparkles size={28} className="text-white" />
                      </div>
                      {/* Sound bars */}
                      <div className="flex items-end gap-0.5 h-4">
                        {[3, 6, 4, 7, 3, 5, 4, 6].map((h, i) => (
                          <div
                            key={i}
                            className="w-1 bg-indigo-400/80 rounded-full animate-pulse"
                            style={{ height: `${h * 2}px`, animationDelay: `${i * 0.1}s` }}
                          />
                        ))}
                      </div>
                    </div>
                    <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
                      <span className="text-[10px] sm:text-xs font-medium text-white bg-black/50 px-2 py-0.5 rounded-full">
                        AI Interviewer
                      </span>
                      <span className="flex items-center gap-1 text-[9px] text-emerald-400 bg-emerald-400/20 px-1.5 py-0.5 rounded-full">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Live
                      </span>
                    </div>
                  </div>

                  {/* Candidate tile */}
                  <div className="relative aspect-video rounded-xl bg-gradient-to-br from-surface-800 to-surface-900 border border-surface-600/40 overflow-hidden flex items-center justify-center">
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                    <div className="relative flex flex-col items-center gap-2">
                      <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-gradient-to-br from-surface-600 to-surface-700 border-2 border-surface-500/40 flex items-center justify-center">
                        <Users size={28} className="text-surface-400" />
                      </div>
                      <div className="flex items-end gap-0.5 h-4 opacity-40">
                        {[2, 4, 3, 5, 2, 4, 3].map((h, i) => (
                          <div
                            key={i}
                            className="w-1 bg-surface-400/60 rounded-full"
                            style={{ height: `${h * 2}px` }}
                          />
                        ))}
                      </div>
                    </div>
                    <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
                      <span className="text-[10px] sm:text-xs font-medium text-white bg-black/50 px-2 py-0.5 rounded-full">
                        You
                      </span>
                      <div className="flex items-center gap-1">
                        <div className="w-5 h-5 rounded-full bg-surface-700/80 flex items-center justify-center">
                          <Mic size={10} className="text-surface-300" />
                        </div>
                        <div className="w-5 h-5 rounded-full bg-surface-700/80 flex items-center justify-center">
                          <Video size={10} className="text-surface-300" />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Interview HUD */}
                <div className="px-3 pb-3 bg-surface-950">
                  <div className="bg-surface-800/60 border border-surface-700/40 rounded-xl p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-surface-500 mb-0.5">Current question</p>
                      <p className="text-sm text-white font-medium leading-snug">
                        "Tell me about a time you resolved a production outage under pressure."
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-center">
                        <p className="text-[10px] text-surface-500">Round</p>
                        <p className="text-sm font-bold text-white">2/3</p>
                      </div>
                      <div className="text-center">
                        <p className="text-[10px] text-surface-500">STAR</p>
                        <p className="text-sm font-bold text-emerald-400">87%</p>
                      </div>
                      <div className="flex items-center gap-1 px-2 py-1 bg-red-500/10 border border-red-500/20 rounded-lg">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                        <span className="text-[10px] text-red-400 font-mono font-bold">03:42</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Floating trust badges */}
              <div className="absolute -right-4 top-1/4 hidden lg:flex flex-col gap-2">
                <div className="glass-card px-3 py-2 text-xs text-surface-300 flex items-center gap-2 shadow-lg animate-float">
                  <Shield size={12} className="text-emerald-400" /> Privacy-first
                </div>
                <div className="glass-card px-3 py-2 text-xs text-surface-300 flex items-center gap-2 shadow-lg animate-float" style={{ animationDelay: '0.5s' }}>
                  <Linkedin size={12} className="text-blue-400" /> Certificate
                </div>
              </div>
            </div>
          </div>

          {/* HOW IT WORKS */}
          <div className="mb-20">
            <div className="text-center mb-10">
              <p className="text-xs uppercase tracking-widest text-accent-cyan font-semibold mb-2">Simple 3-step process</p>
              <h2 className="text-3xl font-bold text-white">How it works</h2>
            </div>
            <div className="grid sm:grid-cols-3 gap-6 relative">
              {/* Connector line desktop */}
              <div className="hidden sm:block absolute top-10 left-[calc(16.67%+1rem)] right-[calc(16.67%+1rem)] h-px bg-gradient-to-r from-cyan-500/30 via-purple-500/30 to-emerald-500/30" />

              {HOW_IT_WORKS.map(({ step, icon: Icon, title, desc, color, bg, border }) => (
                <div key={step} className={`glass-card p-6 border ${border} hover:scale-[1.02] transition-all duration-300 group`}>
                  <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}>
                    <Icon size={24} className={color} />
                  </div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className={`text-3xl font-extrabold ${color} opacity-20`}>{step}</span>
                    <h3 className="text-lg font-bold text-white">{title}</h3>
                  </div>
                  <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* PRICING CARDS */}
          <div id="interview-plans" className="mb-20 scroll-mt-20">
            <div className="text-center mb-10">
              <p className="text-xs uppercase tracking-widest text-indigo-400 font-semibold mb-2">Yearly plans</p>
              <h2 className="text-3xl font-bold text-white mb-3">Simple, honest pricing</h2>
              <p className="text-surface-400 text-sm max-w-lg mx-auto">
                Admins can grant complimentary access. Staff get free interviews by default.
              </p>
            </div>
            <div className="grid sm:grid-cols-3 gap-6 max-w-4xl mx-auto">
              {PLANS.map((plan) => (
                <div
                  key={plan.name}
                  className={`relative glass-card p-6 flex flex-col transition-all duration-300 hover:-translate-y-1 ${
                    plan.highlight
                      ? 'border-indigo-500/40 bg-indigo-500/5 shadow-lg shadow-indigo-500/10'
                      : 'hover:border-surface-600/60'
                  }`}
                >
                  {plan.highlight && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 text-[10px] font-bold text-white uppercase tracking-wider shadow-lg">
                      Most Popular
                    </div>
                  )}
                  <div className="mb-4">
                    <p className="text-sm font-semibold text-surface-300 mb-1">{plan.name}</p>
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-extrabold text-white">{plan.price}</span>
                      {plan.period && <span className="text-surface-500 text-sm">{plan.period}</span>}
                    </div>
                    <p className="text-xs text-surface-500 mt-1">{plan.detail}</p>
                  </div>
                  <ul className="space-y-2 mb-6 flex-1">
                    {plan.features.map(f => (
                      <li key={f} className="flex items-start gap-2 text-sm text-surface-300">
                        <CheckCircle2 size={15} className="text-indigo-400 shrink-0 mt-0.5" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Link
                    to="/pricing#interview-plans"
                    className={`w-full text-center py-2.5 rounded-lg font-semibold text-sm transition-all flex items-center justify-center gap-2 ${
                      plan.highlight ? 'btn-primary' : 'btn-secondary'
                    }`}
                  >
                    {plan.price === '₹0' ? 'Try free' : 'Get started'} <ChevronRight size={15} />
                  </Link>
                </div>
              ))}
            </div>
          </div>

          {/* TESTIMONIALS */}
          <div className="mb-20">
            <div className="text-center mb-8">
              <p className="text-xs uppercase tracking-widest text-accent-green font-semibold mb-2">Community</p>
              <h2 className="text-2xl font-bold text-white">What candidates say</h2>
            </div>
            <div className="max-w-3xl mx-auto">
              <div className="glass-card p-8 border border-surface-700/60 transition-all duration-300">
                <div className="flex gap-1 mb-4">
                  {[...Array(TESTIMONIALS[activeTestimonial].rating)].map((_, i) => (
                    <Star key={i} size={16} className="text-amber-400 fill-amber-400" />
                  ))}
                </div>
                <p className="text-surface-200 text-base leading-relaxed mb-5 italic">
                  "{TESTIMONIALS[activeTestimonial].quote}"
                </p>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-sm font-bold">
                    {TESTIMONIALS[activeTestimonial].name[0]}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{TESTIMONIALS[activeTestimonial].name}</p>
                    <p className="text-xs text-surface-500">{TESTIMONIALS[activeTestimonial].role}</p>
                  </div>
                </div>
              </div>
              <div className="flex justify-center gap-2 mt-4">
                {TESTIMONIALS.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveTestimonial(i)}
                    className={`h-2 rounded-full transition-all duration-200 ${
                      i === activeTestimonial ? 'bg-indigo-400 w-6' : 'w-2 bg-surface-600 hover:bg-surface-500'
                    }`}
                    aria-label={`Testimonial ${i + 1}`}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* FEATURE CHECKLIST */}
          <div className="glass-card p-8 border border-indigo-500/10 mb-20">
            <div className="flex items-center gap-2 mb-6">
              <TrendingUp size={20} className="text-indigo-400" />
              <h2 className="text-lg font-bold text-white">Everything included</h2>
            </div>
            <ul className="grid sm:grid-cols-2 gap-x-8 gap-y-3">
              {CHECKLIST_ITEMS.map(item => (
                <li key={item} className="flex items-start gap-2 text-sm text-surface-300">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* TRUST INDICATORS */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-20">
            {[
              { value: '5,000+', label: 'Interviews completed', icon: Play },
              { value: '93%', label: 'Candidate satisfaction', icon: Star },
              { value: '3–5', label: 'Rounds per cycle', icon: Calendar },
              { value: '48h', label: 'Max scheduling window', icon: Award },
            ].map(({ value, label, icon: Icon }) => (
              <div key={label} className="glass-card p-4 text-center group hover:border-indigo-500/20 transition-all">
                <Icon size={20} className="text-indigo-400 mx-auto mb-2 group-hover:scale-110 transition-transform" />
                <p className="text-2xl font-extrabold text-white">{value}</p>
                <p className="text-xs text-surface-500 mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* FINAL CTA */}
          <div className="text-center">
            <div className="relative inline-block w-full max-w-xl">
              <div className="absolute -inset-2 rounded-2xl bg-gradient-to-r from-indigo-500/20 via-purple-500/20 to-pink-500/20 blur-lg" />
              <div className="relative glass-card px-8 py-10 border border-indigo-500/20">
                <Sparkles size={32} className="text-indigo-400 mx-auto mb-4 animate-pulse" />
                <h2 className="text-2xl sm:text-3xl font-extrabold text-white mb-3">
                  Ready for your next{' '}
                  <span className="bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                    big interview?
                  </span>
                </h2>
                <p className="text-surface-400 text-sm mb-7 max-w-md mx-auto">
                  Start with a free 10-minute sample, no credit card required. Upgrade when you're ready for the full cycle.
                </p>
                <Link
                  to={ctaTo}
                  className="btn-primary inline-flex items-center gap-2 px-10 py-3.5 text-base animate-pulse-glow"
                >
                  {isAuthenticated ? 'Launch your interview' : 'Get started for free'} <ArrowRight size={18} />
                </Link>
                <p className="text-xs text-surface-600 mt-4 flex items-center justify-center gap-1">
                  <Shield size={11} /> Browser voice &middot; No install &middot; Privacy-first
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>
    </PublicLayout>
  )
}
