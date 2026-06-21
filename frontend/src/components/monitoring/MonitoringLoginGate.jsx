import { useState } from 'react'

// Two flavors share one gate. Grafana labs land on the Grafana login; Prometheus
// labs land on a Prometheus-styled login. Both are sessionStorage-gated so a
// reload inside the lab does not force a re-login.
const CREDS = {
  grafana: { user: 'lab_grafana', pass: 'lab_grafana@123', product: 'Grafana', sub: 'Welcome to Grafana' },
  prometheus: { user: 'lab_prometheus', pass: 'lab_prometheus@123', product: 'Prometheus', sub: 'Prometheus / Alertmanager' },
}
const STORAGE_KEY = 'fixitlab_monitoring_auth'

export function isMonitoringAuthenticated() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function setMonitoringAuthenticated() {
  try { sessionStorage.setItem(STORAGE_KEY, '1') } catch { /* ignore */ }
}

export function clearMonitoringAuth() {
  try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
}

export default function MonitoringLoginGate({ flavor = 'grafana', onAuthenticated }) {
  const cfg = CREDS[flavor] || CREDS.grafana
  const isGrafana = flavor === 'grafana'
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setTimeout(() => {
      // Accept either flavor's credentials so the shared simulator opens even if
      // the learner reads the other product's creds from the panel.
      const ok = (user === cfg.user && pass === cfg.pass)
        || (user === CREDS.grafana.user && pass === CREDS.grafana.pass)
        || (user === CREDS.prometheus.user && pass === CREDS.prometheus.pass)
      if (ok) {
        setMonitoringAuthenticated()
        onAuthenticated()
      } else {
        setError(`Invalid credentials. Use ${cfg.user} / ${cfg.pass} for training labs.`)
      }
      setLoading(false)
    }, 350)
  }

  const accent = isGrafana ? '#f7913b' : '#e6522c'
  const bg = isGrafana ? 'linear-gradient(135deg,#0b0c1e,#181b2e 60%,#0b0c1e)' : 'linear-gradient(135deg,#1a1206,#241405 60%,#120c05)'

  return (
    <div className="mon-sim min-h-screen flex items-stretch" style={{ background: '#0b0c1e' }}>
      {/* Left brand panel */}
      <div className="hidden md:flex md:w-1/2 lg:w-3/5 flex-col justify-between p-12 relative overflow-hidden" style={{ background: bg }}>
        <div aria-hidden className="absolute inset-0 opacity-25"
             style={{ background: `radial-gradient(900px 500px at 18% 22%, ${accent}44, transparent 60%)` }} />
        <div className="relative flex items-center gap-3">
          {isGrafana ? (
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden>
              <circle cx="12" cy="12" r="11" fill={accent} opacity="0.18" />
              <path d="M5 16c2-5 4-7 7-7s3 2 3 4-1 3-3 3" stroke={accent} strokeWidth="1.8" fill="none" />
              <circle cx="12" cy="9" r="2.5" fill={accent} />
            </svg>
          ) : (
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden>
              <circle cx="12" cy="12" r="10" fill={accent} opacity="0.2" />
              <path d="M12 3a9 9 0 0 0-6 15.7V21h12v-2.3A9 9 0 0 0 12 3z" stroke={accent} strokeWidth="1.6" fill="none" />
              <circle cx="12" cy="12" r="2.4" fill={accent} />
            </svg>
          )}
          <span className="text-2xl font-bold text-white tracking-tight">{cfg.product}</span>
        </div>
        <div className="relative">
          <h1 className="text-[40px] leading-[1.05] font-light text-white mb-3">
            {isGrafana ? <>Observe.<br /><span className="font-semibold">Visualize. Alert.</span></>
                       : <>Monitor.<br /><span className="font-semibold">Query. Alert.</span></>}
          </h1>
          <p className="text-[#9fb6cc] text-sm max-w-md leading-relaxed">
            {isGrafana
              ? 'Dashboards, panels, template variables, alert rules and contact points — the single pane of glass for your metrics.'
              : 'PromQL queries, scrape targets, exporters, recording & alerting rules, and Alertmanager routing.'}
          </p>
        </div>
        <div className="relative text-[11px] text-[#5d7a93]">
          {isGrafana ? 'Grafana 10.4.2' : 'Prometheus 2.51.0'} · FixitLab training environment
        </div>
      </div>

      {/* Right login panel */}
      <div className="w-full md:w-1/2 lg:w-2/5 flex items-center justify-center p-6 border-l" style={{ background: '#101226', borderColor: '#1f2540' }}>
        <div className="w-full max-w-sm">
          <h2 className="text-xl font-semibold text-white mb-1">{cfg.sub}</h2>
          <p className="text-xs text-[#8fa5b8] mb-6">Sign in to continue</p>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-[11px] text-[#8fa5b8] mb-1.5 uppercase tracking-wide">Email or username</label>
              <input value={user} onChange={e => setUser(e.target.value)} className="mon-input w-full"
                     autoComplete="username" placeholder={cfg.user} />
            </div>
            <div>
              <label className="block text-[11px] text-[#8fa5b8] mb-1.5 uppercase tracking-wide">Password</label>
              <input type="password" value={pass} onChange={e => setPass(e.target.value)} className="mon-input w-full"
                     autoComplete="current-password" />
            </div>
            {error && <p className="text-xs text-[#f08080] bg-[rgba(217,83,79,.12)] border border-[rgba(217,83,79,.3)] rounded px-3 py-2">{error}</p>}
            <button type="submit" disabled={loading} className="mon-btn-primary w-full justify-center py-2.5 text-sm font-bold"
                    style={{ background: accent }}>
              {loading ? 'Signing in…' : 'Log in'}
            </button>
            <button type="button"
                    onClick={() => { setUser(cfg.user); setPass(cfg.pass); setError('') }}
                    className="mon-btn w-full justify-center py-2 text-xs">
              Use lab credentials (autofill)
            </button>
          </form>
          <p className="text-[10px] text-[#8fa5b8] text-center leading-relaxed mt-5 pt-4 border-t" style={{ borderColor: '#1f2540' }}>
            Training credentials:{' '}
            <span className="font-mono text-[#E8EDF2]">{cfg.user}</span> /{' '}
            <span className="font-mono text-[#E8EDF2]">{cfg.pass}</span>
          </p>
        </div>
      </div>
    </div>
  )
}
