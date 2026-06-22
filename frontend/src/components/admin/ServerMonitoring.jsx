import { useState, useEffect, useCallback, useRef } from 'react'
import { adminApi } from '../../api/admin'
import {
  Server, Cpu, MemoryStick, HardDrive, Activity,
  Clock, Network, Wifi, WifiOff, AlertTriangle, ListTree,
  Globe, Lock, HelpCircle, Boxes,
} from 'lucide-react'

// ─── Role / status presentation ────────────────────────────────────────────────

const ROLE_LABEL = { edge: 'Edge', app: 'App', data: 'Database', db: 'Database', labs: 'Labs' }

// Per-node status → badge style. The fleet API can now return four states:
//   online    — live host metrics available
//   reachable — host answers on a port but no metrics agent wired yet
//   unknown   — listed in topology, reachability unconfirmed
//   offline   — peer that should expose metrics but is unreachable
function statusStyle(status) {
  switch (status) {
    case 'online':
      return { label: 'ONLINE', icon: Wifi, cls: 'bg-accent-green/10 text-accent-green border-accent-green/25' }
    case 'reachable':
      return { label: 'REACHABLE', icon: Wifi, cls: 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/25' }
    case 'unknown':
      return { label: 'UNKNOWN', icon: HelpCircle, cls: 'bg-surface-700/40 text-surface-300 border-surface-600/40' }
    default:
      return { label: 'OFFLINE', icon: WifiOff, cls: 'bg-accent-red/10 text-accent-red border-accent-red/25' }
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtBytes(bytes) {
  if (bytes == null || isNaN(bytes)) return 'n/a'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = bytes
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

function fmtUptime(seconds) {
  if (seconds == null || isNaN(seconds)) return 'n/a'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function pctClass(pct) {
  if (pct == null) return { text: 'text-surface-400', bar: 'bg-surface-500' }
  if (pct >= 90) return { text: 'text-accent-red', bar: 'bg-accent-red' }
  if (pct >= 75) return { text: 'text-accent-amber', bar: 'bg-accent-amber' }
  return { text: 'text-accent-green', bar: 'bg-accent-green' }
}

// ─── Radial gauge (lightweight SVG) ────────────────────────────────────────────

function Gauge({ value, label, icon: Icon, sub }) {
  const pct = value == null ? null : Math.max(0, Math.min(100, value))
  const { text } = pctClass(pct)
  const radius = 26
  const circ = 2 * Math.PI * radius
  const dash = pct == null ? 0 : (pct / 100) * circ
  const stroke = pct == null ? 'var(--s-600, #475569)'
    : pct >= 90 ? 'rgb(var(--a-red))'
    : pct >= 75 ? 'rgb(var(--a-amber))'
    : 'rgb(var(--a-green))'

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative w-[68px] h-[68px]">
        <svg viewBox="0 0 68 68" className="w-full h-full -rotate-90">
          <circle cx="34" cy="34" r={radius} fill="none" strokeWidth="6"
            className="stroke-surface-700/60" />
          <circle cx="34" cy="34" r={radius} fill="none" strokeWidth="6"
            stroke={stroke} strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            style={{ transition: 'stroke-dasharray 0.6s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <Icon size={13} className={`${text} mb-0.5`} />
          <span className={`text-[13px] font-bold leading-none ${text}`}>
            {pct == null ? 'n/a' : `${Math.round(pct)}%`}
          </span>
        </div>
      </div>
      <div className="text-center leading-tight">
        <p className="text-[11px] font-medium text-surface-300">{label}</p>
        {sub && <p className="text-[10px] text-surface-500">{sub}</p>}
      </div>
    </div>
  )
}

// ─── Metric row with horizontal bar ────────────────────────────────────────────

function MetricBar({ icon: Icon, label, value, detail }) {
  const pct = value == null ? null : Math.max(0, Math.min(100, value))
  const { text, bar } = pctClass(pct)
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] mb-1">
        <span className="flex items-center gap-1.5 text-surface-400">
          <Icon size={12} /> {label}
        </span>
        <span className={`font-semibold ${text}`}>
          {pct == null ? 'n/a' : `${Math.round(pct)}%`}
          {detail && <span className="text-surface-500 font-normal ml-1">{detail}</span>}
        </span>
      </div>
      <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${pct == null ? 'bg-surface-600' : bar}`}
          style={{ width: `${pct ?? 4}%` }} />
      </div>
    </div>
  )
}

// ─── Service chips ───────────────────────────────────────────────────────────--

function ServiceList({ services }) {
  return (
    <div>
      <p className="flex items-center gap-1 text-[10px] text-surface-500 mb-1.5">
        <Boxes size={11} /> Services ({services.length})
      </p>
      <div className="flex flex-wrap gap-1">
        {services.map((s) => (
          <span
            key={s}
            className="px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-surface-800/60 text-surface-300 border border-surface-700/40"
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}

// ─── Server card ───────────────────────────────────────────────────────────────

function ServerCard({ node }) {
  const online = node.status === 'online'
  const cpu = pctClass(node.cpu_percent)
  const st = statusStyle(node.status)
  const StatusIcon = st.icon
  const role = node.role
  const roleLabel = role ? (ROLE_LABEL[role] || role) : null
  const services = node.services || []

  const cardClass = node.status === 'offline'
    ? 'border-accent-red/25 bg-accent-red/5'
    : !online
      ? 'border-surface-700/50 bg-surface-900/30'
      : (node.cpu_percent >= 90 || node.mem_percent >= 90 || node.disk_percent >= 90)
        ? 'border-accent-amber/25 bg-accent-amber/[0.04]'
        : 'border-surface-700/50 bg-surface-900/40'

  const iconWrap = node.status === 'offline'
    ? 'bg-accent-red/10' : online ? 'bg-accent-cyan/10' : 'bg-surface-700/30'
  const iconColor = node.status === 'offline'
    ? 'text-accent-red' : online ? 'text-accent-cyan' : 'text-surface-300'

  return (
    <div className={`rounded-2xl border p-5 transition-all ${cardClass}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-4">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`p-2 rounded-xl shrink-0 ${iconWrap}`}>
            <Server size={16} className={iconColor} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <p className="text-sm font-semibold text-white truncate">{node.name || node.hostname || 'node'}</p>
              {roleLabel && (
                <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-accent-cyan/12 text-accent-cyan shrink-0">
                  {roleLabel}
                </span>
              )}
              {node.is_local && (
                <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-accent-purple/15 text-accent-purple shrink-0">
                  local
                </span>
              )}
              {node.public != null && (
                node.public
                  ? <Globe size={11} className="text-surface-500 shrink-0" title="Public node" />
                  : <Lock size={11} className="text-surface-500 shrink-0" title="Private (VPC only)" />
              )}
            </div>
            <p className="text-[11px] text-surface-500 font-mono flex items-center gap-1 truncate">
              <Network size={10} /> {node.ip || node.private_ipv4 || 'n/a'}
              {node.public_ipv4 && node.public_ipv4 !== node.ip && (
                <span className="text-surface-600"> · {node.public_ipv4}</span>
              )}
            </p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border shrink-0 ${st.cls}`}>
          <StatusIcon size={10} />
          {st.label}
        </span>
      </div>

      {!online ? (
        <div className="space-y-3">
          <div className={`flex items-start gap-2 text-[12px] rounded-lg px-3 py-2.5 ${
            node.status === 'offline'
              ? 'text-accent-red/80 bg-accent-red/5'
              : 'text-surface-400 bg-surface-800/30'
          }`}>
            {node.status === 'offline'
              ? <AlertTriangle size={14} className="shrink-0 mt-0.5" />
              : <HelpCircle size={14} className="shrink-0 mt-0.5" />}
            <span title={node.error}>
              {node.error || (node.status === 'reachable'
                ? 'Host reachable — host metrics need a monitoring agent'
                : 'Host metrics unavailable')}
            </span>
          </div>
          {services.length > 0 && <ServiceList services={services} />}
        </div>
      ) : (
        <>
          {/* Gauges: CPU / Mem / Disk */}
          <div className="grid grid-cols-3 gap-2 mb-4">
            <Gauge value={node.cpu_percent} label="CPU" icon={Cpu}
              sub={node.cpu_count ? `${node.cpu_count} cores` : undefined} />
            <Gauge value={node.mem_percent} label="Memory" icon={MemoryStick}
              sub={node.mem_total ? fmtBytes(node.mem_total) : undefined} />
            <Gauge value={node.disk_percent} label="Disk" icon={HardDrive}
              sub={node.disk_total ? fmtBytes(node.disk_total) : undefined} />
          </div>

          {/* Detailed bars */}
          <div className="space-y-2.5 mb-4">
            <MetricBar icon={MemoryStick} label="Memory used" value={node.mem_percent}
              detail={node.mem_used != null ? `${fmtBytes(node.mem_used)} / ${fmtBytes(node.mem_total)}` : null} />
            <MetricBar icon={HardDrive} label="Disk used" value={node.disk_percent}
              detail={node.disk_used != null ? `${fmtBytes(node.disk_used)} / ${fmtBytes(node.disk_total)}` : null} />
          </div>

          {/* Stat strip: load / uptime / processes */}
          <div className="grid grid-cols-3 gap-2 pt-3 border-t border-surface-800/60">
            <div className="text-center">
              <p className="flex items-center justify-center gap-1 text-[10px] text-surface-500 mb-0.5">
                <Activity size={11} /> Load
              </p>
              <p className={`text-[12px] font-semibold ${cpu.text}`}>
                {node.load_1 != null ? node.load_1 : 'n/a'}
              </p>
              <p className="text-[10px] text-surface-500">
                {node.load_5 != null ? `${node.load_5} · ${node.load_15}` : '5m · 15m'}
              </p>
            </div>
            <div className="text-center">
              <p className="flex items-center justify-center gap-1 text-[10px] text-surface-500 mb-0.5">
                <Clock size={11} /> Uptime
              </p>
              <p className="text-[12px] font-semibold text-surface-200">{fmtUptime(node.uptime_seconds)}</p>
            </div>
            <div className="text-center">
              <p className="flex items-center justify-center gap-1 text-[10px] text-surface-500 mb-0.5">
                <ListTree size={11} /> Procs
              </p>
              <p className="text-[12px] font-semibold text-surface-200">
                {node.process_count != null ? node.process_count : 'n/a'}
              </p>
            </div>
          </div>

          {services.length > 0 && (
            <div className="pt-3 mt-3 border-t border-surface-800/60">
              <ServiceList services={services} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ─── Main section ────────────────────────────────────────────────────────────--

export default function ServerMonitoring({ refreshMs = 10000, className = '' }) {
  const [fleet, setFleet] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const timer = useRef(null)
  const hadData = useRef(false)

  const load = useCallback(async () => {
    try {
      const data = await adminApi.getFleetMetrics()
      setFleet(data)
      hadData.current = true
      setError(false)
    } catch {
      setError(!hadData.current)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    timer.current = setInterval(load, refreshMs)
    return () => clearInterval(timer.current)
  }, [load, refreshMs])

  const nodes = fleet?.nodes || []
  // "live" = nodes reporting host metrics; "up" = live + reachable hosts.
  const liveCount = fleet?.online ?? 0
  const upCount = liveCount + (fleet?.reachable ?? 0)
  const clusterMeta = fleet?.cluster || {}
  const topologyLabel = fleet?.is_cluster
    ? `${fleet.total}-node cluster${clusterMeta.region ? ` · ${clusterMeta.region}` : ''}`
    : 'single host'

  return (
    <div className={`glass-card p-6 ${className}`}>
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2 flex-wrap">
          <Server size={18} className="text-accent-cyan" />
          Server Monitoring
          {fleet && (
            <span className="text-xs font-normal text-surface-500 ml-1">
              ({upCount}/{fleet.total} up
              {liveCount < upCount ? ` · ${liveCount} reporting metrics` : ''})
            </span>
          )}
          {fleet && (
            <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-surface-800/60 text-surface-400 border border-surface-700/50">
              {topologyLabel}
            </span>
          )}
        </h2>
        <div className="flex items-center gap-3">
          {fleet && (
            <span className="flex items-center gap-1.5 text-[11px] text-surface-500">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
              Live · refresh {Math.round(refreshMs / 1000)}s
            </span>
          )}
        </div>
      </div>

      {/* Cluster note: clarify when nodes are listed without live host metrics */}
      {fleet?.is_cluster && (fleet.reachable > 0 || fleet.unknown > 0) && (
        <div className="mb-4 flex items-start gap-2 text-[11px] text-surface-400 bg-surface-800/30 border border-surface-700/40 rounded-lg px-3 py-2">
          <HelpCircle size={13} className="shrink-0 mt-0.5 text-surface-500" />
          <span>
            Showing all {fleet.total} cluster nodes from topology. Host metrics
            (CPU/memory/disk) are live on the local node; remote nodes need a
            monitoring agent — until then they show role, IP and reachability.
          </span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error && nodes.length === 0 ? (
        <div className="text-center py-10 text-surface-500 text-sm">
          Could not load server metrics
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {nodes.map((node, i) => (
            <ServerCard key={node.name || node.ip || i} node={node} />
          ))}
        </div>
      )}
    </div>
  )
}
