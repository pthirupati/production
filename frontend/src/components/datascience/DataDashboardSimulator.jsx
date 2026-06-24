import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  BarChart3, LineChart, Table2, PieChart, RefreshCw, ArrowLeft, StopCircle,
  Lightbulb, XCircle, Target, Filter, Layers, Sigma, History, RotateCcw,
  Database, CheckCircle2,
} from 'lucide-react'
import { datascienceApi } from '../../api/datascience'
import { LabChromeControls } from '../lab/LabChromeBar'

/* ── scoped, self-contained BI-tool chrome (no shared CSS) ── */
const SCOPED_CSS = `
.ds-sim {
  --ds-bg: #07120c;
  --ds-panel: #0b1a12;
  --ds-panel-2: #0f2018;
  --ds-border: #18382a;
  --ds-text: #d6f5e3;
  --ds-muted: #79a791;
  --ds-green: #34d399;
  --ds-cyan: #38e0d0;
  --ds-amber: #f5c451;
  --ds-red: #ff6b6b;
  --ds-bar: #34d399;
  color: var(--ds-text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--ds-bg);
  min-height: 100%;
}
.ds-sim .ds-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;
  padding: 0.6rem 1rem; background: #050d08; border-bottom: 1px solid var(--ds-border);
  position: sticky; top: 0; z-index: 10;
}
.ds-sim .ds-btn {
  display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 6px;
  padding: 0.45rem 0.8rem; font-size: 0.8rem; font-weight: 600; cursor: pointer;
  border: 1px solid var(--ds-border); background: #102a1e; color: var(--ds-text);
  transition: background 0.12s, filter 0.12s;
}
.ds-sim .ds-btn:hover { background: #163827; }
.ds-sim .ds-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.ds-sim .ds-select {
  background: #061008; border: 1px solid var(--ds-border); border-radius: 6px;
  padding: 0.5rem 0.65rem; color: var(--ds-text); font-size: 0.82rem; outline: none;
  width: 100%; cursor: pointer;
}
.ds-sim .ds-select:focus { border-color: var(--ds-green); box-shadow: 0 0 0 2px rgba(52,211,153,.18); }
.ds-sim .ds-card {
  background: var(--ds-panel); border: 1px solid var(--ds-border); border-radius: 8px;
}
.ds-sim .ds-chip {
  display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.74rem; font-weight: 600;
  padding: 0.32rem 0.7rem; border-radius: 6px; cursor: pointer; white-space: nowrap;
  border: 1px solid var(--ds-border); background: #0c1d14; color: var(--ds-muted);
  transition: color .12s, border-color .12s, background .12s;
}
.ds-sim .ds-chip:hover { color: var(--ds-text); border-color: var(--ds-green); }
.ds-sim .ds-chip-active { color: #042016; background: var(--ds-green); border-color: var(--ds-green); }
.ds-sim .ds-label {
  font-size: 0.66rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--ds-muted); margin-bottom: 0.3rem; display: block;
}
.ds-sim .ds-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.ds-sim .ds-table th {
  text-align: left; color: var(--ds-muted); font-weight: 600; padding: 0.45rem 0.65rem;
  border-bottom: 1px solid var(--ds-border); position: sticky; top: 0; background: var(--ds-panel-2);
}
.ds-sim .ds-table td { padding: 0.45rem 0.65rem; border-bottom: 1px solid #112a1d; }
.ds-sim .ds-table tr:hover td { background: #0e2117; }
.ds-sim .ds-mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }
.ds-sim .ds-banner {
  display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.8rem;
  padding: 0.6rem 0.85rem; border-radius: 8px; margin-bottom: 0.85rem;
}
.ds-sim .ds-banner-goal { background: rgba(56,224,208,.08); border: 1px solid rgba(56,224,208,.28); color: #9beee3; }
.ds-sim .ds-banner-err { background: rgba(255,107,107,.1); border: 1px solid rgba(255,107,107,.3); color: #ffb4b4; }
.ds-sim .ds-banner-ok { background: rgba(52,211,153,.1); border: 1px solid rgba(52,211,153,.32); color: #9ff0cf; }
`

