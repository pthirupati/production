import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Shield, AlertTriangle, Lock, CreditCard, RotateCcw, Mail, KeyRound } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminSecurity() {
  const [metrics, setMetrics] = useState(null)
  const [days, setDays] = useState(7)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [days])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getSecurityMetrics(days)
      setMetrics(data)
    } catch {
      toast.error('Failed to load security metrics')
    } finally {
      setLoading(false)
    }
  }

  if (loading || !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const email = metrics.email_stats || {}

  const cards = [
    { label: 'Failed logins', value: metrics.login_failed, icon: Lock, color: 'text-red-400' },
    { label: 'Successful logins', value: metrics.login_success, icon: Shield, color: 'text-green-400' },
    { label: 'OTP failures', value: metrics.otp_failed || 0, icon: KeyRound, color: 'text-orange-400' },
    { label: 'Emails failed', value: email.failed ?? 0, icon: Mail, color: 'text-red-400' },
    { label: 'Emails sent', value: email.sent ?? 0, icon: Mail, color: 'text-green-400' },
    { label: 'Lab resets', value: metrics.lab_resets, icon: RotateCcw, color: 'text-amber-400' },
    { label: 'Payment failures', value: metrics.payment_failed, icon: CreditCard, color: 'text-orange-400' },
    { label: 'Security alerts', value: metrics.security_alerts, icon: AlertTriangle, color: 'text-purple-400' },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Security & Delivery</h1>
          <p className="text-surface-400 mt-1">Login failures, email delivery, brute-force signals, payment anomalies</p>
        </div>
        <select className="input-field" value={days} onChange={e => setDays(Number(e.target.value))}>
          <option value={1}>Last 24 hours</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      </div>

      <div className="glass-card p-4 flex flex-wrap items-center gap-4 text-sm">
        <span className="text-surface-400">Gmail API:</span>
        <span className={email.gmail_ok ? 'text-accent-green' : 'text-accent-red'}>
          {email.gmail_configured
            ? (email.gmail_ok ? 'Connected' : `Error — ${email.gmail_message || 'refresh failed'}`)
            : 'Not configured'}
        </span>
        {email.failed > 0 && email.sent === 0 && (
          <span className="text-accent-amber text-xs">
            Check GMAIL_OAUTH_* in .env.production and re-run scripts/setup-gmail-oauth.py
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="glass-card p-4">
            <Icon size={20} className={`${color} mb-2`} />
            <p className="text-2xl font-bold text-white">{value}</p>
            <p className="text-xs text-surface-400 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {metrics.suspicious_ips?.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Suspicious IPs (5+ failed logins)</h2>
          <div className="space-y-2">
            {metrics.suspicious_ips.map((row, i) => (
              <div key={i} className="flex justify-between text-sm py-2 border-b border-surface-800 last:border-0">
                <span className="font-mono text-red-400">{row.ip_address}</span>
                <span className="text-surface-400">{row.count} failures</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Recent security events</h2>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {(metrics.recent_events || []).map((ev, i) => (
            <div key={i} className="text-sm py-2 border-b border-surface-800/50 last:border-0">
              <div className="flex flex-wrap gap-2 items-center">
                <span className="text-xs uppercase tracking-wide text-accent-amber">{ev.action}</span>
                <span className="text-surface-500">{new Date(ev.created_at).toLocaleString()}</span>
                {ev.user__username && <span className="text-surface-400">@{ev.user__username}</span>}
                {ev.ip_address && <span className="font-mono text-surface-500">{ev.ip_address}</span>}
              </div>
              {ev.resource && <p className="text-surface-400 mt-0.5 truncate">{ev.resource}</p>}
            </div>
          ))}
          {!metrics.recent_events?.length && (
            <p className="text-surface-500 text-sm">No security events in this period.</p>
          )}
        </div>
      </div>
    </div>
  )
}
