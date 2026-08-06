/**
 * PaymentPage — Modern 3D Payment Flow with Method Selection
 *
 * Features:
 * - Selectable payment methods (UPI, Credit/Debit Card, Net Banking, Wallets)
 * - 3D card transforms, glassmorphism, animated backgrounds
 * - Smooth step transitions with animations
 * - Live currency display (INR/USD)
 * - Razorpay integration (or demo mode fallback)
 */
import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { subscriptionApi } from '../api/subscriptions'
import { interviewsApi } from '../api/interviews'
import { certApi } from '../api/certifications'
import api from '../api/client'
import { PlatformBanners } from '../components/PlatformBanners'
import {
  ArrowLeft, ShieldCheck, Lock, CheckCircle2, Loader2, AlertTriangle,
  Sun, Moon, Terminal, CreditCard, Smartphone, Building2, BadgeCheck,
  IndianRupee, Globe, Clock, Wallet, Fingerprint, Sparkles,
  Star, Award, ChevronRight, ArrowRight, Zap, Shield
} from 'lucide-react'
import toast from 'react-hot-toast'
import { resolveChargeAmountPaise, isOrderUsable, hasDisplayableGst } from '../utils/checkoutAmount'
import { SUPPORT_EMAIL } from '../constants/contact'

/* ──────── PAYMENT METHODS ──────── */
const paymentMethods = [
  {
    id: 'upi',
    label: 'UPI',
    desc: 'Google Pay, PhonePe, Paytm',
    icon: Smartphone,
    gradient: 'from-violet-500 to-purple-600',
    bgGlow: 'bg-violet-500/10',
    borderActive: 'border-violet-500/50',
    shadowActive: 'shadow-violet-500/20',
    popular: true,
  },
  {
    id: 'card',
    label: 'Credit / Debit Card',
    desc: 'Visa, Mastercard, RuPay, Amex',
    icon: CreditCard,
    gradient: 'from-blue-500 to-cyan-500',
    bgGlow: 'bg-blue-500/10',
    borderActive: 'border-blue-500/50',
    shadowActive: 'shadow-blue-500/20',
    popular: false,
  },
  {
    id: 'netbanking',
    label: 'Net Banking',
    desc: '50+ banks supported',
    icon: Building2,
    gradient: 'from-emerald-500 to-teal-500',
    bgGlow: 'bg-emerald-500/10',
    borderActive: 'border-emerald-500/50',
    shadowActive: 'shadow-emerald-500/20',
    popular: false,
  },
  {
    id: 'wallet',
    label: 'Wallets',
    desc: 'Paytm, Amazon Pay, Mobikwik',
    icon: Wallet,
    gradient: 'from-amber-500 to-orange-500',
    bgGlow: 'bg-amber-500/10',
    borderActive: 'border-amber-500/50',
    shadowActive: 'shadow-amber-500/20',
    popular: false,
  },
]

/* ──────── ANIMATED PARTICLES ──────── */
function FloatingParticles() {
  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      {/* Large gradient orbs */}
      <div className="absolute top-[-10%] left-[-5%] w-[600px] h-[600px] bg-accent-cyan/[0.04] rounded-full blur-[150px] animate-float" />
      <div className="absolute bottom-[-10%] right-[-5%] w-[500px] h-[500px] bg-accent-purple/[0.05] rounded-full blur-[130px] animate-float-delayed" />
      <div className="absolute top-1/2 left-1/3 w-[400px] h-[400px] bg-blue-500/[0.03] rounded-full blur-[120px] animate-morph" />
      <div className="absolute top-1/4 right-1/4 w-[300px] h-[300px] bg-violet-500/[0.03] rounded-full blur-[100px] animate-float" />

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage: 'linear-gradient(rgba(6,182,212,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.3) 1px, transparent 1px)',
          backgroundSize: '80px 80px',
        }}
      />

      {/* Floating dots */}
      {[...Array(6)].map((_, i) => (
        <div
          key={i}
          className="absolute w-1 h-1 rounded-full bg-accent-cyan/20 animate-float"
          style={{
            left: `${15 + i * 15}%`,
            top: `${20 + (i % 3) * 25}%`,
            animationDelay: `${i * 0.8}s`,
            animationDuration: `${4 + i}s`,
          }}
        />
      ))}
    </div>
  )
}

/* ──────── RAZORPAY SDK LOADER ──────── */
/**
 * Loads the Razorpay checkout SDK exactly once per document and reports the
 * outcome through the two setters.
 *
 * Exported only so the unmount behaviour can be tested directly — rendering the
 * whole PaymentPage in jsdom drags in the auth/theme stores and four API
 * modules, which makes a leak test measure everything except the leak.
 *
 * Two things here are deliberate and easy to get wrong:
 *
 * 1. The listeners are named, not inline arrows. `removeEventListener` compares
 *    by identity, so re-creating `() => setRazorpayReady(true)` in the cleanup
 *    would detach nothing while looking correct.
 * 2. Cleanup only stops *pending* callbacks via `cancelled`; it never resets
 *    readiness. Setting `razorpayReady` back to false on unmount would disable
 *    the checkout button on remount (StrictMode double-invokes effects), which
 *    turns a harmless leak into a broken payment flow.
 */
export function useRazorpaySdk(setRazorpayReady, setRazorpayFailed) {
  useEffect(() => {
    if (window.Razorpay) { setRazorpayReady(true); return }

    let cancelled = false
    const handleLoad = () => { if (!cancelled) setRazorpayReady(true) }
    const handleError = () => {
      if (cancelled) return
      console.error('Razorpay SDK failed to load')
      setRazorpayFailed(true)
    }

    const existing = document.getElementById('razorpay-sdk')
    if (existing) {
      existing.addEventListener('load', handleLoad)
      existing.addEventListener('error', handleError)
      return () => {
        cancelled = true
        existing.removeEventListener('load', handleLoad)
        existing.removeEventListener('error', handleError)
      }
    }

    // The tag is left in the document on unmount so a remount reuses the
    // in-flight download instead of re-requesting the SDK.
    const script = document.createElement('script')
    script.id = 'razorpay-sdk'
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.async = true
    script.addEventListener('load', handleLoad)
    script.addEventListener('error', handleError)
    document.body.appendChild(script)
    return () => {
      cancelled = true
      script.removeEventListener('load', handleLoad)
      script.removeEventListener('error', handleError)
    }
  }, [setRazorpayReady, setRazorpayFailed])
}

