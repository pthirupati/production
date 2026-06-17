import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api/admin'
import toast from 'react-hot-toast'
import {
  Users, Target, MonitorPlay, TrendingUp,
  Activity, CheckCircle2, XCircle, AlertCircle,
  Mail, Server, RefreshCw, Globe,
  UserPlus, Play, CheckCircle, XOctagon,
  Send, Database, Wifi, MessageSquare, Cpu,
  DollarSign, UserCheck, Wrench,
  RotateCcw, ArrowUpRight, ShieldCheck, Zap,
  ChevronUp, ChevronDown, Minus
} from 'lucide-react'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTimeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function formatUptime(startedAt) {
  if (!startedAt) return '—'
  const diff = Date.now() - new Date(startedAt).getTime()
  const hours = Math.floor(diff / 3600000)
  const mins = Math.floor((diff % 3600000) / 60000)
  if (hours < 1) return `${mins}m`
  if (hours < 24) return `${hours}h ${mins}m`
  const days = Math.floor(hours / 24)
  return `${days}d ${hours % 24}h`
}

// ─── Sparkline bar chart ──────────────────────────────────────────────────────

function Sparkline({ color = 'bg-accent-cyan', seed = 0 }) {
  const heights = Array.from({ length: 6 }, (_, i) => {
    const val = ((seed * 37 + i * 17) % 70) + 20
    return Math.min(100, Math.max(20, val))
  })
  heights[5] = 92
  return (
    <div className="flex items-end gap-0.5 h-8 mt-auto shrink-0">
      {heights.map((h, i) => (
        <div
          key={i}
          className={`w-2 rounded-sm transition-all ${color} ${i === 5 ? 'opacity-100' : 'opacity-35'}`}
          style={{ height: `${h}%` }}
        />
      ))}
    </div>
  )
}

// ─── Delta badge ──────────────────────────────────────────────────────────────

function Delta({ value, suffix = '' }) {
  if (value == null) return null
  const num = typeof value === 'number' ? value : parseFloat(value)
  if (isNaN(num)) return null
  if (num > 0) return (
    <span className="flex items-center gap-0.5 text-[11px] font-semibold text-accent-green">
      <ChevronUp size={12} />{Math.abs(num)}{suffix}
    </span>
  )
  if (num < 0) return (
    <span className="flex items-center gap-0.5 text-[11px] font-semibold text-accent-red">
      <ChevronDown size={12} />{Math.abs(num)}{suffix}
    </span>
  )
  return (
    <span className="flex items-center gap-0.5 text-[11px] font-semibold text-surface-500">
      <Minus size={12} />0{suffix}
    </span>
  )
}

// ─── KPI stat card ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, delta, deltaSuffix, icon: Icon, color, sparkColor, seed }) {
  return (
    <div className="glass-card glass-card-hover p-5 flex flex-col gap-2 group">
      <div className="flex items-center justify-between">
        <div className="p-2 rounded-lg bg-surface-800/60 group-hover:bg-surface-700/60 transition-colors">
          <Icon size={17} className={color} />
        </div>
        <Delta value={delta} suffix={deltaSuffix} />
      </div>
      <div>
        <p className="text-[26px] font-bold text-white leading-tight tracking-tight">{value}</p>
        <p className="text-xs font-medium text-surface-400 mt-0.5">{label}</p>
      </div>
      <div className="flex items-end justify-between gap-2 mt-auto">
        <p className="text-[11px] text-surface-500 leading-snug">{sub}</p>
        <Sparkline color={sparkColor || 'bg-accent-cyan'} seed={seed || 0} />
      </div>
    </div>
  )
}

// ─── Icon maps ────────────────────────────────────────────────────────────────

const SERVICE_ICONS = {
  'Database': Database,
  'Redis': Cpu,
  'Docker': Server,
  'Email': Mail,
  'RabbitMQ': MessageSquare,
  'Celery Workers': Activity,
  'Vault': ShieldCheck,
}

const CONTAINER_SERVICE_ICONS = {
  database: Database,
  redis: Cpu,
  rabbitmq: MessageSquare,
  vault: ShieldCheck,
  backend: Server,
  frontend: Globe,
  gateway: Wifi,
  celery: Activity,
  pgbouncer: Database,
}

function containerIcon(name) {
  const n = (name || '').toLowerCase()
  for (const [k, Icon] of Object.entries(CONTAINER_SERVICE_ICONS)) {
    if (n.includes(k)) return Icon
  }
  return Server
}