const CHART_META = {
  bar: { label: 'Bar', Icon: BarChart3 },
  line: { label: 'Line', Icon: LineChart },
  table: { label: 'Table', Icon: Table2 },
  pie: { label: 'Pie', Icon: PieChart },
}

const PIE_COLORS = ['#34d399', '#38e0d0', '#f5c451', '#7c9bff', '#ff6b6b', '#c084fc', '#fb923c', '#22d3ee']

function fmtNum(v) {
  const n = Number(v)
  if (Number.isNaN(n)) return v
  if (Number.isInteger(n)) return n.toLocaleString()
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

/* ── inline SVG bar chart driven by the engine-computed {label,value} series ── */
function BarChartView({ series }) {
  const W = 640, H = 300, padL = 48, padB = 56, padT = 16, padR = 16
  const max = Math.max(1, ...series.map(s => Number(s.value) || 0))
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const slot = innerW / series.length
  const barW = Math.min(72, slot * 0.62)
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="block">
      {/* axes */}
      <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="var(--ds-border)" strokeWidth="1" />
      <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="var(--ds-border)" strokeWidth="1" />
      {/* gridlines + y labels */}
      {[0, 0.5, 1].map((t, i) => {
        const y = padT + innerH * (1 - t)
        return (
          <g key={i}>
            <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#112a1d" strokeWidth="1" />
            <text x={padL - 6} y={y + 4} textAnchor="end" fontSize="11" fill="var(--ds-muted)" className="ds-mono">
              {fmtNum(Math.round(max * t))}
            </text>
          </g>
        )
      })}
      {series.map((s, i) => {
        const h = (Number(s.value) || 0) / max * innerH
        const x = padL + slot * i + (slot - barW) / 2
        const y = H - padB - h
        return (
          <g key={s.label}>
            <rect x={x} y={y} width={barW} height={Math.max(0, h)} rx="3" fill="var(--ds-bar)" opacity="0.92" />
            <text x={x + barW / 2} y={y - 6} textAnchor="middle" fontSize="11" fill="var(--ds-text)" className="ds-mono">
              {fmtNum(s.value)}
            </text>
            <text x={padL + slot * i + slot / 2} y={H - padB + 18} textAnchor="middle" fontSize="11" fill="var(--ds-muted)">
              {String(s.label).length > 10 ? `${String(s.label).slice(0, 9)}…` : s.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/* ── inline SVG line chart ── */
function LineChartView({ series }) {
  const W = 640, H = 300, padL = 48, padB = 56, padT = 16, padR = 16
  const max = Math.max(1, ...series.map(s => Number(s.value) || 0))
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const stepX = series.length > 1 ? innerW / (series.length - 1) : 0
  const pt = (s, i) => {
    const x = padL + (series.length > 1 ? stepX * i : innerW / 2)
    const y = padT + innerH * (1 - (Number(s.value) || 0) / max)
    return [x, y]
  }
  const path = series.map((s, i) => pt(s, i).join(',')).join(' ')
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="block">
      <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="var(--ds-border)" strokeWidth="1" />
      <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="var(--ds-border)" strokeWidth="1" />
      {[0, 0.5, 1].map((t, i) => {
        const y = padT + innerH * (1 - t)
        return (
          <g key={i}>
            <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#112a1d" strokeWidth="1" />
            <text x={padL - 6} y={y + 4} textAnchor="end" fontSize="11" fill="var(--ds-muted)" className="ds-mono">
              {fmtNum(Math.round(max * t))}
            </text>
          </g>
        )
      })}
      {series.length >= 2 && <polyline points={path} fill="none" stroke="var(--ds-green)" strokeWidth="2" />}
      {series.map((s, i) => {
        const [x, y] = pt(s, i)
        return (
          <g key={s.label}>
            <circle cx={x} cy={y} r="3.5" fill="var(--ds-green)" />
            <text x={x} y={y - 9} textAnchor="middle" fontSize="11" fill="var(--ds-text)" className="ds-mono">{fmtNum(s.value)}</text>
            <text x={x} y={H - padB + 18} textAnchor="middle" fontSize="11" fill="var(--ds-muted)">
              {String(s.label).length > 10 ? `${String(s.label).slice(0, 9)}…` : s.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/* ── inline SVG pie chart ── */
function PieChartView({ series }) {
  const total = series.reduce((a, s) => a + (Number(s.value) || 0), 0)
  const R = 120, cx = 150, cy = 150
  let angle = -Math.PI / 2
  const slices = series.map((s, i) => {
    const frac = total > 0 ? (Number(s.value) || 0) / total : 0
    const start = angle
    const end = angle + frac * Math.PI * 2
    angle = end
    const large = end - start > Math.PI ? 1 : 0
    const x1 = cx + R * Math.cos(start), y1 = cy + R * Math.sin(start)
    const x2 = cx + R * Math.cos(end), y2 = cy + R * Math.sin(end)
    const d = total > 0 && frac >= 0.999
      ? `M ${cx - R} ${cy} A ${R} ${R} 0 1 1 ${cx + R} ${cy} A ${R} ${R} 0 1 1 ${cx - R} ${cy} Z`
      : `M ${cx} ${cy} L ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} Z`
    return { d, color: PIE_COLORS[i % PIE_COLORS.length], label: s.label, value: s.value, pct: frac * 100 }
  })
  return (
    <div className="flex flex-col md:flex-row items-center gap-5">
      <svg width="300" height="300" viewBox="0 0 300 300" className="shrink-0 max-w-[300px]">
        {slices.map((sl, i) => <path key={i} d={sl.d} fill={sl.color} stroke="var(--ds-bg)" strokeWidth="2" />)}
      </svg>
      <div className="space-y-1.5 w-full">
        {slices.map((sl, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: sl.color }} />
            <span className="flex-1 truncate" style={{ color: 'var(--ds-text)' }}>{sl.label}</span>
            <span className="ds-mono" style={{ color: 'var(--ds-muted)' }}>{fmtNum(sl.value)}</span>
            <span className="ds-mono text-[11px]" style={{ color: 'var(--ds-muted)' }}>{sl.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ChartCanvas({ chartType, dimension, measure, aggregation, series }) {
  if (!series || series.length === 0) {
    return (
      <div className="p-10 text-center text-sm" style={{ color: 'var(--ds-muted)' }}>
        <BarChart3 size={26} className="mx-auto mb-2 opacity-50" />
        Pick a dimension, measure and aggregation to build the chart.
      </div>
    )
  }
  const metricLabel = aggregation === 'count'
    ? `count of rows by ${dimension}`
    : `${aggregation || 'sum'} of ${measure} by ${dimension}`
  return (
    <div>
      <div className="text-[12px] mb-2" style={{ color: 'var(--ds-muted)' }}>{metricLabel}</div>
      {chartType === 'bar' && <BarChartView series={series} />}
      {chartType === 'line' && <LineChartView series={series} />}
      {chartType === 'pie' && <PieChartView series={series} />}
      {chartType === 'table' && (
        <table className="ds-table">
          <thead><tr><th>{dimension || 'Group'}</th><th className="text-right">Value</th></tr></thead>
          <tbody>
            {series.map(s => (
              <tr key={s.label}>
                <td>{s.label}</td>
                <td className="text-right ds-mono" style={{ color: 'var(--ds-green)' }}>{fmtNum(s.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/**
 * Data Science / Analytics DASHBOARD builder. Rendered INLINE by LabRunner for
 * data-dashboard labs (simulation_type 'data-dashboard') — no new route. The
 * learner picks a dimension / measure / aggregation / filter / chart type; the
 * backend recomputes the aggregated series each action and the UI renders it as a
 * chart + result table. The fix is graded via the engine on Check Solution.
 */
export default function DataDashboardSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled,
}) {
  const slug = scenario?.slug || ''
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('chart') // chart | data | events
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await datascienceApi.getState(sessionId, slug)
      if (data?.ok === false) { setError(data.error || 'Could not load the dashboard simulator'); return }
      setState(data)
      setError('')
    } catch {
      setError('Could not load the dashboard simulator')
    }
  }, [sessionId, slug])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 25000)
    return () => clearInterval(pollRef.current)
  }, [load])

  // Optimistically apply an action then refresh from the engine (the source of
  // truth for the recomputed series). Keeps the pickers responsive.
  const fire = useCallback(async (fn) => {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const res = await fn()
      if (res?.ok === false) setError(res.error || res.message || 'Action rejected')
      await load()
    } catch {
      setError('Could not apply that change — try again')
    } finally {
      setBusy(false)
    }
  }, [busy, load])

  const dataset = state?.dataset || {}
  const dashboard = state?.dashboard || {}
  const goal = state?.goal || {}
  const summary = state?.summary || {}
  const aggregations = state?.aggregations || ['sum', 'avg', 'count', 'min', 'max']
  const chartTypes = state?.chart_types || ['bar', 'line', 'table', 'pie']
  const dimensions = dataset.dimensions || []
  const measures = dataset.measures || []
  const columns = dataset.columns || []
  const preview = dataset.preview || []
  const series = dashboard.series || []
  const chartType = dashboard.chart_type || 'table'

  // Distinct values for the currently-selected filter column (from the preview),
  // so the learner can pick a value without typing.
  const filterCol = dashboard.filter?.column || ''
  const filterValues = useMemo(() => {
    if (!filterCol) return []
    const seen = []
    for (const r of preview) {
      const v = r?.[filterCol]
      if (v != null && !seen.includes(String(v))) seen.push(String(v))
    }
    return seen
  }, [filterCol, preview])

  const objective = state?.objective || summary.objective || scenario?.description || ''

  return (
    <div className="ds-sim min-h-screen">
      <style>{SCOPED_CSS}</style>

      <div className="ds-topbar">
        <div className="flex items-center gap-3 min-w-0">
          <BarChart3 size={18} style={{ color: 'var(--ds-green)' }} />
          <span className="font-semibold text-white">Data dashboard builder</span>
          <span className="text-xs hidden sm:inline" style={{ color: 'var(--ds-muted)' }}>{state?.title || scenario?.title || slug}</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button className="ds-btn" onClick={load} disabled={busy}><RefreshCw size={13} className={busy ? 'animate-spin' : ''} /> Refresh</button>
          <button className="ds-btn" onClick={() => fire(() => datascienceApi.reset(sessionId))} disabled={busy}><RotateCcw size={13} /> Reset</button>
          <LabChromeControls
            buttonClass="ds-btn"
            onHints={onHints}
            onCheck={onCheck}
            onExtend={onExtend}
            onStop={onStop}
            onBackToTerminal={onExit}
            hintsLabel={hintsLabel || 'Hints'}
            checkDisabled={checkDisabled}
            extendDisabled={extendDisabled}
          />
        </div>
      </div>

      <div className="p-4 max-w-[1180px] mx-auto">
        {error && <div className="ds-banner ds-banner-err"><XCircle size={15} className="shrink-0 mt-0.5" /> {error}</div>}

        {/* objective banner */}
        {objective && (
          <div className="ds-banner ds-banner-goal">
            <Target size={15} className="shrink-0 mt-0.5" style={{ color: 'var(--ds-cyan)' }} />
            <span><b>Objective:</b> {objective}</span>
          </div>
        )}

        {/* KPI strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {[
            ['Dataset', dataset.name || '—', 'var(--ds-cyan)', Database],
            ['Rows', `${summary.rows_in_view ?? dataset.row_count ?? 0}/${dataset.row_count ?? '?'}`, 'var(--ds-text)', Table2],
            ['Groups', series.length, series.length ? 'var(--ds-green)' : 'var(--ds-muted)', Layers],
            ['Built', dashboard.computed ? 'Yes' : 'No', dashboard.computed ? 'var(--ds-green)' : 'var(--ds-muted)', CheckCircle2],
          ].map(([label, val, color, Icon]) => (
            <div key={label} className="ds-card p-3">
              <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--ds-muted)' }}>
                <Icon size={12} /> {label}
              </div>
              <div className="text-base font-bold mt-0.5 ds-mono truncate" style={{ color }}>{val}</div>
            </div>
          ))}
        </div>

        {/* builder controls */}
        <div className="ds-card p-4 mb-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="ds-label"><Layers size={11} className="inline mr-1" />Dimension (group by)</label>
              <select
                className="ds-select"
                value={dashboard.dimension || ''}
                disabled={busy}
                onChange={e => fire(() => datascienceApi.setDimension(sessionId, e.target.value || null))}
              >
                <option value="">— none —</option>
                {dimensions.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="ds-label"><Sigma size={11} className="inline mr-1" />Measure (numeric)</label>
              <select
                className="ds-select"
                value={dashboard.measure || ''}
                disabled={busy || dashboard.aggregation === 'count'}
                onChange={e => fire(() => datascienceApi.setMeasure(sessionId, e.target.value || null))}
              >
                <option value="">— none —</option>
                {measures.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              {dashboard.aggregation === 'count' && (
                <div className="text-[10px] mt-1" style={{ color: 'var(--ds-muted)' }}>count ignores the measure</div>
              )}
            </div>
            <div>
              <label className="ds-label"><Sigma size={11} className="inline mr-1" />Aggregation</label>
              <div className="flex flex-wrap gap-1.5">
                {aggregations.map(a => (
                  <button
                    key={a}
                    type="button"
                    disabled={busy}
                    onClick={() => fire(() => datascienceApi.setAggregation(sessionId, a))}
                    className={`ds-chip ${dashboard.aggregation === a ? 'ds-chip-active' : ''}`}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* filter + chart type row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4 pt-4 border-t" style={{ borderColor: 'var(--ds-border)' }}>
            <div>
              <label className="ds-label"><Filter size={11} className="inline mr-1" />Filter (optional)</label>
              <div className="flex flex-wrap gap-2 items-center">
                <select
                  className="ds-select !w-auto min-w-[120px]"
                  value={filterCol}
                  disabled={busy}
                  onChange={e => {
                    const col = e.target.value
                    if (!col) fire(() => datascienceApi.setFilter(sessionId, '', ''))
                    else fire(() => datascienceApi.setFilter(sessionId, col, ''))
                  }}
                >
                  <option value="">— no filter —</option>
                  {columns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                {filterCol && (
                  <>
                    <span className="ds-mono text-sm" style={{ color: 'var(--ds-muted)' }}>=</span>
                    <select
                      className="ds-select !w-auto min-w-[120px]"
                      value={dashboard.filter?.value ?? ''}
                      disabled={busy}
                      onChange={e => fire(() => datascienceApi.setFilter(sessionId, filterCol, e.target.value))}
                    >
                      <option value="">— pick value —</option>
                      {filterValues.map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                    <button
                      type="button"
                      className="ds-chip"
                      disabled={busy}
                      onClick={() => fire(() => datascienceApi.setFilter(sessionId, '', ''))}
                    >
                      <XCircle size={12} /> clear
                    </button>
                  </>
                )}
              </div>
            </div>
            <div>
              <label className="ds-label"><BarChart3 size={11} className="inline mr-1" />Chart type</label>
              <div className="flex flex-wrap gap-1.5">
                {chartTypes.map(t => {
                  const meta = CHART_META[t] || { label: t, Icon: BarChart3 }
                  const Icon = meta.Icon
                  return (
                    <button
                      key={t}
                      type="button"
                      disabled={busy}
                      onClick={() => fire(() => datascienceApi.setChartType(sessionId, t))}
                      className={`ds-chip ${chartType === t ? 'ds-chip-active' : ''}`}
                    >
                      <Icon size={12} /> {meta.label}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* tabs */}
        <div className="flex items-center gap-2 mb-3">
          {[['chart', 'Dashboard', BarChart3], ['data', 'Dataset', Database], ['events', 'Activity', History]].map(([k, label, Icon]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`ds-chip ${tab === k ? 'ds-chip-active' : ''}`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === 'chart' && (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-3">
            <div className="ds-card p-4">
              <ChartCanvas
                chartType={chartType}
                dimension={dashboard.dimension}
                measure={dashboard.measure}
                aggregation={dashboard.aggregation}
                series={series}
              />
            </div>
            {/* result table — always visible alongside the chart */}
            <div className="ds-card overflow-hidden">
              <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider border-b" style={{ color: 'var(--ds-muted)', borderColor: 'var(--ds-border)' }}>
                Result ({series.length})
              </div>
              {series.length === 0 ? (
                <div className="p-5 text-xs text-center" style={{ color: 'var(--ds-muted)' }}>
                  No result yet — finish the builder above.
                </div>
              ) : (
                <div className="max-h-[360px] overflow-y-auto">
                  <table className="ds-table">
                    <thead><tr><th>{dashboard.dimension || 'Group'}</th><th className="text-right">Value</th></tr></thead>
                    <tbody>
                      {series.map(s => (
                        <tr key={s.label}>
                          <td>{s.label}</td>
                          <td className="text-right ds-mono" style={{ color: 'var(--ds-green)' }}>{fmtNum(s.value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'data' && (
          <div className="ds-card overflow-hidden">
            <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider border-b flex items-center justify-between" style={{ color: 'var(--ds-muted)', borderColor: 'var(--ds-border)' }}>
              <span>{dataset.name || 'dataset'} — preview ({preview.length} of {dataset.row_count ?? preview.length} rows)</span>
            </div>
            {preview.length === 0 ? (
              <div className="p-6 text-sm text-center" style={{ color: 'var(--ds-muted)' }}>No data loaded.</div>
            ) : (
              <div className="max-h-[460px] overflow-auto">
                <table className="ds-table">
                  <thead>
                    <tr>
                      {columns.map(c => (
                        <th key={c}>
                          {c}
                          {dimensions.includes(c) && <span className="ml-1 text-[9px] opacity-70">dim</span>}
                          {measures.includes(c) && <span className="ml-1 text-[9px] opacity-70" style={{ color: 'var(--ds-green)' }}>num</span>}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, i) => (
                      <tr key={i}>
                        {columns.map(c => (
                          <td key={c} className={measures.includes(c) ? 'ds-mono' : ''}>
                            {row[c] != null ? String(row[c]) : ''}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {tab === 'events' && (
          <div className="ds-card p-3">
            {(state?.events || []).length === 0 ? (
              <div className="p-6 text-sm text-center" style={{ color: 'var(--ds-muted)' }}>No actions yet.</div>
            ) : (
              <div className="space-y-1.5">
                {(state.events || []).map((ev, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <CheckCircle2 size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--ds-green)' }} />
                    <span style={{ color: 'var(--ds-text)' }}>{typeof ev === 'string' ? ev : ev.message}</span>
                    {ev?.time && <span className="ds-mono ml-auto shrink-0" style={{ color: 'var(--ds-muted)' }}>{ev.time}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* hint: how grading works */}
        <div className="mt-4 text-[11px] flex items-center gap-1.5" style={{ color: 'var(--ds-muted)' }}>
          <Lightbulb size={12} className="text-[#f5c451]" />
          Build the dashboard to match the objective, then run <b>Check Solution</b> from the lab — grading re-derives the expected result from the source data.
        </div>
      </div>
    </div>
  )
}
