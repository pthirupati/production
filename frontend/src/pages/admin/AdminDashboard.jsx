import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api/admin'
import {
  Users, Target, MonitorPlay, TrendingUp,
  Activity, CheckCircle2, XCircle, AlertCircle,
  Mail, Server, RefreshCw, Globe,
  Clock, UserPlus, Play, CheckCircle, XOctagon,
  Send, Database, Wifi, MessageSquare, Cpu,
  DollarSign, UserCheck, AlertTriangle, Wrench
} from 'lucide-react'

function HealthBadge({ status }) {
  if (status === 'healthy' || status === 'running') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-accent-green/15 text-accent-green border border-accent-green/20">
      <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" /> HEALTHY
    </span>
  }
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-accent-red/15 text-accent-red border border-accent-red/20">
    <span className="w-1.5 h-1.5 rounded-full bg-accent-red" /> DOWN
  </span>
}

const SERVICE_ICONS = {
  'Database': Database,
  'Redis': Cpu,
  'Docker': Server,
  'Email': Mail,
  'RabbitMQ': MessageSquare,
  'Celery Workers': Activity,
}

const ACTIVITY_ICONS = {
  'registration': UserPlus,
  'lab_start': Play,
  'lab_completed': CheckCircle,
  'lab_failed': XOctagon,
}

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

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null)
  const [health, setHealth] = useState(null)
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchOverview = useCallback(async () => {
    try {
      const [o, a] = await Promise.all([
        adminApi.getOverview(),
        adminApi.getActivityFeed().catch(() => []),
      ])
      setOverview(o)
      setActivity(a)
    } catch (e) {
      console.error('Dashboard overview error:', e)
    }
  }, [])

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
    { label: 'Total Users', value: overview?.users?.total || 0, sub: `${overview?.users?.new_7d || 0} new this week`, icon: Users, color: 'text-accent-cyan' },
    { label: 'Paid Subscribers', value: overview?.users?.paid_subscribers || 0, sub: `${overview?.users?.inactive_90d || 0} inactive (90d)`, icon: UserCheck, color: 'text-accent-green' },
    { label: 'Revenue', value: `₹${overview?.revenue?.total || 0}`, sub: `${overview?.revenue?.subscriptions_count || 0} active subs`, icon: DollarSign, color: 'text-accent-amber' },
    { label: 'Active Labs', value: overview?.labs?.running || 0, sub: `${overview?.labs?.completed_24h || 0} completed today`, icon: MonitorPlay, color: 'text-accent-purple' },
    { label: 'Scenarios', value: overview?.scenarios?.active || 0, sub: `${overview?.scenarios?.draft || 0} draft`, icon: Target, color: 'text-accent-cyan' },
    { label: 'Completion Rate', value: `${overview?.completion_rate || 0}%`, sub: `Avg score: ${Math.round(overview?.labs?.avg_score || 0)}`, icon: TrendingUp, color: 'text-accent-green' },
    { label: 'Community', value: overview?.community?.threads || 0, sub: `${overview?.community?.replies || 0} replies`, icon: MessageSquare, color: 'text-accent-amber' },
    { label: 'Maintenance', value: overview?.maintenance_mode ? 'ON' : 'OFF', sub: overview?.maintenance_mode ? 'Enabled' : 'Disabled', icon: Wrench, color: overview?.maintenance_mode ? 'text-accent-red' : 'text-accent-green' },
  ]

  const healthServices = [
    { name: 'Database', key: 'database' },
    { name: 'Redis', key: 'redis' },
    { name: 'Docker', key: 'docker' },
    { name: 'Email', key: 'email' },
    { name: 'RabbitMQ', key: 'rabbitmq' },
    { name: 'Celery Workers', key: 'celery' },
  ]

  const emailStats = health?.email_stats || {}
  const containers = health?.containers || []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Admin Overview</h1>
          <p className="text-surface-400 mt-1">Platform health, monitoring & statistics</p>
        </div>
        <button onClick={() => fetchData(true)} disabled={refreshing}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-800/50 border border-surface-700 text-surface-300 hover:text-white hover:border-surface-500 transition-all text-sm disabled:opacity-50">
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(({ label, value, sub, icon: Icon, color }) => (
          <div key={label} className="glass-card p-5">
            <Icon size={20} className={color + ' mb-3'} />
            <p className="text-2xl font-bold text-white">{value}</p>
            <p className="text-sm text-surface-400 mt-1">{label}</p>
            <p className="text-xs text-surface-500 mt-1">{sub}</p>
          </div>
        ))}
      </div>

      {/* System Health + Email Stats */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Services Health */}
        <div className="lg:col-span-2 glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity size={18} className={health?.overall ? 'text-accent-green' : 'text-accent-red'} />
              System Health
            </h2>
            <span className={`text-xs font-bold px-3 py-1 rounded-full ${
              health?.overall
                ? 'bg-accent-green/15 text-accent-green border border-accent-green/20'
                : 'bg-accent-red/15 text-accent-red border border-accent-red/20'
            }`}>
              {health?.overall ? 'ALL SYSTEMS OPERATIONAL' : 'DEGRADED'}
            </span>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {healthServices.map(({ name, key }) => {
              const svc = health?.[key] || {}
              const isHealthy = svc.status === 'healthy'
              const Icon = SERVICE_ICONS[name] || Server
              return (
                <div key={name} className={`flex items-start gap-3 p-3 rounded-lg transition-all ${
                  isHealthy
                    ? 'bg-accent-green/5 border border-accent-green/10'
                    : 'bg-accent-red/5 border border-accent-red/10'
                }`}>
                  <div className={`mt-0.5 p-1.5 rounded-lg ${isHealthy ? 'bg-accent-green/10' : 'bg-accent-red/10'}`}>
                    <Icon size={16} className={isHealthy ? 'text-accent-green' : 'text-accent-red'} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white">{name}</p>
                    <p className={`text-xs mt-0.5 ${isHealthy ? 'text-accent-green' : 'text-accent-red'}`}>
                      {svc.status || 'unknown'}
                    </p>
                    {svc.details && (
                      <p className="text-[10px] text-surface-500 mt-0.5 truncate">{svc.details}</p>
                    )}
                    {svc.error && (
                      <p className="text-[10px] text-accent-red/80 mt-0.5 truncate" title={svc.error}>
                        {svc.error.slice(0, 60)}
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Email Stats */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <Mail size={18} className="text-accent-cyan" />
            Email Stats
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg bg-surface-800/30 border border-surface-700/50">
              <div className="flex items-center gap-2">
                <Send size={14} className="text-accent-green" />
                <span className="text-sm text-surface-300">Sent (24h)</span>
              </div>
              <span className="text-lg font-bold text-accent-green">{emailStats.sent_24h || 0}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-surface-800/30 border border-surface-700/50">
              <div className="flex items-center gap-2">
                <XCircle size={14} className="text-accent-red" />
                <span className="text-sm text-surface-300">Failed (24h)</span>
              </div>
              <span className={`text-lg font-bold ${(emailStats.failed_24h || 0) > 0 ? 'text-accent-red' : 'text-surface-500'}`}>
                {emailStats.failed_24h || 0}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-surface-800/30 border border-surface-700/50">
              <div className="flex items-center gap-2">
                <Mail size={14} className="text-accent-cyan" />
                <span className="text-sm text-surface-300">Sent (7d)</span>
              </div>
              <span className="text-lg font-bold text-white">{emailStats.sent_7d || 0}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-surface-800/30 border border-surface-700/50">
              <div className="flex items-center gap-2">
                <Mail size={14} className="text-surface-400" />
                <span className="text-sm text-surface-300">Total</span>
              </div>
              <span className="text-lg font-bold text-white">{emailStats.total || 0}</span>
            </div>
            {emailStats.last_sent_at && (
              <p className="text-[11px] text-surface-500 text-center mt-2">
                Last: {new Date(emailStats.last_sent_at).toLocaleString()}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Container Health */}
      {containers.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <Server size={18} className="text-accent-purple" />
            Container Status
            <span className="text-xs font-normal text-surface-500 ml-2">({containers.length} containers)</span>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-surface-500 text-xs uppercase tracking-wider">
                  <th className="pb-3 pr-4">Container</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Health</th>
                  <th className="pb-3 pr-4">Image</th>
                  <th className="pb-3">Uptime</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/50">
                {containers.map((c, i) => {
                  const isUp = c.status === 'running'
                  const isHealthy = c.health === 'healthy' || c.health === 'none'
                  return (
                    <tr key={i} className="hover:bg-surface-800/20 transition-colors">
                      <td className="py-2.5 pr-4">
                        <span className="font-medium text-white">{c.name}</span>
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className={`inline-flex items-center gap-1.5 text-xs ${isUp ? 'text-accent-green' : 'text-accent-red'}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${isUp ? 'bg-accent-green animate-pulse' : 'bg-accent-red'}`} />
                          {c.status}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4">
                        <HealthBadge status={isUp && isHealthy ? 'healthy' : 'unhealthy'} />
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className="text-xs text-surface-400 font-mono truncate block max-w-[200px]">{c.image}</span>
                      </td>
                      <td className="py-2.5">
                        <span className="text-xs text-surface-500">
                          {c.up_since ? formatUptime(c.up_since) : '—'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cloud Providers Status */}
      {health?.cloud_providers && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <Globe size={18} className="text-accent-amber" />
            Cloud Providers
            {health?.cloud_labs && (
              <span className="text-xs font-normal text-surface-500 ml-2">
                ({(health.cloud_labs.active_aws || 0) + (health.cloud_labs.active_do || 0)} active cloud labs)
              </span>
            )}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { key: 'aws_ec2', name: 'AWS EC2', color: 'amber', activeLabs: health?.cloud_labs?.active_aws || 0 },
              { key: 'digitalocean', name: 'DigitalOcean', color: 'blue', activeLabs: health?.cloud_labs?.active_do || 0 },
            ].map(({ key, name, color, activeLabs }) => {
              const prov = health.cloud_providers[key] || {}
              return (
                <div key={key} className={`p-4 rounded-lg border ${
                  prov.configured
                    ? prov.status === 'healthy'
                      ? `bg-accent-${color}/5 border-accent-${color}/20`
                      : 'bg-accent-red/5 border-accent-red/20'
                    : 'bg-surface-800/30 border-surface-700/50'
                }`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-white">{name}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      !prov.configured ? 'bg-surface-700 text-surface-400' :
                      prov.status === 'healthy' ? `bg-accent-green/15 text-accent-green` :
                      prov.status === 'auth_error' ? 'bg-accent-amber/15 text-accent-amber' :
                      'bg-accent-red/15 text-accent-red'
                    }`}>
                      {!prov.configured ? 'Not Configured' :
                        prov.status === 'healthy' ? 'Connected' :
                        prov.status === 'auth_error' ? 'Token Invalid' : 'Error'}
                    </span>
                  </div>
                  {prov.configured && (
                    <div className="space-y-1 text-xs text-surface-400">
                      {prov.region && <p>Region: <span className="text-surface-300">{prov.region}</span></p>}
                      {prov.instance_type && <p>Instance: <span className="text-surface-300">{prov.instance_type}</span></p>}
                      {prov.size && <p>Size: <span className="text-surface-300">{prov.size}</span></p>}
                      <p>Active Labs: <span className="text-white font-medium">{activeLabs}</span></p>
                      {prov.error && <p className="text-accent-red/80 truncate">{prov.error}</p>}
                    </div>
                  )}
                  {!prov.configured && (
                    <p className="text-xs text-surface-500 mt-1">
                      Configure in .env to enable cloud-based labs
                    </p>
                  )}
                </div>
              )
            })}
          </div>
          {health?.cloud_labs && (
            <div className="mt-3 pt-3 border-t border-surface-700/50 flex items-center gap-4 text-xs text-surface-400">
              <span>Docker: <span className="text-white font-medium">{health.cloud_labs.active_docker || 0}</span> active</span>
              <span>Cloud (24h): <span className="text-white font-medium">{health.cloud_labs.total_cloud_24h || 0}</span> sessions</span>
              <span>Cloud Scenarios: <span className="text-white font-medium">{health.cloud_labs.cloud_scenarios || 0}</span> configured</span>
            </div>
          )}
        </div>
      )}

      {/* Recent Activity + Recent Emails side by side */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        {activity.length > 0 && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
              <Clock size={18} className="text-accent-amber" />
              Recent Activity
              <span className="text-xs font-normal text-surface-500 ml-2">(24h)</span>
            </h2>
            <div className="space-y-1 max-h-[360px] overflow-y-auto">
              {activity.slice(0, 15).map((item, i) => {
                const Icon = ACTIVITY_ICONS[item.type] || Activity
                const colors = {
                  'registration': 'text-accent-cyan bg-accent-cyan/10',
                  'lab_start': 'text-accent-amber bg-accent-amber/10',
                  'lab_completed': 'text-accent-green bg-accent-green/10',
                  'lab_failed': 'text-accent-red bg-accent-red/10',
                }
                const colorClass = colors[item.type] || 'text-surface-400 bg-surface-800/30'
                return (
                  <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-surface-800/20 transition-colors">
                    <div className={`p-1.5 rounded-lg shrink-0 ${colorClass}`}>
                      <Icon size={14} />
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

        {/* Recent Emails */}
        {emailStats.recent?.length > 0 && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
              <Mail size={18} className="text-accent-cyan" />
              Recent Emails
            </h2>
            <div className="space-y-1 max-h-[360px] overflow-y-auto">
              {emailStats.recent.map((email, i) => (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-surface-800/20 transition-colors">
                  <div className={`p-1.5 rounded-lg shrink-0 ${email.status === 'sent' ? 'text-accent-green bg-accent-green/10' : 'text-accent-red bg-accent-red/10'}`}>
                    {email.status === 'sent' ? <Send size={14} /> : <XCircle size={14} />}
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
