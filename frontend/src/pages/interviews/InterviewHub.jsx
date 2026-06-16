import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { subscriptionApi } from '../../api/subscriptions'
import { useAuthStore } from '../../store/authStore'
import { usePageTitle } from '../../hooks/usePageTitle'
import {
  Mic, Video, Calendar, Trophy, ChevronRight, Sparkles, Clock, Award, Plus,
  Play, CheckCircle2, Headphones, AlertCircle,
} from 'lucide-react'
import toast from 'react-hot-toast'
import StickyPageToolbar from '../../components/StickyPageToolbar'

const STATUS_COLORS = {
  draft: 'text-surface-400',
  scheduled: 'text-blue-400',
  in_progress: 'text-amber-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
}

export default function InterviewHub() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()
  usePageTitle('Interview Studio', 'AI mock interviews with voice, scheduling, and certificates.')
  const plansRef = useRef(null)
  const [campaigns, setCampaigns] = useState([])
  const [entitlement, setEntitlement] = useState(null)
  const [plans, setPlans] = useState([])
  const [subscribing, setSubscribing] = useState(null)
  const [loading, setLoading] = useState(true)
  const [stripeConfigured, setStripeConfigured] = useState(false)
  const [sampleInfo, setSampleInfo] = useState(null)
  const [startingSample, setStartingSample] = useState(false)

  const load = () => {
    Promise.all([
      interviewsApi.listCampaigns(),
      interviewsApi.getEntitlement(),
      interviewsApi.getPlans(),
      interviewsApi.getSampleInfo().catch(() => null),
    ])
      .then(([c, e, p, sample]) => {
        setCampaigns(c.campaigns || [])
        setEntitlement(e)
        setPlans((p.plans || []).filter(x => x.code !== 'free'))
        setSampleInfo(sample)
      })
      .catch(() => toast.error('Could not load interviews'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    subscriptionApi.getGatewayStatus().then(g => {
      setStripeConfigured(!!g.stripe_configured)
    }).catch(() => {})
  }, [])

  const handleStartSample = async () => {
    if (!isAuthenticated) {
      navigate('/login')
      return
    }
    if (sampleInfo?.active_sample_campaign_id) {
      navigate(`/interviews/campaign/${sampleInfo.active_sample_campaign_id}`)
      return
    }
    setStartingSample(true)
    try {
      const campaign = await interviewsApi.startSampleInterview()
      const round = campaign.rounds?.[0]
      toast.success('Sample interview ready — read the instructions, then join the room')
      if (round?.id) {
        navigate(`/interviews/campaign/${campaign.id}`)
      } else {
        navigate(`/interviews/campaign/${campaign.id}`)
      }
      load()
    } catch (e) {
      const code = e.response?.data?.code
      if (code === 'SAMPLE_USED') {
        toast.error('You already used your free sample. Subscribe for full interviews.')
        plansRef.current?.scrollIntoView({ behavior: 'smooth' })
      } else {
        toast.error(e.response?.data?.error || 'Could not start sample')
      }
    } finally {
      setStartingSample(false)
    }
  }

  const sampleMinutes = sampleInfo?.sample_duration_minutes || entitlement?.sample_duration_minutes || 10
  const showSample = sampleInfo?.sample_available || entitlement?.sample_available

  const handleSubscribe = async (plan, currency = 'INR') => {
    if (!isAuthenticated) {
      toast('Sign in to subscribe', { icon: '🔒' })
      navigate('/login')
      return
    }
    setSubscribing(plan.code)
    try {
      if (currency === 'USD' && stripeConfigured) {
        const checkout = await interviewsApi.createStripeCheckout(plan.code, 'USD')
        if (checkout.checkout_url) {
          window.location.href = checkout.checkout_url
          return
        }
      }
      const gateway = await subscriptionApi.getGatewayStatus()
      if (!gateway.available && !gateway.razorpay_configured) {
        if (import.meta.env.DEV) {
          await interviewsApi.demoActivatePlan(plan.code)
          toast.success(`${plan.name} activated (demo)`)
          load()
          return
        }
        toast.error('Payment gateway unavailable')
        return
      }
      const order = await interviewsApi.createRazorpayOrder(plan.code)
      if (order.demo_mode) {
        navigate(`/payment?product=interview&interview_plan=${plan.code}&amount=${order.amount}&tech=${encodeURIComponent(plan.name)}&token=${order.payment_token}`)
        return
      }
      const params = new URLSearchParams({
        product: 'interview',
        interview_plan: plan.code,
        amount: String(order.amount),
        tech: plan.name,
        order_id: order.order_id,
        razorpay_key: order.razorpay_key_id || '',
      })
      navigate(`/payment?${params.toString()}`)
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not start checkout')
    } finally {
      setSubscribing(null)
    }
  }

  if (!loading && entitlement && entitlement.platform_enabled === false) {
    return (
      <div className="max-w-lg mx-auto p-8 text-center">
        <h1 className="text-xl font-bold text-white">Interview Studio unavailable</h1>
        <p className="text-sm text-surface-400 mt-2">The platform is temporarily disabled. Check back later.</p>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">
      <StickyPageToolbar className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-widest text-indigo-400 font-semibold mb-1">AI Interview Studio</p>
          <h1 className="text-2xl sm:text-3xl font-bold text-white">Mock interviews that feel real</h1>
          <p className="text-surface-400 text-sm mt-2 max-w-xl">
            Multi-round voice interviews with resume-aware questions, hands-on troubleshooting, ITIL/SLA panels,
            scheduling, and LinkedIn-ready certificates. Voice runs in your browser — no extra apps required.
          </p>
        </div>
        <Link
          to="/interviews/setup"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium hover:opacity-90 shrink-0"
        >
          <Plus size={16} /> New interview
        </Link>
      </div>
      </StickyPageToolbar>

      {/* Free sample interview */}
      {showSample && (
        <section className="glass-card p-6 border border-cyan-500/30 bg-gradient-to-br from-cyan-500/5 to-indigo-500/5">
          <div className="flex flex-col lg:flex-row lg:items-start gap-6">
            <div className="flex-1">
              <p className="text-xs uppercase tracking-widest text-cyan-400 font-semibold mb-1">Try before you subscribe</p>
              <h2 className="text-xl font-bold text-white">Free {sampleMinutes}-minute sample interview</h2>
              <p className="text-sm text-surface-400 mt-2">
                One per account — experience voice Q&A, live scoring, and feedback. No payment required.
              </p>
              <ul className="mt-4 space-y-2">
                {(sampleInfo?.instructions || [
                  'Quiet room, stable internet, headphones recommended.',
                  'Microphone and camera required (same as paid interviews).',
                  `${sampleMinutes} minutes · 3–4 quick technical questions.`,
                  'Answer by voice or text; get a mini report at the end.',
                  'Subscribe for full 3–5 round cycles, labs, and certificates.',
                ]).map((line, i) => (
                  <li key={i} className="text-xs text-surface-300 flex items-start gap-2">
                    <CheckCircle2 size={14} className="text-cyan-400 shrink-0 mt-0.5" />
                    {line}
                  </li>
                ))}
              </ul>
            </div>
            <div className="lg:w-56 shrink-0 flex flex-col gap-3">
              <button
                type="button"
                disabled={startingSample}
                onClick={handleStartSample}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 text-white font-semibold text-sm flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50"
              >
                {startingSample ? 'Starting…' : (
                  <>
                    <Play size={16} /> {sampleInfo?.active_sample_campaign_id ? 'Resume sample' : 'Start free sample'}
                  </>
                )}
              </button>
              <p className="text-[10px] text-surface-500 text-center flex items-center justify-center gap-1">
                <Headphones size={10} /> Best with headphones in a quiet space
              </p>
            </div>
          </div>
        </section>
      )}

      {!showSample && entitlement?.sample_interview_used && !entitlement?.is_active && (
        <div className="glass-card p-4 border border-surface-700 flex items-start gap-3">
          <AlertCircle size={18} className="text-amber-400 shrink-0" />
          <div>
            <p className="text-sm text-white font-medium">Sample completed</p>
            <p className="text-xs text-surface-400 mt-1">
              You&apos;ve tried the free preview. Subscribe for 10 full interview attempts per year with multi-round cycles.
            </p>
            <button
              type="button"
              onClick={() => plansRef.current?.scrollIntoView({ behavior: 'smooth' })}
              className="text-xs text-indigo-400 hover:underline mt-2"
            >
              View plans →
            </button>
          </div>
        </div>
      )}

      {entitlement && (
        <div className="glass-card p-4 border border-indigo-500/20 flex flex-wrap gap-4 items-center justify-between">
          <div className="flex items-center gap-3">
            <Sparkles className="text-indigo-400" size={20} />
            <div>
              <p className="text-sm font-medium text-white">{entitlement.plan?.name || 'Free'} plan</p>
              <p className="text-xs text-surface-400">
                {entitlement.interviews_remaining} of {entitlement.interviews_total || entitlement.interviews_remaining} attempt(s) left
                {entitlement.period_end && (
                  <> · expires {new Date(entitlement.period_end).toLocaleDateString()}</>
                )}
                {entitlement.days_remaining != null && entitlement.days_remaining <= 30 && (
                  <span className="text-amber-400"> · {entitlement.days_remaining} days left</span>
                )}
              </p>
            </div>
          </div>
          {!entitlement.is_active && entitlement.renewal_required && (
            <p className="text-xs text-amber-400 w-full sm:w-auto">
              Subscription ended — renew for 10 more attempts (1 year)
            </p>
          )}
          {!entitlement.is_active && !entitlement.renewal_required && (
            <button
              type="button"
              onClick={() => plansRef.current?.scrollIntoView({ behavior: 'smooth' })}
              className="text-xs text-indigo-300 hover:underline"
            >
              Upgrade for full rounds
            </button>
          )}
        </div>
      )}

      <div className="grid sm:grid-cols-3 gap-3">
        {[
          { icon: Mic, title: 'Voice + adaptive', desc: 'Free browser voices (IN/UK/US) — speaks and listens' },
          { icon: Video, title: 'Camera required', desc: 'Mic & video on — 5 min grace then auto-exit' },
          { icon: Calendar, title: '3–5 rounds', desc: 'Schedule next round within 48h after each pass' },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="glass-card p-4 border border-surface-800">
            <Icon size={18} className="text-cyan-400 mb-2" />
            <p className="text-sm font-medium text-white">{title}</p>
            <p className="text-xs text-surface-500 mt-1">{desc}</p>
          </div>
        ))}
      </div>

      {plans.length > 0 && (
        <section ref={plansRef} id="interview-plans">
          <h2 className="text-lg font-semibold text-white mb-3">Interview plans</h2>
          <div className="grid sm:grid-cols-2 gap-3">
            {plans.map(plan => (
              <div key={plan.code} className="glass-card p-5 border border-surface-800 flex flex-col">
                <p className="text-sm font-semibold text-white">{plan.name}</p>
                <p className="text-2xl font-bold text-indigo-300 mt-1">
                  ₹{parseInt(plan.price_inr, 10)}
                  <span className="text-xs text-surface-500 font-normal">/year</span>
                </p>
                <p className="text-[10px] text-surface-500 mt-1">10 interview attempts · auto-expires after 12 months</p>
                <p className="text-xs text-surface-500 mt-2 flex-1">{plan.description}</p>
                <ul className="text-[10px] text-surface-400 mt-3 space-y-1">
                  <li>10 full interview attempts per year</li>
                  <li>Up to {plan.max_rounds} rounds per attempt</li>
                  {plan.voice_enabled && <li>Browser voice (IN / UK / US accents)</li>}
                  {plan.certificate_enabled && <li>LinkedIn certificate</li>}
                </ul>
                <div className="mt-4 flex flex-col gap-2">
                  <button
                    type="button"
                    disabled={subscribing === plan.code || entitlement?.plan?.code === plan.code}
                    onClick={() => handleSubscribe(plan, 'INR')}
                    className="w-full py-2 rounded-lg text-sm font-medium bg-indigo-500/20 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/30 disabled:opacity-50"
                  >
                    {entitlement?.plan?.code === plan.code ? 'Current plan' : subscribing === plan.code ? 'Loading…' : 'Subscribe (INR)'}
                  </button>
                  {stripeConfigured && (
                    <button
                      type="button"
                      disabled={subscribing === plan.code}
                      onClick={() => handleSubscribe(plan, 'USD')}
                      className="w-full py-2 rounded-lg text-xs font-medium border border-surface-600 text-surface-300 hover:bg-surface-800 disabled:opacity-50"
                    >
                      Pay in USD (Stripe)
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <Clock size={18} /> Your interviews
        </h2>
        {loading ? (
          <p className="text-surface-500 text-sm">Loading…</p>
        ) : campaigns.length === 0 ? (
          <div className="glass-card p-8 text-center border border-dashed border-surface-700">
            <Award className="mx-auto text-surface-600 mb-3" size={32} />
            <p className="text-surface-400 text-sm">No interviews yet. Upload your resume and start round one.</p>
            <button
              type="button"
              onClick={() => navigate('/interviews/setup')}
              className="mt-4 text-sm text-indigo-400 hover:underline"
            >
              Set up profile →
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {campaigns.map(c => (
              <button
                key={c.id}
                type="button"
                onClick={() => navigate(`/interviews/campaign/${c.id}`)}
                className="w-full glass-card p-4 border border-surface-800 hover:border-indigo-500/30 text-left flex items-center justify-between gap-3 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-white">{c.title}</p>
                  <p className="text-xs text-surface-500 mt-0.5">
                    {c.round_count} rounds · {c.primary_technology_name || 'Multi-stack'} ·{' '}
                    <span className={STATUS_COLORS[c.status] || ''}>{c.status}</span>
                  </p>
                </div>
                <ChevronRight size={16} className="text-surface-600 shrink-0" />
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="glass-card p-4 border border-emerald-500/20 bg-emerald-500/5">
        <div className="flex items-start gap-3">
          <Trophy className="text-emerald-400 shrink-0 mt-0.5" size={18} />
          <p className="text-xs text-surface-400 leading-relaxed">
            Clear all rounds to earn a verifiable <strong className="text-surface-200">FIXIT-INT</strong> certificate
            you can share on LinkedIn. Round 1: 45 min technical · Round 2: 30 min manager · Round 3: 20 min HR.
          </p>
        </div>
      </div>
    </div>
  )
}
