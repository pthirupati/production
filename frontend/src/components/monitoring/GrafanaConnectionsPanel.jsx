import { useEffect, useState } from 'react'
import {
  Database, Plus, Search, CheckCircle2, XCircle, ChevronRight, ArrowLeft,
  Activity, ScrollText, Timer, BarChart3, LineChart, Layers, Cloud, Cylinder,
} from 'lucide-react'

/* ── catalog of common data source types shown under "Add data source" ── */
/* Original copy only — short, neutral descriptions of each backend's role. */
const CATALOG = [
  { type: 'Prometheus', icon: Activity, blurb: 'Time series database for metrics and PromQL alerting.' },
  { type: 'Loki', icon: ScrollText, blurb: 'Log aggregation that queries labeled log streams.' },
  { type: 'Tempo', icon: Timer, blurb: 'Distributed tracing backend for request spans.' },
  { type: 'Graphite', icon: BarChart3, blurb: 'Classic metrics store with the Graphite query language.' },
  { type: 'InfluxDB', icon: LineChart, blurb: 'Time series database queried with InfluxQL or Flux.' },
  { type: 'Elasticsearch', icon: Layers, blurb: 'Search and analytics engine for documents and logs.' },
  { type: 'MySQL', icon: Database, blurb: 'Relational database queried with SQL panels.' },
  { type: 'PostgreSQL', icon: Database, blurb: 'Relational database queried with SQL panels.' },
  { type: 'CloudWatch', icon: Cloud, blurb: 'AWS metrics and logs for cloud resources.' },
  { type: 'Azure Monitor', icon: Cylinder, blurb: 'Azure metrics, logs, and resource telemetry.' },
]

/* normalize the lab-provided status into a working/error flag */
function isError(status) {
  return String(status || '').toLowerCase() === 'error'
}