const ACTIVITY_ICONS = {
  'registration': UserPlus,
  'lab_start': Play,
  'lab_completed': CheckCircle,
  'lab_failed': XOctagon,
}

const ACTIVITY_COLORS = {
  'registration': 'text-accent-cyan bg-accent-cyan/10',
  'lab_start': 'text-accent-amber bg-accent-amber/10',
  'lab_completed': 'text-accent-green bg-accent-green/10',
  'lab_failed': 'text-accent-red bg-accent-red/10',
}

// ─── Revenue area chart ───────────────────────────────────────────────────────

function RevenueArea({ total, currency }) {
  const bars = [42, 58, 51, 67, 74, 63, 80, 72, 85, 78, 90, 100]
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <TrendingUp size={18} className="text-accent-green" />
          Revenue Trend
        </h2>
        <span className="text-2xl font-bold text-accent-green">{total}</span>
      </div>
      <p className="text-xs text-surface-500 mb-4">Total revenue · {currency}</p>
      <div className="relative h-24 flex items-end gap-1">
        <div
          className="absolute inset-0 rounded-lg opacity-10"
          style={{ background: 'linear-gradient(to top, rgba(52,211,153,0.8), transparent)' }}
        />
        {bars.map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-t-sm bg-accent-green/60 hover:bg-accent-green/90 transition-all cursor-default"
            style={{ height: `${h}%` }}
            title={`Month ${i + 1}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-surface-600 mt-1">
        <span>12mo ago</span>
        <span>Now</span>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null)
  const [currency, setCurrency] = useState('INR')
  const [health, setHealth] = useState(null)
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchOverview = useCallback(async () => {
    try {
      const [o, a, cfg] = await Promise.all([
        adminApi.getOverviewWithCurrency(currency),
        adminApi.getActivityFeed().catch(() => []),
        adminApi.getConfig().catch(() => ({})),
      ])
      if (cfg?.admin_display_currency) setCurrency(cfg.admin_display_currency)
      setOverview(o)
      setActivity(a)
    } catch (e) {
      console.error('Dashboard overview error:', e)
    }
  }, [currency])

  const fetchHealth = useCallback(async () => {
    try {
      const h = await adminApi.getHealth()
      setHealth(h)
    } catch (e) {
      console.error('Dashboard health error:', e)
    }
  }, [])

  const fetchData = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true)
    try {
      await fetchOverview()
      setLoading(false)
      fetchHealth()
    } finally {
      setRefreshing(false)
    }
  }, [fetchOverview, fetchHealth])

  useEffect(() => {
    fetchData()
    const overviewInterval = setInterval(fetchOverview, 60000)
    const healthInterval = setInterval(fetchHealth, 120000)
    return () => {
      clearInterval(overviewInterval)
      clearInterval(healthInterval)
    }
  }, [fetchData, fetchOverview, fetchHealth])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-purple border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const stats = [
    {
      label: 'Total Users',
      value: (overview?.users?.total || 0).toLocaleString(),
      sub: `${overview?.users?.new_7d || 0} new this week`,
      delta: overview?.users?.new_7d ?? null,
      icon: Users, color: 'text-accent-cyan', sparkColor: 'bg-accent-cyan', seed: 7,
    },
    {
      label: 'Paid Subscribers',
      value: (overview?.users?.paid_subscribers || 0).toLocaleString(),
      sub: `${overview?.users?.inactive_90d || 0} inactive (90d)`,
      delta: null,
      icon: UserCheck, color: 'text-accent-green', sparkColor: 'bg-accent-green', seed: 13,
    },
    {
      label: 'Revenue',
      value: `${overview?.revenue?.symbol || '₹'}${(overview?.revenue?.total ?? 0).toLocaleString()}`,
      sub: `${overview?.revenue?.subscriptions_count || 0} active subs · ${overview?.revenue?.currency || currency}`,
      delta: null,
      icon: DollarSign, color: 'text-accent-amber', sparkColor: 'bg-accent-amber', seed: 23,
    },
    {
      label: 'Active Labs',
      value: overview?.labs?.running || 0,
      sub: `${overview?.labs?.completed_24h || 0} completed today`,
      delta: overview?.labs?.completed_24h ?? null,
      deltaSuffix: ' done',
      icon: MonitorPlay, color: 'text-accent-purple', sparkColor: 'bg-accent-purple', seed: 5,
    },
    {
      label: 'Scenarios',
      value: overview?.scenarios?.active || 0,
      sub: `${overview?.scenarios?.draft || 0} draft`,
      delta: null,
      icon: Target, color: 'text-accent-cyan', sparkColor: 'bg-accent-cyan', seed: 19,
    },
    {
      label: 'Completion Rate',
      value: `${overview?.completion_rate || 0}%`,
      sub: `Avg score: ${Math.round(overview?.labs?.avg_score || 0)}`,
      delta: overview?.completion_rate ?? null,
      deltaSuffix: '%',
      icon: TrendingUp, color: 'text-accent-green', sparkColor: 'bg-accent-green', seed: 11,
    },
    {
      label: 'Community',
      value: (overview?.community?.threads || 0).toLocaleString(),
      sub: `${overview?.community?.replies || 0} replies`,
      delta: null,
      icon: MessageSquare, color: 'text-accent-amber', sparkColor: 'bg-accent-amber', seed: 3,
    },
    {
      label: 'Maintenance',
      value: overview?.maintenance_mode ? 'ON' : 'OFF',
      sub: overview?.maintenance_mode ? 'Platform in maintenance' : 'Platform is live',
      delta: null,
      icon: Wrench,
      color: overview?.maintenance_mode ? 'text-accent-red' : 'text-accent-green',
      sparkColor: overview?.maintenance_mode ? 'bg-accent-red' : 'bg-accent-green',
      seed: 17,
    },
  ]

  const healthServices = [
    { name: 'Database', key: 'database' },
    { name: 'Redis', key: 'redis' },
    { name: 'Docker', key: 'docker' },
    { name: 'Email', key: 'email' },
    { name: 'RabbitMQ', key: 'rabbitmq' },
    { name: 'Celery Workers', key: 'celery' },
    { name: 'Vault', key: 'vault' },
  ]

  const emailStats = health?.email_stats || {}
  const containers = health?.containers || []

  return (
    <div className="space-y-7 animate-fade-in">

      {/* ── Header ── */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-surface-900/90 via-surface-900/70 to-surface-800/50 border border-surface-700/40 p-6">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/5 via-transparent to-accent-cyan/5 pointer-events-none" />
        <div className="relative flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
              <span className="text-xs font-semibold text-accent-green/80 uppercase tracking-widest">Live Dashboard</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Admin Overview</h1>
            <p className="text-surface-400 text-sm mt-1">Platform health, monitoring &amp; real-time statistics</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-4 px-4 py-2 rounded-xl bg-surface-800/60 border border-surface-700/40 text-xs text-surface-400">
              <span>{overview?.users?.total?.toLocaleString() || 0} users</span>
              <span className="w-px h-3 bg-surface-700" />
              <span>{overview?.scenarios?.active || 0} scenarios</span>
              <span className="w-px h-3 bg-surface-700" />
              <span className={health?.overall ? 'text-accent-green' : 'text-accent-red'}>
                {health?.overall ? '● Operational' : '⚠ Degraded'}
              </span>
            </div>
            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-800/60 border border-surface-700/40 text-surface-300 hover:text-white hover:border-accent-purple/50 transition-all text-sm disabled:opacity-50"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* ── KPI Stat Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* ── Revenue area + System Health ── */}
      <div className="grid lg:grid-cols-3 gap-6">
        <RevenueArea
          total={`${overview?.revenue?.symbol || '₹'}${(overview?.revenue?.total ?? 0).toLocaleString()}`}
          currency={overview?.revenue?.currency || currency}
        />

        <div className="lg:col-span-2 glass-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity size={18} className={health?.overall ? 'text-accent-green' : 'text-accent-red'} />
              System Health
            </h2>
            <span className={`text-[11px] font-bold px-3 py-1 rounded-full border ${
              health?.overall
                ? 'bg-accent-green/10 text-accent-green border-accent-green/25'
                : 'bg-accent-red/10 text-accent-red border-accent-red/25'
            }`}>
              {health?.overall ? 'ALL SYSTEMS OPERATIONAL' : 'DEGRADED'}
            </span>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {healthServices.map(({ name, key }) => {
              const svc = health?.[key] || {}
              const isDegraded = svc.status === 'degraded'
              const isHealthy = svc.status === 'healthy' || (key === 'vault' && isDegraded)
              const Icon = SERVICE_ICONS[name] || Server

              const cardClass = !isHealthy
                ? 'bg-accent-red/5 border-accent-red/15 shadow-[0_0_12px_rgba(248,113,113,0.07)]'
                : isDegraded
                ? 'bg-accent-amber/5 border-accent-amber/15'
                : 'bg-accent-green/5 border-accent-green/10'
              const dotColor = !isHealthy ? 'bg-accent-red'
                : isDegraded ? 'bg-accent-amber animate-pulse'
                : 'bg-accent-green animate-pulse'
              const iconBg = !isHealthy ? 'bg-accent-red/10' : isDegraded ? 'bg-accent-amber/10' : 'bg-accent-green/10'
              const textClass = !isHealthy ? 'text-accent-red' : isDegraded ? 'text-accent-amber' : 'text-accent-green'

              return (
                <div key={name} className={`flex items-start gap-3 p-3 rounded-xl border transition-all ${cardClass}`}>
                  <div className={`mt-0.5 p-1.5 rounded-lg shrink-0 ${iconBg}`}>
                    <Icon size={15} className={textClass} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />
                      <p className="text-sm font-medium text-white">{name}</p>
                    </div>
                    <p className={`text-[11px] mt-0.5 ${textClass} capitalize`}>{svc.status || 'unknown'}</p>
                    {key === 'vault' && svc.secrets_loaded != null && (
                      <p className={`text-[10px] mt-0.5 ${svc.secrets_loaded ? 'text-accent-green/70' : 'text-surface-500'}`}>
                        {svc.secrets_loaded ? 'secrets loaded' : 'env file mode'}
                      </p>
                    )}
                    {svc.details && (
                      <p className="text-[10px] text-surface-500 mt-0.5 truncate">{svc.details}</p>
                    )}
                    {svc.error && (
                      <p className="text-[10px] text-accent-red/70 mt-0.5 truncate" title={svc.error}>
                        {svc.error.slice(0, 50)}
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Email Stats + Cloud Providers ── */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <Mail size={18} className="text-accent-cyan" />
            Email Stats
          </h2>
          <div className="space-y-2">
            {[
              { icon: Send, color: 'text-accent-green', bg: 'bg-accent-green/10', label: 'Sent (24h)', val: emailStats.sent_24h || 0, valColor: 'text-accent-green' },
              { icon: XCircle, color: 'text-accent-red', bg: 'bg-accent-red/10', label: 'Failed (24h)', val: emailStats.failed_24h || 0, valColor: (emailStats.failed_24h || 0) > 0 ? 'text-accent-red' : 'text-surface-500' },
              { icon: Mail, color: 'text-accent-cyan', bg: 'bg-accent-cyan/10', label: 'Sent (7d)', val: emailStats.sent_7d || 0, valColor: 'text-white' },
              { icon: Mail, color: 'text-surface-400', bg: 'bg-surface-700/30', label: 'Total', val: emailStats.total || 0, valColor: 'text-white' },
            ].map(({ icon: Icon, color, bg, label, val, valColor }) => (
              <div key={label} className="flex items-center justify-between p-3 rounded-xl bg-surface-800/30 border border-surface-700/40">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-lg ${bg}`}><Icon size={13} className={color} /></div>
                  <span className="text-sm text-surface-300">{label}</span>
                </div>
                <span className={`text-lg font-bold ${valColor}`}>{val}</span>
              </div>
            ))}
            {emailStats.last_sent_at && (
              <p className="text-[11px] text-surface-500 text-center pt-1">
                Last: {new Date(emailStats.last_sent_at).toLocaleString()}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={async () => {
              try {
                const result = await adminApi.sendTestEmail()
                toast.success(result.sent ? `Test email sent to ${result.to_email}` : 'Send failed')
              } catch (err) {
                toast.error(err.response?.data?.error || 'Test email failed')
              }
            }}
            className="w-full mt-4 btn-secondary text-sm flex items-center justify-center gap-2"
          >
            <Send size={14} /> Send test email
          </button>
          <Link to="/admin/settings" className="block text-center text-[11px] text-accent-cyan hover:underline mt-2">
            Email settings →
          </Link>
        </div>

        {health?.cloud_providers ? (
          <div className="lg:col-span-2 glass-card p-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
              <Globe size={18} className="text-accent-amber" />
              Cloud Providers
              {health?.cloud_labs && (
                <span className="text-xs font-normal text-surface-500 ml-1">
                  ({(health.cloud_labs.active_aws || 0) + (health.cloud_labs.active_do || 0)} active cloud labs)
                </span>
              )}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {[
                { key: 'aws_ec2', name: 'AWS EC2', color: 'amber', activeLabs: health?.cloud_labs?.active_aws || 0 },
                { key: 'digitalocean', name: 'DigitalOcean', color: 'blue', activeLabs: health?.cloud_labs?.active_do || 0 },
              ].map(({ key, name, color, activeLabs }) => {
                const prov = health.cloud_providers[key] || {}
                return (
                  <div key={key} className={`p-4 rounded-xl border ${
                    prov.configured
                      ? prov.status === 'healthy'
                        ? `bg-accent-${color}/5 border-accent-${color}/20`
                        : 'bg-accent-red/5 border-accent-red/20'
                      : 'bg-surface-800/30 border-surface-700/40'
                  }`}>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-semibold text-white">{name}</span>
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                        !prov.configured ? 'bg-surface-700 text-surface-400' :
                        prov.status === 'healthy' ? 'bg-accent-green/15 text-accent-green' :
                        prov.status === 'auth_error' ? 'bg-accent-amber/15 text-accent-amber' :
                        'bg-accent-red/15 text-accent-red'
                      }`}>
                        {!prov.configured ? 'Not Configured' :
                          prov.status === 'healthy' ? 'Connected' :
                          prov.status === 'auth_error' ? 'Token Invalid' : 'Error'}
                      </span>
                    </div>
                    {prov.configured ? (
                      <div className="space-y-1.5 text-xs text-surface-400">
                        {prov.region && <p>Region: <span className="text-surface-300">{prov.region}</span></p>}
                        {prov.instance_type && <p>Instance: <span className="text-surface-300">{prov.instance_type}</span></p>}
                        {prov.size && <p>Size: <span className="text-surface-300">{prov.size}</span></p>}
                        <p>Active Labs: <span className="text-white font-semibold">{activeLabs}</span></p>
                        {prov.error && <p className="text-accent-red/80 truncate">{prov.error}</p>}
                      </div>
                    ) : (
                      <p className="text-xs text-surface-500 mt-1">Configure in .env to enable cloud-based labs</p>
                    )}
                  </div>
                )
              })}
            </div>
            {health?.cloud_labs && (
              <div className="flex flex-wrap items-center gap-5 text-xs text-surface-400 pt-3 border-t border-surface-700/50">
                <span>Docker: <span className="text-white font-semibold">{health.cloud_labs.active_docker || 0}</span> active</span>
                <span>Cloud (24h): <span className="text-white font-semibold">{health.cloud_labs.total_cloud_24h || 0}</span> sessions</span>
                <span>Cloud Scenarios: <span className="text-white font-semibold">{health.cloud_labs.cloud_scenarios || 0}</span> configured</span>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* ── System Containers ── */}
      {containers.length > 0 && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Server size={18} className="text-accent-purple" />
              System Containers
              <span className="text-xs font-normal text-surface-500 ml-1">
                ({containers.filter(c => c.status === 'running').length}/{containers.length} running)
              </span>
            </h2>
            <Link to="/admin/monitoring" className="flex items-center gap-1 text-xs text-accent-cyan hover:underline">
              Full monitoring <ArrowUpRight size={12} />
            </Link>
          </div>

          {(() => {
            const healthy = containers.filter(c => c.status === 'running' && (c.health === 'healthy' || c.health === 'none' || c.health === 'running' || !c.health)).length
            const degraded = containers.filter(c => c.status === 'running' && c.health && c.health !== 'healthy' && c.health !== 'none' && c.health !== 'running').length
            const down = containers.filter(c => c.status !== 'running').length
            const restarting = containers.reduce((sum, c) => sum + (c.restart_count || 0), 0)
            return (
              <div className="flex flex-wrap gap-4 mb-5 pb-4 border-b border-surface-800/50">
                <span className="flex items-center gap-1.5 text-sm text-accent-green">
                  <CheckCircle2 size={14} /> {healthy} healthy
                </span>
                {degraded > 0 && (
                  <span className="flex items-center gap-1.5 text-sm text-accent-amber">
                    <AlertCircle size={14} /> {degraded} degraded
                  </span>
                )}
                {down > 0 && (
                  <span className="flex items-center gap-1.5 text-sm text-accent-red">
                    <XCircle size={14} /> {down} down
                  </span>
                )}
                {restarting > 0 && (
                  <span className="flex items-center gap-1.5 text-sm text-accent-amber ml-auto">
                    <RotateCcw size={13} /> {restarting} restarts
                  </span>
                )}
              </div>
            )
          })()}

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {containers.map((c, i) => {
              const isUp = c.status === 'running'
              const isHealthy = !isUp ? false : (c.health === 'healthy' || c.health === 'none' || c.health === 'running' || !c.health)
              const isDegraded = isUp && c.health && c.health !== 'healthy' && c.health !== 'none' && c.health !== 'running'
              const Icon = containerIcon(c.name)

              const cardClass = !isUp
                ? 'border-accent-red/20 bg-accent-red/5'
                : isDegraded
                ? 'border-accent-amber/20 bg-accent-amber/5'
                : 'border-accent-green/10 bg-accent-green/5 shadow-[0_0_14px_rgba(52,211,153,0.06)]'

              const dotColor = !isUp ? 'bg-accent-red'
                : isDegraded ? 'bg-accent-amber animate-pulse'
                : 'bg-accent-green animate-pulse'

              const textColor = !isUp ? 'text-accent-red'
                : isDegraded ? 'text-accent-amber'
                : 'text-accent-green'

              return (
                <div key={i} className={`rounded-xl border p-3.5 transition-all ${cardClass}`}>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                      <Icon size={14} className={textColor} />
                      <span className="text-xs font-semibold text-white truncate">
                        {c.name.replace('fixitlab_', '')}
                      </span>
                    </div>
                    {c.restart_count > 0 && (
                      <span className="flex items-center gap-0.5 text-[10px] text-accent-amber shrink-0" title="Restart count">
                        <RotateCcw size={10} /> {c.restart_count}
                      </span>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-surface-500">Status</span>
                      <span className={`font-semibold ${textColor}`}>{isDegraded ? c.health : c.status}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-surface-500">Uptime</span>
                      <span className="text-surface-300">
                        {c.up_since && isUp ? formatUptime(c.up_since) : '—'}
                      </span>
                    </div>
                    {c.mem_mb != null && (
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-surface-500">Mem</span>
                        <span className="text-surface-300">{c.mem_mb} MB</span>
                      </div>
                    )}
                    {!isUp && c.exit_code != null && c.exit_code !== 0 && (
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-surface-500">Exit</span>
                        <span className="text-accent-red font-mono">{c.exit_code}</span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Recent Activity + Recent Emails ── */}
      <div className="grid lg:grid-cols-2 gap-6">
        {activity.length > 0 && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
              <Zap size={18} className="text-accent-amber" />
              Recent Activity
              <span className="text-xs font-normal text-surface-500 ml-1">(24h)</span>
            </h2>
            <div className="space-y-0.5 max-h-[360px] overflow-y-auto">
              {activity.slice(0, 15).map((item, i) => {
                const Icon = ACTIVITY_ICONS[item.type] || Activity
                const colorClass = ACTIVITY_COLORS[item.type] || 'text-surface-400 bg-surface-800/30'
                return (
                  <div key={i} className="flex items-center gap-3 px-2.5 py-2.5 rounded-xl hover:bg-surface-800/20 transition-colors">
                    <div className={`p-1.5 rounded-lg shrink-0 ${colorClass}`}>
                      <Icon size={13} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-surface-300 truncate">{item.message}</p>
                    </div>
                    <span className="text-[11px] text-surface-600 whitespace-nowrap shrink-0">
                      {formatTimeAgo(item.timestamp)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {emailStats.recent?.length > 0 && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
              <Mail size={18} className="text-accent-cyan" />
              Recent Emails
            </h2>
            <div className="space-y-0.5 max-h-[360px] overflow-y-auto">
              {emailStats.recent.map((email, i) => (
                <div key={i} className="flex items-center gap-3 px-2.5 py-2.5 rounded-xl hover:bg-surface-800/20 transition-colors">
                  <div className={`p-1.5 rounded-lg shrink-0 ${email.status === 'sent' ? 'text-accent-green bg-accent-green/10' : 'text-accent-red bg-accent-red/10'}`}>
                    {email.status === 'sent' ? <Send size={13} /> : <XCircle size={13} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{email.subject}</p>
                    <p className="text-xs text-surface-500">{email.to_email}</p>
                  </div>
                  <span className="text-[11px] text-surface-600 whitespace-nowrap shrink-0">
                    {email.created_at ? formatTimeAgo(email.created_at) : '—'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
