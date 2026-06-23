import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bell, Gauge, Search, Server, GitBranch,
  AlertTriangle, XCircle, RefreshCw, Play, Layers,
  Compass, Settings, Plug,
} from 'lucide-react'
import { monitoringApi } from '../../api/monitoring'
import MonitoringLoginGate, { isMonitoringAuthenticated } from './MonitoringLoginGate'
import GrafanaLoginScreen from './GrafanaLoginScreen'
import MonitoringLabChrome from './MonitoringLabChrome'
import GrafanaExplorePanel from './GrafanaExplorePanel'
import GrafanaAlertingPanel from './GrafanaAlertingPanel'
import GrafanaConnectionsPanel from './GrafanaConnectionsPanel'
import GrafanaAdministrationPanel from './GrafanaAdministrationPanel'
import '../../styles/monitoring-sim.css'

/* ── tiny inline sparkline driven by a numeric series ── */
function Sparkline({ values, color = '#56e0b0', height = 56 }) {
  const W = 240, H = height
  const pts = (values && values.length >= 2) ? values : [0, 0]
  const min = Math.min(...pts), max = Math.max(...pts)
  const span = max - min || 1
  const path = pts.map((v, i) => `${(i / (pts.length - 1)) * W},${H - ((v - min) / span) * (H - 8) - 4}`).join(' ')
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block">
      <polyline points={path} fill="none" stroke={color} strokeWidth="1.6" />
      <polyline points={`0,${H} ${path} ${W},${H}`} fill={`${color}1a`} stroke="none" />
    </svg>
  )
}

function fmtVal(v, unit) {
  const n = Number(v)
  if (Number.isNaN(n)) return v
  if (unit === 'bytes') {
    if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GB`
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`
    return `${n.toFixed(0)} B`
  }
  if (unit === 'percent') return `${n.toFixed(1)}%`
  if (unit === 'percentunit') return `${(n * 100).toFixed(2)}%`
  if (unit === 's') return `${n.toFixed(3)} s`
  if (unit === 'reqps') return `${n.toFixed(1)} req/s`
  return Math.abs(n) >= 1000 ? n.toLocaleString() : n.toFixed(2)
}

/* ── a single dashboard panel: evaluates its expr to a value/series ── */
function DashPanel({ panel, sessionId, scenario, noData }) {
  const [series, setSeries] = useState([])
  const [value, setValue] = useState(null)
  const [empty, setEmpty] = useState(noData)

  useEffect(() => {
    let live = true
    const tick = async () => {
      try {
        const res = await monitoringApi.query(sessionId, panel.expr)
        const rows = res?.result?.data?.result || []
        if (!live) return
        if (rows.length === 0) { setEmpty(true); return }
        setEmpty(false)
        const v = Number(rows[0].value[1])
        setValue(v)
        setSeries(prev => [...prev.slice(-23), v])
      } catch {
        if (live) setEmpty(true)
      }
    }
    tick()
    const id = setInterval(tick, 5000)
    return () => { live = false; clearInterval(id) }
  }, [panel.expr, sessionId, scenario])

  const color = panel.type === 'gauge' ? '#f5c451' : '#56e0b0'
  return (
    <div className="mon-card">
      <div className="flex items-center justify-between mb-1">
        <span className="mon-panel-title">{panel.title}</span>
        <span className="mon-panel-sub uppercase">{panel.type}</span>
      </div>
      {empty ? (
        <div className="flex items-center gap-2 text-[#f5c451] text-xs py-5 justify-center">
          <AlertTriangle size={14} /> No data
        </div>
      ) : panel.type === 'stat' || panel.type === 'gauge' ? (
        <div className="mon-stat" style={{ color }}>{value == null ? '—' : fmtVal(value, panel.unit)}</div>
      ) : (
        <>
          <Sparkline values={series} color={color} />
          <div className="mon-panel-sub mt-1">{value == null ? '—' : fmtVal(value, panel.unit)}</div>
        </>
      )}
      <div className="mon-code mt-2 !text-[10px] !py-1.5 opacity-80">{panel.expr}</div>
    </div>
  )
}

