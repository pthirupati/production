import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bell, Gauge, Search, Server, GitBranch,
  AlertTriangle, XCircle, RefreshCw, Play, Layers,
  Compass, Settings, Plug, Plus, Trash2, ChevronUp, ChevronDown, Pencil, ChevronRight, Home, GripVertical,
  ArrowLeft, Terminal, Clock, Share2, Save, X, Copy, SlidersHorizontal,
} from 'lucide-react'
import { monitoringApi } from '../../api/monitoring'
import MonitoringLoginGate, { isMonitoringAuthenticated } from './MonitoringLoginGate'
import GrafanaLoginScreen from './GrafanaLoginScreen'
import MonitoringLabChrome from './MonitoringLabChrome'
import GrafanaExplorePanel from './GrafanaExplorePanel'
import GrafanaAlertingPanel from './GrafanaAlertingPanel'
import GrafanaConnectionsPanel from './GrafanaConnectionsPanel'
import GrafanaAdministrationPanel from './GrafanaAdministrationPanel'
import GrafanaIconSidebar from './GrafanaIconSidebar'
import PrometheusTopNav from './PrometheusTopNav'
import {
  PROMETHEUS_ALERT_GROUPS, PROMETHEUS_CONFIG_YAML, PROMETHEUS_SERVICE_DISCOVERY,
  PROM_TSDB_TOP_METRICS, PROM_TSDB_TOP_LABELS, PROMETHEUS_FLAGS,
} from '../../mockData/prometheus'
import {
  GRAFANA_FOLDERS, GRAFANA_DASHBOARD_BROWSE, GRAFANA_PLAYLISTS, GRAFANA_SNAPSHOTS, GRAFANA_LIBRARY_PANELS,
} from '../../mockData/grafana'
import '../../styles/monitoring-sim.css'
import { simShellClass } from '../../utils/simLayout'

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
function DashPanel({ panel, sessionId, scenario, dashboardUid, noData, editLayout, panelIndex, panelCount, onMutate, isDragging, isDropTarget }) {
  const [series, setSeries] = useState([])
  const [value, setValue] = useState(null)
  const [empty, setEmpty] = useState(noData)
  const [editing, setEditing] = useState(false)
  const [metaEditing, setMetaEditing] = useState(false)
  const [exprDraft, setExprDraft] = useState(panel.expr)
  const [titleDraft, setTitleDraft] = useState(panel.title)
  const [typeDraft, setTypeDraft] = useState(panel.type)
  const [saving, setSaving] = useState(false)

  useEffect(() => { setExprDraft(panel.expr); setTitleDraft(panel.title); setTypeDraft(panel.type) }, [panel.expr, panel.title, panel.type])

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
    <div
      className={`mon-card transition-shadow ${editLayout ? 'cursor-grab active:cursor-grabbing' : ''} ${isDragging ? 'opacity-50 ring-2 ring-[#f7913b]/40' : ''} ${isDropTarget ? 'ring-2 ring-[#f7913b] shadow-lg' : ''}`}
      draggable={editLayout}
      onDragStart={(e) => {
        if (!editLayout) return
        e.dataTransfer.effectAllowed = 'move'
        e.dataTransfer.setData('text/plain', panel.id)
        onMutate?.('drag-start')
      }}
      onDragOver={(e) => {
        if (!editLayout) return
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
        onMutate?.('drag-over')
      }}
      onDragLeave={() => editLayout && onMutate?.('drag-leave')}
      onDrop={(e) => {
        if (!editLayout) return
        e.preventDefault()
        onMutate?.('drop')
      }}
      onDragEnd={() => editLayout && onMutate?.('drag-end')}
    >
      <div className="flex items-center justify-between mb-1 gap-2">
        {metaEditing ? (
          <input className="mon-input flex-1 !text-xs font-semibold" value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)} />
        ) : (
          <span className="mon-panel-title flex items-center gap-1.5 min-w-0">
            {editLayout && <GripVertical size={12} className="text-[#8a93b2] shrink-0" />}
            <span className="truncate">{panel.title}</span>
          </span>
        )}
        <div className="flex items-center gap-1 shrink-0">
          <button type="button" className="mon-btn !p-1" title="Edit panel"
            onClick={() => onMutate?.('edit-panel')}><Pencil size={12} /></button>
          <button type="button" className="mon-btn !p-1" title="Inspect panel data"
            onClick={() => onMutate?.('inspect-panel')}><Search size={12} /></button>
          <button type="button" className="mon-btn !p-1" title="More panel actions"
            onClick={() => onMutate?.('duplicate-panel')}><Copy size={12} /></button>
          {editLayout && (
            <>
              <button type="button" className="mon-btn !p-1" title="Move up" disabled={panelIndex === 0}
                onClick={() => onMutate?.('reorder', { direction: 'up' })}><ChevronUp size={12} /></button>
              <button type="button" className="mon-btn !p-1" title="Move down" disabled={panelIndex >= panelCount - 1}
                onClick={() => onMutate?.('reorder', { direction: 'down' })}><ChevronDown size={12} /></button>
              <button type="button" className="mon-btn !p-1 text-[#ffb4b4]" title="Delete panel"
                onClick={() => onMutate?.('remove')}><Trash2 size={12} /></button>
              <button type="button" className="mon-btn !p-1" title="Edit title/type"
                onClick={() => setMetaEditing((m) => !m)}><Pencil size={12} /></button>
            </>
          )}
          {metaEditing ? (
            <select className="mon-input !text-[10px] !py-0.5" value={typeDraft} onChange={(e) => setTypeDraft(e.target.value)}>
              {['timeseries', 'stat', 'gauge', 'table'].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          ) : (
            <span className="mon-panel-sub uppercase">{panel.type}</span>
          )}
        </div>
      </div>
      {metaEditing && (
        <div className="flex gap-1 mb-2">
          <button type="button" className="mon-btn !text-[10px]" disabled={saving} onClick={async () => {
            setSaving(true)
            try {
              await monitoringApi.action(sessionId, 'update_panel', {
                dashboard_uid: dashboardUid, panel_id: panel.id, title: titleDraft, type: typeDraft,
              })
              setMetaEditing(false)
              onMutate?.('refresh')
            } finally { setSaving(false) }
          }}>Save panel</button>
          <button type="button" className="mon-btn !text-[10px]" onClick={() => setMetaEditing(false)}>Cancel</button>
        </div>
      )}
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
      <div className="mon-code mt-2 !text-[10px] !py-1.5 opacity-80">
        {editing ? (
          <div className="space-y-1">
            <input className="mon-input w-full font-mono !text-[10px]" value={exprDraft}
              onChange={(e) => setExprDraft(e.target.value)} />
            <div className="flex gap-1">
              <button type="button" className="mon-btn !text-[10px] !py-0.5" disabled={saving}
                onClick={async () => {
                  setSaving(true)
                  try {
                    await monitoringApi.action(sessionId, 'update_panel', {
                      dashboard_uid: dashboardUid, panel_id: panel.id, expr: exprDraft,
                    })
                    setEditing(false)
                    onMutate?.('refresh')
                  } finally { setSaving(false) }
                }}>Save query</button>
              <button type="button" className="mon-btn !text-[10px] !py-0.5" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <button type="button" className="text-left w-full hover:text-white" onClick={() => setEditing(true)} title="Edit panel query">
            {panel.expr}
          </button>
        )}
      </div>
    </div>
  )
}

const GRAFANA_TIME_RANGES = [
  'Last 5 minutes', 'Last 15 minutes', 'Last 30 minutes', 'Last 1 hour', 'Last 3 hours',
  'Last 6 hours', 'Last 12 hours', 'Last 24 hours', 'Last 2 days', 'Last 7 days',
  'Last 30 days', 'Today so far', 'This week so far', 'This month so far', 'Custom absolute range',
]

