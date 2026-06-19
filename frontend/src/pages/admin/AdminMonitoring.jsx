import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import {
  Activity, Container, Terminal, Cpu, HardDrive,
  Filter, CheckCircle2, XCircle, AlertCircle, RotateCcw,
  Server, Database, Wifi, MessageSquare, ShieldCheck, Globe,
  Zap,
} from 'lucide-react'
import toast from 'react-hot-toast'

// ─── Icon maps ────────────────────────────────────────────────────────────────

const CONTAINER_ICONS = {
  database: Database, db: Database, redis: Cpu, rabbitmq: MessageSquare,
  vault: ShieldCheck, backend: Server, frontend: Globe,
  gateway: Wifi, celery: Activity, pgbouncer: Database,
  flower: Zap, certbot: ShieldCheck, nginx: Globe,
}

function containerIcon(name) {
  const n = (name || '').toLowerCase()
  for (const [k, Icon] of Object.entries(CONTAINER_ICONS)) {
    if (n.includes(k)) return Icon
  }
  return Container
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatUptime(startedAt) {
  if (!startedAt) return '—'
  const diff = Date.now() - new Date(startedAt).getTime()
  const hours = Math.floor(diff / 3600000)
  const mins = Math.floor((diff % 3600000) / 60000)
  if (hours < 1) return `${mins}m`
  if (hours < 24) return `${hours}h ${mins}m`
  return `${Math.floor(hours / 24)}d ${hours % 24}h`
}

// ─── Container card (grid view) ───────────────────────────────────────────────

function ContainerCard({ c, selected, onSelect }) {
  const isUp = c.status === 'running'
  const isDegraded = isUp && c.health && c.health !== 'healthy' && c.health !== 'none'
  const isUnhealthy = !isUp
  const Icon = containerIcon(c.name)

  const cardBase = 'relative rounded-xl border p-3.5 cursor-pointer transition-all group'
  const cardColor = isUnhealthy
    ? 'border-accent-red/25 bg-accent-red/5 shadow-[0_0_16px_rgba(248,113,113,0.10)]'
    : isDegraded
    ? 'border-accent-amber/25 bg-accent-amber/5'
    : 'border-accent-green/15 bg-accent-green/5 shadow-[0_0_14px_rgba(52,211,153,0.06)]'
  const isSelected = selected?.id === c.id

  const dotColor = isUnhealthy
    ? 'bg-accent-red animate-pulse'
    : isDegraded
    ? 'bg-accent-amber animate-pulse'
    : 'bg-accent-green animate-pulse'
  const textColor = isUnhealthy ? 'text-accent-red' : isDegraded ? 'text-accent-amber' : 'text-accent-green'

  // Status badge
  const badgeText = isUnhealthy
    ? (c.health === 'unhealthy' ? 'unhealthy' : c.status)
    : isDegraded ? c.health : 'healthy'
  const badgeClass = isUnhealthy
    ? 'bg-accent-red/15 text-accent-red border-accent-red/20'
    : isDegraded
    ? 'bg-accent-amber/15 text-accent-amber border-accent-amber/20'
    : 'bg-accent-green/15 text-accent-green border-accent-green/20'

  return (
    <button
      type="button"
      onClick={() => onSelect(c)}
      className={`${cardBase} ${cardColor} ${isSelected ? 'ring-2 ring-accent-cyan/50' : 'hover:ring-1 hover:ring-white/10'}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
          <div className={`p-1 rounded-md bg-surface-800/50 group-hover:bg-surface-700/50 transition-colors`}>
            <Icon size={13} className={textColor} />
          </div>
          <span className="text-xs font-semibold text-white truncate">
            {c.name.replace('fixitlab_', '')}
          </span>
        </div>
        {c.restart_count > 0 && (
          <span className="flex items-center gap-0.5 text-[10px] text-accent-amber shrink-0" title={`${c.restart_count} restarts`}>
            <RotateCcw size={9} /> {c.restart_count}
          </span>
        )}
      </div>

      {/* Status badge */}
      <div className="flex items-center gap-2 mb-2.5">
        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-bold border ${badgeClass}`}>
          {badgeText.toUpperCase()}
        </span>
        <span className={`text-[10px] font-bold uppercase ${c.kind === 'system' ? 'text-accent-purple' : 'text-accent-cyan'}`}>
          {c.kind}
        </span>
      </div>

      {/* Info rows */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-surface-500">Uptime</span>
          <span className="text-surface-300">{c.up_since && isUp ? formatUptime(c.up_since) : '—'}</span>
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
        {c.image && (
          <p className="text-[10px] text-surface-600 truncate pt-0.5" title={c.image}>{c.image}</p>
        )}
      </div>
    </button>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AdminMonitoring() {
  const [containers, setContainers] = useState([])
  const [summary, setSummary] = useState({ total: 0, running: 0 })
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('metrics')
  const [tail, setTail] = useState('200')
  const [logType, setLogType] = useState('all')
  const [search, setSearch] = useState('')
  const [since, setSince] = useState('')
  const [live, setLive] = useState(false)
  const [kindFilter, setKindFilter] = useState('all')

  const loadContainers = useCallback(async () => {
    try {
      const data = await adminApi.getMonitoringContainers(kindFilter)
      setContainers(data.containers || [])
      setSummary({
        total: data.total || 0,
        running: data.running || 0,
        lab_count: data.lab_count,
        system_count: data.system_count,
      })
    } catch {
      toast.error('Could not load containers')
    } finally {
      setLoading(false)
    }
  }, [kindFilter])

  const loadDetail = useCallback(async (id) => {
    try {
      const data = await adminApi.getMonitoringContainer(id)
      setDetail(data)
    } catch {
      setDetail(null)
    }
  }, [])

  const loadLogs = useCallback(async (id) => {
    if (!id) return
    try {
      const data = await adminApi.getMonitoringLogs(id, {
        tail,
        type: logType,
        q: search,
        since,
        live: live ? '1' : '0',
      })
      setLogs(data.lines || [])
    } catch {
      setLogs([])
    }
  }, [tail, logType, search, since, live])

  useEffect(() => { loadContainers() }, [loadContainers])

  useEffect(() => {
    if (!selected) return
    loadDetail(selected.full_id || selected.id)
    if (tab === 'logs') loadLogs(selected.full_id || selected.id)
  }, [selected, tab, loadDetail, loadLogs])

  useEffect(() => {
    if (!live || !selected || tab !== 'logs') return
    const timer = setInterval(() => loadLogs(selected.full_id || selected.id), 3000)
    return () => clearInterval(timer)
  }, [live, selected, tab, loadLogs])

  // Derived counts
  const systemContainers = containers.filter(c => c.kind === 'system')
  const healthySystem = systemContainers.filter(c =>
    c.status === 'running' && (c.health === 'healthy' || c.health === 'running' || !c.health || c.health === 'none')
  ).length
  const downSystem = systemContainers.filter(c => c.status !== 'running').length
  const totalRestarts = containers.reduce((s, c) => s + (c.restart_count || 0), 0)
  const unhealthyContainers = containers.filter(c =>
    c.status !== 'running' || (c.health && c.health !== 'healthy' && c.health !== 'none' && c.health !== 'running')
  )

  // All system containers shown in the quick-glance row
  const systemServiceList = systemContainers

  return (
    <div className="space-y-5 sm:space-y-6 animate-fade-in">

      <AdminPageHeader
        title="Monitoring"
        subtitle={`${summary.running} running / ${summary.total} containers${summary.lab_count != null ? ` · ${summary.lab_count} labs · ${summary.system_count} system` : ''}`}
        onRefresh={loadContainers}
        actions={
          <>
            {[
              { k: 'all', label: 'All' },
              { k: 'lab', label: 'Lab containers' },
              { k: 'system', label: 'System' },
            ].map(({ k, label }) => (
              <button
                key={k}
                type="button"
                onClick={() => setKindFilter(k)}
                className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                  kindFilter === k
                    ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10'
                    : 'border-surface-700 text-surface-400 hover:border-surface-500 hover:text-surface-300'
                }`}
              >
                {label}
              </button>
            ))}
          </>
        }
      />

      {/* ── Summary KPI row ── */}
      {systemContainers.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { icon: CheckCircle2, color: 'text-accent-green', bg: 'bg-accent-green/10', val: healthySystem, label: 'System Healthy' },
            { icon: XCircle, color: 'text-accent-red', bg: 'bg-accent-red/10', val: downSystem, label: 'Down' },
            { icon: Activity, color: 'text-accent-cyan', bg: 'bg-accent-cyan/10', val: summary.running, label: 'Running' },
            {
              icon: RotateCcw,
              color: totalRestarts > 0 ? 'text-accent-amber' : 'text-surface-500',
              bg: totalRestarts > 0 ? 'bg-accent-amber/10' : 'bg-surface-800/30',
              val: totalRestarts,
              label: 'Total Restarts',
            },
          ].map(({ icon: Icon, color, bg, val, label }) => (
            <div key={label} className="fx-stat-card p-4 flex items-center gap-3">
              <div className={`p-2 rounded-lg ${bg} shrink-0`}>
                <Icon size={16} className={color} />
              </div>
              <div>
                <p className="text-xl font-bold text-white">{val}</p>
                <p className="text-[11px] text-surface-500 mt-0.5">{label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Alerts: unhealthy containers callout ── */}
      {unhealthyContainers.length > 0 && (
        <div className="glass-card p-4 border border-accent-red/20 bg-accent-red/5">
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle size={16} className="text-accent-red" />
            <span className="text-sm font-semibold text-accent-red">{unhealthyContainers.length} container{unhealthyContainers.length > 1 ? 's' : ''} need attention</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {unhealthyContainers.map((c, i) => {
              const Icon = containerIcon(c.name)
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => { setSelected(c); setTab('metrics') }}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accent-red/10 border border-accent-red/20 text-accent-red text-xs hover:bg-accent-red/20 transition-colors"
                >
                  <Icon size={12} />
                  {c.name.replace('fixitlab_', '')}
                  <span className="ml-0.5 opacity-70">· {c.status}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── System Services quick-glance row ── */}
      {systemServiceList.length > 0 && kindFilter !== 'lab' && (
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
            <Zap size={15} className="text-accent-purple" />
            System Services
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-8 gap-3">
            {systemServiceList.map((c, i) => {
              const isUp = c.status === 'running'
              const isDegraded = isUp && c.health && c.health !== 'healthy' && c.health !== 'none'
              const Icon = containerIcon(c.name)
              const dotColor = !isUp ? 'bg-accent-red' : isDegraded ? 'bg-accent-amber animate-pulse' : 'bg-accent-green animate-pulse'
              const textColor = !isUp ? 'text-accent-red' : isDegraded ? 'text-accent-amber' : 'text-accent-green'
              const bgColor = !isUp ? 'bg-accent-red/10' : isDegraded ? 'bg-accent-amber/10' : 'bg-accent-green/10'
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => { setSelected(c); setTab('metrics') }}
                  className="flex flex-col items-center gap-2 p-3 rounded-xl bg-surface-800/30 hover:bg-surface-700/30 border border-surface-700/40 transition-all"
                >
                  <div className={`p-2 rounded-lg ${bgColor}`}>
                    <Icon size={16} className={textColor} />
                  </div>
                  <span className="text-[11px] text-surface-300 font-medium text-center leading-tight truncate w-full">
                    {c.name.replace('fixitlab_', '')}
                  </span>
                  <span className={`w-2 h-2 rounded-full ${dotColor}`} />
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Container grid + detail panel ── */}
      <div className="grid lg:grid-cols-3 gap-5">

        {/* Left: container grid */}
        <div className="lg:col-span-2 space-y-2">
          {loading ? (
            <div className="glass-card p-10 text-center text-surface-500">
              <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              Loading containers…
            </div>
          ) : containers.length === 0 ? (
            <div className="glass-card p-10 text-center text-surface-500">No containers found</div>
          ) : (
            <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
              {containers.map(c => (
                <ContainerCard
                  key={c.full_id || c.id}
                  c={c}
                  selected={selected}
                  onSelect={(c) => { setSelected(c); setTab('metrics') }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right: detail panel */}
        <div className="glass-card p-5 min-h-[320px]">
          {!selected ? (
            <div className="h-full flex flex-col items-center justify-center text-center gap-3 text-surface-500">
              <Container size={32} className="opacity-30" />
              <p className="text-sm">Select a container to view metrics and logs</p>
            </div>
          ) : (
            <>
              {/* Selected container header */}
              <div className="mb-4 pb-3 border-b border-surface-800/50">
                <div className="flex items-center gap-2 mb-1">
                  {(() => {
                    const Icon = containerIcon(selected.name)
                    const isUp = selected.status === 'running'
                    const textColor = !isUp ? 'text-accent-red' : 'text-accent-green'
                    return <Icon size={15} className={textColor} />
                  })()}
                  <span className="text-sm font-semibold text-white">{selected.name.replace('fixitlab_', '')}</span>
                </div>
                <p className="text-[11px] text-surface-500 font-mono truncate">{selected.full_id?.slice(0, 12) || selected.id}</p>
              </div>

              {/* Tabs */}
              <div className="flex gap-2 mb-4">
                {['metrics', 'logs'].map(t => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTab(t)}
                    className={`px-3 py-1.5 rounded-lg text-sm capitalize transition-colors ${
                      tab === t
                        ? 'bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30'
                        : 'text-surface-400 hover:text-surface-300'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>

              {/* Metrics tab */}
              {tab === 'metrics' && detail && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-surface-900/60 rounded-xl border border-surface-800/50">
                      <Cpu size={15} className="text-accent-purple mb-1.5" />
                      <p className="text-[11px] text-surface-500">Memory</p>
                      <p className="text-lg font-bold text-white">{detail.stats?.memory_percent ?? '—'}%</p>
                      <p className="text-[10px] text-surface-500">{detail.stats?.memory_usage_mb} / {detail.stats?.memory_limit_mb} MB</p>
                      {detail.stats?.memory_percent != null && (
                        <div className="mt-2 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              detail.stats.memory_percent > 80 ? 'bg-accent-red'
                              : detail.stats.memory_percent > 60 ? 'bg-accent-amber'
                              : 'bg-accent-green'
                            }`}
                            style={{ width: `${Math.min(detail.stats.memory_percent, 100)}%` }}
                          />
                        </div>
                      )}
                    </div>
                    <div className="p-3 bg-surface-900/60 rounded-xl border border-surface-800/50">
                      <HardDrive size={15} className="text-accent-amber mb-1.5" />
                      <p className="text-[11px] text-surface-500">Status</p>
                      <p className="text-lg font-bold text-white capitalize">{detail.status}</p>
                      {selected?.restart_count > 0 && (
                        <p className="text-[10px] text-accent-amber flex items-center gap-1 mt-1.5">
                          <RotateCcw size={9} /> {selected.restart_count} restarts
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="p-3 bg-surface-900/60 rounded-xl border border-surface-800/50">
                    <Terminal size={15} className="text-accent-cyan mb-1.5" />
                    <p className="text-[11px] text-surface-500">Uptime / Session</p>
                    {selected?.up_since && (
                      <p className="text-sm font-semibold text-white mt-0.5">{formatUptime(selected.up_since)}</p>
                    )}
                    <p className="text-[10px] font-mono text-surface-400 truncate mt-0.5">
                      {detail.labels?.['fixitlab.session_id'] || detail.labels?.['fixitlab.scenario'] || '—'}
                    </p>
                  </div>
                  <pre className="text-xs bg-surface-950 p-3 rounded-xl border border-surface-800 overflow-x-auto text-surface-400 max-h-48">
                    {JSON.stringify(detail.labels || {}, null, 2)}
                  </pre>
                </div>
              )}
              {tab === 'metrics' && !detail && (
                <div className="text-center text-surface-500 text-sm pt-8">Loading metrics…</div>
              )}

              {/* Logs tab */}
              {tab === 'logs' && (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2 items-end">
                    <label className="text-xs text-surface-500 flex items-center gap-1">
                      Tail
                      <select className="input-field ml-1 py-1 text-xs" value={tail} onChange={e => setTail(e.target.value)}>
                        <option value="100">100</option>
                        <option value="200">200</option>
                        <option value="500">500</option>
                      </select>
                    </label>
                    <label className="text-xs text-surface-500 flex items-center gap-1">
                      Type
                      <select className="input-field ml-1 py-1 text-xs" value={logType} onChange={e => setLogType(e.target.value)}>
                        <option value="all">All</option>
                        <option value="stdout">stdout</option>
                        <option value="stderr">stderr</option>
                      </select>
                    </label>
                    <input
                      type="datetime-local"
                      className="input-field py-1 text-xs"
                      value={since}
                      onChange={e => setSince(e.target.value)}
                    />
                    <input
                      type="search"
                      placeholder="Filter text…"
                      className="input-field py-1 text-xs flex-1 min-w-[100px]"
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                    />
                    <label className="flex items-center gap-1 text-xs text-surface-400 cursor-pointer">
                      <input type="checkbox" checked={live} onChange={e => setLive(e.target.checked)} className="rounded" />
                      <span className={live ? 'text-accent-green' : ''}>Live</span>
                    </label>
                    <button
                      type="button"
                      onClick={() => loadLogs(selected.full_id || selected.id)}
                      className="btn-secondary text-xs flex items-center gap-1"
                    >
                      <Filter size={12} /> Apply
                    </button>
                  </div>
                  <pre className="text-[11px] leading-relaxed bg-surface-950 p-3 rounded-xl border border-surface-800 h-[340px] overflow-auto font-mono text-surface-300">
                    {logs.length ? logs.join('\n') : 'No log lines'}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
