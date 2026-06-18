import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Shield, AlertTriangle, Lock, CreditCard, RotateCcw, Mail, KeyRound, Ban, Globe, X, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'

const METRIC_KEYS = [
  { key: 'login_failed', label: 'Failed logins', icon: Lock, color: 'text-red-400' },
  { key: 'login_success', label: 'Successful logins', icon: Shield, color: 'text-green-400' },
  { key: 'otp_failed', label: 'OTP failures', icon: KeyRound, color: 'text-orange-400' },
  { key: 'payment_failed', label: 'Payment failures', icon: CreditCard, color: 'text-orange-400' },
  { key: 'email_failed', label: 'Email failures', icon: Mail, color: 'text-red-300' },
  { key: 'rate_limit_hits', label: 'Rate limit hits', icon: AlertTriangle, color: 'text-amber-400' },
  { key: 'lab_resets', label: 'Lab resets', icon: RotateCcw, color: 'text-amber-400' },
  { key: 'security_alerts', label: 'Security alerts', icon: AlertTriangle, color: 'text-purple-400' },
]

export default function AdminSecurity() {
  const [metrics, setMetrics] = useState(null)
  const [days, setDays] = useState(7)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [clearingEmails, setClearingEmails] = useState(false)
  const [blockIp, setBlockIp] = useState('')
  const [blockUserEmail, setBlockUserEmail] = useState('')
  const [blockCountry, setBlockCountry] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      setMetrics(await adminApi.getSecurityMetrics(days))
    } catch {
      toast.error('Failed to load security metrics')
    } finally {
      setLoading(false)
    }
  }

  const handleBlockUser = async (email, block = true) => {
    if (!email?.trim()) return
    try {
      await adminApi.securityAction({
        action: block ? 'block_user' : 'unblock_user',
        email: email.trim(),
      })
      toast.success(block ? `Blocked ${email}` : `Unblocked ${email}`)
      setBlockUserEmail('')
    } catch {
      toast.error('User action failed')
    }
  }

  useEffect(() => { loadData() }, [days])

  const openDetail = async (metricKey) => {
    setDetailLoading(true)
    setDetail({ metric: metricKey, rows: [] })
    try {
      const data = await adminApi.getSecurityDetail(metricKey, days)
      // Backend returns { detail: '...', rows: [] } — normalise to metric key
      setDetail({ metric: data.detail || metricKey, rows: data.rows || [] })
    } catch {
      toast.error('Failed to load details')
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleBlockIp = async (ip) => {
    try {
      const res = await adminApi.securityAction({ action: 'block_ip', ip })
      setMetrics(m => ({ ...m, blocked_ips: res.blocked_ips }))
      toast.success(`Blocked ${ip}`)
    } catch {
      toast.error('Block failed')
    }
  }

  const handleUnblockIp = async (ip) => {
    try {
      const res = await adminApi.securityAction({ action: 'unblock_ip', ip })
      setMetrics(m => ({ ...m, blocked_ips: res.blocked_ips }))
      toast.success(`Unblocked ${ip}`)
    } catch {
      toast.error('Unblock failed')
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

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Security & Delivery</h1>
          <p className="text-surface-400 mt-1">Click any metric to inspect events, block IPs, or review delivery health</p>
        </div>
        <div className="flex gap-2">
          <select className="input-field text-sm" value={days} onChange={e => setDays(Number(e.target.value))}>
            <option value={1}>Last 24 hours</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <button type="button" onClick={loadData} className="btn-secondary text-sm">Refresh</button>
        </div>
      </div>

      <div className="glass-card p-4 flex flex-wrap items-center gap-4 text-sm">
        <span className="text-surface-400">Gmail API:</span>
        <span className={email.gmail_ok ? 'text-accent-green' : 'text-accent-red'}>
          {email.gmail_configured ? (email.gmail_ok ? 'Connected' : `Error — ${email.gmail_message || 'refresh failed'}`) : 'Not configured'}
        </span>
        <span className="text-surface-500">|</span>
        <span className="text-surface-400">Emails sent: <strong className="text-white">{email.sent ?? 0}</strong></span>
        <span className="text-surface-400">Failed: <strong className="text-accent-red">{email.failed ?? 0}</strong></span>
        <button type="button" className="text-xs text-accent-cyan hover:underline" onClick={() => openDetail('email_failed')}>
          View email failures
        </button>
        <button
          type="button"
          disabled={clearingEmails}
          className="text-xs text-accent-red hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={async () => {
            setClearingEmails(true)
            try {
              const res = await adminApi.securityAction({ action: 'clear_email_failures' })
              toast.success(`Cleared ${res.cleared || 0} failed email log(s)`)
              loadData()
              setDetail(null)
            } catch { toast.error('Clear failed') } finally { setClearingEmails(false) }
          }}
        >
          {clearingEmails ? 'Clearing…' : 'Clear failures'}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {METRIC_KEYS.map(({ key, label, icon: Icon, color }) => (
          <button
            key={key}
            type="button"
            onClick={() => openDetail(key)}
            className="glass-card glass-card-hover p-4 text-left group"
          >
            <Icon size={18} className={`${color} mb-2`} />
            <p className="text-2xl font-bold text-white">{metrics[key] ?? 0}</p>
            <p className="text-xs text-surface-400 mt-1 flex items-center justify-between">
              {label}
              <ChevronRight size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
            </p>
          </button>
        ))}
      </div>

      {/* Block IP / country / user */}
      <div className="grid md:grid-cols-3 gap-4">
        <div className="glass-card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Ban size={16} /> Block user account</h2>
          <div className="flex gap-2">
            <input className="input-field flex-1 text-sm" placeholder="user@email.com" value={blockUserEmail} onChange={e => setBlockUserEmail(e.target.value)} />
            <button type="button" className="btn-primary text-sm" onClick={() => handleBlockUser(blockUserEmail, true)}>Block</button>
          </div>
        </div>
        <div className="glass-card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Ban size={16} /> Block IP address</h2>
          <div className="flex gap-2">
            <input className="input-field flex-1 text-sm font-mono" placeholder="203.0.113.42" value={blockIp} onChange={e => setBlockIp(e.target.value)} />
            <button type="button" className="btn-primary text-sm" onClick={() => { handleBlockIp(blockIp); setBlockIp('') }}>Block</button>
          </div>
          {(metrics.blocked_ips || []).length > 0 && (
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {metrics.blocked_ips.map(ip => (
                <div key={ip} className="flex justify-between text-xs py-1 border-b border-surface-800">
                  <span className="font-mono text-red-400">{ip}</span>
                  <button type="button" className="text-surface-400 hover:text-white" onClick={() => handleUnblockIp(ip)}>Unblock</button>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="glass-card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Globe size={16} /> Block country (ISO code)</h2>
          <div className="flex gap-2">
            <input className="input-field flex-1 text-sm uppercase" placeholder="CN" maxLength={2} value={blockCountry} onChange={e => setBlockCountry(e.target.value)} />
            <button type="button" className="btn-secondary text-sm" onClick={async () => {
              try {
                const res = await adminApi.securityAction({ action: 'block_country', country: blockCountry })
                setMetrics(m => ({ ...m, blocked_countries: res.blocked_countries }))
                setBlockCountry('')
                toast.success('Country blocked')
              } catch { toast.error('Failed') }
            }}>Block</button>
          </div>
          {(metrics.blocked_countries || []).map(c => (
            <div key={c} className="flex justify-between text-xs">
              <span className="font-mono">{c}</span>
              <button type="button" className="text-surface-400 hover:text-white" onClick={async () => {
                const res = await adminApi.securityAction({ action: 'unblock_country', country: c })
                setMetrics(m => ({ ...m, blocked_countries: res.blocked_countries }))
              }}>Unblock</button>
            </div>
          ))}
        </div>
      </div>

      {metrics.suspicious_ips?.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Threat IPs (5+ failed logins)</h2>
          <div className="space-y-2">
            {metrics.suspicious_ips.map((row, i) => (
              <div key={i} className="flex justify-between items-center text-sm py-2 border-b border-surface-800 last:border-0">
                <span className="font-mono text-red-400">{row.ip_address}</span>
                <div className="flex items-center gap-3">
                  <span className="text-surface-400">{row.count} failures</span>
                  <button type="button" className="btn-secondary text-xs py-1 px-2" onClick={() => handleBlockIp(row.ip_address)}>Block</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detail modal */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="glass-card w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-surface-700">
              <h3 className="font-semibold text-white capitalize">{detail.metric?.replace(/_/g, ' ')} — details</h3>
              <button type="button" onClick={() => setDetail(null)} className="p-1 text-surface-400 hover:text-white"><X size={18} /></button>
            </div>
            <div className="overflow-y-auto p-4 space-y-2 flex-1">
              {detailLoading ? (
                <p className="text-surface-500 text-sm">Loading…</p>
              ) : (detail.rows || []).map((row, i) => (
                <div key={row.id || i} className="text-sm py-2 border-b border-surface-800/50">
                  <div className="flex flex-wrap gap-2 items-center">
                    <span className="text-surface-500">{new Date(row.created_at).toLocaleString()}</span>
                    {row.user__username && <span className="text-surface-300">@{row.user__username}</span>}
                    {row.to_email && <span className="text-accent-cyan">{row.to_email}</span>}
                    {row.ip_address && (
                      <>
                        <span className="font-mono text-surface-400">{row.ip_address}</span>
                        <button type="button" className="text-xs text-accent-red hover:underline" onClick={() => handleBlockIp(row.ip_address)}>Block IP</button>
                      </>
                    )}
                  </div>
                  {row.subject && <p className="text-white mt-0.5 font-medium">{row.subject}</p>}
                  {row.error && <p className="text-accent-red text-xs mt-0.5 whitespace-pre-wrap">{row.error}</p>}
                  {row.resource && <p className="text-surface-400 mt-0.5 truncate">{row.resource}</p>}
                </div>
              ))}
              {!detailLoading && !detail.rows?.length && (
                <p className="text-surface-500 text-sm">No events in this period.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
