import { useCallback, useMemo, useState } from 'react'
import {
  Compass, Database, Play, RefreshCw, History, Columns2,
  AlertTriangle, Search, Clock,
} from 'lucide-react'
import { monitoringApi } from '../../api/monitoring'

/* ── tiny inline sparkline driven by a numeric series (matches MonitoringSimulator) ── */
function Sparkline({ values, color = '#f7913b', height = 64 }) {
  const W = 280, H = height
  const pts = (values && values.length >= 2) ? values : [0, 0]
  const min = Math.min(...pts), max = Math.max(...pts)
  const span = max - min || 1
  const path = pts
    .map((v, i) => `${(i / (pts.length - 1)) * W},${H - ((v - min) / span) * (H - 8) - 4}`)
    .join(' ')
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block">
      <polyline points={path} fill="none" stroke={color} strokeWidth="1.6" />
      <polyline points={`0,${H} ${path} ${W},${H}`} fill={`${color}1a`} stroke="none" />
    </svg>
  )
}

function fmtNum(v) {
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return Math.abs(n) >= 1000
    ? n.toLocaleString(undefined, { maximumFractionDigits: 4 })
    : n.toFixed(4).replace(/\.?0+$/, '')
}

const EXAMPLE_QUERIES = [
  'up',
  'up == 0',
  'sum by(job)(up)',
  'rate(node_cpu_seconds_total{mode="idle"}[5m])',
  'node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100',
  'prometheus_tsdb_head_series',
]

/**
 * GrafanaExplorePanel — an original functional emulation of Grafana's "Explore" view
 * for the FixitLab monitoring sim. Lets a learner pick a data source, type a PromQL
 * expression, run it, and view the result both as a Prometheus-style series table and
 * as an inline sparkline that accumulates the scalar value across repeated runs.
 *
 * Purely presentational beyond monitoringApi.query — resilient to missing props.
 */
