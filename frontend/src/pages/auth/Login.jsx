import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { Mail, Lock, ArrowRight, AlertCircle, Eye, EyeOff, Shield } from '../../ui/eagerIcons'
import toast from 'react-hot-toast'
import { startOAuth } from '../../utils/oauth'
import { AuthShell } from '../../components/design'

// Map a login request error to an ACCURATE message. Critically, a 429 (throttle)
// or 5xx (server busy / mid-deploy) must NOT be shown as "Invalid credentials" —
// the credentials may be perfectly correct. Only a real 400/401 means bad creds.
function loginErrorMessage(err) {
  const res = err?.response
  if (!res) {
    return err?.code === 'ECONNABORTED'
      ? 'The server took too long to respond. Please try again.'
      : 'Network error — check your connection and try again.'
  }
  const status = res.status
  const data = res.data || {}
  if (status === 429) {
    const retryAfter = res.headers?.['retry-after']
    return retryAfter
      ? `Too many attempts. Please wait ${retryAfter}s and try again.`
      : 'Too many attempts. Please wait a moment and try again.'
  }
  if (status >= 500) {
    return 'The server is temporarily unavailable. Please try again in a moment.'
  }
  if (status === 403) {
    return data.error || 'Access denied. Please contact support if this continues.'
  }
  // 400 / 401 — genuine credential / validation failure. Prefer the server's
  // specific message, fall back to the classic phrasing.
  return data.error || data.detail || 'Invalid credentials'
}

/**
 * Read a post-login redirect target from a `?next=` query string.
 *
 * Unlike the router-state convention, this value IS attacker-controllable — a
 * crafted /login?next=... link is a classic open redirect, and a `javascript:`
 * payload would be worse. So only a same-origin, site-root-relative path is
 * accepted, and everything else degrades to null (the caller's default home):
 *
 *   - must start with a single '/' — rejects 'https://evil.test' and, critically,
 *     protocol-relative '//evil.test', which browsers treat as absolute
 *   - rejects '/\evil.test', which some parsers normalise to a network path
 *   - rejects a bare '/login' target, which would bounce the user straight back
 *
 * Exported for direct testing; there is no other consumer.
 */
