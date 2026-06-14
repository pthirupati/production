import { useState, useMemo, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { Mail, Lock, ArrowRight, AlertCircle, Phone, Eye, EyeOff, Check, X, ShieldCheck, ArrowLeft, Terminal, Server, Cloud, Activity, Shield } from 'lucide-react'
import toast from 'react-hot-toast'

/* ── Animated illustration for registration ── */
function RegisterIllustration() {
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
          {[
            { icon: Terminal, label: 'Live Labs', value: '9+', color: 'accent-cyan' },
            { icon: Server, label: 'Technologies', value: '5', color: 'accent-green' },
            { icon: Cloud, label: 'Cloud Providers', value: '3', color: 'accent-purple' },
            { icon: Activity, label: 'Uptime', value: '99.9%', color: 'accent-amber' },
          ].map(({ icon: Icon, label, value, color }, i) => (
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

        {/* Testimonial */}
        <div className="mt-8 glass-card p-5 animate-fade-in" style={{ animationDelay: '1s' }}>
          <div className="flex mb-2 gap-0.5">
            {[...Array(5)].map((_, i) => (
              <svg key={i} className="w-3.5 h-3.5 text-accent-amber fill-accent-amber" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
            ))}
          </div>
          <p className="text-sm text-surface-300 italic leading-relaxed">"FixitLab is the closest thing to real incident response practice. Way better than reading docs."</p>
          <p className="text-xs text-surface-500 mt-2">— Sarah K., SRE at Cloudflare</p>
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
  const navigate = useNavigate()

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

  const otpExpired = otpExpiryTimer <= 0 && step === 'otp'

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
    setLoading(true)
    try {
      await authApi.register(email, password, phoneNumber, sessionToken, firstName, lastName)
      toast.success('Account created!')
      navigate('/dashboard')
    } catch (err) {
      const data = err.response?.data
      if (data) {
        const msg = data.error || data.detail || data.email?.[0] || data.password?.[0] || data.phone_number?.[0] || 'Registration failed. Please try again.'
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
    <div className="min-h-screen bg-surface-950 flex">
      {/* Left panel — illustration (hidden on mobile) */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-[55%] bg-gradient-to-br from-surface-900 via-surface-950 to-surface-900 relative overflow-hidden">
        <div className="absolute inset-0">
          <div className="glow-orb-cyan absolute top-1/4 left-1/3" />
          <div className="glow-orb-purple absolute bottom-1/4 right-1/4" />
          <div className="absolute inset-0 hero-grid" />
        </div>
        <RegisterIllustration />
        <div className="absolute top-6 left-8 flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/25">
              <Terminal size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">FixitLab</span>
          </Link>
        </div>
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-surface-950 via-surface-950/80 to-transparent p-8 pt-20">
          <p className="text-lg font-semibold text-white">Join 10,000+ engineers</p>
          <p className="text-sm text-surface-400 mt-1">Free tier includes 5 challenges per day — no credit card required</p>
        </div>
      </div>

      {/* Right panel — register form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 relative overflow-y-auto">
        {/* Mobile background */}
        <div className="lg:hidden fixed inset-0 pointer-events-none">
          <div className="absolute inset-0 hero-grid" />
          <div className="glow-orb-cyan absolute top-1/3 right-1/4" />
          <div className="glow-orb-purple absolute bottom-1/3 left-1/4" />
        </div>

      <div className="w-full max-w-md relative animate-fade-in">
        <div className="text-center mb-8">
          <Link to="/" className="lg:hidden inline-flex items-center gap-2 mb-6 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/25 group-hover:shadow-accent-cyan/40 transition-shadow">
              <Terminal size={20} className="text-white" />
            </div>
            <span className="text-2xl font-bold text-white">FixitLab</span>
          </Link>
          <h1 className="text-2xl font-extrabold text-white mb-2">Create Account</h1>
          <p className="text-surface-400">Start your hands-on learning journey</p>
        </div>

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

        <div className="glass-card p-8">
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

              <button type="submit" disabled={loading || (confirm.length > 0 && !passwordsMatch)}
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
        </div>

        <p className="text-center text-sm text-surface-500 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-accent-cyan hover:underline font-medium">Sign in</Link>
        </p>

        {/* Trust badges */}
        <div className="flex items-center justify-center gap-6 mt-8 text-surface-600">
          <div className="flex items-center gap-1.5 text-xs">
            <Shield size={12} /> SSL Encrypted
          </div>
          <div className="flex items-center gap-1.5 text-xs">
            <Server size={12} /> Free Tier Available
          </div>
        </div>
      </div>
      </div>
    </div>
  )
}