export default function GrafanaExplorePanel({ sessionId, scenarioSlug, datasources = [] }) {
  // Normalize datasources, defaulting to a Prometheus source if none provided.
  const sources = useMemo(() => {
    const list = Array.isArray(datasources) ? datasources : []
    if (list.length === 0) {
      return [{ uid: 'prom-default', name: 'Prometheus', type: 'prometheus', is_default: true }]
    }
    return list
  }, [datasources])

  const defaultSource = useMemo(
    () => sources.find(d => d.is_default) || sources[0],
    [sources],
  )

  const [dsUid, setDsUid] = useState(defaultSource?.uid ?? defaultSource?.name ?? '')
  const [expr, setExpr] = useState('up')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [series, setSeries] = useState([])
  const [history, setHistory] = useState([])
  const [split, setSplit] = useState(false)

  const dsKey = useCallback(
    (d) => d?.uid ?? d?.name ?? '',
    [],
  )
  const activeSource = useMemo(
    () => sources.find(d => dsKey(d) === dsUid) || defaultSource,
    [sources, dsUid, dsKey, defaultSource],
  )

  const runQuery = useCallback(async (q) => {
    const query = (q ?? expr ?? '').trim()
    if (!query) return
    setRunning(true)
    try {
      const res = await monitoringApi.query(sessionId, query)
      const payload = res?.result || { status: 'error', error: 'no response' }
      setResult(payload)

      // Accumulate the scalar value of the first series into the inline graph.
      if (payload.status === 'success') {
        const rows = payload.data?.result || []
        if (rows.length > 0) {
          const v = Number(rows[0]?.value?.[1])
          if (!Number.isNaN(v)) setSeries(prev => [...prev.slice(-23), v])
        }
      }
    } catch (e) {
      setResult({ status: 'error', error: e?.message || 'query failed' })
    } finally {
      setRunning(false)
      // Push onto client-side history (most recent first, dedupe consecutive, cap ~8).
      setHistory(prev => {
        if (prev[0] === query) return prev
        return [query, ...prev.filter(h => h !== query)].slice(0, 8)
      })
    }
  }, [expr, sessionId])

  const rows = result?.status === 'success' ? (result.data?.result || []) : []

  return (
    <div className="mon-card !p-0 overflow-hidden">
      {/* header */}
      <div className="flex items-center justify-between gap-3 px-3 py-2.5 border-b border-[#262a45] flex-wrap">
        <div className="flex items-center gap-2">
          <Compass size={16} style={{ color: '#f7913b' }} />
          <span className="mon-panel-title">Explore</span>
          {scenarioSlug && <span className="mon-panel-sub hidden sm:inline">{scenarioSlug}</span>}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-[#8a93b2]">
            <Database size={13} />
            <select
              className="mon-input !py-1 !text-xs"
              value={dsUid}
              onChange={e => setDsUid(e.target.value)}
            >
              {sources.map(d => (
                <option key={dsKey(d)} value={dsKey(d)}>
                  {d.name || d.type || dsKey(d)}{d.is_default ? ' (default)' : ''}
                </option>
              ))}
            </select>
          </label>
          <button
            className={`mon-tab flex items-center gap-1.5 ${split ? 'mon-tab-active' : ''}`}
            onClick={() => setSplit(s => !s)}
            title="Split view (visual only)"
          >
            <Columns2 size={13} /> Split
          </button>
        </div>
      </div>

      <div className="p-3 space-y-3">
        {/* query editor row */}
        <div className="flex items-center gap-2">
          <span className="mon-panel-sub font-mono hidden sm:inline">
            {activeSource?.type || 'prometheus'}
          </span>
          <input
            className="mon-input flex-1 font-mono"
            value={expr}
            spellCheck={false}
            placeholder="Enter a PromQL expression…"
            onChange={e => setExpr(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') runQuery() }}
          />
          <button
            className="mon-btn-primary flex items-center gap-1.5"
            style={{ background: '#f7913b', color: '#1a1206' }}
            disabled={running}
            onClick={() => runQuery()}
          >
            {running ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
            Run query
          </button>
        </div>

        {/* example-query chips */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="mon-panel-sub flex items-center gap-1"><Search size={12} /> Examples:</span>
          {EXAMPLE_QUERIES.map(s => (
            <button
              key={s}
              className="mon-tab !text-[11px] font-mono"
              onClick={() => { setExpr(s); runQuery(s) }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* inline graph: accumulated scalar across runs */}
        <div className="mon-card">
          <div className="flex items-center justify-between mb-1">
            <span className="mon-panel-title">Graph</span>
            <span className="mon-panel-sub">
              {series.length === 0
                ? 'run a query to plot a point'
                : `${series.length} sample${series.length === 1 ? '' : 's'} · last ${fmtNum(series[series.length - 1])}`}
            </span>
          </div>
          {series.length === 0 ? (
            <div className="flex items-center gap-2 text-[#8a93b2] text-xs py-6 justify-center">
              <AlertTriangle size={14} /> No data points yet — each run appends the first series value
            </div>
          ) : (
            <Sparkline values={series} color="#f7913b" />
          )}
        </div>

        {/* results table */}
        <div className="mon-card !p-0 overflow-hidden">
          {!result ? (
            <div className="text-[#8a93b2] text-xs p-4 flex items-center gap-2 justify-center">
              <Search size={14} /> Run a query to see results
            </div>
          ) : result.status === 'error' ? (
            <div className="text-[#ffb4b4] text-xs p-3 font-mono">error: {result.error || 'query failed'}</div>
          ) : rows.length === 0 ? (
            <div className="text-[#f5c451] text-xs p-4 flex items-center gap-2 justify-center">
              <AlertTriangle size={14} /> Empty query result — no series match
            </div>
          ) : (
            <table className="mon-table">
              <thead>
                <tr>
                  <th>Series (labels)</th>
                  <th className="text-right">Value</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 60).map((row, i) => {
                  const metric = row?.metric || {}
                  const { __name__, ...labels } = metric
                  const lbl = Object.entries(labels).map(([k, v]) => `${k}="${v}"`).join(', ')
                  return (
                    <tr key={i}>
                      <td className="font-mono">
                        <span className="text-[#f7913b]">{__name__ || ''}</span>
                        <span className="text-[#8a93b2]">{lbl ? `{${lbl}}` : ''}</span>
                      </td>
                      <td className="text-right font-mono text-[#56e0b0]">
                        {fmtNum(row?.value?.[1])}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* query history (client-side, last ~8) */}
        {history.length > 0 && (
          <div className="mon-card !p-0 overflow-hidden">
            <div className="px-3 py-2 mon-panel-sub border-b border-[#262a45] flex items-center gap-2">
              <History size={13} /> Query history
            </div>
            <ul>
              {history.map((h, i) => (
                <li
                  key={`${h}-${i}`}
                  className="flex items-center justify-between gap-3 px-3 py-1.5 border-b border-[#262a45] last:border-b-0"
                >
                  <button
                    className="font-mono text-xs text-[#d8def0] truncate text-left hover:text-[#f7913b]"
                    onClick={() => { setExpr(h); runQuery(h) }}
                    title={h}
                  >
                    {h}
                  </button>
                  <span className="mon-panel-sub flex items-center gap-1 shrink-0">
                    <Clock size={11} /> {i === 0 ? 'latest' : `#${i + 1}`}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