export function safeNextParam(search) {
  let next
  try {
    next = new URLSearchParams(search || '').get('next')
  } catch {
    return null
  }
  if (!next) return null
  if (!next.startsWith('/')) return null
  if (next.startsWith('//') || next.startsWith('/\\')) return null
  if (next === '/login' || next.startsWith('/login?')) return null
  return next
}

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [mfaToken, setMfaToken] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)
  const [error, setError] = useState('')
  const [socialConfig, setSocialConfig] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    authApi.getSocialConfig().then(setSocialConfig).catch(() => {})
  }, [])

  const handleSocialLogin = (provider) => {
    if (socialConfig && !socialConfig?.[provider]?.enabled) {
      toast.error(`${provider === 'github' ? 'GitHub' : 'Google'} login is not configured. Add ${provider.toUpperCase()}_CLIENT_ID and ${provider.toUpperCase()}_CLIENT_SECRET to your .env file.`, { duration: 5000 })
      return
    }
    startOAuth(provider, 'login')
  }

  const finishLogin = (data) => {
    toast.success('Welcome back!')
    // Honor a redirect target set by a gated page (e.g. starting a cert exam),
    // otherwise land on the role's default home.
    //
    // Two conventions reach us and both must be honored. ProtectedRoute /
    // AdminRoute (AppRouter.jsx:124,135) pass `location.state.from`, but three
    // call sites redirect with a `?next=` query param instead —
    // PaymentPage.jsx:288 (renewal), :325 (cert checkout) and
    // InterviewInvite.jsx:29 (invitation). Those are the highest-intent deep
    // links in the product and, until this read `next`, all three silently
    // dumped the user on /dashboard. state.from is preferred because it is not
    // attacker-controllable; `next` is validated by safeNextParam.
    const target = location.state?.from || safeNextParam(location.search)
    navigate(target || (data.user?.is_staff ? '/admin' : '/dashboard'))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authApi.login(email, password)
      // Audit Z2-3: MFA accounts get a challenge here, not a session.
      if (data.mfa_required) {
        setMfaToken(data.mfa_token)
        setLoading(false)
        return
      }
      finishLogin(data)
    } catch (err) {
      setError(loginErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleMfaSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authApi.verifyMfa({
        mfaToken,
        ...(useRecovery ? { recoveryCode: mfaCode.trim() } : { code: mfaCode.trim() }),
      })
      if (data.recovery_codes_remaining !== undefined && data.recovery_codes_remaining <= 2) {
        // Running out silently is how people end up locked out permanently.
        toast(`Only ${data.recovery_codes_remaining} recovery codes left — generate new ones in your profile.`,
          { icon: '\u26A0\uFE0F', duration: 8000 })
      }
      finishLogin(data)
    } catch (err) {
      // The challenge expires after 5 minutes; say so rather than showing a bare
      // "invalid code" that sends people hunting for a wrong answer.
      const detail = err?.response?.data?.error
      setError(detail || 'Could not verify that code. Please try again.')
      if (err?.response?.status === 401 && detail?.includes('expired')) {
        setMfaToken('')
        setMfaCode('')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to continue building your skills"
      footer={
        <>
          <p className="text-center text-sm text-surface-500 mt-6">
            Don&apos;t have an account?{' '}
            <Link to="/register" className="text-accent-cyan hover:underline font-medium">Sign up free</Link>
          </p>
          <div className="flex items-center justify-center gap-6 mt-8 text-surface-600">
            <div className="flex items-center gap-1.5 text-xs">
              <Shield size={12} /> SSL Encrypted
            </div>
            <div className="flex items-center gap-1.5 text-xs">
              <Lock size={12} /> Secure Auth
            </div>
          </div>
        </>
      }
    >
      {error && (
        <div className="flex items-center gap-2 bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm p-3 rounded-lg mb-6 animate-slide-up">
          <AlertCircle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Audit Z2-3: second factor. Replaces the credential form rather than
          appearing beside it — leaving the email/password fields on screen invites
          people to retype credentials that were already accepted. */}
      {mfaToken ? (
        <form onSubmit={handleMfaSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5">
              {useRecovery ? 'Recovery code' : 'Authentication code'}
            </label>
            <input
              type="text"
              value={mfaCode}
              onChange={(e) => { setMfaCode(e.target.value); setError('') }}
              className="input-field text-center tracking-[0.4em] text-lg"
              placeholder={useRecovery ? 'xxxxxxxxxx' : '000000'}
              /* `one-time-code` is what lets iOS and Android offer the code from
                 the authenticator or SMS without the user switching apps. */
              autoComplete="one-time-code"
              inputMode={useRecovery ? 'text' : 'numeric'}
              maxLength={useRecovery ? 20 : 6}
              required
              autoFocus
            />
            <p className="text-xs text-surface-500 mt-2">
              {useRecovery
                ? 'Each recovery code works once.'
                : 'Open your authenticator app and enter the 6-digit code.'}
            </p>
          </div>

          <button type="submit" disabled={loading || !mfaCode.trim()} className="btn-primary w-full">
            {loading ? 'Verifying…' : 'Verify'}
          </button>

          <div className="flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={() => { setUseRecovery((v) => !v); setMfaCode(''); setError('') }}
              className="text-accent-cyan hover:underline"
            >
              {useRecovery ? 'Use authenticator code' : 'Lost your device? Use a recovery code'}
            </button>
            <button
              type="button"
              onClick={() => { setMfaToken(''); setMfaCode(''); setUseRecovery(false); setError('') }}
              className="text-surface-500 hover:text-surface-300"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
      <>
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

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-surface-700/50" /></div>
        <div className="relative flex justify-center"><span className="bg-surface-900/80 px-3 text-xs text-surface-500">or continue with</span></div>
      </div>

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
      {socialConfig?.github?.enabled && (
        <p className="text-xs text-surface-500 text-center mt-3">
          Sign in with GitHub or Google if you already have a FixitLab account with the same email.
        </p>
      )}
      </>
      )}
    </AuthShell>
  )
}
