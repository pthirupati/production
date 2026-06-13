import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api/admin'
import { Activity, Container, RefreshCw, Terminal, Cpu, HardDrive, Filter } from 'lucide-react'
import toast from 'react-hot-toast'

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

  return (
    <div className="space-y-4 sm:space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
            <Activity size={22} className="text-accent-cyan" /> Monitoring
          </h1>
          <p className="text-surface-400 text-sm mt-1">
            {summary.running} running / {summary.total} containers
            {summary.lab_count != null && ` · ${summary.lab_count} labs · ${summary.system_count} system`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {['all', 'lab', 'system'].map(k => (
            <button key={k} type="button" onClick={() => setKindFilter(k)}
              className={`px-3 py-1 rounded text-xs border ${kindFilter === k ? 'border-accent-cyan text-accent-cyan' : 'border-surface-700 text-surface-400'}`}>
              {k === 'all' ? 'All' : k === 'lab' ? 'Lab' : 'System'}
            </button>
          ))}
          <button type="button" onClick={loadContainers} className="btn-secondary text-sm flex items-center gap-2">
          <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 glass-card overflow-hidden max-h-[70vh] overflow-y-auto">
          {loading ? (
            <div className="p-8 text-center text-surface-500">Loading…</div>
          ) : containers.length === 0 ? (
            <div className="p-8 text-center text-surface-500">No lab containers</div>
          ) : (
            containers.map(c => (
              <button
                key={c.full_id || c.id}
                type="button"
                onClick={() => { setSelected(c); setTab('metrics') }}
                className={`w-full text-left px-4 py-3 border-b border-surface-800/50 hover:bg-surface-800/40 ${
                  selected?.id === c.id ? 'bg-accent-cyan/10 border-l-2 border-l-accent-cyan' : ''
                }`}
              >
                <div className="flex items-center gap-2">
                  <Container size={14} className="text-surface-500" />
                  <span className="text-sm font-mono text-white truncate">{c.name}</span>
                </div>
                <p className="text-xs text-surface-500 mt-1 truncate">{c.scenario || c.session_id || c.kind}</p>
                <span className={`text-[10px] uppercase font-bold mt-1 inline-block mr-2 ${
                  c.kind === 'system' ? 'text-accent-purple' : 'text-accent-cyan'
                }`}>{c.kind}</span>
                <span className={`text-[10px] uppercase font-bold mt-1 inline-block ${
                  c.status === 'running' ? 'text-accent-green' : 'text-surface-500'
                }`}>{c.health || c.status}</span>
              </button>
            ))
          )}
        </div>

        <div className="lg:col-span-2 glass-card p-4 min-h-[320px]">
          {!selected ? (
            <div className="h-full flex items-center justify-center text-surface-500 text-sm">
              Select a container to view metrics and logs
            </div>
          ) : (
            <>
              <div className="flex flex-wrap gap-2 mb-4">
                {['metrics', 'logs'].map(t => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTab(t)}
                    className={`px-3 py-1.5 rounded-lg text-sm capitalize ${
                      tab === t ? 'bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30' : 'text-surface-400'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>

              {tab === 'metrics' && detail && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="p-3 bg-surface-900/50 rounded-lg">
                      <Cpu size={16} className="text-accent-purple mb-1" />
                      <p className="text-xs text-surface-500">Memory</p>
                      <p className="text-lg font-bold text-white">{detail.stats?.memory_percent ?? '—'}%</p>
                      <p className="text-[10px] text-surface-500">{detail.stats?.memory_usage_mb} / {detail.stats?.memory_limit_mb} MB</p>
                    </div>
                    <div className="p-3 bg-surface-900/50 rounded-lg">
                      <HardDrive size={16} className="text-accent-amber mb-1" />
                      <p className="text-xs text-surface-500">Status</p>
                      <p className="text-lg font-bold text-white capitalize">{detail.status}</p>
                    </div>
                    <div className="p-3 bg-surface-900/50 rounded-lg col-span-2 sm:col-span-1">
                      <Terminal size={16} className="text-accent-cyan mb-1" />
                      <p className="text-xs text-surface-500">Session</p>
                      <p className="text-xs font-mono text-surface-300 truncate">{detail.labels?.['fixitlab.session_id'] || '—'}</p>
                    </div>
                  </div>
                  <pre className="text-xs bg-surface-950 p-3 rounded border border-surface-800 overflow-x-auto text-surface-400">
                    {JSON.stringify(detail.labels || {}, null, 2)}
                  </pre>
                </div>
              )}

              {tab === 'logs' && (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2 items-end">
                    <label className="text-xs text-surface-500">
                      Tail
                      <select className="input-field ml-1 py-1 text-xs" value={tail} onChange={e => setTail(e.target.value)}>
                        <option value="100">100</option>
                        <option value="200">200</option>
                        <option value="500">500</option>
                      </select>
                    </label>
                    <label className="text-xs text-surface-500">
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
                      className="input-field py-1 text-xs flex-1 min-w-[120px]"
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                    />
                    <label className="flex items-center gap-1 text-xs text-surface-400">
                      <input type="checkbox" checked={live} onChange={e => setLive(e.target.checked)} /> Live
                    </label>
                    <button type="button" onClick={() => loadLogs(selected.full_id || selected.id)} className="btn-secondary text-xs flex items-center gap-1">
                      <Filter size={12} /> Apply
                    </button>
                  </div>
                  <pre className="text-[11px] leading-relaxed bg-surface-950 p-3 rounded border border-surface-800 h-[360px] overflow-auto font-mono text-surface-300">
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