/* ── detail card for a single data source, with an echoing Test button ── */
function DatasourceDetail({ ds, onBack }) {
  const d = ds || {}
  const err = isError(d.status)
  const [tested, setTested] = useState(null)

  // reset any prior test result when the selected source changes
  useEffect(() => { setTested(null) }, [d.uid])

  const runTest = () => {
    setTested({
      ok: !err,
      text: err
        ? (d.message || 'Data source returned an error.')
        : (d.message || 'Data source is working. Query succeeded.'),
    })
  }

  return (
    <div className="space-y-3">
      <button className="mon-tab flex items-center gap-2" onClick={onBack}>
        <ArrowLeft size={14} /> Back to data sources
      </button>

      <div className="mon-card space-y-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="mon-panel-title flex items-center gap-2">
              <Database size={15} style={{ color: '#f7913b' }} /> {d.name || 'Unnamed data source'}
              {d.is_default && <span className="mon-badge mon-badge-up">default</span>}
            </div>
            <div className="mon-panel-sub uppercase mt-0.5">{d.type || 'unknown'}</div>
          </div>
          <span className={`mon-badge ${err ? 'mon-badge-down' : 'mon-badge-up'}`}>
            {err ? <XCircle size={12} /> : <CheckCircle2 size={12} />}
            {err ? 'Error' : 'Working'}
          </span>
        </div>

        <table className="mon-table">
          <tbody>
            <tr>
              <td className="text-[#8a93b2] w-40">Name</td>
              <td className="text-[#d8def0]">{d.name || '—'}</td>
            </tr>
            <tr>
              <td className="text-[#8a93b2]">Type</td>
              <td className="text-[#d8def0]">{d.type || '—'}</td>
            </tr>
            <tr>
              <td className="text-[#8a93b2]">URL</td>
              <td className="font-mono text-[#d8def0]">{d.url || '—'}</td>
            </tr>
            <tr>
              <td className="text-[#8a93b2]">UID</td>
              <td className="font-mono text-[#8a93b2]">{d.uid || '—'}</td>
            </tr>
            <tr>
              <td className="text-[#8a93b2]">Default</td>
              <td className="text-[#d8def0]">{d.is_default ? 'Yes' : 'No'}</td>
            </tr>
            <tr>
              <td className="text-[#8a93b2]">Status</td>
              <td className={err ? 'text-[#ffb4b4]' : 'text-[#56e0b0]'}>{err ? 'Error' : 'Working'}</td>
            </tr>
          </tbody>
        </table>

        {d.message && (
          <div className={err ? 'text-[#ffb4b4] text-xs' : 'mon-panel-sub'}>{d.message}</div>
        )}

        <div className="flex items-center gap-2">
          <button className="mon-btn-primary" onClick={runTest}>
            <Activity size={14} /> Test
          </button>
          <span className="mon-panel-sub">Save &amp; test connectivity for this data source.</span>
        </div>

        {tested && (
          <div className={`mon-banner ${tested.ok ? '' : 'mon-banner-err'}`}>
            {tested.ok ? <CheckCircle2 size={15} className="shrink-0" /> : <XCircle size={15} className="shrink-0" />}
            <span>{tested.text}</span>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── list of configured data sources from props ── */
function DatasourceList({ datasources, onSelect }) {
  const list = datasources || []
  if (list.length === 0) {
    return (
      <div className="mon-card text-center mon-panel-sub py-10">
        No data sources are configured for this lab scenario yet.
      </div>
    )
  }
  return (
    <div className="space-y-2">
      {list.map((d, i) => {
        const err = isError(d.status)
        return (
          <button
            key={d.uid || `${d.name}-${i}`}
            onClick={() => onSelect(d)}
            className="mon-card w-full text-left flex items-center justify-between gap-3 hover:border-[#f7913b]"
          >
            <div className="min-w-0">
              <div className="mon-panel-title flex items-center gap-2">
                <Database size={14} style={{ color: '#f7913b' }} /> {d.name || 'Unnamed data source'}
                {d.is_default && <span className="mon-badge mon-badge-up">default</span>}
              </div>
              <div className="mon-panel-sub font-mono truncate">
                {(d.type || 'unknown')} · {d.url || 'no url'}
              </div>
              {err && d.message && <div className="text-[#ffb4b4] text-xs mt-1">{d.message}</div>}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`mon-badge ${err ? 'mon-badge-down' : 'mon-badge-up'}`}>
                {err ? <XCircle size={12} /> : <CheckCircle2 size={12} />}
                {err ? 'Error' : 'Working'}
              </span>
              <ChevronRight size={16} className="text-[#8a93b2]" />
            </div>
          </button>
        )
      })}
    </div>
  )
}

/* ── read-only catalog grid for "Add data source" ── */
function AddDatasource() {
  const [selected, setSelected] = useState(null)
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mon-panel-sub">
        <Search size={14} /> Browse data source types. Connections are provisioned by the lab scenario.
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {CATALOG.map((c) => {
          const Icon = c.icon
          const active = selected === c.type
          return (
            <button
              key={c.type}
              onClick={() => setSelected(active ? null : c.type)}
              className={`mon-card text-left space-y-1 ${active ? 'border-[#f7913b]' : 'hover:border-[#f7913b]'}`}
            >
              <div className="mon-panel-title flex items-center gap-2">
                <Icon size={15} style={{ color: '#f7913b' }} /> {c.type}
              </div>
              <div className="mon-panel-sub">{c.blurb}</div>
              {active && (
                <div className="mon-panel-sub flex items-center gap-1.5 pt-1" style={{ color: '#f7913b' }}>
                  <CheckCircle2 size={12} /> Configured via lab scenario
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/**
 * GrafanaConnectionsPanel — emulates Grafana's "Connections / Data sources" area.
 * Two sub-tabs: a list of the scenario's configured data sources (with a detail
 * card + echoing Test button) and a read-only catalog for adding new types.
 * Rendered standalone or embedded; resilient to missing/empty props.
 */
export default function GrafanaConnectionsPanel({ datasources = [] }) {
  const list = Array.isArray(datasources) ? datasources : []
  const [sub, setSub] = useState('list') // list | add
  const [selected, setSelected] = useState(null)

  const switchSub = (next) => {
    setSub(next)
    setSelected(null)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <button
          className={`mon-tab flex items-center gap-2 ${sub === 'list' ? 'mon-tab-active' : ''}`}
          onClick={() => switchSub('list')}
        >
          <Database size={14} /> Data sources
        </button>
        <button
          className={`mon-tab flex items-center gap-2 ${sub === 'add' ? 'mon-tab-active' : ''}`}
          onClick={() => switchSub('add')}
        >
          <Plus size={14} /> Add data source
        </button>
      </div>

      {sub === 'list' && (
        selected
          ? <DatasourceDetail ds={selected} onBack={() => setSelected(null)} />
          : <DatasourceList datasources={list} onSelect={setSelected} />
      )}

      {sub === 'add' && <AddDatasource />}
    </div>
  )
}
