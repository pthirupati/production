import { Link } from 'react-router-dom'
import PublicLayout from '../../components/layout/PublicLayout'
import { useAuthStore } from '../../store/authStore'
import { usePageTitle } from '../../hooks/usePageTitle'
import {
  Mic, Video, Calendar, Award, CheckCircle2, ArrowRight, Sparkles, Shield,
} from 'lucide-react'

const FEATURES = [
  { icon: Mic, title: 'Voice mock interviews', desc: 'Browser-based voices — Indian, UK, and US accents.' },
  { icon: Video, title: 'Camera & mic required', desc: 'Realistic interview conditions with professional presence scoring.' },
  { icon: Calendar, title: '3–5 round cycles', desc: 'Technical, manager, HR, deep-dive, and leadership panels — schedule within 48h.' },
  { icon: Award, title: 'Verifiable certificates', desc: 'Clear all rounds and earn a FIXIT-INT certificate you can share on LinkedIn.' },
]

const PLANS = [
  { name: 'Free sample', price: '₹0', detail: '10 min · one-time preview' },
  { name: 'Interview Pro', price: '₹999/yr', detail: '10 attempts · 3 rounds each' },
  { name: 'Premium', price: '₹2,499/yr', detail: '10 attempts · 5 rounds · certificate' },
]

export default function InterviewLanding() {
  const { isAuthenticated } = useAuthStore()
  usePageTitle(
    'AI Mock Interview Studio',
    'Multi-round voice mock interviews with resume-aware questions, browser TTS, scheduling, and LinkedIn certificates.',
  )

  const ctaTo = isAuthenticated ? '/interviews' : '/register'

  return (
    <PublicLayout>
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-1/3 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl" />
        </div>

        <div className="max-w-5xl mx-auto px-4 py-16 relative">
          <div className="text-center mb-14 animate-fade-in">
            <p className="text-xs uppercase tracking-widest text-indigo-400 font-semibold mb-3">AI Interview Studio</p>
            <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4">
              Mock interviews that feel{' '}
              <span className="bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">real</span>
            </h1>
            <p className="text-surface-400 text-lg max-w-2xl mx-auto">
              Multi-round voice interviews tailored to your resume. Try a free 10-minute sample, then subscribe for full cycles and certificates.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center mt-8">
              <Link to={ctaTo} className="btn-primary inline-flex items-center justify-center gap-2 px-8 py-3">
                {isAuthenticated ? 'Try free sample' : 'Sign up & try free'} <ArrowRight size={18} />
              </Link>
              <Link to="/pricing#interview-plans" className="btn-secondary inline-flex items-center justify-center gap-2 px-8 py-3">
                View plans
              </Link>
            </div>
            <p className="text-xs text-emerald-400 mt-4 flex items-center justify-center gap-1">
              <Shield size={12} /> Browser voice · Privacy-first
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-4 mb-14">
            {FEATURES.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="glass-card p-5 border border-surface-800">
                <Icon size={22} className="text-indigo-400 mb-3" />
                <h2 className="text-sm font-semibold text-white">{title}</h2>
                <p className="text-xs text-surface-500 mt-2">{desc}</p>
              </div>
            ))}
          </div>

          <div className="glass-card p-6 border border-indigo-500/20 mb-14">
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Sparkles size={18} className="text-indigo-400" /> Simple monthly plans
            </h2>
            <div className="grid sm:grid-cols-3 gap-3">
              {PLANS.map(p => (
                <div key={p.name} className="rounded-xl border border-surface-700 p-4 text-center">
                  <p className="text-sm font-medium text-white">{p.name}</p>
                  <p className="text-xl font-bold text-indigo-300 mt-1">{p.price}<span className="text-xs text-surface-500">/mo</span></p>
                  <p className="text-xs text-surface-500 mt-2">{p.detail}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-surface-500 mt-4">
              Admins can grant complimentary access. Staff get free interviews by default.
            </p>
          </div>

          <ul className="space-y-2 text-sm text-surface-400 max-w-xl mx-auto">
            {[
              'Resume upload for personalized technical & HR questions',
              'Adaptive difficulty after strong answers',
              'Hands-on troubleshooting segments in the answer panel',
              'Post-round feedback report with study plan links',
              'Public certificate verification (FIXIT-INT-*)',
            ].map(item => (
              <li key={item} className="flex items-start gap-2">
                <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </PublicLayout>
  )
}