/* ──────── MAIN COMPONENT ──────── */
export default function PaymentPage() {
  const { user } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const paymentToken = searchParams.get('token')
  const techNameParam = searchParams.get('tech')
  const amountINRParam = searchParams.get('amount')
  const techIdParam = searchParams.get('tech_id')
  const renewSlug = searchParams.get('technology')
  const isRenewFlow = searchParams.get('renew') === '1' && !!renewSlug
  const orgSlug = searchParams.get('org_slug')
  const productType = searchParams.get('product')
  const interviewPlan = searchParams.get('interview_plan')
  const certSlugParam = searchParams.get('cert')
  const isCertProduct = !!certSlugParam
  const isInterviewProduct = productType === 'interview' && !!interviewPlan
  const existingOrderId = searchParams.get('order_id')
  const existingRazorpayKey = searchParams.get('razorpay_key')
  const displayCurrency = searchParams.get('display_currency') || 'INR'
  const displayAmountUSD = searchParams.get('display_amount')
  const paramExchangeRate = searchParams.get('exchange_rate')

  const [renewBootstrap, setRenewBootstrap] = useState(null)
  const [renewLoading, setRenewLoading] = useState(isRenewFlow)
  const [certBootstrap, setCertBootstrap] = useState(null)
  const [certLoading, setCertLoading] = useState(isCertProduct)

  const techName = techNameParam || renewBootstrap?.techName || certBootstrap?.trackName
  const amountINR = amountINRParam || renewBootstrap?.amountINR || certBootstrap?.amountINR
  const techId = techIdParam || renewBootstrap?.techId || certBootstrap?.techId
  const paymentTokenResolved = paymentToken || renewBootstrap?.orderId || certBootstrap?.orderId
  const orderIdResolved = existingOrderId || renewBootstrap?.orderId || certBootstrap?.orderId
  const razorpayKeyResolved = existingRazorpayKey || renewBootstrap?.razorpayKey || certBootstrap?.razorpayKey

  const [step, setStep] = useState('summary') // summary -> processing -> success -> failed
  const [selectedMethod, setSelectedMethod] = useState('upi')
  const [razorpayReady, setRazorpayReady] = useState(false)
  const [razorpayFailed, setRazorpayFailed] = useState(false)
  const [paymentResult, setPaymentResult] = useState(null)
  const [error, setError] = useState('')
  const [gatewayDown, setGatewayDown] = useState(false)
  const [gatewayChecked, setGatewayChecked] = useState(false)
  const [platformConfig, setPlatformConfig] = useState(null)
  const [upiId, setUpiId] = useState('')
  const [couponCode, setCouponCode] = useState(searchParams.get('coupon') || '')
  const [appliedCoupon, setAppliedCoupon] = useState(null)
  const [couponLoading, setCouponLoading] = useState(false)
  const [hoveredMethod, setHoveredMethod] = useState(null)
  // Server-computed GST breakup, populated from the create-order response. Null
  // until an order exists, because until then we genuinely do not know the tax
  // (audit Z1-14 — this line used to print a hardcoded "GST (included) ₹0").
  const [gstBreakup, setGstBreakup] = useState(null)
  // Double-submit guard (audit Z1-14). `step` was doing this job, but it is set
  // back to 'summary' before Razorpay's modal opens, so a second click in that
  // window created a second order — two Razorpay orders and two pending
  // PaymentTransaction rows for one purchase. A ref, not state: two clicks in the
  // same tick would both read a stale `false` from state.
  const checkoutInFlight = useRef(false)
  const cardRef = useRef(null)

  // Display amounts (coupon may override URL amount)
  const baseAmount = parseInt(amountINR) || 0
  const finalAmountINR = appliedCoupon?.discounted_amount ?? baseAmount
  const discountSaved = appliedCoupon?.discount_saved ?? 0
  const amountNum = finalAmountINR
  const displayAmount = displayCurrency === 'USD' && displayAmountUSD && !appliedCoupon
    ? `$${displayAmountUSD}`
    : `\u20B9${finalAmountINR}`
  const secondaryAmount = displayCurrency === 'USD' && displayAmountUSD && !appliedCoupon
    ? `(\u20B9${amountINR} INR)`
    : ''

  const applyCoupon = async (codeOverride) => {
    const code = (codeOverride || couponCode).trim()
    if (!code || !techId) return false
    setCouponLoading(true)
    setError('')
    try {
      const result = await subscriptionApi.validateCoupon(parseInt(techId), code)
      setAppliedCoupon(result)
      setCouponCode(result.code || code)
      toast.success(`Coupon ${result.code} applied — save ₹${result.discount_saved}`)
      return true
    } catch (err) {
      setAppliedCoupon(null)
      if (!codeOverride) {
        toast.error(err.response?.data?.error || 'Invalid coupon code')
      }
      return false
    } finally {
      setCouponLoading(false)
    }
  }

  // Auto-apply coupon from ?coupon= URL param once techId is known
  useEffect(() => {
    const urlCoupon = searchParams.get('coupon')
    if (!urlCoupon || !techId || appliedCoupon || isInterviewProduct || isCertProduct) return
    applyCoupon(urlCoupon)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [techId, searchParams])

  // Load Razorpay SDK
  useEffect(() => {
    api.get('/config/').then(res => setPlatformConfig(res.data)).catch(() => {})
  }, [])

  useRazorpaySdk(setRazorpayReady, setRazorpayFailed)

  // Renewal deep link: /payment?technology=linux&renew=1
  useEffect(() => {
    if (!isRenewFlow) return
    if (!user) {
      navigate(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`, { replace: true })
      return
    }
    let cancelled = false
    setRenewLoading(true)
    api.get('/technologies/')
      .then(res => {
        const techs = Array.isArray(res.data) ? res.data : []
        const tech = techs.find(t => t.slug === renewSlug)
        if (!tech || cancelled) {
          if (!cancelled) navigate('/pricing', { replace: true })
          return
        }
        return subscriptionApi.createRazorpayOrder(tech.id).then(order => {
          if (cancelled) return
          if (!order?.order_id) {
            navigate('/pricing', { replace: true })
            return
          }
          setRenewBootstrap({
            techName: tech.name,
            techId: String(tech.id),
            amountINR: String(tech.price || order.amount_inr || 499),
            orderId: order.order_id,
            razorpayKey: order.razorpay_key_id,
          })
        })
      })
      .catch(() => { if (!cancelled) navigate('/pricing', { replace: true }) })
      .finally(() => { if (!cancelled) setRenewLoading(false) })
    return () => { cancelled = true }
  }, [isRenewFlow, renewSlug, user, navigate])

  // Certification track checkout: /payment?cert=rhcsa
  useEffect(() => {
    if (!isCertProduct || !certSlugParam) return
    if (!user) {
      navigate(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`, { replace: true })
      return
    }
    let cancelled = false
    setCertLoading(true)
    Promise.all([certApi.detail(certSlugParam), certApi.createRazorpayOrder(certSlugParam)])
      .then(([track, order]) => {
        if (cancelled) return
        if (!order?.order_id) {
          navigate(`/certifications/${certSlugParam}`, { replace: true })
          return
        }
        const pricing = track?.pricing || {}
        setCertBootstrap({
          trackName: track?.name || certSlugParam,
          trackSlug: certSlugParam,
          techId: track?.technology_id ? String(track.technology_id) : '',
          amountINR: String(order.amount || pricing.standalone_price || pricing.bundled_price || 0),
          orderId: order.order_id,
          razorpayKey: order.razorpay_key_id,
        })
      })
      .catch(() => { if (!cancelled) navigate(`/certifications/${certSlugParam}`, { replace: true }) })
      .finally(() => { if (!cancelled) setCertLoading(false) })
    return () => { cancelled = true }
  }, [isCertProduct, certSlugParam, user, navigate])

  // Block checkout when payment gateway is not configured
  useEffect(() => {
    subscriptionApi.getGatewayStatus()
      .then((data) => {
        const down = !data?.available && !orderIdResolved
        setGatewayDown(down)
        if (down) setStep('gateway_down')
      })
      .catch(() => setGatewayDown(true))
      .finally(() => setGatewayChecked(true))
  }, [orderIdResolved])

  // Redirect if missing required checkout params (after renewal bootstrap)
  useEffect(() => {
    if (renewLoading || certLoading) return
    if (isRenewFlow && !renewBootstrap && !techNameParam) return
    if (isCertProduct && !certBootstrap && !techNameParam) return
    if (!paymentToken && !orderIdResolved && !isRenewFlow && !isCertProduct) {
      navigate('/pricing', { replace: true })
      return
    }
    if (!techName || !amountINR) {
      if (!isRenewFlow && !isCertProduct) navigate('/pricing', { replace: true })
    }
  }, [paymentToken, orderIdResolved, techName, amountINR, navigate, renewLoading, certLoading, isRenewFlow, isCertProduct, renewBootstrap, certBootstrap, techNameParam])

  // 3D tilt effect on card
  useEffect(() => {
    const card = cardRef.current
    if (!card) return

    const handleMouseMove = (e) => {
      const rect = card.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const centerX = rect.width / 2
      const centerY = rect.height / 2
      const rotateX = ((y - centerY) / centerY) * -5
      const rotateY = ((x - centerX) / centerX) * 5
      card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`
    }

    const handleMouseLeave = () => {
      card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1, 1, 1)'
    }

    card.addEventListener('mousemove', handleMouseMove)
    card.addEventListener('mouseleave', handleMouseLeave)
    return () => {
      card.removeEventListener('mousemove', handleMouseMove)
      card.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [step])

  // Wrapper holds the double-submit guard so every exit path releases it,
  // including the several early `return`s below. Releasing after `rzp.open()` is
  // deliberate and sufficient: the window being guarded is order creation, and
  // once the Razorpay modal is up it owns the screen. If the user dismisses it,
  // the page is interactive again and a retry should be allowed.
  const openRazorpayCheckout = async () => {
    if (checkoutInFlight.current) return
    checkoutInFlight.current = true
    try {
      await runRazorpayCheckout()
    } finally {
      checkoutInFlight.current = false
    }
  }

  const runRazorpayCheckout = async () => {
    setError('')

    // Validate payment method inputs
    if (selectedMethod === 'upi' && upiId && !/^[\w.\-]+@[\w]+$/.test(upiId.trim())) {
      setError('Please enter a valid UPI ID (e.g., yourname@upi)')
      return
    }

    // Require real Razorpay order — no demo/fake payments
    if (!existingOrderId && !orderIdResolved) {
      setError('Payment gateway is unavailable. Please try again later.')
      setStep('gateway_down')
      return
    }

    // RAZORPAY MODE: Real payment with Razorpay Checkout
    if (!razorpayReady || !window.Razorpay) {
      setError('Payment system is loading. Please wait a moment and try again.')
      return
    }

    try {
      setStep('processing')

      let orderId = orderIdResolved
      let razorpayKey = razorpayKeyResolved
      let amountPaise = amountNum * 100

      const couponToUse = appliedCoupon?.code || ''

      // Pre-created renew/cert orders ignore coupons — always create a fresh order
      // at checkout when a coupon is applied so the discounted amount is charged.
      if (appliedCoupon || !orderId) {
        const orderData = isInterviewProduct
          ? await interviewsApi.createRazorpayOrder(interviewPlan)
          : isCertProduct
            ? await certApi.createRazorpayOrder(certSlugParam)
            : await subscriptionApi.createRazorpayOrder(
                parseInt(techId),
                couponToUse,
              )

        if (!isOrderUsable(orderData)) {
          setError(orderData.error || 'Payment gateway is unavailable.')
          setStep('gateway_down')
          return
        }

        orderId = orderData.order_id
        razorpayKey = orderData.razorpay_key_id
        // The server's figure always wins — the page amount comes from an editable
        // URL parameter (audit Z6-12, tested in utils/checkoutAmount.test.js).
        amountPaise = resolveChargeAmountPaise({
          serverAmountPaise: orderData.amount_paise,
          couponApplied: Boolean(appliedCoupon),
          discountedTotalInr: finalAmountINR,
          baseAmountInr: amountNum,
        })
        if (orderData.gst) setGstBreakup(orderData.gst)
      }

      if (!orderId) {
        setError('Failed to create payment order. Please try again.')
        setStep('summary')
        return
      }

      setStep('summary')

      const methodMap = { upi: 'upi', card: 'card', netbanking: 'netbanking', wallet: 'wallet' }

      const options = {
        key: razorpayKey,
        amount: amountPaise,
        currency: 'INR',
        name: 'FixitLab',
        description: isInterviewProduct
          ? `${techName} — Monthly Interview Plan`
          : isCertProduct
            ? `${techName} — Certification Track (1 year)`
            : `${techName} \u2014 1-Year Access`,
        order_id: orderId,
        prefill: {
          name: user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user?.username,
          email: user?.email || '',
          method: methodMap[selectedMethod] || 'upi',
        },
        notes: {
          technology: techName,
          technology_id: techId,
        },
        theme: {
          color: '#06b6d4',
          backdrop_color: 'rgba(0,0,0,0.85)',
        },
        modal: {
          ondismiss: () => {
            setStep('summary')
            toast('Payment cancelled.', { icon: '\u26A0\uFE0F' })
          },
          confirm_close: true,
          escape: false,
        },
        handler: async (response) => {
          setStep('processing')
          try {
            const verifyPayload = {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            }
            const verifyResult = orgSlug
              ? await subscriptionApi.verifyOrgPayment(orgSlug, verifyPayload)
              : isInterviewProduct
                ? await interviewsApi.verifyRazorpayPayment({
                    ...verifyPayload,
                    plan_code: interviewPlan,
                  })
                : isCertProduct
                  ? await certApi.verifyRazorpayPayment({
                      ...verifyPayload,
                      track_slug: certSlugParam,
                    })
                  : await subscriptionApi.verifyRazorpayPayment({
                      ...verifyPayload,
                      technology_id: parseInt(techId),
                    })
            setPaymentResult(verifyResult)
            setStep('success')
            toast.success(
              orgSlug
                ? 'Organization seats updated!'
                : isInterviewProduct
                  ? 'Interview plan activated!'
                  : isCertProduct
                    ? 'Certification track unlocked!'
                    : 'Payment verified successfully!',
            )
          } catch (err) {
            setError(err?.response?.data?.error || 'Payment verification failed. Contact support.')
            setStep('failed')
          }
        },
      }

      const rzp = new window.Razorpay(options)
      rzp.on('payment.failed', (response) => {
        setError(response.error?.description || 'Payment failed. Please try again.')
        setStep('failed')
      })
      rzp.open()

    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to initiate payment. Please try again.')
      setStep('summary')
    }
  }

  if (renewLoading || certLoading) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center">
        <Loader2 size={32} className="text-accent-cyan animate-spin" />
      </div>
    )
  }

  if ((!paymentToken && !orderIdResolved) || !gatewayChecked) return null

  if (step === 'gateway_down' || gatewayDown) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center p-6">
        <div className="max-w-md text-center glass-card p-8">
          <AlertTriangle size={48} className="text-accent-amber mx-auto mb-4" />
          <h1 className="text-xl font-bold text-white mb-2">Payment gateway unavailable</h1>
          <p className="text-surface-400 text-sm mb-6">
            Online payments are not configured yet. No charge has been made.
            Free scenarios are still available.
          </p>
          <Link to="/pricing" className="btn-primary inline-flex items-center gap-2">
            <ArrowLeft size={16} /> Back to Pricing
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface-950 relative overflow-hidden">
      <FloatingParticles />

      <div className="sticky top-0 z-50 relative">
      {/* Header */}
      <nav className="border-b border-surface-700/20 backdrop-blur-2xl bg-surface-950/90">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/pricing" className="p-2 text-surface-400 hover:text-white transition-colors rounded-lg hover:bg-surface-800/50">
              <ArrowLeft size={18} />
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/20">
                <Terminal size={16} className="text-white" />
              </div>
              <span className="font-bold text-white">FixitLab</span>
              <span className="text-surface-500 text-sm">/ Checkout</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-surface-400 bg-surface-800/40 px-3 py-1.5 rounded-full border border-surface-700/20 backdrop-blur-xl">
              <Lock size={12} className="text-accent-green" />
              <span>256-bit SSL</span>
            </div>
            <button onClick={toggleTheme} className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800/50 transition-all">
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </div>
      </nav>
      <PlatformBanners config={platformConfig} showMaintenance showPromo={false} />
      </div>

      <div className="max-w-5xl mx-auto px-6 py-10 relative z-10">

        {/* ════════════════ STEP: SUMMARY ════════════════ */}
        {step === 'summary' && (
          <div className="grid lg:grid-cols-5 gap-8 animate-slide-up">

            {/* ── LEFT: Payment Method Selection ── */}
            <div className="lg:col-span-3 space-y-6">
              <div>
                <h1 className="text-3xl font-extrabold text-white mb-2 bg-gradient-to-r from-white to-surface-300 bg-clip-text text-transparent">
                  Choose Payment Method
                </h1>
                <p className="text-surface-400">Select how you&apos;d like to pay for {techName}</p>
              </div>

              {/* Payment Method Cards — 3D hover */}
              <div className="grid grid-cols-2 gap-4">
                {paymentMethods.map(method => {
                  const Icon = method.icon
                  const isSelected = selectedMethod === method.id
                  const isHovered = hoveredMethod === method.id
                  return (
                    <button
                      key={method.id}
                      onClick={() => setSelectedMethod(method.id)}
                      onMouseEnter={() => setHoveredMethod(method.id)}
                      onMouseLeave={() => setHoveredMethod(null)}
                      className={`relative p-5 rounded-2xl border-2 text-left transition-all duration-500
                        ${isSelected
                          ? `${method.borderActive} ${method.bgGlow} shadow-xl ${method.shadowActive}`
                          : 'border-surface-700/30 hover:border-surface-600/50 bg-surface-800/20 hover:bg-surface-800/40'
                        }
                      `}
                      style={{
                        transform: isHovered
                          ? 'perspective(800px) rotateY(3deg) rotateX(-2deg) scale(1.03)'
                          : 'perspective(800px) rotateY(0) rotateX(0) scale(1)',
                        transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
                      }}
                    >
                      {/* Popular badge */}
                      {method.popular && (
                        <div className="absolute -top-2.5 right-3 px-2.5 py-0.5 rounded-full bg-gradient-to-r from-violet-500 to-purple-600 text-[9px] font-bold text-white uppercase tracking-widest shadow-lg">
                          Popular
                        </div>
                      )}

                      {/* Selection indicator */}
                      <div className={`absolute top-4 right-4 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all duration-300 ${
                        isSelected
                          ? `bg-gradient-to-br ${method.gradient} border-transparent`
                          : 'border-surface-600'
                      }`}>
                        {isSelected && <CheckCircle2 size={12} className="text-white" />}
                      </div>

                      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${method.gradient} flex items-center justify-center mb-3 shadow-lg transition-transform duration-300 ${isSelected ? 'scale-110' : ''}`}>
                        <Icon size={22} className="text-white" />
                      </div>

                      <h3 className={`font-bold mb-0.5 transition-colors ${isSelected ? 'text-white' : 'text-surface-300'}`}>
                        {method.label}
                      </h3>
                      <p className="text-xs text-surface-500">{method.desc}</p>
                    </button>
                  )
                })}
              </div>

              {/* Payment Method Details Form */}
              <div className="glass-card p-5 animate-fade-in">
                {selectedMethod === 'upi' && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Smartphone size={16} className="text-violet-400" /> Enter UPI Details
                    </h4>
                    <div>
                      <label className="text-xs text-surface-400 block mb-1.5">UPI ID</label>
                      <input
                        type="text"
                        value={upiId}
                        onChange={(e) => setUpiId(e.target.value)}
                        placeholder="yourname@upi, yourname@paytm, etc."
                        className="input-field w-full text-sm"
                      />
                      <p className="text-[10px] text-surface-500 mt-1.5">
                        Razorpay opens a secure checkout — your bank or UPI app will verify the payment with OTP or PIN, same as PhonePe or bank transfer.
                      </p>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-surface-800/40 rounded-lg border border-surface-700/20">
                      <div className="flex gap-2">
                        {['GPay', 'PhonePe', 'Paytm', 'BHIM'].map(app => (
                          <div key={app} className="px-2 py-1 bg-surface-700/40 rounded text-[10px] text-surface-400 font-medium">{app}</div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {selectedMethod === 'card' && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                      <CreditCard size={16} className="text-blue-400" /> Card Payment
                    </h4>
                    <div className="p-4 bg-surface-800/30 rounded-xl border border-surface-700/20 space-y-3">
                      <div>
                        <label className="text-xs text-surface-400 block mb-1.5">Card Number</label>
                        <div className="input-field w-full text-sm text-surface-500 cursor-not-allowed flex items-center gap-2">
                          <CreditCard size={14} className="text-surface-500" />
                          <span>**** **** **** ****</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-surface-400 block mb-1.5">Expiry</label>
                          <div className="input-field w-full text-sm text-surface-500 cursor-not-allowed">MM / YY</div>
                        </div>
                        <div>
                          <label className="text-xs text-surface-400 block mb-1.5">CVV</label>
                          <div className="input-field w-full text-sm text-surface-500 cursor-not-allowed">***</div>
                        </div>
                      </div>
                      <p className="text-[10px] text-surface-500 flex items-center gap-1.5">
                        <Lock size={10} className="text-accent-green" />
                        Card details will be entered securely on Razorpay&apos;s PCI-certified checkout
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {['Visa', 'Mastercard', 'RuPay', 'Amex'].map(card => (
                        <div key={card} className="px-2.5 py-1 bg-surface-700/40 rounded text-[10px] text-surface-400 font-medium border border-surface-700/30">{card}</div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedMethod === 'netbanking' && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Building2 size={16} className="text-emerald-400" /> Net Banking
                    </h4>
                    <p className="text-xs text-surface-400">
                      You will be redirected to your bank&apos;s secure login page to authorize the payment.
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {['SBI', 'HDFC', 'ICICI', 'Axis', 'Kotak', 'PNB', 'BOB', 'Union'].map(bank => (
                        <div key={bank} className="flex items-center gap-2 p-2.5 bg-surface-800/40 rounded-lg border border-surface-700/20 text-xs text-surface-300">
                          <Building2 size={12} className="text-emerald-400/60" />
                          {bank} Bank
                        </div>
                      ))}
                    </div>
                    <p className="text-[10px] text-surface-500">50+ banks supported via Razorpay</p>
                  </div>
                )}

                {selectedMethod === 'wallet' && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Wallet size={16} className="text-amber-400" /> Wallet Payment
                    </h4>
                    <p className="text-xs text-surface-400">
                      Select your wallet and you&apos;ll be redirected to authorize the payment.
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { name: 'Paytm', color: 'text-blue-400' },
                        { name: 'Amazon Pay', color: 'text-yellow-400' },
                        { name: 'Mobikwik', color: 'text-cyan-400' },
                        { name: 'Freecharge', color: 'text-green-400' },
                      ].map(w => (
                        <div key={w.name} className="flex items-center gap-2 p-2.5 bg-surface-800/40 rounded-lg border border-surface-700/20 text-xs text-surface-300">
                          <Wallet size={12} className={w.color} />
                          {w.name}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Security badges */}
              <div className="glass-card p-5 space-y-3 bg-surface-800/10">
                <h3 className="font-semibold text-white flex items-center gap-2 text-sm">
                  <Shield size={16} className="text-accent-green" /> Payment Security
                </h3>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { icon: Lock, label: 'PCI DSS Level 1', color: 'text-accent-green' },
                    { icon: Fingerprint, label: '3D Secure / OTP', color: 'text-accent-cyan' },
                    { icon: ShieldCheck, label: 'RBI Compliant', color: 'text-accent-purple' },
                  ].map(({ icon: SIcon, label, color }) => (
                    <div key={label} className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-surface-800/30 border border-surface-700/20">
                      <SIcon size={16} className={color} />
                      <p className="text-[10px] text-surface-400 text-center">{label}</p>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-surface-500 leading-relaxed">
                  Razorpay handles all card validation and bank OTP. Your payment details are entered directly on Razorpay&apos;s certified checkout — <strong className="text-surface-400">we never see or store your card/UPI data.</strong>
                </p>
              </div>

              {razorpayFailed && (
                <div className="glass-card p-4 border-accent-amber/30 bg-accent-amber/5 animate-fade-in">
                  <div className="flex items-center gap-2 text-accent-amber mb-1.5">
                    <AlertTriangle size={16} />
                    <p className="font-medium text-sm">Razorpay SDK could not load</p>
                  </div>
                  <p className="text-xs text-surface-400">
                    This may be due to an ad blocker or network issue. Please disable ad blockers and refresh.
                  </p>
                </div>
              )}

              {error && (
                <div className="glass-card p-4 border-accent-red/30 bg-accent-red/5 flex items-center gap-3 animate-shake">
                  <AlertTriangle size={16} className="text-accent-red shrink-0" />
                  <p className="text-sm text-accent-red">{error}</p>
                </div>
              )}

              {/* Pay Now Button */}
              <button
                onClick={openRazorpayCheckout}
                disabled={razorpayFailed && !paymentToken}
                className="w-full py-4 rounded-2xl text-lg font-bold flex items-center justify-center gap-3 disabled:opacity-40
                  bg-gradient-to-r from-accent-cyan via-accent-blue to-accent-purple text-white
                  shadow-2xl shadow-accent-cyan/20 hover:shadow-accent-cyan/40
                  hover:scale-[1.02] active:scale-[0.98] transition-all duration-300
                  relative overflow-hidden group"
              >
                {/* Shimmer effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
                <Lock size={18} className="relative z-10" />
                <span className="relative z-10">Pay {displayAmount} Securely</span>
                <ArrowRight size={18} className="relative z-10 group-hover:translate-x-1 transition-transform" />
              </button>

              <div className="flex items-center justify-center gap-6 text-xs text-surface-500">
                <span className="flex items-center gap-1"><ShieldCheck size={12} className="text-accent-green" /> PCI DSS Level 1</span>
                <span className="flex items-center gap-1"><Lock size={12} /> 256-bit encryption</span>
                <span className="flex items-center gap-1"><BadgeCheck size={12} /> RBI compliant</span>
              </div>
            </div>

            {/* ── RIGHT: Order Summary Card (3D tilt) ── */}
            <div className="lg:col-span-2">
              <div
                ref={cardRef}
                className="glass-card p-6 sticky top-24 border-surface-700/30 will-change-transform"
                style={{ transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles size={14} className="text-accent-cyan animate-pulse" />
                  <h3 className="text-sm font-bold text-surface-400 uppercase tracking-wider">Order Summary</h3>
                </div>

                {/* Tech card */}
                <div className="relative rounded-2xl overflow-hidden mb-5">
                  <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/20 via-accent-blue/10 to-accent-purple/20" />
                  <div className="relative p-5">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-14 h-14 rounded-xl bg-white/10 backdrop-blur-xl flex items-center justify-center border border-white/10 shadow-xl">
                        <Terminal size={24} className="text-white" />
                      </div>
                      <div>
                        <p className="font-extrabold text-white text-xl">{techName}</p>
                        <p className="text-xs text-surface-300 flex items-center gap-1">
                          <Star size={10} className="text-accent-amber" /> 1-Year Access
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {[
                        { icon: CheckCircle2, label: `All ${techName} scenarios` },
                        { icon: Zap, label: 'Full hints & solutions' },
                        { icon: Award, label: 'Completion certificate' },
                        { icon: ShieldCheck, label: 'Priority support' },
                      ].map(({ icon: FIcon, label }) => (
                        <div key={label} className="flex items-center gap-1.5 text-surface-200">
                          <FIcon size={11} className="text-accent-green shrink-0" />
                          <span>{label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Price breakdown */}
                <div className="space-y-2.5 text-sm mb-5">
                  <div className="flex justify-between text-surface-400">
                    <span>{techName} Subscription</span>
                    <span>{'\u20B9'}{baseAmount || amountINR}</span>
                  </div>
                  {discountSaved > 0 && (
                    <div className="flex justify-between text-accent-green">
                      <span>Coupon ({appliedCoupon?.code})</span>
                      <span>-{'\u20B9'}{discountSaved}</span>
                    </div>
                  )}
                  {/* Coupon input */}
                  <div className="pt-2 border-t border-surface-700/20">
                    <label className="text-xs text-surface-500 block mb-1.5">Promo code</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={couponCode}
                        onChange={(e) => { setCouponCode(e.target.value.toUpperCase()); setAppliedCoupon(null) }}
                        placeholder="SAVE10"
                        className="input-field flex-1 text-sm py-2"
                      />
                      <button
                        type="button"
                        onClick={applyCoupon}
                        disabled={couponLoading || !couponCode.trim()}
                        className="px-3 py-2 rounded-lg bg-surface-700 text-xs font-medium text-white hover:bg-surface-600 disabled:opacity-40"
                      >
                        {couponLoading ? '...' : 'Apply'}
                      </button>
                    </div>
                  </div>
                  {displayCurrency === 'USD' && displayAmountUSD && (
                    <div className="flex justify-between text-surface-500 text-xs">
                      <span>Converted to USD</span>
                      <span>${displayAmountUSD}</span>
                    </div>
                  )}
                  {/* Audit Z1-14: this was a hardcoded "GST (included) ₹0", which
                      would have been a false statement on the invoice the moment GST
                      was switched on. The figures come from the create-order response,
                      which reads them off the transaction that was actually written —
                      so what is shown here is what appears on the tax invoice. Before
                      an order exists we do not know the tax, so we say nothing rather
                      than assert a zero. */}
                  {hasDisplayableGst(gstBreakup) ? (
                    <>
                      <div className="flex justify-between text-surface-500">
                        <span>Taxable value</span>
                        <span>{'\u20B9'}{gstBreakup.taxable_amount}</span>
                      </div>
                      {Number(gstBreakup.igst_amount) > 0 ? (
                        <div className="flex justify-between text-surface-500">
                          <span>IGST ({Math.round(Number(gstBreakup.gst_rate) * 100)}%)</span>
                          <span>{'\u20B9'}{gstBreakup.igst_amount}</span>
                        </div>
                      ) : (
                        <>
                          <div className="flex justify-between text-surface-500">
                            <span>CGST ({Math.round(Number(gstBreakup.gst_rate) * 50)}%)</span>
                            <span>{'\u20B9'}{gstBreakup.cgst_amount}</span>
                          </div>
                          <div className="flex justify-between text-surface-500">
                            <span>SGST ({Math.round(Number(gstBreakup.gst_rate) * 50)}%)</span>
                            <span>{'\u20B9'}{gstBreakup.sgst_amount}</span>
                          </div>
                        </>
                      )}
                      <p className="text-[10px] text-surface-600">
                        Tax is included in the total below — you are not charged extra.
                      </p>
                    </>
                  ) : null}
                  <div className="border-t border-surface-700/30 pt-3 flex justify-between text-white font-bold">
                    <span>Total</span>
                    <div className="text-right">
                      <span className="text-2xl bg-gradient-to-r from-white to-accent-cyan bg-clip-text text-transparent">
                        {displayAmount}
                      </span>
                      {secondaryAmount && (
                        <p className="text-[10px] text-surface-500 font-normal mt-0.5">{secondaryAmount}</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Selected payment method indicator */}
                <div className="flex items-center gap-2.5 p-3 rounded-xl bg-surface-800/30 border border-surface-700/20 mb-4">
                  {(() => {
                    const method = paymentMethods.find(m => m.id === selectedMethod)
                    const MIcon = method?.icon || CreditCard
                    return (
                      <>
                        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${method?.gradient || 'from-gray-500 to-gray-600'} flex items-center justify-center`}>
                          <MIcon size={14} className="text-white" />
                        </div>
                        <div className="flex-1">
                          <p className="text-xs font-medium text-surface-300">Paying via</p>
                          <p className="text-xs text-surface-500">{method?.label || 'UPI'}</p>
                        </div>
                        <ChevronRight size={14} className="text-surface-500" />
                      </>
                    )
                  })()}
                </div>

                <div className="flex items-center gap-2 text-xs text-surface-500 pt-3 border-t border-surface-700/20">
                  <Lock size={12} className="text-accent-green shrink-0" />
                  <span>Your payment info is processed by Razorpay. We never store card details.</span>
                </div>

                <div className="mt-3 p-2.5 bg-surface-800/20 border border-surface-700/15 rounded-lg">
                  <p className="text-[10px] text-surface-500 flex items-center gap-1.5">
                    <Clock size={10} /> Session expires in 30 minutes
                  </p>
                </div>

                {paramExchangeRate && displayCurrency === 'USD' && (
                  <div className="mt-3 text-center">
                    <p className="text-[10px] text-surface-500">
                      Exchange rate: 1 USD = {'\u20B9'}{paramExchangeRate} (live)
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ════════════════ STEP: PROCESSING ════════════════ */}
        {step === 'processing' && (
          <div className="flex flex-col items-center justify-center py-24 animate-fade-in">
            {/* Animated concentric rings */}
            <div className="relative mb-10">
              <div className="w-32 h-32 rounded-full border-[3px] border-accent-cyan/10 animate-spin-slow" />
              <div className="absolute inset-2 rounded-full border-[3px] border-accent-purple/15 animate-spin" style={{ animationDirection: 'reverse' }} />
              <div className="absolute inset-4 rounded-full border-[3px] border-accent-blue/20 animate-spin-slow" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-cyan to-accent-purple flex items-center justify-center shadow-2xl shadow-accent-cyan/30">
                  <IndianRupee size={28} className="text-white" />
                </div>
              </div>
            </div>
            <h2 className="text-2xl font-extrabold text-white mb-3 bg-gradient-to-r from-white to-surface-300 bg-clip-text text-transparent">
              Processing Payment
            </h2>
            <p className="text-surface-400 text-sm mb-6 text-center max-w-sm">
              Verifying your payment with the bank. This may take a few moments...
            </p>
            <div className="flex items-center gap-2 px-4 py-2 bg-surface-800/30 rounded-full border border-surface-700/20">
              <Lock size={12} className="text-accent-green" />
              <span className="text-xs text-surface-500">Do not close this page</span>
            </div>
          </div>
        )}

        {/* ════════════════ STEP: SUCCESS ════════════════ */}
        {step === 'success' && (
          <div className="max-w-lg mx-auto flex flex-col items-center py-16 animate-scale-in">
            {/* Animated success icon */}
            <div className="relative mb-8">
              <div className="w-24 h-24 rounded-full bg-accent-green/20 border-2 border-accent-green/30 flex items-center justify-center animate-bounce-subtle">
                <CheckCircle2 size={48} className="text-accent-green" />
              </div>
              <div className="absolute -inset-4 rounded-full bg-accent-green/5 blur-xl animate-pulse" />
              {/* Confetti dots */}
              {[...Array(8)].map((_, i) => (
                <div
                  key={i}
                  className="absolute w-2 h-2 rounded-full animate-float"
                  style={{
                    background: ['#06b6d4', '#a855f7', '#eab308', '#22c55e', '#f43f5e'][i % 5],
                    left: `${50 + 40 * Math.cos(i * Math.PI / 4)}%`,
                    top: `${50 + 40 * Math.sin(i * Math.PI / 4)}%`,
                    animationDelay: `${i * 0.2}s`,
                    animationDuration: '3s',
                  }}
                />
              ))}
            </div>

            <h2 className="text-3xl font-extrabold text-white mb-3 bg-gradient-to-r from-accent-green to-accent-cyan bg-clip-text text-transparent">
              Payment Successful!
            </h2>
            <p className="text-surface-400 text-sm mb-8 text-center max-w-md">
              {isInterviewProduct
                ? `Your ${techName} plan is active. Start a multi-round AI interview with free browser voice.`
                : `Your ${techName} subscription is now active for 1 year. You have full access to all ${techName} scenarios, hints, and certificates.`}
            </p>

            <div className="glass-card p-6 w-full mb-8 border-accent-green/20 bg-accent-green/[0.02]">
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-surface-400">Technology</span>
                  <span className="text-white font-semibold">{techName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-400">Amount Paid</span>
                  <span className="text-accent-green font-bold">{'\u20B9'}{finalAmountINR || amountINR}</span>
                </div>
                {paymentResult?.subscription_id && (
                  <div className="flex justify-between">
                    <span className="text-surface-400">Subscription ID</span>
                    <span className="text-surface-300 font-mono text-xs">{paymentResult.subscription_id}</span>
                  </div>
                )}
                {paymentResult?.razorpay_payment_id && (
                  <div className="flex justify-between">
                    <span className="text-surface-400">Payment ID</span>
                    <span className="text-surface-300 font-mono text-xs">{paymentResult.razorpay_payment_id}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-surface-400">Access</span>
                  <span className="text-surface-300">{isInterviewProduct ? '30 days' : '1 Year'}</span>
                </div>
                <div className="border-t border-surface-700/30 pt-2 flex justify-between">
                  <span className="text-surface-400">Status</span>
                  <span className="text-accent-green font-semibold flex items-center gap-1"><BadgeCheck size={14} /> Verified & Active</span>
                </div>
              </div>
            </div>

            <div className="flex gap-3 w-full">
              <Link
                to={isInterviewProduct ? '/interviews' : '/dashboard'}
                className="btn-primary flex-1 text-center py-3.5 flex items-center justify-center gap-2 text-base font-bold"
              >
                {isInterviewProduct ? 'Start Interviewing' : 'Go to Dashboard'}
              </Link>
              <Link to={isInterviewProduct ? '/interviews/setup' : '/pricing'} className="btn-secondary flex-1 text-center py-3.5 font-semibold">
                {isInterviewProduct ? 'Set Up Profile' : 'Subscribe More'}
              </Link>
            </div>

            <p className="text-xs text-surface-500 mt-6 text-center">
              Your invoice is available in Profile → Payment Invoices. A confirmation email was sent to {user?.email}
            </p>
          </div>
        )}

        {/* ════════════════ STEP: FAILED ════════════════ */}
        {step === 'failed' && (
          <div className="max-w-lg mx-auto flex flex-col items-center py-16 animate-slide-up">
            <div className="relative mb-8">
              <div className="w-24 h-24 rounded-full bg-accent-red/20 border-2 border-accent-red/30 flex items-center justify-center">
                <AlertTriangle size={44} className="text-accent-red animate-pulse" />
              </div>
              <div className="absolute -inset-4 rounded-full bg-accent-red/5 blur-xl" />
            </div>

            <h2 className="text-3xl font-extrabold text-white mb-3">Payment Failed</h2>
            <p className="text-surface-400 text-sm mb-6 text-center max-w-md">{error || 'Your payment could not be processed. No amount has been deducted from your account.'}</p>

            <div className="glass-card p-5 w-full mb-6 border-accent-red/20 bg-accent-red/[0.02]">
              <h3 className="text-sm font-semibold text-white mb-3">Common reasons:</h3>
              <ul className="text-xs text-surface-400 space-y-2">
                {[
                  'Insufficient funds in your account',
                  'Incorrect OTP entered',
                  'Bank declined the transaction',
                  'Payment session timed out',
                ].map(reason => (
                  <li key={reason} className="flex items-center gap-2">
                    <div className="w-1 h-1 rounded-full bg-accent-red/50" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex gap-3 w-full">
              <button onClick={() => { setStep('summary'); setError('') }} className="btn-primary flex-1 py-3.5 flex items-center justify-center gap-2 font-bold">
                <CreditCard size={16} /> Try Again
              </button>
              <Link to="/pricing" className="btn-secondary flex-1 text-center py-3.5 font-semibold">
                Back to Pricing
              </Link>
            </div>

            <p className="text-xs text-surface-500 mt-6 text-center">
              If amount was deducted, it will be refunded within 5-7 business days. Contact{' '}
              <a href={`mailto:${SUPPORT_EMAIL}`} className="text-accent-cyan hover:underline">support</a> for help.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
