import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { Mail, Lock, ArrowRight, AlertCircle, Eye, EyeOff, Terminal, Server, Shield, Cpu, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import { buildOAuthAuthorizeUrl } from '../../utils/oauth'

/* ── Animated server-room illustration (left panel) ── */
function ServerIllustration() {
  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      {/* Animated grid background */}
      <div className="absolute inset-0 opacity-[0.04]"
        style={{ backgroundImage: 'linear-gradient(rgb(var(--a-cyan)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--a-cyan)) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      {/* Glow orbs */}
      <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-accent-cyan/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-1/3 right-1/4 w-48 h-48 bg-brand-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      <div className="absolute top-1/2 right-1/3 w-32 h-32 bg-accent-purple/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />

      {/* Server rack SVG */}
      <div className="relative z-10 max-w-xs mx-auto px-4">
        <svg viewBox="0 0 400 500" className="w-full drop-shadow-2xl" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Rack frame */}
          <rect x="60" y="40" width="280" height="420" rx="12" className="fill-surface-800/80 stroke-surface-600" strokeWidth="2" />
          <rect x="70" y="50" width="260" height="400" rx="8" className="fill-surface-900/90" />

          {/* Server units */}
          {[0, 1, 2, 3, 4].map((i) => (
            <g key={i} transform={`translate(0, ${i * 75})`}>
              <rect x="85" y="65" width="230" height="60" rx="6" className="fill-surface-800 stroke-surface-700" strokeWidth="1" />
              {/* Status LED */}
              <circle cx="105" cy="95" r="4" className={i < 3 ? 'fill-accent-green' : i === 3 ? 'fill-accent-amber' : 'fill-accent-red'}>
                <animate attributeName="opacity" values="1;0.4;1" dur={`${1.5 + i * 0.3}s`} repeatCount="indefinite" />
              </circle>
              {/* Drive bays */}
              {[0, 1, 2, 3, 4, 5].map((j) => (
                <rect key={j} x={125 + j * 28} y="78" width="20" height="34" rx="2" className="fill-surface-700 stroke-surface-600" strokeWidth="0.5" />
              ))}
              {/* Activity LEDs */}
              <circle cx="296" cy="88" r="2" className="fill-accent-cyan">
                <animate attributeName="opacity" values="0;1;0" dur={`${0.2 + i * 0.1}s`} repeatCount="indefinite" />
              </circle>
              <circle cx="296" cy="102" r="2" className="fill-accent-cyan/40" />
            </g>
          ))}
        </svg>

        {/* Floating badges */}
        <div className="absolute -top-4 -right-4 bg-surface-800/90 backdrop-blur border border-accent-green/30 rounded-lg px-3 py-2 animate-bounce" style={{ animationDuration: '3s' }}>
          <div className="flex items-center gap-2 text-accent-green text-xs font-medium">
            <Shield size={14} /> Secure
          </div>
        </div>
        <div className="absolute top-1/3 -left-8 bg-surface-800/90 backdrop-blur border border-accent-cyan/30 rounded-lg px-3 py-2 animate-bounce" style={{ animationDuration: '4s', animationDelay: '1s' }}>
          <div className="flex items-center gap-2 text-accent-cyan text-xs font-medium">
            <Cpu size={14} /> 99.9% Uptime
          </div>
        </div>
        <div className="absolute bottom-1/4 -right-6 bg-surface-800/90 backdrop-blur border border-accent-amber/30 rounded-lg px-3 py-2 animate-bounce" style={{ animationDuration: '3.5s', animationDelay: '0.5s' }}>
          <div className="flex items-center gap-2 text-accent-amber text-xs font-medium">
            <Zap size={14} /> Live Labs
          </div>
        </div>
      </div>

      {/* Bottom terminal snippet */}
      <div className="absolute bottom-8 left-8 right-8 bg-surface-900/90 backdrop-blur border border-surface-700/50 rounded-xl p-4 text-left">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2.5 h-2.5 rounded-full bg-accent-red/70" />
          <div className="w-2.5 h-2.5 rounded-full bg-accent-amber/70" />
          <div className="w-2.5 h-2.5 rounded-full bg-accent-green/70" />
          <span className="text-[10px] text-surface-500 ml-2 font-mono">terminal</span>
        </div>
        <div className="font-mono text-xs space-y-1">
          <p><span className="text-accent-green">$</span> <span className="text-surface-300">ssh lab@fixitlab.com</span></p>
          <p className="text-surface-500">Connected to scenario: <span className="text-accent-cyan">broken-nginx</span></p>
          <p><span className="text-accent-green">root@lab</span>:<span className="text-brand-400">~</span># <span className="text-surface-400 animate-pulse">▊</span></p>
        </div>
      </div>
    </div>
  )
}

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [socialConfig, setSocialConfig] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    authApi.getSocialConfig().then(setSocialConfig).catch(() => {})
  }, [])

  const handleSocialLogin = (provider) => {
    if (!socialConfig?.[provider]?.enabled) {
      toast.error(`${provider === 'github' ? 'GitHub' : 'Google'} login is not configured. Add ${provider.toUpperCase()}_CLIENT_ID and ${provider.toUpperCase()}_CLIENT_SECRET to your .env file.`, { duration: 5000 })
      return
    }
    sessionStorage.setItem('oauth_intent', 'login')
    const url = buildOAuthAuthorizeUrl(socialConfig, provider)
    if (!url) return
    window.location.href = url
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authApi.login(email, password)
      toast.success('Welcome back!')
      navigate(data.user?.is_staff ? '/admin' : '/dashboard')
    } catch (err) {
      setError(err.response?.data?.error || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-950 flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-[55%] bg-gradient-to-br from-surface-900 via-surface-950 to-surface-900 relative overflow-hidden">
        {/* Background decorations */}
        <div className="absolute inset-0">
          <div className="glow-orb-cyan absolute top-1/4 left-1/3" />
          <div className="glow-orb-purple absolute bottom-1/4 right-1/4" />
          <div className="absolute inset-0 hero-grid" />
        </div>
        <ServerIllustration />
        {/* Brand overlay at top */}
        <div className="absolute top-6 left-8 flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/25">
              <Terminal size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">FixitLab</span>
          </Link>
        </div>
        </div>

      {/* Right panel — login form */}
      <div className="flex-1 flex items-center justify-center px-6 py-8 relative">
        {/* Mobile-only decorative background */}
        <div className="lg:hidden fixed inset-0 pointer-events-none">
          <div className="absolute inset-0 hero-grid" />
          <div className="glow-orb-cyan absolute top-1/4 left-1/4" />
          <div className="glow-orb-purple absolute bottom-1/4 right-1/4" />
        </div>

        <div className="w-full max-w-lg relative animate-fade-in">
          {/* Mobile logo */}
          <div className="text-center mb-8 lg:mb-10">
            <Link to="/" className="lg:hidden inline-flex items-center gap-2 mb-6 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-purple flex items-center justify-center shadow-lg shadow-accent-cyan/20 group-hover:shadow-accent-cyan/40 transition-shadow">
                <Terminal size={20} className="text-white" />
              </div>
              <span className="text-2xl font-bold text-white">FixitLab</span>
            </Link>
            <h1 className="text-3xl font-extrabold text-white mb-2">Welcome back</h1>
            <p className="text-surface-400">Sign in to continue building your skills</p>
          </div>

          <div className="glass-card p-8">
            {error && (
              <div className="flex items-center gap-2 bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm p-3 rounded-lg mb-6 animate-slide-up">
                <AlertCircle size={16} className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError('') }}
                    className="input-field pl-10"
                    placeholder="you@example.com"
                    required
                    autoComplete="email"
                    autoFocus
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setError('') }}
                    className="input-field pl-10 pr-10"
                    placeholder="••••••••"
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300 transition-colors"
                    tabIndex={-1}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4 rounded border-surface-600 bg-surface-800 text-accent-cyan focus:ring-accent-cyan/30" />
                  <span className="text-sm text-surface-400">Remember me</span>
                </label>
                <Link to="/forgot-password" className="text-sm text-accent-cyan hover:underline transition-colors">
                  Forgot password?
                </Link>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full flex items-center justify-center gap-2 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <><span className="w-4 h-4 border-2 border-surface-950/30 border-t-surface-950 rounded-full animate-spin" /> Signing in...</>
                ) : (
                  <>Sign In <ArrowRight size={16} /></>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-surface-700/50" /></div>
              <div className="relative flex justify-center"><span className="bg-surface-800 px-3 text-xs text-surface-500">or continue with</span></div>
            </div>

            {/* Social login */}
            <div className="grid grid-cols-2 gap-3">
              <button type="button" onClick={() => handleSocialLogin('github')} className="btn-secondary flex items-center justify-center gap-2 py-2.5 text-sm">
                <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                GitHub
              </button>
              <button type="button" onClick={() => handleSocialLogin('google')} className="btn-secondary flex items-center justify-center gap-2 py-2.5 text-sm">
                <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                Google
              </button>
            </div>
            <p className="text-xs text-surface-500 text-center mt-3">
              GitHub and Google sign-in only work for existing accounts. New users must{' '}
              <Link to="/register" className="text-accent-cyan hover:underline">register first</Link>.
            </p>
          </div>

          <p className="text-center text-sm text-surface-500 mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-accent-cyan hover:underline font-medium">Sign up free</Link>
          </p>

          {/* Trust badges */}
          <div className="flex items-center justify-center gap-6 mt-8 text-surface-600">
            <div className="flex items-center gap-1.5 text-xs">
              <Shield size={12} /> SSL Encrypted
            </div>
            <div className="flex items-center gap-1.5 text-xs">
              <Lock size={12} /> Secure Auth
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