/* ── Grafana view ── */
function GrafanaView({ state, sessionId, scenario }) {
  const graf = state.grafana || {}
  const [activeDash, setActiveDash] = useState(graf.dashboards?.[0]?.uid || '')
  const [sub, setSub] = useState('dashboards') // dashboards | alerting | datasources | contactpoints
  const noDataPanels = new Set(state.broken?.panels_no_data || [])
  const dash = (graf.dashboards || []).find(d => d.uid === activeDash) || graf.dashboards?.[0]

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-4">
      {/* left rail */}
      <div className="space-y-1">
        {[['dashboards', 'Dashboards', Gauge], ['explore', 'Explore', Compass], ['alerting', 'Alerting', Bell],
          ['connections', 'Connections', Plug], ['administration', 'Administration', Settings]].map(([k, label, Icon]) => (
          <button key={k} onClick={() => setSub(k)}
                  className={`mon-tab w-full !justify-start flex items-center gap-2 ${sub === k ? 'mon-tab-active' : ''}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      <div>
        {sub === 'dashboards' && dash && (
          <>
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              {(graf.dashboards || []).map(d => (
                <button key={d.uid} onClick={() => setActiveDash(d.uid)}
                        className={`mon-tab ${d.uid === activeDash ? 'mon-tab-active' : ''}`}>{d.title}</button>
              ))}
            </div>
            {/* template variables */}
            {dash.templating?.length > 0 && (
              <div className="flex items-center gap-3 mb-3 flex-wrap">
                {dash.templating.map(v => (
                  <label key={v.name} className="flex items-center gap-1.5 text-xs text-[#8a93b2]">
                    {v.label || v.name}:
                    <select className="mon-input !py-1 !text-xs" defaultValue={v.current}>
                      {(v.options || []).map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </label>
                ))}
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(dash.panels || []).map(p => (
                <DashPanel key={`${dash.uid}-${p.id}`} panel={p} sessionId={sessionId}
                           scenario={scenario} noData={noDataPanels.has(p.id)} />
              ))}
            </div>
          </>
        )}

        {/* Empty-state: never leave the default Dashboards tab blank. */}
        {sub === 'dashboards' && !dash && (
          <div className="mon-card text-center py-12">
            <Gauge size={28} className="mx-auto mb-3 text-[#8a93b2]" />
            <div className="mon-panel-title mb-1">No dashboards provisioned for this scenario</div>
            <div className="mon-panel-sub max-w-md mx-auto">
              This lab focuses on data sources, alerting or PromQL rather than pre-built dashboards.
              Use the <span className="text-[#f7913b]">Explore</span> tab to run queries, or check{' '}
              <span className="text-[#f7913b]">Alerting</span> and{' '}
              <span className="text-[#f7913b]">Connections</span> for what to investigate.
            </div>
          </div>
        )}

        {sub === 'explore' && (
          <GrafanaExplorePanel sessionId={sessionId} scenarioSlug={scenario} datasources={graf.datasources || []} />
        )}

        {sub === 'alerting' && <GrafanaAlertingPanel graf={graf} />}

        {sub === 'connections' && <GrafanaConnectionsPanel datasources={graf.datasources || []} />}

        {sub === 'administration' && <GrafanaAdministrationPanel scenario={scenario} />}
      </div>
    </div>
  )
}

/* ── Prometheus view ── */
function PrometheusView({ state, sessionId, scenario, defaultExpr }) {
  const prom = state.prometheus || {}
  const [sub, setSub] = useState('query') // query | targets | rules | alertmanager
  const [expr, setExpr] = useState(defaultExpr || 'up')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)

  const runQuery = useCallback(async (q) => {
    setRunning(true)
    try {
      const res = await monitoringApi.query(sessionId, q ?? expr)
      setResult(res?.result || { status: 'error', error: 'no response' })
    } catch (e) {
      setResult({ status: 'error', error: e?.message || 'query failed' })
    } finally {
      setRunning(false)
    }
  }, [expr, sessionId])

  useEffect(() => { runQuery(defaultExpr || 'up') }, []) // eslint-disable-line

  const SAMPLES = [
    'up', 'up == 0', 'sum by(job)(up)',
    'rate(node_cpu_seconds_total{mode="idle"}[5m])',
    'sum(rate(http_requests_total{code="500"}[5m])) / sum(rate(http_requests_total[5m]))',
    'node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100',
    'prometheus_tsdb_head_series',
  ]

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {[['query', 'Graph / PromQL', Search], ['targets', 'Targets', Server],
          ['rules', 'Rules', GitBranch], ['alertmanager', 'Alertmanager', Bell]].map(([k, label, Icon]) => (
          <button key={k} onClick={() => setSub(k)}
                  className={`mon-tab flex items-center gap-2 ${sub === k ? 'mon-tab-active' : ''}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {sub === 'query' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <input className="mon-input flex-1 font-mono" value={expr} spellCheck={false}
                   onChange={e => setExpr(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') runQuery() }}
                   placeholder="Enter a PromQL expression…" />
            <button className="mon-btn-primary" style={{ background: '#e6522c', color: '#1a1206' }}
                    disabled={running} onClick={() => runQuery()}>
              {running ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />} Execute
            </button>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {SAMPLES.map(s => (
              <button key={s} className="mon-tab !text-[11px] font-mono" onClick={() => { setExpr(s); runQuery(s) }}>{s}</button>
            ))}
          </div>
          {result && (
            <div className="mon-card !p-0 overflow-hidden">
              {result.status === 'error' ? (
                <div className="text-[#ffb4b4] text-xs p-3 font-mono">error: {result.error}</div>
              ) : (result.data?.result || []).length === 0 ? (
                <div className="text-[#f5c451] text-xs p-4 flex items-center gap-2 justify-center">
                  <AlertTriangle size={14} /> Empty query result — no series match
                </div>
              ) : (
                <table className="mon-table">
                  <thead><tr><th>Series (labels)</th><th className="text-right">Value</th></tr></thead>
                  <tbody>
                    {(result.data.result).slice(0, 60).map((row, i) => {
                      const { __name__, ...labels } = row.metric
                      const lbl = Object.entries(labels).map(([k, v]) => `${k}="${v}"`).join(', ')
                      return (
                        <tr key={i}>
                          <td className="font-mono">
                            <span className="text-[#e6a35c]">{__name__ || ''}</span>
                            <span className="text-[#8a93b2]">{lbl ? `{${lbl}}` : ''}</span>
                          </td>
                          <td className="text-right font-mono text-[#56e0b0]">{Number(row.value[1]).toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {sub === 'targets' && (
        <div className="mon-card !p-0 overflow-hidden">
          <table className="mon-table">
            <thead><tr><th>Job</th><th>Endpoint</th><th>State</th><th>Last scrape</th><th>Error</th></tr></thead>
            <tbody>
              {(prom.targets || []).map((t, i) => (
                <tr key={i}>
                  <td className="font-medium text-[#d8def0]">{t.job}</td>
                  <td className="font-mono opacity-80">{t.scrape_url}</td>
                  <td>
                    <span className={`mon-badge ${t.health === 'down' ? 'mon-badge-down' : 'mon-badge-up'}`}>
                      {t.health === 'down' ? 'DOWN' : 'UP'}
                    </span>
                  </td>
                  <td className="font-mono opacity-70">{t.scrape_duration_ms}ms</td>
                  <td className="text-[#ffb4b4] text-xs">{t.last_error || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sub === 'rules' && (
        <div className="space-y-3">
          <div className="mon-card !p-0 overflow-hidden">
            <div className="px-3 py-2 mon-panel-sub border-b border-[#262a45] flex items-center gap-2"><Layers size={13} /> Recording rules</div>
            <table className="mon-table">
              <thead><tr><th>Group</th><th>Name</th><th>Expr</th><th>Health</th></tr></thead>
              <tbody>
                {(prom.recording_rules || []).map((r, i) => (
                  <tr key={i}>
                    <td className="font-mono">{r.group}</td>
                    <td className="font-medium text-[#d8def0]">{r.name}</td>
                    <td className="font-mono text-xs opacity-80">{r.expr}</td>
                    <td><span className={`mon-badge ${r.health === 'err' ? 'mon-badge-down' : 'mon-badge-up'}`}>{r.health}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            <div className="px-3 py-2 mon-panel-sub border-b border-[#262a45] flex items-center gap-2"><Bell size={13} /> Alerting rules</div>
            <table className="mon-table">
              <thead><tr><th>Group</th><th>Alert</th><th>Expr</th><th>For</th><th>State</th></tr></thead>
              <tbody>
                {(prom.alerting_rules || []).map((r, i) => (
                  <tr key={i}>
                    <td className="font-mono">{r.group}</td>
                    <td className="font-medium text-[#d8def0]">{r.name}</td>
                    <td className="font-mono text-xs opacity-80">{r.expr}</td>
                    <td className="font-mono">{r.for}</td>
                    <td><span className={`mon-badge ${r.state === 'firing' ? 'mon-badge-down' : r.state === 'pending' ? 'mon-badge-warn' : 'mon-badge-up'}`}>{r.state}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {sub === 'alertmanager' && prom.alertmanager && (
        <div className="space-y-3">
          <div className="mon-card">
            <div className="mon-panel-title mb-1">Routing tree</div>
            <div className="mon-code">{JSON.stringify(prom.alertmanager.route, null, 2)}</div>
          </div>
          <div className="mon-card">
            <div className="mon-panel-title mb-1">Receivers</div>
            <div className="flex gap-2 flex-wrap">
              {(prom.alertmanager.receivers || []).map(r => (
                <span key={r.name} className={`mon-badge ${r.configured ? 'mon-badge-up' : 'mon-badge-down'}`}>{r.name} · {r.type}</span>
              ))}
            </div>
          </div>
          {(prom.remote_write || []).length > 0 && (
            <div className="mon-card">
              <div className="mon-panel-title mb-1">Remote write</div>
              {prom.remote_write.map((rw, i) => (
                <div key={i} className="text-xs">
                  <span className="font-mono">{rw.url}</span> —{' '}
                  <span className={rw.health === 'down' ? 'text-[#ffb4b4]' : 'text-[#56e0b0]'}>{rw.health}</span>
                  {rw.queue_pending ? <span className="opacity-70"> · {rw.queue_pending.toLocaleString()} pending</span> : null}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Top-level Grafana + Prometheus simulator. Rendered INLINE by LabRunner for
 * monitoring labs (simulation_type grafana/prometheus/monitoring) — no new route.
 * `flavor` selects which view is primary; both are always reachable via the tabs.
 */
export default function MonitoringSimulator({ sessionId, scenario, flavor = 'grafana', onExit, onStop, onHints }) {
  const [authed, setAuthed] = useState(isMonitoringAuthenticated())
  const [state, setState] = useState(null)
  const [view, setView] = useState(flavor === 'prometheus' ? 'prometheus' : 'grafana')
  const [error, setError] = useState('')
  const slug = scenario?.slug || ''
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await monitoringApi.getState(sessionId, slug)
      setState(data)
      setError('')
    } catch (e) {
      setError('Could not load the monitoring simulator')
    }
  }, [sessionId, slug])

  useEffect(() => {
    if (!authed) return
    load()
    pollRef.current = setInterval(load, 15000)
    return () => clearInterval(pollRef.current)
  }, [authed, load])

  if (!authed) {
    // The login gate is the first thing a learner sees when they open the sim.
    // Forward the lab chrome handlers so Hints / Stop / Back to lab work here too
    // (mirrors how the VMware / Nmap sims keep that chrome reachable at all times).
    return flavor === 'prometheus'
      ? <MonitoringLoginGate flavor={flavor} onAuthenticated={() => setAuthed(true)}
                             onExit={onExit} onStop={onStop} onHints={onHints} />
      : <GrafanaLoginScreen onAuthenticated={() => setAuthed(true)}
                            scenario={scenario} onExit={onExit} onStop={onStop} onHints={onHints} />
  }

  const accent = flavor === 'prometheus' ? '#e6522c' : '#f7913b'
  const product = flavor === 'prometheus' ? 'Prometheus' : 'Grafana'
  const summary = state?.summary || {}

  return (
    <div className="mon-sim mon-shell min-h-screen">
      <MonitoringLabChrome
        product={product}
        accent={accent}
        subtitle={scenario?.title || slug}
        onExit={onExit}
        onStop={onStop}
        onHints={onHints}
      >
        <button className={`mon-tab ${view === 'grafana' ? 'mon-tab-active' : ''}`} onClick={() => setView('grafana')}>Grafana</button>
        <button className={`mon-tab ${view === 'prometheus' ? 'mon-tab-active' : ''}`} onClick={() => setView('prometheus')}>Prometheus</button>
        <button className="mon-btn" onClick={load}><RefreshCw size={13} /> Refresh</button>
      </MonitoringLabChrome>

      <div className="p-4 max-w-[1200px] mx-auto">
        {error && <div className="mon-banner mon-banner-err"><XCircle size={15} /> {error}</div>}

        {/* fault summary banner so the learner knows what to investigate */}
        {state?.broken?.summary && (
          <div className={`mon-banner ${summary.datasources_failing || summary.targets_down ? 'mon-banner-err' : ''}`}>
            <AlertTriangle size={15} className="shrink-0 mt-0.5" />
            <span>{state.broken.summary}</span>
          </div>
        )}

        {/* quick KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {[
            ['Targets up', `${summary.targets_total - (summary.targets_down || 0)}/${summary.targets_total}`, (summary.targets_down ? '#ff6b6b' : '#56e0b0')],
            ['Datasources OK', `${summary.datasources_total - (summary.datasources_failing || 0)}/${summary.datasources_total}`, (summary.datasources_failing ? '#ff6b6b' : '#56e0b0')],
            ['Alerts firing', summary.alerts_firing || 0, (summary.alerts_firing ? '#f5c451' : '#56e0b0')],
            ['Head series', (summary.head_series || 0).toLocaleString(), (summary.high_cardinality ? '#ff6b6b' : '#8a93b2')],
          ].map(([label, val, color]) => (
            <div key={label} className="mon-card">
              <div className="mon-panel-sub">{label}</div>
              <div className="mon-stat" style={{ color }}>{val}</div>
            </div>
          ))}
        </div>

        {!state ? (
          <div className="text-center text-[#8a93b2] py-16">Loading {product} state…</div>
        ) : view === 'grafana' ? (
          <GrafanaView state={state} sessionId={sessionId} scenario={slug} />
        ) : (
          <PrometheusView state={state} sessionId={sessionId} scenario={slug}
                          defaultExpr={summary.targets_down ? 'up == 0' : 'up'} />
        )}
      </div>
    </div>
  )
}
