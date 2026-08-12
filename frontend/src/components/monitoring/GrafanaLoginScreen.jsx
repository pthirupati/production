import { useState } from 'react'
import { User, Lock, LogIn, Loader2, AlertCircle } from 'lucide-react'
import { setMonitoringAuthenticated } from './MonitoringLoginGate'
import MonitoringLabChrome from './MonitoringLabChrome'
import { useModalA11y } from '../ConfirmModal'
import '../../styles/monitoring-sim.css'

const ACCENT = '#f7913b'

// Accepted training credentials. The dedicated lab account plus Grafana's
// classic default (admin/admin) for realism in the hands-on environment.
const VALID = [
  { user: 'lab_grafana', pass: 'lab_grafana@123' },
  { user: 'admin', pass: 'admin' },
]

/* ── Original "Grafana-style" orb mark (CSS/SVG, not the real logo) ── */
function GrafanaOrb({ size = 52 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <defs>
        <radialGradient id="grafOrbGlow" cx="38%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#ffd27a" />
          <stop offset="45%" stopColor={ACCENT} />
          <stop offset="100%" stopColor="#c45e10" />
        </radialGradient>
      </defs>
      <circle cx="24" cy="24" r="22" fill={ACCENT} opacity="0.14" />
      <circle cx="24" cy="24" r="15" fill="url(#grafOrbGlow)" />
      {/* stylized rising-line motif over the orb */}
      <path d="M14 30c3-8 6-11 10-11s5 3 5 6-2 5-5 5"
            stroke="#1a1206" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <circle cx="24" cy="19" r="3" fill="#1a1206" />
    </svg>
  )
}

/**
 * GrafanaLoginScreen — an original, functional emulation of Grafana's login
 * page for the FixitLab monitoring training labs. Centered card on a dark
 * gradient. On a successful sign-in it marks the shared monitoring session as
 * authenticated and invokes the supplied callback.
 *
 * Props: { onAuthenticated, scenario, onExit, onStop, onHints }
 * The lab chrome handlers are forwarded from MonitoringSimulator so Hints /
 * Stop / Back to lab stay reachable even before the learner signs in.
 */
export default function GrafanaLoginScreen({
  onAuthenticated, scenario, onExit, onStop, onHints,
  onCheck, onExtend, hintsLabel, checkDisabled, extendDisabled, embedded = false,
  vmwareHref = null,
}) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const loginCardRef = useModalA11y(true, onExit || (() => {}))

  const submit = (e) => {
    e.preventDefault()
    if (loading) return
    setLoading(true)
    setError('')
    // Brief loading state for authenticity.
    setTimeout(() => {
      const ok = VALID.some(c => c.user === user.trim() && c.pass === pass)
      if (ok) {
        setMonitoringAuthenticated()
        if (typeof onAuthenticated === 'function') onAuthenticated()
      } else {
        setError('Invalid username or password.')
        setLoading(false)
      }
    }, 350)
  }

  const shellClass = embedded
    ? 'mon-sim mon-shell h-full min-h-0 flex flex-col relative overflow-hidden'
    : 'mon-sim mon-shell min-h-[100dvh] flex flex-col relative overflow-hidden'

  return (
    <div
      className={shellClass}
      style={{ background: 'radial-gradient(1100px 620px at 50% -10%, #1c1322 0%, #0b0c1e 55%, #07080f 100%)' }}
    >
      {/* Lab chrome — keeps Hints / Check / +30m / Stop reachable before sign-in. */}
      <MonitoringLabChrome
        product="Grafana"
        accent={ACCENT}
        subtitle={scenario?.title || scenario?.slug || ''}
        onExit={onExit}
        onStop={onStop}
        onHints={onHints}
        onCheck={onCheck}
        onExtend={onExtend}
        hintsLabel={hintsLabel}
        checkDisabled={checkDisabled}
        extendDisabled={extendDisabled}
        vmwareHref={vmwareHref}
      />

      {/* ambient accent glow */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none"
        style={{ background: `radial-gradient(720px 420px at 50% 14%, ${ACCENT}24, transparent 65%)` }}
      />

      <div className="flex-1 flex items-center justify-center p-6 relative">

      <div className="relative w-full max-w-[380px]">
        {/* brand mark + wordmark */}
        <div className="flex flex-col items-center mb-7">
          <GrafanaOrb />
          <span className="mt-3 text-[22px] font-bold tracking-tight text-white">Grafana</span>
        </div>

        <div
          ref={loginCardRef}
          tabIndex={-1}
          role="dialog"
          aria-modal="true"
          aria-label="Sign in to Grafana"
          className="mon-card !p-7 outline-none"
          style={{ borderColor: '#262a45', background: '#121425' }}
        >
          <h1 className="text-center text-lg font-semibold mb-1" style={{ color: '#d8def0' }}>
            Welcome to Grafana
          </h1>
          <p className="text-center text-xs mb-6" style={{ color: '#8a93b2' }}>
            Sign in to your training instance
          </p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-[11px] uppercase tracking-wide mb-1.5" style={{ color: '#8a93b2' }}>
                Username
              </label>
              <div className="relative">
                <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: '#8a93b2' }} />
                <input
                  className="mon-input w-full !pl-9"
                  value={user}
                  autoComplete="username"
                  spellCheck={false}
                  placeholder="email or username"
                  onChange={e => setUser(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wide mb-1.5" style={{ color: '#8a93b2' }}>
                Password
              </label>
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: '#8a93b2' }} />
                <input
                  type="password"
                  className="mon-input w-full !pl-9"
                  value={pass}
                  autoComplete="current-password"
                  placeholder="password"
                  onChange={e => setPass(e.target.value)}
                />
              </div>
            </div>

            {error && (
              <div className="mon-banner mon-banner-err !mb-0 text-xs">
                <AlertCircle size={14} className="shrink-0" /> {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mon-btn-primary w-full justify-center py-2.5 text-sm font-bold"
              style={{ background: ACCENT, color: '#1a1206', opacity: loading ? 0.75 : 1 }}
            >
              {loading
                ? <><Loader2 size={15} className="animate-spin" /> Logging in…</>
                : <><LogIn size={15} /> Log in</>}
            </button>

            <div className="text-center">
              <button
                type="button"
                className="text-xs hover:underline"
                style={{ color: '#8a93b2' }}
                onClick={(e) => e.preventDefault()}
              >
                Forgot your password?
              </button>
            </div>
          </form>
        </div>

        <p
          className="text-center text-[11px] leading-relaxed mt-5"
          style={{ color: '#8a93b2' }}
        >
          Training credentials:{' '}
          <span className="mon-code !inline !px-1.5 !py-0.5">lab_grafana</span>
          {' / '}
          <span className="mon-code !inline !px-1.5 !py-0.5">lab_grafana@123</span>
        </p>
      </div>
      </div>
    </div>
  )
}
