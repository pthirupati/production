import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bell, Gauge, Search, Server, GitBranch,
  AlertTriangle, XCircle, RefreshCw, Play, Layers,
  Compass, Settings, Plug, Plus, Trash2, ChevronUp, ChevronDown, Pencil, ChevronRight, Home, GripVertical,
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

const GRAFANA_NAV_MAP = {
  home: 'home',
  dashboards: 'dashboards',
  explore: 'explore',
  alerting: 'alerting',
  connections: 'connections',
  admin: 'administration',
}

/* ── Grafana view ── */
function GrafanaView({ state, sessionId, scenario, onReload, activeNav, grafanaChildNav }) {
  const graf = state.grafana || {}
  const [activeDash, setActiveDash] = useState(graf.dashboards?.[0]?.uid || '')
  const [sub, setSub] = useState(GRAFANA_NAV_MAP[activeNav] || 'dashboards')
  const [editLayout, setEditLayout] = useState(false)
  const [adding, setAdding] = useState(false)
  const [dragPanelId, setDragPanelId] = useState(null)
  const [dropPanelId, setDropPanelId] = useState(null)
  const [newPanel, setNewPanel] = useState({ title: 'New panel', expr: 'up', type: 'timeseries' })
  const noDataPanels = new Set(state.broken?.panels_no_data || [])
  const dash = (graf.dashboards || []).find(d => d.uid === activeDash) || graf.dashboards?.[0]
  const externalNav = activeNav != null

  useEffect(() => {
    if (activeNav) setSub(GRAFANA_NAV_MAP[activeNav] || 'dashboards')
  }, [activeNav])

  const mutatePanels = async (kind, panelId, extra = {}) => {
    if (!dash) return
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
              <div className="mon-panel-sub px-2 py-1 mb-1">Folders</div>
              {GRAFANA_FOLDERS.map((f) => (
                <button key={f.id} type="button" className="w-full text-left px-2 py-1.5 text-xs rounded hover:bg-white/5 text-[#d8def0]">
                  📁 {f.name} <span className="text-[#8a93b2]">({f.dashboards})</span>
                </button>
              ))}
            </div>
            <div>
              <div className="mon-panel-title mb-3">Dashboards</div>
              <table className="w-full text-sm">
                <thead><tr className="text-[#8a93b2] text-xs border-b border-[#262a45]">
                  <th className="text-left py-2 px-2">Name</th><th className="text-left py-2">Folder</th><th className="text-left py-2">Tags</th><th className="text-left py-2">Updated</th>
                </tr></thead>
                <tbody>
                  {GRAFANA_DASHBOARD_BROWSE.map((d) => (
                    <tr key={d.uid} className="border-b border-[#262a45]/50 hover:bg-white/5 cursor-pointer" onClick={() => setActiveDash(d.uid)}>
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
            <div className="mon-panel-title mb-3">Playlists</div>
            {GRAFANA_PLAYLISTS.map((p) => (
              <div key={p.id} className="flex justify-between py-2 border-b border-[#262a45]/50 text-sm">
                <span>{p.name}</span><span className="text-[#8a93b2]">{p.dashboards} dashboards · {p.interval}</span>
              </div>
            ))}
          </div>
        )}

        {sub === 'dashboards' && grafanaChildNav === 'Snapshots' && (
          <div className="mon-card">
            {GRAFANA_SNAPSHOTS.map((s) => (
              <div key={s.id} className="py-2 border-b border-[#262a45]/50 text-sm flex justify-between">
                <span>{s.name}</span><span className="text-[#8a93b2]">expires {s.expires}</span>
              </div>
            ))}
          </div>
        )}

        {sub === 'dashboards' && grafanaChildNav === 'Library panels' && (
          <div className="grid sm:grid-cols-2 gap-3">
            {GRAFANA_LIBRARY_PANELS.map((p) => (
              <div key={p.id} className="mon-card !p-3">
                <div className="font-medium text-sm">{p.name}</div>
                <div className="text-[10px] text-[#8a93b2] mt-1">{p.type} · {p.datasource}</div>
              </div>
            ))}
          </div>
        )}

        {sub === 'dashboards' && dash && !['Browse', 'Playlists', 'Snapshots', 'Library panels'].includes(grafanaChildNav) && (
          <>
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              {(graf.dashboards || []).map(d => (
                <button key={d.uid} onClick={() => setActiveDash(d.uid)}
                        className={`mon-tab ${d.uid === activeDash ? 'mon-tab-active' : ''}`}>{d.title}</button>
              ))}
              <span className="flex-1" />
              <button type="button" className={`mon-tab ${editLayout ? 'mon-tab-active' : ''}`}
                onClick={() => setEditLayout((e) => !e)}>
                <Pencil size={13} /> {editLayout ? 'Done editing' : 'Edit dashboard'}
              </button>
              {editLayout && (
                <>
                  <span className="text-[10px] text-[#8a93b2] hidden sm:inline">Drag panels to reorder</span>
                  <button type="button" className="mon-btn-primary !text-xs" onClick={() => setAdding(true)}>
                    <Plus size={13} /> Add panel
                  </button>
                </>
              )}
            </div>
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
function PrometheusAlertsPanel({ prom }) {
  const [openGroups, setOpenGroups] = useState(() => new Set(['instance-health']))
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

/* ── Prometheus status sub-pages ── */
function PrometheusStatusPanel({ prom, statusSub }) {
  if (statusSub === 'configuration') {
    return (
      <div className="mon-card bg-white !border-gray-200">
        <div className="px-3 py-2 text-sm font-semibold text-gray-800 border-b border-gray-100">Configuration</div>
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
            {PROMETHEUS_SERVICE_DISCOVERY.map((sd) => (
              <tr key={sd.job} className="border-t border-gray-100">
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
      <div className="grid sm:grid-cols-2 gap-3">
        {[
          ['Start time', prom.started_at || '2026-06-20 08:00:00 UTC'],
          ['Version', '2.51.0'],
          ['Head series', (prom.head_series || 124832).toLocaleString()],
          ['Retention', prom.retention || '15d'],
          ['Storage', prom.storage || 'local TSDB'],
          ['Query engine', 'PromQL'],
        ].map(([k, v]) => (
          <div key={k} className="mon-card bg-white !border-gray-200 !p-3">
            <div className="text-xs text-gray-500">{k}</div>
            <div className="text-sm font-mono text-gray-800 mt-0.5">{v}</div>
          </div>
        ))}
      </div>
    )
  }
  if (statusSub === 'rules') {
    return (
      <div className="space-y-3">
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
    <div className="mon-card !p-0 overflow-hidden bg-white !border-gray-200">
      <table className="w-full text-sm">
        <thead><tr className="bg-gray-50 text-gray-500 text-xs"><th className="px-3 py-2 text-left">Job</th><th className="px-3 py-2 text-left">Endpoint</th><th className="px-3 py-2 text-left">State</th><th className="px-3 py-2 text-left">Last scrape</th><th className="px-3 py-2 text-left">Error</th></tr></thead>
        <tbody>
          {(prom.targets || []).map((t, i) => (
            <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
              <td className="px-3 py-2 font-medium">{t.job}</td>
              <td className="px-3 py-2 font-mono text-xs">{t.scrape_url}</td>
              <td className="px-3 py-2"><span className={`text-xs font-bold ${t.health === 'down' ? 'text-red-600' : 'text-green-600'}`}>{t.health === 'down' ? 'DOWN' : 'UP'}</span></td>
              <td className="px-3 py-2 font-mono text-xs text-gray-500">{t.scrape_duration_ms}ms</td>
              <td className="px-3 py-2 text-xs text-red-600">{t.last_error || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
function PrometheusView({ state, sessionId, scenario, defaultExpr, activeNav, statusSub = 'targets' }) {
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

      {showAlerts && <PrometheusAlertsPanel prom={prom} />}

      {showStatus && <PrometheusStatusPanel prom={prom} statusSub={statusSub} />}

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
export default function MonitoringSimulator({
  sessionId, scenario, flavor = 'grafana', embedded = false,
  onExit, onStop, onHints, onCheck, onExtend, hintsLabel, checkDisabled, extendDisabled,
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
      >
        <button className={`mon-tab ${view === 'grafana' ? 'mon-tab-active' : ''}`} onClick={() => setView('grafana')}>Grafana</button>
        <button className={`mon-tab ${view === 'prometheus' ? 'mon-tab-active' : ''}`} onClick={() => setView('prometheus')}>Prometheus</button>
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
          <GrafanaView state={state} sessionId={sessionId} scenario={slug} onReload={load} activeNav={grafanaNav} grafanaChildNav={grafanaChildNav} />
        ) : (
          <PrometheusView state={state} sessionId={sessionId} scenario={slug}
                          defaultExpr={summary.targets_down ? 'up == 0' : 'up'}
                          activeNav={promNav} statusSub={promStatusSub} />
        )}
          </div>
        </div>
      </div>
    </div>
  )
}
