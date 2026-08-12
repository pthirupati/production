import { useState, useMemo, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { scenarioApi } from '../../api/scenarios'
import { Mail, Lock, ArrowRight, AlertCircle, Phone, Eye, EyeOff, Check, X, ShieldCheck, ArrowLeft, Terminal, Server, Cloud, Activity, Shield } from '../../ui/eagerIcons'
import toast from 'react-hot-toast'
import { startOAuth } from '../../utils/oauth'
import { AuthShell } from '../../components/design'

/* ── Animated illustration for registration ──
 *
 * Stats are LIVE from /api/stats/ (PlatformStatsView, 2-min cache, never 500s —
 * it returns zeros on DB error). They used to be hardcoded "9+ Live Labs" and
 * "5 Technologies", which understated the catalogue by three orders of
 * magnitude and read as placeholder copy to anyone evaluating the product.
 * Falls back to conservative floors only while the request is in flight.
 */
function RegisterIllustration() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    let cancelled = false
    scenarioApi
      .getPlatformStats()
      .then((d) => { if (!cancelled) setStats(d) })
      .catch(() => { /* keep the loading floors — never block signup on this */ })
    return () => { cancelled = true }
  }, [])

  const fmt = (n) => {
    if (!n || n <= 0) return null
    if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k+`
    return `${n}+`
  }

  const cards = [
    {
      icon: Terminal,
      label: 'Hands-on labs',
      value: fmt(stats?.total_scenarios) || '—',
      color: 'accent-cyan',
    },
    {
      icon: Server,
      label: 'Technologies',
      value: fmt(stats?.total_technologies) || '—',
      color: 'accent-green',
    },
    {
      icon: Cloud,
      label: 'Labs solved',
      value: fmt(stats?.total_completions) || '—',
      color: 'accent-purple',
    },
    {
      icon: Activity,
      label: 'Engineers training',
      value: fmt(stats?.total_users) || '—',
      color: 'accent-amber',
    },
  ]

  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      {/* Grid background */}
      <div className="absolute inset-0 opacity-[0.04]"
        style={{ backgroundImage: 'linear-gradient(rgb(var(--a-cyan)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--a-cyan)) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      {/* Glow orbs */}
      <div className="absolute top-1/3 right-1/4 w-72 h-72 bg-accent-purple/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-1/4 left-1/3 w-56 h-56 bg-accent-cyan/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1.5s' }} />

      {/* Central illustration - cloud + terminal mashup */}
      <div className="relative z-10 max-w-md mx-auto px-8">
        {/* Stats cards */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          {cards.map(({ icon: Icon, label, value, color }, i) => (
            <div key={label} className="glass-card p-4 text-center animate-fade-in" style={{ animationDelay: `${i * 0.15}s` }}>
              <Icon size={24} className={`mx-auto mb-2 text-${color}`} />
              <p className="text-2xl font-bold text-white">{value}</p>
              <p className="text-xs text-surface-400">{label}</p>
            </div>
          ))}
        </div>

        {/* Feature list */}
        <div className="space-y-3">
          {[
            { text: 'Real environments — Linux, Docker, databases & more', color: 'accent-green' },
            { text: 'Auto-validated solutions with instant feedback', color: 'accent-cyan' },
            { text: 'Progressive hints when you are stuck', color: 'accent-amber' },
            { text: 'Global leaderboard and achievements', color: 'accent-purple' },
          ].map(({ text, color }, i) => (
            <div key={i} className="flex items-center gap-3 animate-fade-in" style={{ animationDelay: `${0.6 + i * 0.1}s` }}>
              <div className={`w-6 h-6 rounded-full bg-${color}/10 flex items-center justify-center shrink-0`}>
                <Check size={12} className={`text-${color}`} />
              </div>
              <p className="text-sm text-surface-300">{text}</p>
            </div>
          ))}
        </div>

        {/* What you get — factual proof points.
         *
         * This slot previously held a five-star quote attributed to
         * "Sarah K., SRE at Cloudflare". That person does not exist and
         * Cloudflare has not endorsed this product, so it was a fabricated
         * endorsement using a real company's name to imply one — deceptive
         * advertising, and squarely a misleading-advertisement risk under the
         * Consumer Protection Act 2019 / CCPA endorsement rules in India.
         * Replaced with claims that are true and checkable from the product
         * itself. Do NOT reintroduce invented testimonials here: if and when
         * real users consent to be quoted, attribute them properly. The home
         * page uses generic role personas ("DevOps Engineer · Enterprise"),
         * which is a defensible middle ground. */}
        <div className="mt-8 glass-card p-5 animate-fade-in" style={{ animationDelay: '1s' }}>
          <p className="text-xs font-semibold text-surface-200 mb-3 tracking-wide uppercase">
            Included from day one
          </p>
          <div className="space-y-2">
            {[
              'Free tier — start solving without a card',
              'Guided tutorials, then break-fix labs on the same stack',
              'Voice AI interviews with verifiable certificates',
            ].map((t) => (
              <div key={t} className="flex items-start gap-2.5">
                <Check size={13} className="text-accent-green mt-0.5 shrink-0" />
                <p className="text-xs text-surface-300 leading-relaxed">{t}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function PasswordStrength({ password }) {
  const checks = useMemo(() => [
    { label: '8+ characters', met: password.length >= 8 },
    { label: 'Uppercase letter', met: /[A-Z]/.test(password) },
    { label: 'Lowercase letter', met: /[a-z]/.test(password) },
    { label: 'Number', met: /\d/.test(password) },
    { label: 'Special character', met: /[!@#$%^&*(),.?":{}|<>]/.test(password) },
  ], [password])

  const score = checks.filter(c => c.met).length
  const strength = score <= 1 ? 'Weak' : score <= 3 ? 'Fair' : score <= 4 ? 'Good' : 'Strong'
  const colors = {
    Weak: { bar: 'bg-accent-red', text: 'text-accent-red' },
    Fair: { bar: 'bg-accent-amber', text: 'text-accent-amber' },
    Good: { bar: 'bg-brand-400', text: 'text-brand-400' },
    Strong: { bar: 'bg-accent-green', text: 'text-accent-green' },
  }

  if (!password) return null

  return (
    <div className="mt-2 space-y-2 animate-fade-in">
      <div className="flex items-center gap-2">
        <div className="flex-1 flex gap-1">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className={`h-1 flex-1 rounded-full transition-all duration-300 ${i <= score ? colors[strength].bar : 'bg-surface-700'}`} />
          ))}
        </div>
        <span className={`text-xs font-medium ${colors[strength].text}`}>{strength}</span>
      </div>
      <div className="grid grid-cols-2 gap-1">
        {checks.map(({ label, met }) => (
          <div key={label} className={`flex items-center gap-1 text-xs transition-colors ${met ? 'text-accent-green' : 'text-surface-500'}`}>
            {met ? <Check size={10} /> : <X size={10} />}
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}

function OTPInput({ value, onChange }) {
  const inputRefs = useRef([])
  const digits = value.split('').concat(Array(6 - value.length).fill(''))

  useEffect(() => {
    inputRefs.current[0]?.focus()
  }, [])

  const handleChange = (index, e) => {
    const val = e.target.value.replace(/\D/g, '')
    if (!val) return
    const newDigits = [...digits]
    newDigits[index] = val[val.length - 1]
    const newCode = newDigits.join('')
    onChange(newCode)
    if (index < 5 && val) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace') {
      const newDigits = [...digits]
      if (newDigits[index]) {
        newDigits[index] = ''
        onChange(newDigits.join(''))
      } else if (index > 0) {
        newDigits[index - 1] = ''
        onChange(newDigits.join(''))
        inputRefs.current[index - 1]?.focus()
      }
    }
  }

  const handlePaste = (e) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (pasted) {
      onChange(pasted)
      const focusIdx = Math.min(pasted.length, 5)
      inputRefs.current[focusIdx]?.focus()
    }
  }

  return (
    <div className="flex gap-2 justify-center" onPaste={handlePaste}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={el => inputRefs.current[i] = el}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          className="w-12 h-14 text-center text-xl font-bold bg-surface-800/50 border border-surface-700 rounded-lg text-white
            focus:outline-none focus:ring-2 focus:ring-accent-cyan/50 focus:border-accent-cyan transition-all"
        />
      ))}
    </div>
  )
}

export default function Register() {
  // Step: 'email' → 'otp' → 'details'
  const [step, setStep] = useState('email')
  const [email, setEmail] = useState('')
  const [sessionToken, setSessionToken] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [location, setLocation] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [emailExists, setEmailExists] = useState(false)
  const [resendTimer, setResendTimer] = useState(0)
  const [otpExpiryTimer, setOtpExpiryTimer] = useState(0)
  const [socialConfig, setSocialConfig] = useState(null)
  const [acceptedLegal, setAcceptedLegal] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    authApi.getSocialConfig().then(setSocialConfig).catch(() => {})
  }, [])

  const handleSocialRegister = (provider) => {
    if (socialConfig && !socialConfig?.[provider]?.enabled) {
      toast.error(`${provider === 'github' ? 'GitHub' : 'Google'} sign-up is not configured on this server.`, { duration: 5000 })
      return
    }
    startOAuth(provider, 'register')
  }

  const OTP_EXPIRY_SECONDS = 120

  const passwordsMatch = confirm.length > 0 && password === confirm

  const syncExpiryFromResponse = (res) => {
    if (res?.expires_in_seconds) {
      setOtpExpiryTimer(res.expires_in_seconds)
    } else if (res?.expires_at) {
      const remaining = Math.max(0, Math.floor((new Date(res.expires_at) - Date.now()) / 1000))
      setOtpExpiryTimer(remaining)
    } else {
      setOtpExpiryTimer(OTP_EXPIRY_SECONDS)
    }
  }


  // Resend countdown timer
  useEffect(() => {
    if (resendTimer > 0) {
      const t = setTimeout(() => setResendTimer(resendTimer - 1), 1000)
      return () => clearTimeout(t)
    }
  }, [resendTimer])

  // OTP expiry countdown (2 minutes)
  useEffect(() => {
    if (otpExpiryTimer > 0) {
      const t = setTimeout(() => setOtpExpiryTimer(otpExpiryTimer - 1), 1000)
      return () => clearTimeout(t)
    }
  }, [otpExpiryTimer])

  const otpExpiryMinutes = Math.floor(otpExpiryTimer / 60)
  const otpExpirySeconds = otpExpiryTimer % 60

  const handleSendOTP = async (e) => {
    e?.preventDefault()
    setError('')
    setEmailExists(false)
    if (!email.trim()) { setError('Email is required'); return }
    setLoading(true)
    try {
      const res = await authApi.sendOTP(email.trim())
      setSessionToken(res.session_token)
      setStep('otp')
      setResendTimer(60)
      syncExpiryFromResponse(res)
      toast.success('Verification code sent!')
    } catch (err) {
      const data = err.response?.data
      if (data?.error_code === 'email_exists') {
        setEmailExists(true)
        setError('')
      } else {
        setError(data?.error || 'Failed to send verification code')
      }
    } finally { setLoading(false) }
  }

  const handleVerifyOTP = async (e) => {
    e?.preventDefault()
    setError('')
    if (otpExpiryTimer <= 0) {
      setError('OTP expired. Please request a new verification code.')
      return
    }
    if (otpCode.length !== 6) { setError('Please enter the 6-digit code'); return }
    setLoading(true)
    try {
      await authApi.verifyOTP(sessionToken, otpCode)
      setStep('details')
      toast.success('Email verified!')
    } catch (err) {
      const data = err.response?.data
      const msg = data?.error || 'Invalid verification code. Please check the OTP and try again.'
      setError(msg)
      if (data?.error_code === 'otp_expired') {
        setOtpExpiryTimer(0)
      }
    } finally { setLoading(false) }
  }

  const handleResendOTP = async () => {
    setError('')
    setOtpCode('')
    setLoading(true)
    try {
      const res = await authApi.sendOTP(email.trim())
      setSessionToken(res.session_token)
      setResendTimer(60)
      syncExpiryFromResponse(res)
      toast.success('New code sent!')
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to resend code'
      setError(msg)
    } finally { setLoading(false) }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setError('')
    if (password !== confirm) { setError('Passwords do not match'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters'); return }
    if (!firstName.trim()) { setError('First name is required'); return }
    if (!lastName.trim()) { setError('Last name is required'); return }
    if (!phoneNumber.trim()) { setError('Phone number is required'); return }
    if (!acceptedLegal) {
      setError('Please accept the Terms of Service and Privacy Policy to continue.')
      return
    }
    setLoading(true)
    try {
      await authApi.register(email, password, phoneNumber, sessionToken, firstName, lastName, true)
      toast.success('Account created!')
      navigate('/dashboard')
    } catch (err) {
      const data = err.response?.data
      if (data) {
        const msg = data.error || data.detail || data.accepted_legal?.[0]
          || data.email?.[0] || data.password?.[0] || data.phone_number?.[0]
          || 'Registration failed. Please try again.'
        setError(msg)
      } else {
        setError('Network error. Please check your connection.')
      }
    } finally { setLoading(false) }
  }

  const stepIndicators = [
    { key: 'email', label: 'Email' },
    { key: 'otp', label: 'Verify' },
    { key: 'details', label: 'Account' },
  ]
  const currentStepIdx = stepIndicators.findIndex(s => s.key === step)

  return (
    <AuthShell
      title="Create your account"
      subtitle="Start practicing real incident response"
      illustration={<RegisterIllustration />}
      footer={
        <>
          <p className="text-center text-sm text-surface-500 mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-accent-cyan hover:underline font-medium">Sign in</Link>
          </p>
          <div className="flex items-center justify-center gap-6 mt-8 text-surface-600">
            <div className="flex items-center gap-1.5 text-xs">
              <Shield size={12} /> SSL Encrypted
            </div>
            <div className="flex items-center gap-1.5 text-xs">
              <Server size={12} /> Free Tier Available
            </div>
          </div>
        </>
      }
    >
      {/* Step indicator */}
      <div className="flex items-center justify-center gap-2 mb-6">
        {stepIndicators.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
              i < currentStepIdx ? 'bg-accent-green text-black' :
              i === currentStepIdx ? 'bg-accent-cyan text-black' :
              'bg-surface-800 text-surface-500'
            }`}>
              {i < currentStepIdx ? <Check size={14} /> : i + 1}
            </div>
            <span className={`text-xs font-medium ${i <= currentStepIdx ? 'text-white' : 'text-surface-600'}`}>{s.label}</span>
            {i < stepIndicators.length - 1 && (
              <div className={`w-8 h-0.5 ${i < currentStepIdx ? 'bg-accent-green' : 'bg-surface-700'}`} />
            )}
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm p-3 rounded-lg mb-6 animate-slide-up">
          <AlertCircle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {emailExists && step === 'email' && (
        <div className="bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-sm p-4 rounded-lg mb-6 space-y-3 animate-slide-up">
          <p>This email is already registered. Please sign in or reset your password.</p>
          <div className="flex flex-wrap gap-3">
            <Link to="/login" className="btn-primary text-sm py-2 px-4">Sign in</Link>
            <Link to="/forgot-password" className="btn-secondary text-sm py-2 px-4">Forgot password</Link>
          </div>
        </div>
      )}

      {/* Step 1: Email */}
      {step === 'email' && (
        <form onSubmit={handleSendOTP} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                  <input type="email" value={email} onChange={(e) => { setEmail(e.target.value); setError(''); setEmailExists(false) }}
                    className="input-field pl-10" placeholder="you@example.com" required autoComplete="email" autoFocus />
                </div>
                <p className="text-xs text-surface-500 mt-2">We'll send a 6-digit code valid for 2 minutes.</p>
              </div>
              <button type="submit" disabled={loading}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                {loading ? (
                  <><span className="w-4 h-4 border-2 border-surface-950/30 border-t-surface-950 rounded-full animate-spin" /> Sending code...</>
                ) : (
                  <>Send Verification Code <ArrowRight size={16} /></>
                )}
              </button>

              <div className="relative my-2">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-surface-700/50" /></div>
                <div className="relative flex justify-center"><span className="bg-surface-800 px-3 text-xs text-surface-500">or sign up with</span></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <button type="button" onClick={() => handleSocialRegister('github')} className="btn-secondary flex items-center justify-center gap-2 py-2.5 text-sm">
                  <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                  GitHub
                </button>
                <button type="button" onClick={() => handleSocialRegister('google')} className="btn-secondary flex items-center justify-center gap-2 py-2.5 text-sm">
                  <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                  Google
                </button>
              </div>
              <p className="text-xs text-surface-500 text-center">
                OAuth creates your account instantly. Email OTP registration is also available above.
              </p>
            </form>
          )}

          {/* Step 2: OTP Verification */}
          {step === 'otp' && (
            <form onSubmit={handleVerifyOTP} className="space-y-5">
              <div className="text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center">
                  <ShieldCheck size={28} className="text-accent-cyan" />
                </div>
                <p className="text-sm text-surface-400">
                  Enter the 6-digit code sent to
                </p>
                <p className="text-sm font-semibold text-white mt-1">{email}</p>
                {otpExpiryTimer > 0 ? (
                  <p className={`text-xs mt-2 font-medium ${otpExpiryTimer <= 30 ? 'text-accent-amber' : 'text-surface-400'}`}>
                    Code expires in {otpExpiryMinutes}:{otpExpirySeconds.toString().padStart(2, '0')}
                  </p>
                ) : (
                  <p className="text-sm mt-3 font-semibold text-accent-red">
                    OTP expired — regenerate if needed
                  </p>
                )}
              </div>

              {otpExpiryTimer > 0 ? (
                <>
                  <OTPInput value={otpCode} onChange={setOtpCode} />

                  <button type="submit" disabled={loading || otpCode.length !== 6}
                    className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                    {loading ? (
                      <><span className="w-4 h-4 border-2 border-surface-950/30 border-t-surface-950 rounded-full animate-spin" /> Verifying...</>
                    ) : (
                      <>Verify Code <ArrowRight size={16} /></>
                    )}
                  </button>
                </>
              ) : (
                <button type="button" onClick={handleResendOTP} disabled={loading}
                  className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50">
                  {loading ? (
                    <><span className="w-4 h-4 border-2 border-surface-950/30 border-t-surface-950 rounded-full animate-spin" /> Sending...</>
                  ) : (
                    <>Resend Verification Code</>
                  )}
                </button>
              )}

              <div className="flex items-center justify-between text-sm">
                <button type="button" onClick={() => { setStep('email'); setError(''); setOtpCode('') }}
                  className="text-surface-400 hover:text-white flex items-center gap-1 transition-colors">
                  <ArrowLeft size={14} /> Change email
                </button>
                <button type="button" onClick={handleResendOTP}
                  disabled={resendTimer > 0 || loading}
                  className="text-accent-cyan hover:text-accent-cyan/80 disabled:text-surface-600 disabled:cursor-not-allowed transition-colors">
                  {resendTimer > 0 ? `Resend in ${resendTimer}s` : 'Resend code'}
                </button>
              </div>
            </form>
          )}

          {/* Step 3: Account Details */}
          {step === 'details' && (
            <form onSubmit={handleRegister} className="space-y-5">
              <div className="flex items-center gap-2 bg-accent-green/10 border border-accent-green/20 text-accent-green text-sm p-3 rounded-lg mb-2">
                <Check size={16} className="shrink-0" />
                <span>Email verified: <strong>{email}</strong></span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-1.5">First Name</label>
                  <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)}
                    className="input-field" placeholder="John" autoComplete="given-name" autoFocus />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-1.5">Last Name</label>
                  <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)}
                    className="input-field" placeholder="Doe" autoComplete="family-name" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Phone Number</label>
                <div className="relative">
                  <Phone size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                  <input type="tel" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)}
                    className="input-field pl-10" placeholder="+1234567890" autoComplete="tel" required />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Location / Country</label>
                <div className="relative">
                  <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500 w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
                  <input type="text" value={location} onChange={(e) => setLocation(e.target.value)}
                    className="input-field pl-10" placeholder="e.g., United States, India" autoComplete="country-name" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                  <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => { setPassword(e.target.value); setError('') }}
                    className="input-field pl-10 pr-10" placeholder="Create a strong password" required autoComplete="new-password" autoFocus />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300 transition-colors"
                    tabIndex={-1} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <PasswordStrength password={password} />
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Confirm Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                  <input type={showConfirm ? 'text' : 'password'} value={confirm} onChange={(e) => { setConfirm(e.target.value); setError('') }}
                    className={`input-field pl-10 pr-10 ${confirm.length > 0 ? (passwordsMatch ? 'border-accent-green/50 focus:border-accent-green' : 'border-accent-red/50 focus:border-accent-red') : ''}`}
                    placeholder="Repeat your password" required autoComplete="new-password" />
                  <button type="button" onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300 transition-colors"
                    tabIndex={-1} aria-label={showConfirm ? 'Hide password' : 'Show password'}>
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {confirm.length > 0 && !passwordsMatch && (
                  <p className="text-xs text-accent-red mt-1 animate-fade-in">Passwords don't match</p>
                )}
                {passwordsMatch && (
                  <p className="text-xs text-accent-green mt-1 flex items-center gap-1 animate-fade-in"><Check size={10} /> Passwords match</p>
                )}
              </div>

              <label className="flex items-start gap-2 text-xs text-surface-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={acceptedLegal}
                  onChange={(e) => { setAcceptedLegal(e.target.checked); setError('') }}
                  className="mt-0.5 rounded"
                  required
                />
                <span>
                  I agree to the{' '}
                  <Link to="/terms" target="_blank" rel="noreferrer" className="text-accent-cyan hover:underline">
                    Terms of Service
                  </Link>
                  {' '}and{' '}
                  <Link to="/privacy" target="_blank" rel="noreferrer" className="text-accent-cyan hover:underline">
                    Privacy Policy
                  </Link>
                  .
                </span>
              </label>

              <button type="submit" disabled={loading || !acceptedLegal || (confirm.length > 0 && !passwordsMatch)}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                {loading ? (
                  <><span className="w-4 h-4 border-2 border-surface-950/30 border-t-surface-950 rounded-full animate-spin" /> Creating account...</>
                ) : (
                  <>Create Account <ArrowRight size={16} /></>
                )}
              </button>

              <button type="button" onClick={() => { setStep('email'); setError(''); setOtpCode(''); setSessionToken('') }}
                className="w-full text-center text-sm text-surface-500 hover:text-surface-300 transition-colors">
                Use a different email
              </button>
            </form>
          )}
    </AuthShell>
  )
}
