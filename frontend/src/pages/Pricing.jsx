import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import {
  Check, ArrowRight, Zap, Crown, Loader2, Sun, Moon, Server, Globe,
  Monitor, Database, Cpu, Shield, Lock, Sparkles, ShoppingCart, X,
  IndianRupee, DollarSign, BadgeCheck, ChevronRight, ChevronDown,
  RefreshCw, ShieldCheck, AlertTriangle, Mic2, Menu,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { useDataStore } from '../store/dataStore'
import { subscriptionApi } from '../api/subscriptions'
import { interviewsApi } from '../api/interviews'
import api from '../api/client'
import { PlatformBanners } from '../components/PlatformBanners'
import { PUBLIC_NAV_PRIMARY, PUBLIC_NAV_LINKS } from '../constants/publicNav'
import MarketingFooter from './home/components/MarketingFooter'
import { mergeTechnologies } from '../constants/techCatalog'
import { PageHeader, FixitPanel } from '../components/design'
import toast from 'react-hot-toast'

const techIcons = {
  Linux: Server,
  Docker: Monitor,
  Networking: Globe,
  'Web Servers': Globe,
  Databases: Database,
  AWS: Cpu,
  Kubernetes: Cpu,
  Security: Shield,
}

const techColors = {
  Linux: { from: 'from-amber-500', to: 'to-orange-600', bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', shadow: 'shadow-amber-500/10' },
  Docker: { from: 'from-blue-500', to: 'to-cyan-500', bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20', shadow: 'shadow-blue-500/10' },
  Networking: { from: 'from-emerald-500', to: 'to-teal-500', bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', shadow: 'shadow-emerald-500/10' },
  'Web Servers': { from: 'from-purple-500', to: 'to-violet-500', bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20', shadow: 'shadow-purple-500/10' },
  Databases: { from: 'from-rose-500', to: 'to-pink-500', bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/20', shadow: 'shadow-rose-500/10' },
  AWS: { from: 'from-yellow-500', to: 'to-amber-500', bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/20', shadow: 'shadow-yellow-500/10' },
  Kubernetes: { from: 'from-indigo-500', to: 'to-blue-600', bg: 'bg-indigo-500/10', text: 'text-indigo-400', border: 'border-indigo-500/20', shadow: 'shadow-indigo-500/10' },
  Security: { from: 'from-red-500', to: 'to-rose-600', bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', shadow: 'shadow-red-500/10' },
}

const defaultColor = {
  from: 'from-accent-cyan',
  to: 'to-accent-blue',
  bg: 'bg-accent-cyan/10',
  text: 'text-accent-cyan',
  border: 'border-accent-cyan/20',
  shadow: 'shadow-accent-cyan/10',
}

const freeFeatures = [
  'Demo scenarios for every technology',
  'Community forum with screenshot attachments',
  'Global leaderboard & achievements',
  'Basic hints system',
  'Progress tracking & lab history',
  'GitHub / Google sign-in',
]

const paidFeatures = [
  'All scenarios for the subscribed technology',
  'Docker, AWS EC2, and DigitalOcean lab modes',
  'Full hint system with detailed explanations',
  'Certificate upon completion',
  'Priority leaderboard ranking',
  'Coupon codes at checkout',
  'Team / enterprise seat licensing (contact sales)',
]

const FAQ_ITEMS = [
  {
    q: 'How does per-technology pricing work?',
    a: 'You subscribe to individual technologies (e.g., Linux, Docker). Each subscription gives you 1-year access to all scenarios, hints, and the certificate for that technology.',
  },
  {
    q: 'How do interview plans work?',
    a: 'Interview Studio plans are billed yearly. Pro and Premium include 10 full mock interview attempts per year with multi-round voice interviews and detailed feedback reports.',
  },
  {
    q: 'What can I access for free?',
    a: 'Free users get demo scenarios for every technology, one interview sample, community forum, leaderboard, and basic progress tracking.',
  },
  {
    q: 'Can I subscribe to multiple technologies at once?',
    a: 'Yes! Use "Add to Cart" for each technology, then "Subscribe All" in the cart panel.',
  },
  {
    q: 'Will I get a certificate?',
    a: 'Yes — technology completion certificates and FIXIT-INT interview certificates are verifiable on the Verify Certificate page.',
  },
  {
    q: 'Are prices per month or per year?',
    a: 'All subscriptions are yearly (1-year access from purchase). Interview plan prices shown are per year, not per month.',
  },
  {
    q: 'Do paid plans include mock interview attempts?',
    a: 'Yes. Pro and Premium interview plans include 10 full mock interview attempts per year with multi-round voice interviews and detailed STAR-scored feedback reports.',
  },
]

function FAQAccordion({ items }) {
  const [open, setOpen] = useState(null)
  return (
    <div className="space-y-3">
      {items.map(({ q, a }, i) => (
        <FixitPanel key={i} padding="p-0" className={`border transition-all duration-200 ${open === i ? 'border-accent-cyan/20' : 'hover:border-surface-600/60'}`}>
          <button
            type="button"
            onClick={() => setOpen(open === i ? null : i)}
            className="w-full flex items-center justify-between px-5 py-4 text-left gap-4"
          >
            <span className={`text-sm font-semibold transition-colors ${open === i ? 'text-accent-cyan' : 'text-white'}`}>{q}</span>
            <ChevronDown
              size={16}
              className={`text-surface-400 shrink-0 transition-transform duration-200 ${open === i ? 'rotate-180 text-accent-cyan' : ''}`}
            />
          </button>
          {open === i && (
            <div className="px-5 pb-4">
              <p className="text-sm text-surface-400 leading-relaxed">{a}</p>
            </div>
          )}
        </FixitPanel>
      ))}
    </div>
  )
}

export default function Pricing() {
  const { isAuthenticated, user } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [technologies, setTechnologies] = useState([])
  const [mySubscriptions, setMySubscriptions] = useState([])
  const [subscribing, setSubscribing] = useState(null)
  const [searchParams] = useSearchParams()
  const navigateTo = useNavigate()

  const [currency, setCurrency] = useState('USD')
  const [exchangeRate, setExchangeRate] = useState(null)
  const [rateLoading, setRateLoading] = useState(true)

  const [cart, setCart] = useState([])
  const [showCart, setShowCart] = useState(false)
  const [gatewayDown, setGatewayDown] = useState(false)
  const [gatewayMessage, setGatewayMessage] = useState('')
  const [platformConfig, setPlatformConfig] = useState(null)
  const [couponCode, setCouponCode] = useState('')
  const [appliedCoupon, setAppliedCoupon] = useState(null)
  const [couponLoading, setCouponLoading] = useState(false)
  const [batchProcessing, setBatchProcessing] = useState(false)
  const [stripeConfigured, setStripeConfigured] = useState(false)
  const [interviewPlans, setInterviewPlans] = useState([])
  const [interviewEntitlement, setInterviewEntitlement] = useState(null)
  const [subscribingInterview, setSubscribingInterview] = useState(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  useEffect(() => {
    api.get('/config/', { silentError: true }).then(res => setPlatformConfig(res.data)).catch(() => {})
  }, [])

  useEffect(() => {
    const fetchRate = async () => {
      setRateLoading(true)
      try {
        const data = await subscriptionApi.getCurrencyRate('USD')
        setExchangeRate(data.exchange_rate)
      } catch {
        setExchangeRate(83.50)
      } finally {
        setRateLoading(false)
      }
    }
    fetchRate()
  }, [])

  useEffect(() => {
    if (user) {
      const fetchProfile = async () => {
        try {
          const mod = await import('../api/auth')
          const profile = await mod.authApi.getProfile()
          const country = (profile?.country || '').toLowerCase().trim()
          if (country === 'india' || country === 'in' || country === 'ind') {
            setCurrency('INR')
          } else {
            setCurrency('USD')
          }
        } catch {
          setCurrency('USD')
        }
      }
      fetchProfile()
    }
  }, [user])

  useEffect(() => {
    getTechnologies()
      .then(data => setTechnologies(mergeTechnologies(data)))
      .catch(() => setTechnologies(mergeTechnologies([])))
    interviewsApi.getPlans().then(d => setInterviewPlans(d.plans || [])).catch(() => {})
    if (isAuthenticated) {
      subscriptionApi.getMySubscriptions()
        .then(data => setMySubscriptions(data.subscriptions || []))
        .catch(() => {})
      interviewsApi.getEntitlement()
        .then(setInterviewEntitlement)
        .catch(() => {})
    }
  }, [isAuthenticated])

  useEffect(() => {
    subscriptionApi.getGatewayStatus()
      .then((data) => {
        setStripeConfigured(!!data?.stripe_configured)
        setGatewayDown(!data?.available)
        setGatewayMessage(data?.banner_message || '')
      })
      .catch(() => setGatewayDown(true))
  }, [])

  useEffect(() => {
    if (searchParams.get('success') === 'true') {
      toast.success('Subscription activated! You now have full access.', { duration: 5000 })
    }
  }, [searchParams])

  const isSubscribed = (techName) =>
    mySubscriptions.some(s => s.technology?.name === techName && s.is_active)

  const getDisplayPrice = useCallback((priceINR) => {
    if (currency === 'USD' && exchangeRate && exchangeRate > 0) {
      const usd = (priceINR / exchangeRate).toFixed(2)
      return { amount: parseFloat(usd), display: `$${usd}`, symbol: '$' }
    }
    return { amount: priceINR, display: `₹${priceINR}`, symbol: '₹' }
  }, [currency, exchangeRate])

  const isInCart = (techId) => cart.some(item => item.id === techId)

  const addToCart = (tech) => {
    if (!isInCart(tech.id) && !isSubscribed(tech.name)) {
      setCart(prev => [...prev, tech])
      toast.success(`${tech.name} added to cart`)
    }
  }

  const removeFromCart = (techId) => {
    setCart(prev => prev.filter(item => item.id !== techId))
  }

  const cartTotal = useMemo(() => cart.reduce((sum, tech) => sum + (tech.price || 499), 0), [cart])

  const handleInterviewSubscribe = async (plan) => {
    if (!isAuthenticated) {
      toast('Please sign in first to subscribe.', { icon: '🔒' })
      navigateTo('/login')
      return
    }
    if (plan.code === 'free') {
      navigateTo('/interviews')
      return
    }
    if (gatewayDown) {
      toast.error(gatewayMessage || 'Payment gateway is unavailable.')
      return
    }
    setSubscribingInterview(plan.code)
    try {
      if (currency === 'USD' && stripeConfigured) {
        const checkout = await interviewsApi.createStripeCheckout(plan.code, 'USD')
        if (checkout.checkout_url) {
          window.location.href = checkout.checkout_url
          return
        }
      }
      const order = await interviewsApi.createRazorpayOrder(plan.code)
      const params = new URLSearchParams({
        type: 'interview',
        plan: plan.code,
        order_id: order.order_id || order.id,
        amount: order.amount,
        currency: order.currency || 'INR',
      })
      navigateTo(`/payment?${params}`)
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not start checkout')
    } finally {
      setSubscribingInterview(null)
    }
  }

  const isInterviewSubscribed = (plan) => {
    if (!interviewEntitlement) return false
    const code = interviewEntitlement.plan?.code
    if (plan.code === 'free') {
      return code === 'free' && interviewEntitlement.is_active
    }
    return code === plan.code && (interviewEntitlement.is_subscribed || interviewEntitlement.is_admin_granted_free)
  }

  const handleSubscribe = async (tech) => {
    if (!isAuthenticated) {
      toast('Please sign in first to subscribe.', { icon: '🔒' })
      return
    }
    if (gatewayDown) {
      toast.error(gatewayMessage || 'Payment gateway is unavailable. Try again later.')
      return
    }

    setSubscribing(tech.id)

    try {
      if (currency === 'USD' && stripeConfigured) {
        const checkout = await subscriptionApi.createStripeTechCheckout(
          tech.id,
          'USD',
          appliedCoupon?.code || couponCode.trim(),
        )
        if (checkout.checkout_url) {
          window.location.href = checkout.checkout_url
          return
        }
      }

      const orderData = await subscriptionApi.createRazorpayOrder(tech.id, appliedCoupon?.code || couponCode.trim())
      const params = new URLSearchParams({
        token: orderData.payment_token || orderData.order_id || '',
        tech: tech.name,
        amount: String(orderData.amount || tech.price || 499),
        tech_id: String(tech.id),
        currency: 'INR',
      })
      if (appliedCoupon?.code || couponCode.trim()) {
        params.set('coupon', appliedCoupon?.code || couponCode.trim())
      }
      if (orderData.order_id) {
        params.set('order_id', orderData.order_id)
        params.set('razorpay_key', orderData.razorpay_key_id || '')
      }
      if (currency === 'USD' && exchangeRate) {
        const usdAmount = ((orderData.amount || tech.price || 499) / exchangeRate).toFixed(2)
        params.set('display_currency', 'USD')
        params.set('display_amount', usdAmount)
        params.set('exchange_rate', exchangeRate.toFixed(2))
      }

      setSubscribing(null)
      navigateTo(`/payment?${params.toString()}`)
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to initiate payment. Please try again.'
      toast.error(msg)
      setSubscribing(null)
    }
  }

  const handleBatchSubscribe = async () => {
    if (!isAuthenticated) {
      toast('Please sign in first to subscribe.', { icon: '🔒' })
      return
    }
    if (cart.length === 0) return
    if (cart.length === 1) {
      handleSubscribe(cart[0])
      return
    }

    setBatchProcessing(true)
    try {
      const tech = cart[0]
      const orderData = await subscriptionApi.createRazorpayOrder(tech.id)
      if (!orderData.order_id) {
        toast.error(orderData.error || 'Payment gateway unavailable')
        return
      }
      const params = new URLSearchParams({
        token: orderData.payment_token || orderData.order_id || '',
        tech: tech.name,
        amount: String(orderData.amount || tech.price || 499),
        tech_id: String(tech.id),
        currency: 'INR',
      })
      if (orderData.order_id) {
        params.set('order_id', orderData.order_id)
        params.set('razorpay_key', orderData.razorpay_key_id || '')
      }
      navigateTo(`/payment?${params.toString()}`)
    } catch (err) {
      const msg = err.response?.data?.error || 'Batch subscription failed. Please try individually.'
      toast.error(msg)
    } finally {
      setBatchProcessing(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-950 relative overflow-hidden">
      {/* Background orbs */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-20 left-[10%] w-[500px] h-[500px] bg-accent-cyan/[0.03] rounded-full blur-[120px] animate-float" />
        <div className="absolute bottom-20 right-[10%] w-[400px] h-[400px] bg-accent-purple/[0.04] rounded-full blur-[100px] animate-float" style={{ animationDelay: '2s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-500/[0.02] rounded-full blur-[150px]" />
      </div>

      {/* Navbar */}
      <div className="sticky top-0 z-50 relative">
        <nav className="border-b border-surface-800/50 backdrop-blur-xl bg-surface-950/90">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
            <Link to="/" className="flex items-center gap-2.5 shrink-0">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-blue-600 flex items-center justify-center">
                <span className="text-white font-bold text-sm">F</span>
              </div>
              <span className="text-xl font-bold text-white">FixitLab</span>
            </Link>
            <div className="hidden lg:flex items-center gap-4 min-w-0">
              {PUBLIC_NAV_PRIMARY.map(({ to, label }) => (
                <Link key={to} to={to} className="text-sm text-surface-400 hover:text-white transition-colors relative group whitespace-nowrap">
                  {label}
                  <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-accent-cyan to-accent-purple group-hover:w-full transition-all duration-300" />
                </Link>
              ))}
            </div>
            <button
              type="button"
              className="lg:hidden p-2 text-surface-400 hover:text-white shrink-0"
              onClick={() => setMobileNavOpen(v => !v)}
              aria-label="Menu"
            >
              {mobileNavOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
              {/* Currency toggle */}
              <div className="flex bg-surface-800/60 rounded-lg border border-surface-700/40 overflow-hidden">
                <button
                  onClick={() => setCurrency('INR')}
                  className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${currency === 'INR' ? 'bg-accent-cyan/20 text-accent-cyan' : 'text-surface-400 hover:text-surface-200'}`}
                >
                  <IndianRupee size={12} /> INR
                </button>
                <button
                  onClick={() => setCurrency('USD')}
                  className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${currency === 'USD' ? 'bg-accent-cyan/20 text-accent-cyan' : 'text-surface-400 hover:text-surface-200'}`}
                >
                  <DollarSign size={12} /> USD
                </button>
              </div>

              {/* Cart button */}
              {cart.length > 0 && (
                <button
                  onClick={() => setShowCart(!showCart)}
                  className="relative p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800/50 transition-all"
                >
                  <ShoppingCart size={18} />
                  <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-accent-cyan text-[10px] font-bold text-white flex items-center justify-center">
                    {cart.length}
                  </span>
                </button>
              )}

              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg text-surface-400 hover:text-surface-100 hover:bg-surface-800 transition-all"
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              {isAuthenticated ? (
                <Link to="/dashboard" className="text-sm text-surface-300 hover:text-surface-100">Dashboard</Link>
              ) : (
                <Link to="/login" className="text-sm text-surface-300 hover:text-surface-100">Sign In</Link>
              )}
            </div>
          </div>
        </nav>
        <PlatformBanners config={platformConfig} showMaintenance showPromo />
        {mobileNavOpen && (
          <div className="md:hidden border-t border-surface-800/50 bg-surface-950/95 backdrop-blur-xl px-4 py-3 flex flex-col gap-2 max-h-[60vh] overflow-y-auto">
            {PUBLIC_NAV_LINKS.map(({ to, label }) => (
              <Link key={to} to={to} onClick={() => setMobileNavOpen(false)} className="text-sm text-surface-300 py-2">
                {label}
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12 relative z-10">

        {/* Gateway warning */}
        {gatewayDown && (
          <div className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400 flex items-start gap-2">
            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
            <span>{gatewayMessage || 'Payment gateway is unavailable. Free scenarios still work.'}</span>
          </div>
        )}

        {/* Promo code */}
        {isAuthenticated && !gatewayDown && (
          <div className="mb-8 max-w-md mx-auto flex gap-2">
            <input
              type="text"
              value={couponCode}
              onChange={e => { setCouponCode(e.target.value.toUpperCase()); setAppliedCoupon(null) }}
              placeholder="Promo code (e.g. SAVE10)"
              className="input-field flex-1 text-sm"
            />
            <button
              type="button"
              disabled={couponLoading || !couponCode.trim() || cart.length !== 1}
              onClick={async () => {
                if (cart.length !== 1) {
                  toast('Add one technology to cart to validate coupon', { icon: 'ℹ️' })
                  return
                }
                setCouponLoading(true)
                try {
                  const r = await subscriptionApi.validateCoupon(cart[0].id, couponCode.trim())
                  setAppliedCoupon(r)
                  toast.success(`Save ₹${r.discount_saved} on checkout!`)
                } catch (err) {
                  toast.error(err.response?.data?.error || 'Invalid coupon')
                } finally {
                  setCouponLoading(false)
                }
              }}
              className="btn-secondary px-4 text-sm whitespace-nowrap disabled:opacity-40"
            >
              {couponLoading ? '...' : 'Apply'}
            </button>
          </div>
        )}
        {appliedCoupon && (
          <p className="text-center text-sm text-accent-green mb-6">
            Coupon {appliedCoupon.code} applied — &#x20B9;{appliedCoupon.discount_saved} off at checkout
          </p>
        )}

        {/* Hero */}
        <div className="mb-14 animate-fade-in mesh-gradient rounded-2xl py-12 px-6 relative overflow-hidden">
          {/* Orb elements */}
          <div className="orb absolute top-[-60px] left-[-80px] w-[320px] h-[320px] bg-accent-cyan/[0.08] rounded-full blur-[80px] pointer-events-none" />
          <div className="orb absolute bottom-[-40px] right-[-60px] w-[280px] h-[280px] bg-accent-purple/[0.08] rounded-full blur-[70px] pointer-events-none" />
          <div className="orb absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[200px] bg-blue-500/[0.04] rounded-full blur-[90px] pointer-events-none" />

          <div className="relative">
            <PageHeader
              eyebrow="Technology + Interview Studio"
              title="Simple Yearly Pricing"
              subtitle="Subscribe per technology for lab scenarios, or choose an AI Interview Studio plan — both billed yearly."
              className="text-center [&_.flex]:justify-center [&_h1]:mx-auto [&_p]:mx-auto"
            />
          </div>
          <div className="flex flex-wrap justify-center gap-3 mt-6">
            <a href="#technology-pricing" className="btn-secondary text-sm">Technology labs</a>
            <a href="#interview-plans" className="btn-primary text-sm inline-flex items-center gap-1">
              <Mic2 size={14} /> Interview plans
            </a>
          </div>
          {currency === 'USD' && exchangeRate && (
            <div className="inline-flex items-center gap-2 mt-4 px-3 py-1.5 bg-surface-800/50 rounded-full border border-surface-700/30 animate-fade-in">
              <RefreshCw size={12} className={`text-accent-cyan ${rateLoading ? 'animate-spin' : ''}`} />
              <span className="text-xs text-surface-400">
                Live rate: 1 USD = &#x20B9;{exchangeRate.toFixed(2)}
              </span>
              <span className="text-[10px] text-surface-500">(updated hourly)</span>
            </div>
          )}
        </div>

        {/* Free vs Paid comparison */}
        <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto mb-16">
          {/* Free */}
          <FixitPanel padding="p-8" className="hover:border-surface-600/40 transition-all duration-500 group reveal reveal-delay-1">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-surface-700 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <Zap size={20} className="text-surface-300" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Free Tier</h3>
                <p className="text-sm text-surface-400">Always free, no credit card</p>
              </div>
            </div>
            <p className="text-2xl font-extrabold text-white mb-5 mt-3">&#x20B9;0 <span className="text-sm font-normal text-surface-500">forever</span></p>
            <ul className="space-y-3">
              {freeFeatures.map(f => (
                <li key={f} className="flex items-center gap-3 text-sm text-surface-300">
                  <Check size={16} className="text-surface-500 shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <div className="mt-6">
              <Link to="/register" className="btn-secondary w-full text-center block py-2.5 text-sm">
                Get started free
              </Link>
            </div>
          </FixitPanel>

          {/* Paid */}
          <FixitPanel padding="p-8" className="border-accent-cyan/20 bg-gradient-to-br from-accent-cyan/5 to-transparent hover:border-accent-cyan/40 transition-all duration-500 group hover:shadow-lg hover:shadow-accent-cyan/5 reveal reveal-delay-2 pricing-card-featured">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-cyan to-blue-600 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <Crown size={20} className="text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Per-Technology Subscription</h3>
                <p className="text-sm text-accent-cyan">1-year access per technology</p>
              </div>
            </div>
            <p className="text-sm text-surface-400 mt-3 mb-5">From &#x20B9;499/yr per technology</p>
            <ul className="space-y-3">
              {paidFeatures.map(f => (
                <li key={f} className="flex items-center gap-3 text-sm text-surface-300">
                  <Check size={16} className="text-accent-green shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <div className="mt-6">
              <a href="#technology-pricing" className="btn-primary w-full text-center block py-2.5 text-sm">
                Browse technologies <ArrowRight size={14} className="inline ml-1" />
              </a>
            </div>
          </FixitPanel>
        </div>

        {/* Technology pricing grid */}
        <h2 id="technology-pricing" className="text-2xl font-bold text-white text-center mb-2 scroll-mt-24">
          Technology Subscriptions
        </h2>
        <p className="text-surface-400 text-center mb-2 text-sm">1-year access per technology</p>
        <p className="text-surface-500 text-center mb-8 flex items-center justify-center gap-2 text-sm">
          <ShoppingCart size={14} /> Select multiple technologies and subscribe at once
        </p>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 max-w-6xl mx-auto mb-20">
          {technologies.map((tech) => {
            const Icon = techIcons[tech.name] || Server
            const colors = techColors[tech.name] || defaultColor
            const priceINR = tech.price || 499
            const priceDisplay = getDisplayPrice(priceINR)
            const subscribed = isSubscribed(tech.name)
            const inCart = isInCart(tech.id)

            const revealDelay = ['reveal-delay-1','reveal-delay-2','reveal-delay-3','reveal-delay-4']
            return (
              <FixitPanel
                key={tech.id}
                className={`relative flex flex-col transition-all duration-300 hover:-translate-y-1 hover:shadow-xl group reveal ${revealDelay[technologies.indexOf(tech) % revealDelay.length]} ${
                  subscribed
                    ? 'border-emerald-500/30 bg-emerald-500/5'
                    : inCart
                    ? `${colors.border} bg-gradient-to-br ${colors.bg} to-transparent`
                    : `hover:${colors.border} hover:shadow-lg ${colors.shadow}`
                }`}
              >
                {tech.name === 'AWS' && !subscribed && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-yellow-500 to-amber-500 text-[10px] font-bold text-white uppercase tracking-wider shadow-lg">
                    Popular
                  </div>
                )}

                {inCart && (
                  <div className="absolute top-3 right-3">
                    <div className={`w-6 h-6 rounded-full bg-gradient-to-br ${colors.from} ${colors.to} flex items-center justify-center`}>
                      <Check size={12} className="text-white" />
                    </div>
                  </div>
                )}

                {/* Icon + name */}
                <div className="flex items-center gap-3 mb-5">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 group-hover:scale-110 ${subscribed ? 'bg-emerald-500/20' : colors.bg}`}>
                    <Icon size={24} className={subscribed ? 'text-emerald-400' : colors.text} />
                  </div>
                  <div>
                    <h3 className="font-bold text-white">{tech.name}</h3>
                    <p className="text-xs text-surface-400">{tech.scenario_count || 0} scenarios</p>
                  </div>
                </div>

                {/* Price */}
                <div className="mb-1">
                  {rateLoading && currency === 'USD' ? (
                    <span className="text-2xl font-extrabold text-surface-500 animate-pulse">Loading...</span>
                  ) : (
                    <>
                      <span className="text-3xl font-extrabold text-white">{priceDisplay.display}</span>
                      <span className="text-surface-400 ml-1 text-sm">/year</span>
                    </>
                  )}
                </div>
                {currency === 'USD' && !rateLoading && (
                  <p className="text-xs text-surface-500 mb-4 flex items-center gap-1">
                    <IndianRupee size={10} /> &#x20B9;{priceINR} INR
                  </p>
                )}
                {(currency === 'INR' || rateLoading) && <div className="mb-4" />}

                {/* Feature list */}
                <ul className="space-y-2 mb-6 text-sm flex-1">
                  <li className="flex items-center gap-2 text-surface-300">
                    <Check size={14} className="text-accent-green shrink-0" /> All {tech.name} scenarios
                  </li>
                  <li className="flex items-center gap-2 text-surface-300">
                    <Check size={14} className="text-accent-green shrink-0" /> Full hints & solutions
                  </li>
                  <li className="flex items-center gap-2 text-surface-300">
                    <Check size={14} className="text-accent-green shrink-0" /> Completion certificate
                  </li>
                </ul>

                {/* Action */}
                {subscribed ? (
                  <div className="w-full py-2.5 rounded-lg font-semibold text-center bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center gap-2">
                    <Crown size={16} /> Subscribed
                  </div>
                ) : inCart ? (
                  <button
                    onClick={() => removeFromCart(tech.id)}
                    className="w-full py-2.5 rounded-lg font-semibold text-center border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-all flex items-center justify-center gap-2"
                  >
                    <X size={14} /> Remove from Cart
                  </button>
                ) : (
                  <div className="space-y-2">
                    <button
                      onClick={() => handleSubscribe(tech)}
                      disabled={subscribing === tech.id}
                      className="w-full btn-primary py-2.5 flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {subscribing === tech.id ? (
                        <><Loader2 size={14} className="animate-spin" /> Processing...</>
                      ) : (
                        <>Buy Now <ArrowRight size={14} /></>
                      )}
                    </button>
                    <button
                      onClick={() => addToCart(tech)}
                      className="w-full py-2 rounded-lg text-center border border-surface-600 text-surface-400 hover:border-accent-cyan/40 hover:text-accent-cyan transition-all flex items-center justify-center gap-2 text-xs"
                    >
                      <ShoppingCart size={13} /> Add to Cart
                    </button>
                  </div>
                )}
              </FixitPanel>
            )
          })}
        </div>

      </div>

      {/* Interview Studio plans */}
      <section id="interview-plans" className="max-w-6xl mx-auto px-4 py-16 border-t border-surface-800/50 scroll-mt-24 relative z-10">
      <div className="gradient-border-animated rounded-2xl p-px mb-[-1rem]"><div className="rounded-2xl bg-surface-950/80 backdrop-blur-sm pb-8">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/20 rounded-full px-4 py-1.5 text-sm text-indigo-400 mb-4">
            <Sparkles size={13} className="animate-pulse" />
            <span className="font-semibold">AI-powered</span>
          </div>
          <h2 className="text-2xl font-bold text-white flex items-center justify-center gap-2 mb-2">
            <Mic2 className="text-indigo-400" size={22} /> AI Interview Studio
          </h2>
          <p className="text-sm text-surface-400 max-w-xl mx-auto">
            Yearly mock interview plans with AI-powered voice interviews and detailed feedback. 10 full interview attempts per year on paid tiers.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 max-w-4xl mx-auto">
          {(interviewPlans.length ? interviewPlans : [
            { code: 'free', name: 'Free Mini', price_inr: 0, interviews_per_month: 1, max_rounds: 1, description: '1 sample per month' },
            { code: 'pro', name: 'Interview Pro', price_inr: 999, interviews_per_month: 10, max_rounds: 3, description: 'Voice + reports' },
            { code: 'premium', name: 'Interview Premium', price_inr: 2499, interviews_per_month: 10, max_rounds: 5, description: 'Certificate + 5 rounds' },
          ]).filter(p => p.code !== 'admin-demo' && p.is_active !== false).map((plan, planIdx) => {
            const priceINR = Number(plan.price_inr || 0)
            const priceDisplay = getDisplayPrice(priceINR)
            const subscribed = isInterviewSubscribed(plan)
            const isPro = plan.code === 'pro'
            const planRevealDelays = ['reveal-delay-1', 'reveal-delay-2', 'reveal-delay-3']

            return (
              <FixitPanel
                key={plan.code}
                className={`relative flex flex-col transition-all duration-300 hover:-translate-y-1 reveal ${planRevealDelays[planIdx] || 'reveal-delay-1'} ${
                  isPro
                    ? 'border-indigo-500/40 bg-indigo-500/5 shadow-lg shadow-indigo-500/10 pricing-card-featured'
                    : 'hover:border-surface-600/60'
                }`}
              >
                {isPro && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 text-[10px] font-bold text-white uppercase tracking-wider shadow-lg">
                    Most Popular
                  </div>
                )}

                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isPro ? 'bg-indigo-500/20' : 'bg-surface-700/60'}`}>
                    <Mic2 size={20} className={isPro ? 'text-indigo-400' : 'text-surface-400'} />
                  </div>
                  <div>
                    <p className="font-bold text-white text-sm">{plan.name}</p>
                    <p className="text-[10px] text-surface-500 mt-0.5">{plan.description}</p>
                  </div>
                </div>

                <div className="mb-4">
                  <span className="text-3xl font-extrabold text-white">{priceDisplay.display}</span>
                  <span className="text-surface-500 text-sm ml-1">/year</span>
                  {currency === 'USD' && priceINR > 0 && !rateLoading && (
                    <p className="text-xs text-surface-500 mt-1">&#x20B9;{priceINR} INR</p>
                  )}
                </div>

                <ul className="space-y-2 mb-6 flex-1 text-sm">
                  <li className="flex items-center gap-2 text-surface-300">
                    <Check size={14} className="text-indigo-400 shrink-0" />
                    {plan.interviews_per_month || 1} attempt{(plan.interviews_per_month || 1) > 1 ? 's' : ''}/yr
                  </li>
                  <li className="flex items-center gap-2 text-surface-300">
                    <Check size={14} className="text-indigo-400 shrink-0" />
                    Up to {plan.max_rounds} round{plan.max_rounds > 1 ? 's' : ''}
                  </li>
                  {plan.code !== 'free' && (
                    <li className="flex items-center gap-2 text-surface-300">
                      <Check size={14} className="text-indigo-400 shrink-0" />
                      STAR-scored feedback report
                    </li>
                  )}
                  {plan.code === 'premium' && (
                    <li className="flex items-center gap-2 text-surface-300">
                      <Check size={14} className="text-indigo-400 shrink-0" />
                      FIXIT-INT LinkedIn certificate
                    </li>
                  )}
                </ul>

                {subscribed ? (
                  <span className="inline-flex items-center justify-center gap-1.5 text-sm text-emerald-400 py-2.5 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
                    <BadgeCheck size={16} /> Subscribed
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={subscribingInterview === plan.code}
                    onClick={() => handleInterviewSubscribe(plan)}
                    className={`w-full text-sm py-2.5 disabled:opacity-50 flex items-center justify-center gap-2 rounded-lg font-semibold transition-all ${
                      isPro ? 'btn-primary' : 'btn-secondary'
                    }`}
                  >
                    {subscribingInterview === plan.code ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : plan.code === 'free' ? (
                      'Start free'
                    ) : (
                      <><ShoppingCart size={14} /> Subscribe</>
                    )}
                  </button>
                )}
              </FixitPanel>
            )
          })}
        </div>

        <p className="text-center mt-6 text-xs text-surface-500">
          Interview billing is separate from technology lab subscriptions.
        </p>
      </div></div>
      </section>

      {/* FAQ accordion */}
      <section className="max-w-2xl mx-auto px-4 pb-20 relative z-10">
        <h2 className="text-2xl font-bold text-white text-center mb-8">Frequently Asked Questions</h2>
        <FAQAccordion items={FAQ_ITEMS} />
      </section>

      {/* Floating Cart Panel */}
      {showCart && cart.length > 0 && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowCart(false)} />
          <div className="relative w-full max-w-md bg-surface-900 border-l border-surface-700/50 h-full overflow-y-auto shadow-2xl">
            <div className="sticky top-0 bg-surface-900/95 backdrop-blur-xl border-b border-surface-700/30 p-5 flex items-center justify-between z-10">
              <div className="flex items-center gap-2">
                <ShoppingCart size={18} className="text-accent-cyan" />
                <h2 className="text-lg font-bold text-white">Cart ({cart.length})</h2>
              </div>
              <button onClick={() => setShowCart(false)} className="p-1.5 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 transition-all">
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {cart.map(tech => {
                const colors = techColors[tech.name] || defaultColor
                const Icon = techIcons[tech.name] || Server
                const priceINR = tech.price || 499
                const priceDisplay = getDisplayPrice(priceINR)
                return (
                  <FixitPanel key={tech.id} padding="p-4" className="flex items-center gap-3 animate-fade-in">
                    <div className={`w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center shrink-0`}>
                      <Icon size={18} className={colors.text} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-white text-sm">{tech.name}</p>
                      <p className="text-xs text-surface-400">{tech.scenario_count || 0} scenarios &middot; 1 year</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-bold text-white text-sm">{priceDisplay.display}</p>
                      {currency === 'USD' && (
                        <p className="text-[10px] text-surface-500">&#x20B9;{priceINR}</p>
                      )}
                    </div>
                    <button onClick={() => removeFromCart(tech.id)} className="p-1 text-surface-500 hover:text-red-400 transition-colors shrink-0">
                      <X size={14} />
                    </button>
                  </FixitPanel>
                )
              })}
            </div>

            <div className="sticky bottom-0 bg-surface-900/95 backdrop-blur-xl border-t border-surface-700/30 p-5 space-y-4">
              {cart.length >= 3 && (
                <div className="flex items-center gap-2 p-3 bg-accent-green/10 border border-accent-green/20 rounded-lg animate-fade-in">
                  <BadgeCheck size={16} className="text-accent-green shrink-0" />
                  <p className="text-xs text-accent-green">
                    Great choice! Subscribing to {cart.length}+ technologies maximizes your learning!
                  </p>
                </div>
              )}
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-surface-400">
                  <span>{cart.length} technolog{cart.length > 1 ? 'ies' : 'y'}</span>
                  <span>{getDisplayPrice(cartTotal).display}</span>
                </div>
                {currency === 'USD' && (
                  <div className="flex justify-between text-xs text-surface-500">
                    <span>INR equivalent</span>
                    <span>&#x20B9;{cartTotal}</span>
                  </div>
                )}
                <div className="flex justify-between text-white font-bold text-lg pt-2 border-t border-surface-700/30">
                  <span>Total</span>
                  <span>{getDisplayPrice(cartTotal).display}</span>
                </div>
              </div>
              <button
                onClick={handleBatchSubscribe}
                disabled={batchProcessing}
                className="btn-primary w-full py-3.5 text-base font-bold flex items-center justify-center gap-2.5 disabled:opacity-50 shadow-lg shadow-accent-cyan/20"
              >
                {batchProcessing ? (
                  <><Loader2 size={18} className="animate-spin" /> Processing...</>
                ) : (
                  <><Lock size={16} /> Subscribe All ({cart.length})</>
                )}
              </button>
              <div className="flex items-center justify-center gap-1.5 text-xs text-surface-500">
                <ShieldCheck size={12} className="text-accent-green" />
                <span>Secure payment via Razorpay</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Cart FAB */}
      {cart.length > 0 && !showCart && (
        <button
          onClick={() => setShowCart(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-3 bg-gradient-to-r from-accent-cyan to-accent-blue text-white px-5 py-3 rounded-2xl shadow-2xl shadow-accent-cyan/30 hover:shadow-accent-cyan/50 transition-all hover:scale-105 animate-slide-up"
        >
          <ShoppingCart size={18} />
          <span className="font-bold">{cart.length} item{cart.length > 1 ? 's' : ''}</span>
          <span className="text-sm opacity-80">&middot;</span>
          <span className="font-bold">{getDisplayPrice(cartTotal).display}</span>
          <ChevronRight size={16} />
        </button>
      )}

      <MarketingFooter />
    </div>
  )
}
