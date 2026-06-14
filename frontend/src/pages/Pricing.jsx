import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import {
  Check, ArrowRight, Zap, Crown, Loader2, Sun, Moon, Server, Globe,
  Monitor, Database, Cpu, Shield, Lock, Sparkles, ShoppingCart, X,
  IndianRupee, DollarSign, BadgeCheck, ChevronRight,
  RefreshCw, ShieldCheck, AlertTriangle
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { scenarioApi } from '../api/scenarios'
import { subscriptionApi } from '../api/subscriptions'
import api from '../api/client'
import { PlatformBanners } from '../components/PlatformBanners'
import toast from 'react-hot-toast'

const techIcons = { Linux: Server, Docker: Monitor, Networking: Globe, 'Web Servers': Globe, Databases: Database, AWS: Cpu, Kubernetes: Cpu, Security: Shield }

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

const defaultColor = { from: 'from-accent-cyan', to: 'to-accent-blue', bg: 'bg-accent-cyan/10', text: 'text-accent-cyan', border: 'border-accent-cyan/20', shadow: 'shadow-accent-cyan/10' }

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

export default function Pricing() {
  const { isAuthenticated, user } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const [technologies, setTechnologies] = useState([])
  const [mySubscriptions, setMySubscriptions] = useState([])
  const [subscribing, setSubscribing] = useState(null)
  const [searchParams] = useSearchParams()
  const navigateTo = useNavigate()

  // Currency state — default USD per user request
  const [currency, setCurrency] = useState('USD')
  const [exchangeRate, setExchangeRate] = useState(null)
  const [rateLoading, setRateLoading] = useState(true)

  // Cart state for multi-tech subscribe
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

  useEffect(() => {
    api.get('/config/').then(res => setPlatformConfig(res.data)).catch(() => {})
  }, [])

  // Fetch live exchange rate on mount
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

  // Detect user country from profile and set default currency
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

  // Load technologies and subscriptions
  useEffect(() => {
    scenarioApi.getTechnologies().then(setTechnologies).catch(() => {})
    if (isAuthenticated) {
      subscriptionApi.getMySubscriptions()
        .then(data => setMySubscriptions(data.subscriptions || []))
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

  const isSubscribed = (techName) => {
    return mySubscriptions.some(s => s.technology?.name === techName && s.is_active)
  }

  // Convert INR price to display price — ACTUAL CONVERSION using live rate
  const getDisplayPrice = useCallback((priceINR) => {
    if (currency === 'USD' && exchangeRate && exchangeRate > 0) {
      const usd = (priceINR / exchangeRate).toFixed(2)
      return { amount: parseFloat(usd), display: `$${usd}`, symbol: '$' }
    }
    return { amount: priceINR, display: `\u20B9${priceINR}`, symbol: '\u20B9' }
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

  const cartTotal = useMemo(() => {
    return cart.reduce((sum, tech) => sum + (tech.price || 499), 0)
  }, [cart])

  const handleSubscribe = async (tech) => {
    if (!isAuthenticated) {
      toast('Please sign in first to subscribe.', { icon: '\uD83D\uDD12' })
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
      toast('Please sign in first to subscribe.', { icon: '\uD83D\uDD12' })
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
      {/* Animated background orbs */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-20 left-[10%] w-[500px] h-[500px] bg-accent-cyan/[0.03] rounded-full blur-[120px] animate-float" />
        <div className="absolute bottom-20 right-[10%] w-[400px] h-[400px] bg-accent-purple/[0.04] rounded-full blur-[100px] animate-float-delayed" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-500/[0.02] rounded-full blur-[150px]" />
      </div>

      {/* Navbar + offer/maintenance banners */}
      <div className="sticky top-0 z-50 relative">
      <nav className="border-b border-surface-800/50 backdrop-blur-xl bg-surface-950/90">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">F</span>
            </div>
            <span className="text-xl font-bold text-white">FixitLab</span>
          </Link>
          <div className="hidden md:flex items-center gap-5">
            {[
              { to: '/faq', label: 'FAQ' },
              { to: '/verify-certificate', label: 'Verify Certificate' },
              { to: '/contact', label: 'Contact' },
            ].map(({ to, label }) => (
              <Link key={to} to={to} className="text-sm text-surface-400 hover:text-white transition-colors relative group">
                {label}
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-accent-cyan to-accent-purple group-hover:w-full transition-all duration-300" />
              </Link>
            ))}
          </div>
          <div className="flex items-center gap-3">
            {/* Currency Toggle */}
            <div className="flex bg-surface-800/60 rounded-lg border border-surface-700/40 overflow-hidden">
              <button
                onClick={() => setCurrency('INR')}
                className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${
                  currency === 'INR'
                    ? 'bg-accent-cyan/20 text-accent-cyan'
                    : 'text-surface-400 hover:text-surface-200'
                }`}
              >
                <IndianRupee size={12} /> INR
              </button>
              <button
                onClick={() => setCurrency('USD')}
                className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${
                  currency === 'USD'
                    ? 'bg-accent-cyan/20 text-accent-cyan'
                    : 'text-surface-400 hover:text-surface-200'
                }`}
              >
                <DollarSign size={12} /> USD
              </button>
            </div>

            {/* Cart Button */}
            {cart.length > 0 && (
              <button
                onClick={() => setShowCart(!showCart)}
                className="relative p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800/50 transition-all"
              >
                <ShoppingCart size={18} />
                <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-accent-cyan text-[10px] font-bold text-white flex items-center justify-center animate-scale-in">
                  {cart.length}
                </span>
              </button>
            )}

            <button onClick={toggleTheme}
              className="p-2 rounded-lg text-surface-400 hover:text-surface-100 hover:bg-surface-800 transition-all"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
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
      </div>

      <div className="max-w-7xl mx-auto px-6 py-12 relative z-10">
        {gatewayDown && (
          <div className="mb-8 rounded-lg border border-accent-amber/30 bg-accent-amber/10 px-4 py-3 text-sm text-accent-amber flex items-start gap-2">
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
            Coupon {appliedCoupon.code} applied — ₹{appliedCoupon.discount_saved} off at checkout
          </p>
        )}
        {/* Hero */}
        <div className="text-center mb-14 relative">
          <div className="relative">
            <div className="inline-flex items-center gap-2 bg-accent-cyan/10 border border-accent-cyan/20 rounded-full px-4 py-1.5 text-sm text-accent-cyan mb-6 animate-fade-in">
              <Sparkles size={14} className="animate-pulse" /> Per-Technology Pricing
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold mb-4 bg-gradient-to-r from-white via-cyan-300 to-accent-purple bg-clip-text text-transparent animate-slide-up">
              Pay Only For What You Learn
            </h1>
            <p className="text-surface-400 text-lg max-w-2xl mx-auto animate-fade-in">
              Subscribe to individual technologies. Get 1-year access to all scenarios, hints, and certificates for each technology you choose.
            </p>

            {/* Exchange rate indicator */}
            {currency === 'USD' && exchangeRate && (
              <div className="inline-flex items-center gap-2 mt-4 px-3 py-1.5 bg-surface-800/50 rounded-full border border-surface-700/30 animate-fade-in">
                <RefreshCw size={12} className={`text-accent-cyan ${rateLoading ? 'animate-spin' : ''}`} />
                <span className="text-xs text-surface-400">
                  Live rate: 1 USD = {'\u20B9'}{exchangeRate.toFixed(2)}
                </span>
                <span className="text-[10px] text-surface-500">(updated hourly)</span>
              </div>
            )}
          </div>
        </div>

        {/* Free vs Paid comparison */}
        <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto mb-16">
          <div className="glass-card p-8 hover:border-surface-600/40 transition-all duration-500 group">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-surface-700 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <Zap size={20} className="text-surface-300" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Free Tier</h3>
                <p className="text-sm text-surface-400">Always free, no credit card</p>
              </div>
            </div>
            <ul className="space-y-3">
              {freeFeatures.map(f => (
                <li key={f} className="flex items-center gap-3 text-sm text-surface-300">
                  <Check size={16} className="text-surface-500 shrink-0" /> {f}
                </li>
              ))}
            </ul>
          </div>
          <div className="glass-card p-8 border-accent-cyan/20 bg-gradient-to-br from-accent-cyan/5 to-transparent hover:border-accent-cyan/40 transition-all duration-500 group hover:shadow-lg hover:shadow-accent-cyan/5">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <Crown size={20} className="text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Per-Technology Subscription</h3>
                <p className="text-sm text-accent-cyan">1-year access per technology</p>
              </div>
            </div>
            <ul className="space-y-3">
              {paidFeatures.map(f => (
                <li key={f} className="flex items-center gap-3 text-sm text-surface-300">
                  <Check size={16} className="text-accent-green shrink-0" /> {f}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Technology pricing grid */}
        <h2 className="text-2xl font-bold text-white text-center mb-3">Choose Your Technologies</h2>
        <p className="text-surface-400 text-center mb-8 flex items-center justify-center gap-2">
          <ShoppingCart size={14} />
          Select multiple technologies and subscribe at once
        </p>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 max-w-6xl mx-auto mb-16">
          {technologies.map((tech) => {
            const Icon = techIcons[tech.name] || Server
            const colors = techColors[tech.name] || defaultColor
            const priceINR = tech.price || 499
            const priceDisplay = getDisplayPrice(priceINR)
            const subscribed = isSubscribed(tech.name)
            const inCart = isInCart(tech.id)
            return (
              <div key={tech.id}
                className={`relative glass-card p-6 transition-all duration-500 hover:-translate-y-1 hover:shadow-xl group ${
                  subscribed
                    ? 'border-accent-green/30 bg-accent-green/5'
                    : inCart
                    ? `${colors.border} bg-gradient-to-br ${colors.bg} to-transparent`
                    : `hover:${colors.border} hover:shadow-lg ${colors.shadow}`
                }`}
              >
                {/* Popular badge for AWS */}
                {tech.name === 'AWS' && !subscribed && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-yellow-500 to-amber-500 text-[10px] font-bold text-white uppercase tracking-wider shadow-lg">
                    Popular
                  </div>
                )}

                {/* Cart indicator */}
                {inCart && (
                  <div className="absolute top-3 right-3">
                    <div className={`w-6 h-6 rounded-full bg-gradient-to-br ${colors.from} ${colors.to} flex items-center justify-center animate-scale-in`}>
                      <Check size={12} className="text-white" />
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 group-hover:scale-110 ${
                    subscribed ? 'bg-accent-green/20' : colors.bg
                  }`}>
                    <Icon size={24} className={subscribed ? 'text-accent-green' : colors.text} />
                  </div>
                  <div>
                    <h3 className="font-bold text-white">{tech.name}</h3>
                    <p className="text-xs text-surface-400">{tech.scenario_count || 0} scenarios</p>
                  </div>
                </div>

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

                {/* Show original INR price when displaying USD */}
                {currency === 'USD' && !rateLoading && (
                  <p className="text-xs text-surface-500 mb-4 flex items-center gap-1">
                    <IndianRupee size={10} />
                    {'\u20B9'}{priceINR} INR
                  </p>
                )}
                {(currency === 'INR' || rateLoading) && <div className="mb-4" />}

                <ul className="space-y-2 mb-6 text-sm">
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

                {subscribed ? (
                  <div className="w-full py-2.5 rounded-lg font-semibold text-center bg-accent-green/10 text-accent-green border border-accent-green/20 flex items-center justify-center gap-2">
                    <Crown size={16} /> Subscribed
                  </div>
                ) : inCart ? (
                  <button
                    onClick={() => removeFromCart(tech.id)}
                    className="w-full py-2.5 rounded-lg font-semibold text-center border border-accent-red/30 text-accent-red hover:bg-accent-red/10 transition-all flex items-center justify-center gap-2"
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
              </div>
            )
          })}
        </div>

        {/* FAQ */}
        <div className="max-w-2xl mx-auto">
          <h2 className="text-xl font-bold text-white text-center mb-6">Frequently Asked Questions</h2>
          <div className="space-y-4">
            {[
              { q: 'How does per-technology pricing work?', a: 'You subscribe to individual technologies (e.g., Linux, Docker). Each subscription gives you 1-year access to all scenarios, hints, and the certificate for that technology.' },
              { q: 'What can I access for free?', a: 'Free users get access to demo scenarios for every technology, the community forum, leaderboard, and basic progress tracking.' },
              { q: 'Is the subscription one-time or recurring?', a: 'Subscriptions are valid for 1 year from purchase. You will receive renewal reminders 7 days before expiry via email and in-app notifications. Renew anytime to extend access for another year.' },
              { q: 'Can I subscribe to multiple technologies at once?', a: 'Yes! Use the "Add to Cart" button for each technology you want, then click "Subscribe All" in the cart panel to subscribe in one go.' },
              { q: 'Will I get a certificate?', a: 'Yes! After completing all scenarios for a subscribed technology, you can generate a verifiable certificate that can be shared and verified by anyone.' },
              { q: 'Are prices shown in different currencies?', a: 'Yes! Use the INR/USD toggle to see prices in your preferred currency. We fetch live exchange rates updated hourly. Payment is processed in INR by Razorpay.' },
              { q: 'Do you offer refunds?', a: 'Refund requests can be made within 7 days of purchase. Contact fixitlab.techsupport@gmail.com.' },
            ].map(({ q, a }) => (
              <div key={q} className="glass-card p-5 hover:border-accent-cyan/20 transition-all group">
                <h3 className="text-sm font-semibold text-white mb-1.5 group-hover:text-accent-cyan transition-colors">{q}</h3>
                <p className="text-sm text-surface-400 leading-relaxed">{a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Floating Cart Panel */}
      {showCart && cart.length > 0 && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowCart(false)} />

          <div className="relative w-full max-w-md bg-surface-900 border-l border-surface-700/50 h-full overflow-y-auto animate-slide-in-right shadow-2xl">
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
                  <div key={tech.id} className="glass-card p-4 flex items-center gap-3 animate-fade-in">
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
                        <p className="text-[10px] text-surface-500">{'\u20B9'}{priceINR}</p>
                      )}
                    </div>
                    <button onClick={() => removeFromCart(tech.id)} className="p-1 text-surface-500 hover:text-accent-red transition-colors shrink-0">
                      <X size={14} />
                    </button>
                  </div>
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
                    <span>{'\u20B9'}{cartTotal}</span>
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
    </div>
  )
}