const GRAFANA_REFRESH_INTERVALS = ['Off', '5s', '10s', '30s', '1m', '5m', '15m', '30m', '1h', '1d']
const GRAFANA_PANEL_TYPES = [
  'timeseries', 'barchart', 'stat', 'gauge', 'bargauge', 'table', 'piechart', 'heatmap',
  'state-timeline', 'status-history', 'histogram', 'logs', 'node-graph', 'text', 'alert-list',
]
const GRAFANA_TRANSFORMS = [
  'Calculate field', 'Config from query', 'Convert field type', 'Extract fields', 'Filter by name',
  'Filter data by query', 'Group by', 'Join by field', 'Labels to fields', 'Limit', 'Merge',
  'Organize fields', 'Prepare time series', 'Reduce', 'Rename by regex', 'Series to rows', 'Sort by',
]
const GRAFANA_UNITS = ['none', 'percent', 'percentunit', 'bytes', 's', 'reqps', 'short', 'ops/s', 'bits/sec', 'ms']

function GrafanaTimePicker({ range, refresh, open, onToggle, onRange, onRefresh, onReload }) {
  return (
    <div className="relative">
      <button type="button" className="mon-tab flex items-center gap-1" onClick={onToggle}>
        <Clock size={13} /> {range}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 z-30 w-[420px] max-w-[90vw] mon-card shadow-2xl !p-0 overflow-hidden">
          <div className="grid grid-cols-2">
            <div className="p-3 border-r border-[#262a45]">
              <div className="mon-panel-title text-sm mb-2">Quick ranges</div>
              <div className="grid gap-1 max-h-72 overflow-y-auto">
                {GRAFANA_TIME_RANGES.map((r) => (
                  <button key={r} type="button"
                    className={`text-left px-2 py-1.5 rounded text-xs ${range === r ? 'bg-[#f7913b]/20 text-[#f7913b]' : 'text-[#d8def0] hover:bg-white/5'}`}
                    onClick={() => onRange(r)}>
                    {r}
                  </button>
                ))}
              </div>
            </div>
            <div className="p-3 space-y-3">
              <div>
                <div className="mon-panel-title text-sm mb-2">Absolute time range</div>
                <label className="block text-[10px] text-[#8a93b2] mb-1">From</label>
                <input className="mon-input w-full !text-xs mb-2" value="2026-06-28 03:00:00" readOnly />
                <label className="block text-[10px] text-[#8a93b2] mb-1">To</label>
                <input className="mon-input w-full !text-xs" value="now" readOnly />
              </div>
              <div>
                <div className="mon-panel-title text-sm mb-2">Refresh interval</div>
                <div className="flex flex-wrap gap-1">
                  {GRAFANA_REFRESH_INTERVALS.map((r) => (
                    <button key={r} type="button"
                      className={`mon-tab !text-[11px] ${refresh === r ? 'mon-tab-active' : ''}`}
                      onClick={() => onRefresh(r)}>
                      {r}
                    </button>
                  ))}
                </div>
              </div>
              <button type="button" className="mon-btn-primary w-full !justify-center" onClick={onReload}>
                <RefreshCw size={13} /> Apply time range
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function GrafanaPanelEditor({ panel, dashboardUid, sessionId, onClose, onReload }) {
  const [tab, setTab] = useState('query')
  const [draft, setDraft] = useState(() => ({
    title: panel?.title || '',
    expr: panel?.expr || 'up',
    type: panel?.type || 'timeseries',
    unit: panel?.unit || 'none',
    legend: 'Table',
    tooltip: 'All series',
    threshold: '80',
    transform: 'Reduce',
    alertName: `${panel?.title || 'Panel'} threshold`,
  }))
  const [saving, setSaving] = useState(false)

  if (!panel) return null

  const save = async () => {
    setSaving(true)
    try {
      await monitoringApi.action(sessionId, 'update_panel', {
        dashboard_uid: dashboardUid,
        panel_id: panel.id,
        title: draft.title,
        expr: draft.expr,
        type: draft.type,
        unit: draft.unit,
      })
      onReload?.()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] bg-black/70 flex items-stretch justify-center p-4">
      <div className="w-full max-w-6xl bg-[#111217] border border-[#30324a] rounded-lg shadow-2xl overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-[#30324a] flex items-center gap-3">
          <div>
            <div className="text-white font-semibold">Edit panel</div>
            <div className="text-[11px] text-[#8a93b2]">Dashboard panel editor · query, transforms, alerting, field options</div>
          </div>
          <span className="flex-1" />
          <button type="button" className="mon-btn !text-xs flex items-center gap-1" disabled={saving} onClick={save}>
            <Save size={13} /> Save
          </button>
          <button type="button" className="mon-btn !p-1.5" onClick={onClose}><X size={14} /></button>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_330px] min-h-0 flex-1">
          <div className="p-4 overflow-auto">
            <div className="mon-card mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="mon-panel-title">{draft.title || 'Untitled panel'}</div>
                <span className="mon-badge mon-badge-up">{draft.type}</span>
              </div>
              <Sparkline values={[12, 18, 14, 25, 31, 29, 38, 42, 37, 49, 46, 52]} color="#f7913b" height={130} />
            </div>
            <div className="flex gap-2 mb-3 flex-wrap">
              {[
                ['query', 'Query'],
                ['transform', 'Transform data'],
                ['alert', 'Alert'],
              ].map(([k, label]) => (
                <button key={k} type="button" className={`mon-tab ${tab === k ? 'mon-tab-active' : ''}`} onClick={() => setTab(k)}>
                  {label}
                </button>
              ))}
            </div>
            {tab === 'query' && (
              <div className="space-y-3">
                <div className="mon-card">
                  <div className="flex items-center justify-between mb-2">
                    <div className="mon-panel-title text-sm">Query A</div>
                    <span className="text-[10px] text-[#8a93b2]">Data source: Prometheus</span>
                  </div>
                  <label className="block text-[10px] text-[#8a93b2] mb-1">Legend</label>
                  <input className="mon-input w-full mb-2" value="{{instance}}" readOnly />
                  <label className="block text-[10px] text-[#8a93b2] mb-1">PromQL</label>
                  <textarea className="mon-input w-full font-mono min-h-[90px]" value={draft.expr}
                    onChange={(e) => setDraft((d) => ({ ...d, expr: e.target.value }))} />
                  <div className="grid sm:grid-cols-4 gap-2 mt-3">
                    {['rate', 'sum', 'avg', 'by label'].map((op) => <button key={op} type="button" className="mon-tab !text-[11px]">{op}</button>)}
                  </div>
                </div>
                <div className="mon-card grid sm:grid-cols-3 gap-3">
                  <label className="text-xs text-[#8a93b2]">Max data points<input className="mon-input w-full mt-1" value="1100" readOnly /></label>
                  <label className="text-xs text-[#8a93b2]">Min interval<input className="mon-input w-full mt-1" value="$__interval" readOnly /></label>
                  <label className="text-xs text-[#8a93b2]">Relative time<input className="mon-input w-full mt-1" value="" placeholder="1h" readOnly /></label>
                </div>
              </div>
            )}
            {tab === 'transform' && (
              <div className="mon-card">
                <div className="mon-panel-title text-sm mb-3">Transformations</div>
                <select className="mon-input w-full mb-3" value={draft.transform}
                  onChange={(e) => setDraft((d) => ({ ...d, transform: e.target.value }))}>
                  {GRAFANA_TRANSFORMS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <div className="grid sm:grid-cols-2 gap-2">
                  {GRAFANA_TRANSFORMS.slice(0, 8).map((t) => (
                    <button key={t} type="button" className="mon-tab !justify-start !text-[11px]">{t}</button>
                  ))}
                </div>
              </div>
            )}
            {tab === 'alert' && (
              <div className="mon-card space-y-3">
                <div className="mon-panel-title text-sm">Alert rule</div>
                <input className="mon-input w-full" value={draft.alertName}
                  onChange={(e) => setDraft((d) => ({ ...d, alertName: e.target.value }))} />
                <div className="grid sm:grid-cols-3 gap-2">
                  <select className="mon-input"><option>IS ABOVE</option><option>IS BELOW</option><option>OUTSIDE RANGE</option></select>
                  <input className="mon-input" value={draft.threshold}
                    onChange={(e) => setDraft((d) => ({ ...d, threshold: e.target.value }))} />
                  <select className="mon-input"><option>for 5m</option><option>for 10m</option><option>for 1h</option></select>
                </div>
                <textarea className="mon-input w-full min-h-[70px]" value="Summary: panel threshold exceeded\nRunbook URL: https://runbooks.fixitlab.io/monitoring" readOnly />
              </div>
            )}
          </div>
          <div className="border-l border-[#30324a] p-4 overflow-auto bg-[#181a2f]">
            <div className="mon-panel-title mb-3 flex items-center gap-2"><SlidersHorizontal size={14} /> Panel options</div>
            <div className="space-y-3">
              <label className="block text-xs text-[#8a93b2]">Title<input className="mon-input w-full mt-1" value={draft.title}
                onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))} /></label>
              <label className="block text-xs text-[#8a93b2]">Visualization
                <select className="mon-input w-full mt-1" value={draft.type}
                  onChange={(e) => setDraft((d) => ({ ...d, type: e.target.value }))}>
                  {GRAFANA_PANEL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <label className="block text-xs text-[#8a93b2]">Unit
                <select className="mon-input w-full mt-1" value={draft.unit}
                  onChange={(e) => setDraft((d) => ({ ...d, unit: e.target.value }))}>
                  {GRAFANA_UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
                </select>
              </label>
              {[
                ['Tooltip mode', draft.tooltip, ['Single', 'All series', 'Hidden']],
                ['Legend mode', draft.legend, ['List', 'Table', 'Hidden']],
                ['Color scheme', 'Classic palette', ['Classic palette', 'Green-Yellow-Red', 'Blue-Yellow-Red', 'Fixed color']],
                ['Graph style', 'Lines', ['Lines', 'Bars', 'Points']],
              ].map(([label, value, opts]) => (
                <label key={label} className="block text-xs text-[#8a93b2]">{label}
                  <select className="mon-input w-full mt-1" defaultValue={value}>
                    {opts.map((o) => <option key={o}>{o}</option>)}
                  </select>
                </label>
              ))}
              <div className="mon-card !p-3 bg-[#111217]">
                <div className="text-xs font-semibold mb-2 text-[#d8def0]">Thresholds</div>
                <div className="flex items-center gap-2">
                  <span className="w-4 h-4 rounded bg-green-500" />
                  <input className="mon-input flex-1 !py-1" value="Base" readOnly />
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className="w-4 h-4 rounded bg-red-500" />
                  <input className="mon-input flex-1 !py-1" value={draft.threshold}
                    onChange={(e) => setDraft((d) => ({ ...d, threshold: e.target.value }))} />
                </div>
              </div>
              <button type="button" className="mon-tab w-full !justify-start"><Plus size={13} /> Add field override</button>
              <button type="button" className="mon-tab w-full !justify-start"><Plus size={13} /> Add data link</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const GRAFANA_NAV_MAP = {
  home: 'home',
  dashboards: 'dashboards',
  explore: 'explore',
  alerting: 'alerting',
  connections: 'connections',
  admin: 'administration',
}

/* ── Grafana view ── */
function GrafanaView({ state, sessionId, scenario, onReload, activeNav, grafanaChildNav, setGrafanaChildNav }) {
  const graf = state.grafana || {}
  const browse = state.grafana_browse || {}
  const folders = browse.folders?.length ? browse.folders : GRAFANA_FOLDERS
  const playlists = browse.playlists?.length ? browse.playlists : GRAFANA_PLAYLISTS
  const snapshots = browse.snapshots?.length ? browse.snapshots : GRAFANA_SNAPSHOTS
  const libraryPanels = browse.library_panels?.length ? browse.library_panels : GRAFANA_LIBRARY_PANELS
  const [activeDash, setActiveDash] = useState(graf.dashboards?.[0]?.uid || '')
  const [sub, setSub] = useState(GRAFANA_NAV_MAP[activeNav] || 'dashboards')
  const [editLayout, setEditLayout] = useState(false)
  const [adding, setAdding] = useState(false)
  const [dragPanelId, setDragPanelId] = useState(null)
  const [dropPanelId, setDropPanelId] = useState(null)
  const [timeRange, setTimeRange] = useState('Last 6 hours')
  const [refreshInterval, setRefreshInterval] = useState('30s')
  const [timePickerOpen, setTimePickerOpen] = useState(false)
  const [panelEditor, setPanelEditor] = useState(null)
  const [toast, setToast] = useState('')
  const [newPanel, setNewPanel] = useState({ title: 'New panel', expr: 'up', type: 'timeseries' })
  const noDataPanels = new Set(state.broken?.panels_no_data || [])
  const dash = (graf.dashboards || []).find(d => d.uid === activeDash) || graf.dashboards?.[0]
  const externalNav = activeNav != null

  const browseDashboards = useMemo(() => {
    const fromState = (graf.dashboards || []).map((d) => ({
      uid: d.uid,
      title: d.title,
      folder: d.folder || 'General',
      tags: d.tags || ['lab'],
      updated: 'Just now',
    }))
    const stateUids = new Set(fromState.map((d) => d.uid))
    const extrasSrc = browse.browse_dashboards?.length ? browse.browse_dashboards : GRAFANA_DASHBOARD_BROWSE
    const extras = extrasSrc.filter((d) => !stateUids.has(d.uid))
    return [...fromState, ...extras]
  }, [graf.dashboards, browse.browse_dashboards])

  useEffect(() => {
    if (activeNav) setSub(GRAFANA_NAV_MAP[activeNav] || 'dashboards')
  }, [activeNav])

  const mutatePanels = async (kind, panelId, extra = {}) => {
    if (!dash) return
    const panel = (dash.panels || []).find((p) => p.id === panelId)
    if (kind === 'edit-panel' || kind === 'inspect-panel') {
      if (panel) setPanelEditor(panel)
      return
    }
    if (kind === 'duplicate-panel') {
      if (!panel) return
      await monitoringApi.action(sessionId, 'add_panel', {
        dashboard_uid: dash.uid,
        title: `${panel.title} copy`,
        expr: panel.expr,
        type: panel.type,
      })
      setToast('Panel duplicated')
      onReload?.()
      return
    }
    if (kind === 'drag-start') {
      setDragPanelId(panelId)
      return
    }
    if (kind === 'drag-over') {
      setDropPanelId(panelId)
      return
    }
    if (kind === 'drag-leave') {
      setDropPanelId((prev) => (prev === panelId ? null : prev))
      return
    }
    if (kind === 'drag-end') {
      setDragPanelId(null)
      setDropPanelId(null)
      return
    }
    if (kind === 'drop') {
      const targetId = panelId
      if (!dragPanelId || dragPanelId === targetId) {
        setDragPanelId(null)
        setDropPanelId(null)
        return
      }
      const ids = (dash.panels || []).map((p) => p.id)
      const fromIdx = ids.indexOf(dragPanelId)
      const toIdx = ids.indexOf(targetId)
      if (fromIdx < 0 || toIdx < 0) {
        setDragPanelId(null)
        setDropPanelId(null)
        return
      }
      const order = [...ids]
      order.splice(fromIdx, 1)
      order.splice(toIdx, 0, dragPanelId)
      setDragPanelId(null)
      setDropPanelId(null)
      await monitoringApi.action(sessionId, 'reorder_panels', { dashboard_uid: dash.uid, order })
      onReload?.()
      return
    }
    if (kind === 'remove') {
      await monitoringApi.action(sessionId, 'remove_panel', { dashboard_uid: dash.uid, panel_id: panelId })
    } else if (kind === 'reorder') {
      const ids = (dash.panels || []).map((p) => p.id)
      const idx = ids.indexOf(panelId)
      const swap = extra.direction === 'up' ? idx - 1 : idx + 1
      if (swap < 0 || swap >= ids.length) return
      ;[ids[idx], ids[swap]] = [ids[swap], ids[idx]]
      await monitoringApi.action(sessionId, 'reorder_panels', { dashboard_uid: dash.uid, order: ids })
    }
    onReload?.()
  }

  const addPanel = async () => {
    if (!dash) return
    await monitoringApi.action(sessionId, 'add_panel', {
      dashboard_uid: dash.uid,
      title: newPanel.title,
      expr: newPanel.expr,
      type: newPanel.type,
    })
    setAdding(false)
    setNewPanel({ title: 'New panel', expr: 'up', type: 'timeseries' })
    onReload?.()
  }

  const createDashboard = async () => {
    try {
      const res = await monitoringApi.action(sessionId, 'add_dashboard', {
        title: 'New dashboard',
        folder: 'General',
      })
      if (res?.dashboard?.uid) {
        setActiveDash(res.dashboard.uid)
        setGrafanaChildNav?.('View')
        onReload?.()
      }
    } catch {
      /* ignore */
    }
  }

  return (
    <div className={externalNav ? '' : 'grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-4'}>
      {!externalNav && (
      <div className="space-y-1">
        {[['dashboards', 'Dashboards', Gauge], ['explore', 'Explore', Compass], ['alerting', 'Alerting', Bell],
          ['connections', 'Connections', Plug], ['administration', 'Administration', Settings]].map(([k, label, Icon]) => (
          <button key={k} onClick={() => setSub(k)}
                  className={`mon-tab w-full !justify-start flex items-center gap-2 ${sub === k ? 'mon-tab-active' : ''}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>
      )}

      <div>
        {sub === 'home' && (
          <div className="mon-card">
            <div className="flex items-center gap-2 mb-3">
              <Home size={20} className="text-[#f7913b]" />
              <div className="mon-panel-title">Welcome to Grafana</div>
            </div>
            <p className="mon-panel-sub mb-4">Use the sidebar to browse dashboards, run Explore queries, review alerting rules, or manage data sources.</p>
            <div className="grid sm:grid-cols-2 gap-3">
              {[
                ['Dashboards', `${(graf.dashboards || []).length} provisioned`, Gauge],
                ['Datasources', `${(graf.datasources || []).length} configured`, Plug],
                ['Alerts', `${(graf.alert_rules || []).length} rules`, Bell],
              ].map(([label, val, Icon]) => (
                <div key={label} className="mon-card !p-3 flex items-center gap-3">
                  <Icon size={18} className="text-[#f7913b]" />
                  <div><div className="text-sm font-medium text-[#d8def0]">{label}</div><div className="mon-panel-sub">{val}</div></div>
                </div>
              ))}
            </div>
          </div>
        )}

        {sub === 'dashboards' && grafanaChildNav === 'Browse' && (
          <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-4">
            <div className="mon-card !p-2">
              <div className="flex items-center justify-between px-2 py-1 mb-1">
                <div className="mon-panel-sub">Folders</div>
                <button type="button" className="text-[10px] text-[#f7913b]" onClick={async () => {
                  await monitoringApi.createFolder(sessionId, { name: `Folder ${folders.length + 1}` })
                  onReload?.()
                }}>+ New</button>
              </div>
              {folders.map((f) => (
                <button key={f.id} type="button" className="w-full text-left px-2 py-1.5 text-xs rounded hover:bg-white/5 text-[#d8def0]">
                  📁 {f.name} <span className="text-[#8a93b2]">({f.dashboards})</span>
                </button>
              ))}
            </div>
            <div>
              <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
                <div className="mon-panel-title">Dashboards</div>
                <button type="button" className="mon-btn-primary !text-xs flex items-center gap-1" onClick={createDashboard}>
                  <Plus size={13} /> New dashboard
                </button>
              </div>
              <table className="w-full text-sm">
                <thead><tr className="text-[#8a93b2] text-xs border-b border-[#262a45]">
                  <th className="text-left py-2 px-2">Name</th><th className="text-left py-2">Folder</th><th className="text-left py-2">Tags</th><th className="text-left py-2">Updated</th>
                </tr></thead>
                <tbody>
                  {browseDashboards.map((d) => (
                    <tr key={d.uid} className="border-b border-[#262a45]/50 hover:bg-white/5 cursor-pointer" onClick={() => {
                      if ((graf.dashboards || []).some((gd) => gd.uid === d.uid)) {
                        setActiveDash(d.uid)
                        setGrafanaChildNav?.('View')
                      } else {
                        setGrafanaChildNav?.('Browse')
                      }
                    }}>
                      <td className="py-2 px-2 text-[#f7913b]">{d.title}</td>
                      <td className="py-2 text-[#8a93b2]">{d.folder}</td>
                      <td className="py-2">{d.tags.map((t) => <span key={t} className="mon-badge mon-badge-up mr-1 text-[9px]">{t}</span>)}</td>
                      <td className="py-2 text-[#8a93b2]">{d.updated}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {sub === 'dashboards' && grafanaChildNav === 'Playlists' && (
          <div className="mon-card">
            <div className="flex items-center justify-between mb-3">
              <div className="mon-panel-title">Playlists</div>
              <button type="button" className="mon-btn-primary !text-xs" onClick={async () => {
                await monitoringApi.createPlaylist(sessionId, { name: `Playlist ${playlists.length + 1}`, dashboards: 2 })
                onReload?.()
              }}>+ New playlist</button>
            </div>
            {playlists.map((p) => (
              <div key={p.id} className="flex justify-between py-2 border-b border-[#262a45]/50 text-sm">
                <span>{p.name}</span><span className="text-[#8a93b2]">{p.dashboards} dashboards · {p.interval}</span>
              </div>
            ))}
          </div>
        )}

        {sub === 'dashboards' && grafanaChildNav === 'Snapshots' && (
          <div className="mon-card">
            <div className="flex items-center justify-between mb-3">
              <div className="mon-panel-title">Snapshots</div>
              <button type="button" className="mon-btn-primary !text-xs" onClick={async () => {
                await monitoringApi.createSnapshot(sessionId, { name: `Snapshot ${new Date().toISOString().slice(0, 10)}` })
                onReload?.()
              }}>+ New snapshot</button>
            </div>
            {snapshots.map((s) => (
              <div key={s.id} className="py-2 border-b border-[#262a45]/50 text-sm flex justify-between">
                <span>{s.name}</span><span className="text-[#8a93b2]">expires {s.expires}</span>
              </div>
            ))}
          </div>
        )}

        {sub === 'dashboards' && grafanaChildNav === 'Library panels' && (
          <div>
            <div className="flex justify-end mb-3">
              <button type="button" className="mon-btn-primary !text-xs" onClick={async () => {
                await monitoringApi.createLibraryPanel(sessionId, { name: `Panel ${libraryPanels.length + 1}` })
                onReload?.()
              }}>+ New panel</button>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              {libraryPanels.map((p) => (
                <div key={p.id} className="mon-card !p-3">
                  <div className="font-medium text-sm">{p.name}</div>
                  <div className="text-[10px] text-[#8a93b2] mt-1">{p.type} · {p.datasource}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {sub === 'dashboards' && !dash && !['Browse', 'Playlists', 'Snapshots', 'Library panels'].includes(grafanaChildNav) && (
          <div className="mon-card text-center py-14">
            <Gauge size={36} className="mx-auto text-[#f7913b] mb-3 opacity-80" />
            <div className="mon-panel-title mb-2">No dashboards yet</div>
            <p className="mon-panel-sub mb-4">Create a dashboard to start building panels and visualizations.</p>
            <button type="button" className="mon-btn-primary inline-flex items-center gap-1" onClick={createDashboard}>
              <Plus size={14} /> New dashboard
            </button>
          </div>
        )}

        {sub === 'dashboards' && dash && !['Browse', 'Playlists', 'Snapshots', 'Library panels'].includes(grafanaChildNav) && (
          <>
            <div className="mon-card !p-3 mb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <button type="button" className="mon-tab flex items-center gap-1" onClick={() => { setActiveDash(''); setGrafanaChildNav?.('Browse') }}>
                  <ArrowLeft size={13} /> Back
                </button>
                <div className="min-w-0">
                  <div className="text-lg font-semibold text-[#d8def0] flex items-center gap-2">
                    {dash.title}
                    <button type="button" className="text-[#8a93b2] hover:text-[#f7913b]" title="Star dashboard">★</button>
                  </div>
                  <div className="text-[11px] text-[#8a93b2]">Folder: {dash.folder || 'General'} · UID: {dash.uid}</div>
                </div>
                <span className="flex-1" />
                <button type="button" className="mon-tab flex items-center gap-1" onClick={() => setToast('Share link copied')}>
                  <Share2 size={13} /> Share
                </button>
                <button type="button" className="mon-tab flex items-center gap-1" onClick={() => setToast('Dashboard saved')}>
                  <Save size={13} /> Save
                </button>
                <button type="button" className="mon-tab flex items-center gap-1" onClick={() => setToast('Dashboard settings opened')}>
                  <Settings size={13} /> Settings
                </button>
                <button type="button" className="mon-btn-primary !text-xs flex items-center gap-1" onClick={() => setAdding(true)}>
                  <Plus size={13} /> Add panel
                </button>
                <GrafanaTimePicker
                  range={timeRange}
                  refresh={refreshInterval}
                  open={timePickerOpen}
                  onToggle={() => setTimePickerOpen((o) => !o)}
                  onRange={(r) => { setTimeRange(r); setTimePickerOpen(false) }}
                  onRefresh={(r) => setRefreshInterval(r)}
                  onReload={() => { setTimePickerOpen(false); onReload?.() }}
                />
                <button type="button" className="mon-tab !p-2" title="Refresh dashboard" onClick={onReload}>
                  <RefreshCw size={13} />
                </button>
                <button type="button" className={`mon-tab ${editLayout ? 'mon-tab-active' : ''}`}
                  onClick={() => setEditLayout((e) => !e)}>
                  <Pencil size={13} /> {editLayout ? 'Done editing' : 'Edit'}
                </button>
              </div>
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                {(graf.dashboards || []).map(d => (
                  <button key={d.uid} onClick={() => setActiveDash(d.uid)}
                          className={`mon-tab ${d.uid === activeDash ? 'mon-tab-active' : ''}`}>{d.title}</button>
                ))}
                {editLayout && <span className="text-[10px] text-[#8a93b2]">Drag panels to reorder. Use panel menus for edit, inspect, duplicate, or delete.</span>}
              </div>
            </div>
            {toast && (
              <div className="mb-3 mon-card !p-2 flex items-center justify-between text-xs text-[#d8def0]">
                <span>{toast}</span>
                <button type="button" className="text-[#8a93b2] hover:text-white" onClick={() => setToast('')}><X size={13} /></button>
              </div>
            )}
            {adding && (
              <div className="mon-card mb-3 space-y-2">
                <p className="mon-panel-title text-sm">New panel</p>
                <input className="mon-input w-full" placeholder="Title" value={newPanel.title}
                  onChange={(e) => setNewPanel((p) => ({ ...p, title: e.target.value }))} />
                <input className="mon-input w-full font-mono text-xs" placeholder="PromQL expr" value={newPanel.expr}
                  onChange={(e) => setNewPanel((p) => ({ ...p, expr: e.target.value }))} />
                <select className="mon-input w-full" value={newPanel.type}
                  onChange={(e) => setNewPanel((p) => ({ ...p, type: e.target.value }))}>
                  {['timeseries', 'stat', 'gauge', 'table'].map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <div className="flex gap-2">
                  <button type="button" className="mon-btn-primary !text-xs" onClick={addPanel}>Create panel</button>
                  <button type="button" className="mon-btn !text-xs" onClick={() => setAdding(false)}>Cancel</button>
                </div>
              </div>
            )}
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
              {(dash.panels || []).map((p, i) => (
                <DashPanel key={`${dash.uid}-${p.id}`} panel={p} sessionId={sessionId}
                           scenario={scenario} dashboardUid={dash.uid} noData={noDataPanels.has(p.id)}
                           editLayout={editLayout} panelIndex={i} panelCount={(dash.panels || []).length}
                           isDragging={dragPanelId === p.id}
                           isDropTarget={dropPanelId === p.id && dragPanelId !== p.id}
                           onMutate={(kind, extra) => {
                             if (kind === 'refresh') { onReload?.(); return }
                             mutatePanels(kind, p.id, extra)
                           }} />
              ))}
            </div>
            <GrafanaPanelEditor
              panel={panelEditor}
              dashboardUid={dash.uid}
              sessionId={sessionId}
              onClose={() => setPanelEditor(null)}
              onReload={onReload}
            />
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

        {sub === 'connections' && <GrafanaConnectionsPanel datasources={graf.datasources || []} sessionId={sessionId} onReload={onReload} />}

        {sub === 'administration' && <GrafanaAdministrationPanel scenario={scenario} />}
      </div>
    </div>
  )
}

/* ── Prometheus alerts (classic UI) ── */
function PrometheusAlertsPanel({ prom, sessionId, onReload }) {
  const [openGroups, setOpenGroups] = useState(() => new Set(['instance-health']))
  const [busyRule, setBusyRule] = useState('')
  const groups = PROMETHEUS_ALERT_GROUPS.map((g) => ({
    ...g,
    rules: g.rules.map((r) => {
      const live = (prom.alerting_rules || []).find((lr) => lr.name === r.name)
      return live ? { ...r, state: live.state, expr: live.expr || r.expr } : r
    }),
  }))

  const toggle = (name) => setOpenGroups((prev) => {
    const next = new Set(prev)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    return next
  })

  const silence = async (rule) => {
    if (!sessionId) return
    setBusyRule(rule.name)
    try {
      await monitoringApi.action(sessionId, 'silence_alert', {
        matchers: [{ name: 'alertname', value: rule.name, isRegex: false }],
        comment: `Silenced ${rule.name} from Prometheus Alerts`,
      })
      onReload?.()
    } finally {
      setBusyRule('')
    }
  }

  const toggleRule = async (rule) => {
    if (!sessionId) return
    setBusyRule(rule.name)
    try {
      await monitoringApi.action(sessionId, 'toggle_alert_rule', { name: rule.name })
      onReload?.()
    } finally {
      setBusyRule('')
    }
  }

  return (
    <div className="space-y-2">
      {groups.map((g) => {
        const open = openGroups.has(g.name)
        const firing = g.rules.filter((r) => r.state === 'firing').length
        return (
          <div key={g.name} className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
            <button type="button" onClick={() => toggle(g.name)}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-left text-sm font-semibold text-gray-800 hover:bg-gray-50 border-b border-gray-100">
              {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <span className="font-mono">{g.name}</span>
              <span className="ml-auto text-xs font-normal text-gray-500">{g.rules.length} rules · {firing} firing</span>
            </button>
            {open && (
              <table className="w-full text-xs">
                <thead><tr className="bg-gray-50 text-gray-500">
                  <th className="px-4 py-2 text-left font-medium">State</th>
                  <th className="px-4 py-2 text-left font-medium">Alert</th>
                  <th className="px-4 py-2 text-left font-medium">Summary</th>
                  <th className="px-4 py-2 text-left font-medium">Active Since</th>
                  <th className="px-4 py-2 text-left font-medium">Actions</th>
                </tr></thead>
                <tbody>
                  {g.rules.map((r) => (
                    <tr key={r.name} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2">
                        <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          r.state === 'firing' ? 'bg-red-100 text-red-700' : r.state === 'pending' ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-700'
                        }`}>{r.state}</span>
                      </td>
                      <td className="px-4 py-2 font-mono text-gray-800">{r.name}</td>
                      <td className="px-4 py-2 text-gray-600">{r.annotations?.summary || r.expr}</td>
                      <td className="px-4 py-2 text-gray-400">{r.for || '—'}</td>
                      <td className="px-4 py-2">
                        <div className="flex gap-1">
                          <button type="button" className="px-2 py-1 rounded border border-gray-200 text-[10px] text-gray-700 hover:bg-gray-50"
                            disabled={busyRule === r.name} onClick={() => toggleRule(r)}>
                            {r.state === 'firing' ? 'Resolve' : 'Fire'}
                          </button>
                          <button type="button" className="px-2 py-1 rounded border border-amber-200 text-[10px] text-amber-700 hover:bg-amber-50"
                            disabled={busyRule === r.name} onClick={() => silence(r)}>
                            Silence
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )
      })}
    </div>
  )
}

function normalizePromTarget(t) {
  const labels = t.labels || {}
  const instance = t.instance || labels.instance || ''
  const job = t.job || labels.job || 'custom'
  return {
    ...t,
    job,
    instance,
    endpoint: t.scrape_url || (instance ? `http://${instance}/metrics` : ''),
    lastScrape: t.last_scrape || t.lastScrape || '',
    duration: t.scrape_duration_ms ?? t.scrapeDurationMs ?? '—',
    error: t.last_error || t.lastError || '',
  }
}

/* ── Prometheus status sub-pages ── */
function PrometheusStatusPanel({ prom, statusSub, sessionId, onReload }) {
  const [newTarget, setNewTarget] = useState({ job: 'node', url: 'http://localhost:9100/metrics' })
  const [newRule, setNewRule] = useState({ group: 'lab', name: '', expr: 'up == 0', for: '5m' })
  const [busy, setBusy] = useState(false)
  const [flagFilter, setFlagFilter] = useState('')
  const targets = (prom.targets || []).map(normalizePromTarget)

  const addTarget = async () => {
    if (!sessionId || !newTarget.url.trim()) return
    setBusy(true)
    try {
      await monitoringApi.action(sessionId, 'add_scrape_target', {
        job: newTarget.job.trim(),
        scrape_url: newTarget.url.trim(),
      })
      onReload?.()
    } finally {
      setBusy(false)
    }
  }

  const addRule = async () => {
    if (!sessionId || !newRule.name.trim()) return
    setBusy(true)
    try {
      await monitoringApi.action(sessionId, 'add_alert_rule', newRule)
      onReload?.()
    } finally {
      setBusy(false)
    }
  }

  const reloadConfig = async () => {
    if (!sessionId) return
    setBusy(true)
    try {
      await monitoringApi.action(sessionId, 'reload_config', {})
      onReload?.()
    } finally {
      setBusy(false)
    }
  }

  const deleteTarget = async (target) => {
    if (!sessionId) return
    setBusy(true)
    try {
      await monitoringApi.action(sessionId, 'delete_scrape_target', {
        scrape_url: target.scrape_url,
        instance: target.instance,
      })
      onReload?.()
    } finally {
      setBusy(false)
    }
  }

  if (statusSub === 'configuration') {
    return (
      <div className="mon-card bg-white !border-gray-200 !p-0">
        <div className="px-3 py-2 text-sm font-semibold text-gray-800 border-b border-gray-100 flex items-center justify-between gap-2">
          <span>Configuration</span>
          <button type="button" className="px-2 py-1 rounded border border-gray-200 text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-1"
            disabled={busy} onClick={reloadConfig}>
            <RefreshCw size={12} /> Reload
          </button>
        </div>
        <pre className="p-4 text-xs font-mono text-gray-700 overflow-x-auto whitespace-pre">{PROMETHEUS_CONFIG_YAML}</pre>
      </div>
    )
  }
  if (statusSub === 'service-discovery') {
    return (
      <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
        <table className="w-full text-sm">
          <thead><tr className="bg-gray-50 text-gray-500 text-xs">
            <th className="px-3 py-2 text-left">Job</th><th className="px-3 py-2 text-left">Discovered targets</th><th className="px-3 py-2 text-left">Labels</th>
          </tr></thead>
          <tbody>
            {[
              ...PROMETHEUS_SERVICE_DISCOVERY,
              ...Object.values(targets.reduce((acc, t) => {
                acc[t.job] = acc[t.job] || { job: t.job, discovered: 0, labels: ['job', 'instance'] }
                acc[t.job].discovered += 1
                return acc
              }, {})),
            ].map((sd, i) => (
              <tr key={`${sd.job}-${i}`} className="border-t border-gray-100">
                <td className="px-3 py-2 font-mono">{sd.job}</td>
                <td className="px-3 py-2">{sd.discovered}</td>
                <td className="px-3 py-2 font-mono text-xs text-gray-600">{(sd.labels || []).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (statusSub === 'runtime') {
    return (
      <div className="space-y-3">
        <div className="flex justify-end">
          <button type="button" className="px-3 py-1.5 rounded border border-gray-200 text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-1"
            disabled={busy} onClick={reloadConfig}>
            <RefreshCw size={12} /> Reload configuration
          </button>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            ['Start time', prom.started_at || '2026-06-20 08:00:00 UTC'],
            ['Version', prom.version || '2.51.0'],
            ['Head series', (prom.tsdb?.head_series || prom.head_series || 124832).toLocaleString()],
            ['Retention', prom.tsdb?.retention || prom.retention || '15d'],
            ['Storage', prom.storage || 'local TSDB'],
            ['WAL corruptions', prom.tsdb?.wal_corruptions ?? 0],
            ['Scrape interval', prom.scrape_interval || '15s'],
            ['Evaluation interval', prom.evaluation_interval || '15s'],
            ['Query engine', 'PromQL'],
          ].map(([k, v]) => (
            <div key={k} className="mon-card bg-white !border-gray-200 !p-3">
              <div className="text-xs text-gray-500">{k}</div>
              <div className="text-sm font-mono text-gray-800 mt-0.5">{v}</div>
            </div>
          ))}
        </div>
      </div>
    )
  }
  if (statusSub === 'tsdb') {
    const headSeries = prom.tsdb?.head_series || prom.head_series || 124832
    const cards = [
      ['Head chunks', (prom.tsdb?.head_chunks ?? Math.round(headSeries * 3.1)).toLocaleString()],
      ['Chunk count', (prom.tsdb?.chunk_count ?? Math.round(headSeries * 8.4)).toLocaleString()],
      ['Number of series', headSeries.toLocaleString()],
      ['Number of label pairs', (prom.tsdb?.label_pairs ?? 9421).toLocaleString()],
      ['Min time', prom.tsdb?.min_time || '2026-06-13T08:00:00Z'],
      ['Max time', prom.tsdb?.max_time || '2026-06-28T03:42:11Z'],
    ]
    const topByMetric = PROM_TSDB_TOP_METRICS
    const topLabels = PROM_TSDB_TOP_LABELS
    return (
      <div className="space-y-4">
        <div className="text-sm font-semibold text-gray-800">TSDB Status</div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {cards.map(([k, v]) => (
            <div key={k} className="mon-card bg-white !border-gray-200 !p-3">
              <div className="text-xs text-gray-500">{k}</div>
              <div className="text-sm font-mono text-gray-800 mt-0.5">{v}</div>
            </div>
          ))}
        </div>
        <div className="grid lg:grid-cols-2 gap-3">
          <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
            <div className="px-3 py-2 text-xs font-semibold text-gray-600 border-b">Top 10 series count by metric names</div>
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Name</th><th className="px-3 py-2 text-right">Count</th></tr></thead>
              <tbody>
                {topByMetric.map(([name, count]) => (
                  <tr key={name} className="border-t border-gray-100"><td className="px-3 py-2 font-mono text-xs">{name}</td><td className="px-3 py-2 text-right font-mono text-xs">{count.toLocaleString()}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
            <div className="px-3 py-2 text-xs font-semibold text-gray-600 border-b">Top 10 label names with value count</div>
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Label</th><th className="px-3 py-2 text-right">Values</th></tr></thead>
              <tbody>
                {topLabels.map(([name, count]) => (
                  <tr key={name} className="border-t border-gray-100"><td className="px-3 py-2 font-mono text-xs">{name}</td><td className="px-3 py-2 text-right font-mono text-xs">{count.toLocaleString()}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }
  if (statusSub === 'flags') {
    const q = flagFilter.trim().toLowerCase()
    const rows = PROMETHEUS_FLAGS.filter(([k, v]) => !q || k.toLowerCase().includes(q) || String(v).toLowerCase().includes(q))
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="text-sm font-semibold text-gray-800">Command-Line Flags</div>
          <input className="mon-input bg-white !text-gray-800 !w-64" placeholder="Filter by flag name…" value={flagFilter}
            onChange={(e) => setFlagFilter(e.target.value)} />
        </div>
        <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Flag</th><th className="px-3 py-2 text-left">Value</th></tr></thead>
            <tbody>
              {rows.map(([k, v]) => (
                <tr key={k} className="border-t border-gray-100 hover:bg-gray-50"><td className="px-3 py-2 font-mono text-xs text-gray-800">{k}</td><td className="px-3 py-2 font-mono text-xs text-gray-600">{String(v)}</td></tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={2} className="px-3 py-6 text-center text-xs text-gray-400">No flags match “{flagFilter}”.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }
  if (statusSub === 'rules') {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="text-sm font-semibold text-gray-800">Alerting rules</div>
          <button type="button" className="mon-btn-primary !text-xs flex items-center gap-1" style={{ background: '#e6522c' }}
            disabled={busy || !newRule.name.trim()} onClick={addRule}>
            <Plus size={13} /> New alert rule
          </button>
        </div>
        <div className="mon-card bg-white !border-gray-200 p-3 grid sm:grid-cols-4 gap-2">
          <input className="mon-input bg-white !text-gray-800" placeholder="Group" value={newRule.group}
            onChange={(e) => setNewRule((p) => ({ ...p, group: e.target.value }))} />
          <input className="mon-input bg-white !text-gray-800" placeholder="Alert name" value={newRule.name}
            onChange={(e) => setNewRule((p) => ({ ...p, name: e.target.value }))} />
          <input className="mon-input bg-white !text-gray-800 font-mono text-xs sm:col-span-2" placeholder="PromQL expr" value={newRule.expr}
            onChange={(e) => setNewRule((p) => ({ ...p, expr: e.target.value }))} />
        </div>
        <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
          <div className="px-3 py-2 text-xs font-semibold text-gray-600 border-b">Recording rules</div>
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Group</th><th className="px-3 py-2 text-left">Name</th><th className="px-3 py-2 text-left">Expr</th></tr></thead>
            <tbody>
              {(prom.recording_rules || []).map((r, i) => (
                <tr key={i} className="border-t border-gray-100"><td className="px-3 py-2 font-mono">{r.group}</td><td className="px-3 py-2">{r.name}</td><td className="px-3 py-2 font-mono text-xs text-gray-600">{r.expr}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
          <div className="px-3 py-2 text-xs font-semibold text-gray-600 border-b">Alerting rules</div>
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Group</th><th className="px-3 py-2 text-left">Alert</th><th className="px-3 py-2 text-left">State</th></tr></thead>
            <tbody>
              {(prom.alerting_rules || []).map((r, i) => (
                <tr key={i} className="border-t border-gray-100"><td className="px-3 py-2 font-mono">{r.group}</td><td className="px-3 py-2">{r.name}</td>
                  <td className="px-3 py-2"><span className={`text-xs font-bold ${r.state === 'firing' ? 'text-red-600' : 'text-green-600'}`}>{r.state}</span></td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }
  // targets (default)
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="text-sm font-semibold text-gray-800">Scrape targets</div>
        <button type="button" className="mon-btn-primary !text-xs flex items-center gap-1" style={{ background: '#e6522c' }}
          disabled={busy || !newTarget.url.trim()} onClick={addTarget}>
          <Plus size={13} /> Add target
        </button>
      </div>
      <div className="mon-card bg-white !border-gray-200 p-3 grid sm:grid-cols-3 gap-2">
        <input className="mon-input bg-white !text-gray-800" placeholder="Job" value={newTarget.job}
          onChange={(e) => setNewTarget((p) => ({ ...p, job: e.target.value }))} />
        <input className="mon-input bg-white !text-gray-800 font-mono text-xs sm:col-span-2" placeholder="http://host:port/metrics"
          value={newTarget.url} onChange={(e) => setNewTarget((p) => ({ ...p, url: e.target.value }))} />
      </div>
      <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
      <table className="w-full text-sm">
        <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Job</th><th className="px-3 py-2 text-left">Instance</th><th className="px-3 py-2 text-left">Endpoint</th><th className="px-3 py-2 text-left">State</th><th className="px-3 py-2 text-left">Last scrape</th><th className="px-3 py-2 text-left">Error</th><th className="px-3 py-2 text-left">Actions</th></tr></thead>
        <tbody>
          {targets.map((t, i) => (
            <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
              <td className="px-3 py-2 font-medium">
                {t.job}
                {t.job === 'vmware-guest' && (
                  <span
                    className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded font-semibold"
                    style={{ background: 'rgba(79,167,232,0.12)', color: '#4fa7e8', border: '1px solid rgba(79,167,232,0.35)' }}
                    title="Discovered from VMware vCenter in this lab session"
                  >
                    VMware
                  </span>
                )}
              </td>
              <td className="px-3 py-2 font-mono text-xs">{t.instance || '—'}</td>
              <td className="px-3 py-2 font-mono text-xs">{t.endpoint || '—'}</td>
              <td className="px-3 py-2"><span className={`text-xs font-bold ${t.health === 'down' ? 'text-red-600' : 'text-green-600'}`}>{t.health === 'down' ? 'DOWN' : 'UP'}</span></td>
              <td className="px-3 py-2 font-mono text-xs text-gray-500">{t.lastScrape || `${t.duration}ms`}</td>
              <td className="px-3 py-2 text-xs text-red-600">{t.error || ''}</td>
              <td className="px-3 py-2">
                <button type="button" className="px-2 py-1 border border-red-200 text-red-600 rounded text-[10px]"
                  disabled={busy} onClick={() => deleteTarget(t)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  )
}

function PromQueryGraph({ result }) {
  const rows = result?.data?.result || []
  if (rows.length === 0) return null
  const values = rows.slice(0, 1).map((r) => Number(r.value[1])).filter((n) => !Number.isNaN(n))
  const v = values[0] ?? 0
  const pts = Array.from({ length: 24 }, (_, i) => v * (0.85 + Math.sin(i / 3) * 0.08 + (i / 24) * 0.05))
  const W = 640, H = 120, min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1
  const path = pts.map((p, i) => `${(i / (pts.length - 1)) * W},${H - ((p - min) / span) * (H - 12) - 6}`).join(' ')
  return (
    <div className="mon-card bg-white !border-gray-200 mb-3">
      <div className="text-xs text-gray-500 mb-1 px-1">Graph</div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block">
        <polyline points={path} fill="none" stroke="#e6522c" strokeWidth="2" />
        <polyline points={`0,${H} ${path} ${W},${H}`} fill="rgba(230,82,44,0.12)" stroke="none" />
      </svg>
    </div>
  )
}

/* ── Prometheus view ── */
function PrometheusView({ state, sessionId, scenario, defaultExpr, activeNav, statusSub = 'targets', onReload }) {
  const prom = state.prometheus || {}
  const externalNav = activeNav != null
  const [sub, setSub] = useState('query')
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

  const showGraph = !externalNav || activeNav === 'graph'
  const showAlerts = externalNav && activeNav === 'alerts'
  const showStatus = externalNav && activeNav === 'status'
  const showHelp = externalNav && activeNav === 'help'

  return (
    <div>
      {!externalNav && (
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {[['query', 'Graph / PromQL', Search], ['targets', 'Targets', Server],
          ['rules', 'Rules', GitBranch], ['alertmanager', 'Alertmanager', Bell]].map(([k, label, Icon]) => (
          <button key={k} onClick={() => setSub(k)}
                  className={`mon-tab flex items-center gap-2 ${sub === k ? 'mon-tab-active' : ''}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>
      )}

      {showHelp && (
        <div className="mon-card bg-white !border-gray-200 p-4 text-sm text-gray-700">
          <p className="font-semibold mb-2">Prometheus Help</p>
          <p>Use the <b>Graph</b> tab to run PromQL queries. Check <b>Alerts</b> for firing rules and <b>Status → Targets</b> for scrape health.</p>
        </div>
      )}

      {showAlerts && <PrometheusAlertsPanel prom={prom} sessionId={sessionId} onReload={onReload} />}

      {showStatus && <PrometheusStatusPanel prom={prom} statusSub={statusSub} sessionId={sessionId} onReload={onReload} />}

      {(showGraph || (!externalNav && sub === 'query')) && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <input className="mon-input flex-1 font-mono bg-white !text-gray-800 !border-gray-300" value={expr} spellCheck={false}
                   onChange={e => setExpr(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') runQuery() }}
                   placeholder="Enter a PromQL expression…" />
            <button className="mon-btn-primary" style={{ background: '#e6522c', color: '#fff' }}
                    disabled={running} onClick={() => runQuery()}>
              {running ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />} Execute
            </button>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {SAMPLES.map(s => (
              <button key={s} className="mon-tab !text-[11px] font-mono" onClick={() => { setExpr(s); runQuery(s) }}>{s}</button>
            ))}
          </div>
          {result && result.status !== 'error' && <PromQueryGraph result={result} />}
          {result && (
            <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
              {result.status === 'error' ? (
                <div className="text-red-600 text-xs p-3 font-mono">error: {result.error}</div>
              ) : (result.data?.result || []).length === 0 ? (
                <div className="text-amber-700 text-xs p-4 flex items-center gap-2 justify-center">
                  <AlertTriangle size={14} /> Empty query result — no series match
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Series (labels)</th><th className="px-3 py-2 text-right">Value</th></tr></thead>
                  <tbody>
                    {(result.data.result).slice(0, 60).map((row, i) => {
                      const { __name__, ...labels } = row.metric
                      const lbl = Object.entries(labels).map(([k, v]) => `${k}="${v}"`).join(', ')
                      return (
                        <tr key={i} className="border-t border-gray-100">
                          <td className="px-3 py-2 font-mono text-xs">
                            <span className="text-[#e6522c]">{__name__ || ''}</span>
                            <span className="text-gray-500">{lbl ? `{${lbl}}` : ''}</span>
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-green-700">{Number(row.value[1]).toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
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

      {!externalNav && sub === 'targets' && (
        <PrometheusStatusPanel prom={prom} statusSub="targets" sessionId={sessionId} onReload={onReload} />
      )}

      {!externalNav && sub === 'rules' && (
        <PrometheusStatusPanel prom={prom} statusSub="rules" sessionId={sessionId} onReload={onReload} />
      )}

      {!externalNav && sub === 'alertmanager' && prom.alertmanager && (
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
          <div className="mon-card">
            <div className="mon-panel-title mb-2 flex items-center justify-between gap-2">
              <span>Silences</span>
              <button
                type="button"
                className="text-xs px-2 py-1 rounded bg-[#E6522C] text-white"
                onClick={async () => {
                  await monitoringApi.action(sessionId, 'create_silence', { alertname: 'NodeDown', comment: 'Lab silence' })
                  onReload?.()
                }}
              >
                Create silence
              </button>
            </div>
            {(prom.alertmanager.silences || []).length ? (
              <div className="space-y-2">
                {prom.alertmanager.silences.map((s) => (
                  <div key={s.id} className="rounded border border-[#262a45] bg-[#0d1024] p-2 text-xs">
                    <div className="flex justify-between gap-2">
                      <span className="font-mono text-[#f5c451]">{s.id}</span>
                      <span className="text-[#8a93b2]">{s.state || 'active'} · ends {s.ends_at}</span>
                    </div>
                    <div className="font-mono mt-1 text-[#d8def0]">
                      {(s.matchers || []).map((m) => `${m.name}="${m.value}"`).join(', ') || 'no matchers'}
                    </div>
                    <div className="text-[#8a93b2] mt-1 flex justify-between gap-2">
                      <span>{s.comment} · {s.created_by}</span>
                      {s.state !== 'expired' && (
                        <button
                          type="button"
                          className="text-[#ff6b6b] underline"
                          onClick={async () => {
                            await monitoringApi.action(sessionId, 'expire_silence', { id: s.id })
                            onReload?.()
                          }}
                        >
                          Expire
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#8a93b2]">No active silences. Use Create silence or Prometheus → Alerts → Silence.</p>
            )}
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
export default function MonitoringSimulator({
  sessionId, scenario, flavor = 'grafana', embedded = false,
  onExit, onStop, onHints, onCheck, onExtend, hintsLabel, checkDisabled, extendDisabled,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const [authed, setAuthed] = useState(isMonitoringAuthenticated())
  const [state, setState] = useState(null)
  const [view, setView] = useState(flavor === 'prometheus' ? 'prometheus' : 'grafana')
  const [grafanaNav, setGrafanaNav] = useState('dashboards')
  const [grafanaNavExpanded, setGrafanaNavExpanded] = useState(null)
  const [grafanaChildNav, setGrafanaChildNav] = useState('Browse')
  const [promNav, setPromNav] = useState('graph')
  const [promStatusSub, setPromStatusSub] = useState('targets')
  const [error, setError] = useState('')
  const slug = scenario?.slug || ''
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await monitoringApi.getState(sessionId, slug)
      setState(data)
      setError('')
    } catch (e) {
      setError('Could not load the monitoring console')
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
    const gateProps = {
      onAuthenticated: () => setAuthed(true),
      scenario,
      onExit,
      onStop,
      onHints,
      onCheck,
      onExtend,
      hintsLabel,
      checkDisabled,
      extendDisabled,
      embedded,
      vmwareHref,
    }
    return flavor === 'prometheus'
      ? <MonitoringLoginGate flavor={flavor} {...gateProps} />
      : <GrafanaLoginScreen {...gateProps} />
  }

  const accent = flavor === 'prometheus' ? '#e6522c' : '#f7913b'
  const product = flavor === 'prometheus' ? 'Prometheus' : 'Grafana'
  const summary = state?.summary || {}

  return (
    <div className={simShellClass(embedded)}>
      <MonitoringLabChrome
        product={product}
        accent={accent}
        subtitle={scenario?.title || slug}
        onExit={onExit}
        onStop={onStop}
        onHints={onHints}
        onCheck={onCheck}
        onExtend={onExtend}
        hintsLabel={hintsLabel}
        checkDisabled={checkDisabled}
        extendDisabled={extendDisabled}
        backLabel={simTerminalOpen ? 'Hide terminal' : 'Terminal'}
        vmwareHref={vmwareHref}
      >
        <button className={`mon-tab ${view === 'grafana' ? 'mon-tab-active' : ''}`} onClick={() => setView('grafana')}>Grafana</button>
        <button className={`mon-tab ${view === 'prometheus' ? 'mon-tab-active' : ''}`} onClick={() => setView('prometheus')}>Prometheus</button>
        {onToggleTerminal && (
          <button
            type="button"
            className={`mon-tab flex items-center gap-1 ${simTerminalOpen ? 'mon-tab-active' : ''}`}
            onClick={onToggleTerminal}
          >
            <Terminal size={13} /> Terminal
          </button>
        )}
        <button className="mon-btn" onClick={load}><RefreshCw size={13} /> Refresh</button>
      </MonitoringLabChrome>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {view === 'grafana' && (
          <GrafanaIconSidebar active={grafanaNav} onSelect={setGrafanaNav}
            expanded={grafanaNavExpanded} onToggleExpand={(k) => setGrafanaNavExpanded((p) => p === k ? null : k)}
            onChildSelect={(parent, child) => { setGrafanaNav(parent); setGrafanaChildNav(child) }} />
        )}
        <div className={`flex-1 min-h-0 flex flex-col overflow-hidden ${view === 'prometheus' ? 'bg-[#f5f5f5]' : ''}`}>
          {view === 'prometheus' && (
            <PrometheusTopNav active={promNav} onSelect={setPromNav}
              statusSub={promStatusSub} onStatusSelect={setPromStatusSub} />
          )}
          <div className="flex-1 min-h-0 overflow-auto p-4 w-full max-w-none">
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
          <GrafanaView
            state={state}
            sessionId={sessionId}
            scenario={slug}
            onReload={load}
            activeNav={grafanaNav}
            grafanaChildNav={grafanaChildNav}
            setGrafanaChildNav={setGrafanaChildNav}
          />
        ) : (
          <PrometheusView state={state} sessionId={sessionId} scenario={slug}
                          defaultExpr={summary.targets_down ? 'up == 0' : 'up'}
                          activeNav={promNav} statusSub={promStatusSub} onReload={load} />
        )}
          </div>
        </div>
      </div>
    </div>
  )
}
