import { useMemo, useState } from 'react'
import { ChevronRight, AlertCircle, AlertTriangle, Info, XCircle } from 'lucide-react'
import { useOS } from '../store'
import { Dialog, Tabs } from '../ui'
import { eventXml } from '../events'

const LevelIcon = ({ level }) => {
  if (level === 'Critical') return <XCircle size={14} color="#c42b1c" />
  if (level === 'Error') return <AlertCircle size={14} color="#c42b1c" />
  if (level === 'Warning') return <AlertTriangle size={14} color="#9d5d00" />
  return <Info size={14} color="#0078d4" />
}

export default function EventViewer() {
  const os = useOS()
  const [log, setLog] = useState('System')
  const [sel, setSel] = useState(0)
  const [tab, setTab] = useState('General')
  const [filter, setFilter] = useState(null)
  const [active, setActive] = useState(null) // applied filter
  const [expand, setExpand] = useState({ win: true })

  const logs = ['Application', 'Security', 'Setup', 'System']
  const events = useMemo(() => {
    let evs = log === 'Administrative Events'
      ? logs.flatMap((l) => (os.events[l] || []).map((e) => ({ ...e })))
      : (os.events[log] || [])
    if (active?.levels?.length) evs = evs.filter((e) => active.levels.includes(e.level))
    if (active?.ids) { const ids = active.ids.split(',').map((s) => s.trim()).filter(Boolean); if (ids.length) evs = evs.filter((e) => ids.includes(String(e.id))) }
    if (log === 'Administrative Events') evs = evs.filter((e) => ['Critical', 'Error', 'Warning'].includes(e.level)).sort((a, b) => b.time.localeCompare(a.time))
    return evs
  }, [log, os.events, active]) // eslint-disable-line

  const cur = events[sel] || events[0]

  return (
    <div className="winos-app">
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 240 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}>📋 Event Viewer (Local)</div>
          <div className="winos-tree-row" style={{ paddingLeft: 22 }} onClick={() => setExpand((x) => ({ ...x, cv: !x.cv }))}><ChevronRight size={12} style={{ transform: expand.cv ? 'rotate(90deg)' : '' }} />Custom Views</div>
          {expand.cv && <div className={`winos-tree-row ${log === 'Administrative Events' ? 'sel' : ''}`} style={{ paddingLeft: 44 }} onClick={() => { setLog('Administrative Events'); setSel(0) }}>Administrative Events</div>}
          <div className="winos-tree-row" style={{ paddingLeft: 22 }} onClick={() => setExpand((x) => ({ ...x, wl: !x.wl }))}><ChevronRight size={12} style={{ transform: expand.wl !== false ? 'rotate(90deg)' : '' }} />Windows Logs</div>
          {expand.wl !== false && logs.map((l) => (
            <div key={l} className={`winos-tree-row ${log === l ? 'sel' : ''}`} style={{ paddingLeft: 44 }} onClick={() => { setLog(l); setSel(0) }}>{l}</div>
          ))}
          <div className="winos-tree-row" style={{ paddingLeft: 22 }}><ChevronRight size={12} />Applications and Services Logs</div>
        </div>

        <div className="winos-main" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="winos-toolbar">
            <strong>{log}</strong><span style={{ color: '#666' }}>Number of events: {events.length}</span>
            <span style={{ flex: 1 }} />
            <button className="winos-btn" onClick={() => setFilter({ levels: ['Critical', 'Error', 'Warning', 'Information'], ids: '' })}>Filter Current Log…</button>
            {active && <button className="winos-btn" onClick={() => setActive(null)}>Clear Filter</button>}
            <button className="winos-btn" onClick={() => {
              os.clearLog(log)
              if (os.labAction) os.labAction('clear_event_log', { log })
            }} disabled={log === 'Administrative Events'}>Clear Log…</button>
          </div>
          <div style={{ flex: '1 1 55%', overflow: 'auto' }}>
            <table className="winos-table">
              <thead><tr><th>Level</th><th>Date and Time</th><th>Source</th><th>Event ID</th><th>Task Category</th></tr></thead>
              <tbody>
                {events.map((e, i) => (
                  <tr key={i} className={sel === i ? 'sel' : ''} onClick={() => setSel(i)}>
                    <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><LevelIcon level={e.level} />{e.level}</span></td>
                    <td>{e.time}</td><td>{e.src}</td><td>{e.id}</td><td>{e.task || 'None'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {cur && (
            <div style={{ flex: '1 1 45%', borderTop: '2px solid #ccc', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <Tabs tabs={['General', 'Details']} active={tab} onChange={setTab} />
              <div style={{ flex: 1, overflow: 'auto', padding: 12, fontSize: 12 }}>
                {tab === 'General' ? (
                  <>
                    <div style={{ whiteSpace: 'pre-wrap', marginBottom: 10 }}>{cur.msg}</div>
                    <div className="winos-grid2" style={{ fontSize: 11.5 }}>
                      <span style={{ color: '#666' }}>Log Name:</span><span>{cur.log}</span>
                      <span style={{ color: '#666' }}>Source:</span><span>{cur.src}</span>
                      <span style={{ color: '#666' }}>Event ID:</span><span>{cur.id}</span>
                      <span style={{ color: '#666' }}>Level:</span><span>{cur.level}</span>
                      <span style={{ color: '#666' }}>Logged:</span><span>{cur.time}</span>
                      <span style={{ color: '#666' }}>Keywords:</span><span>{cur.kw}</span>
                      <span style={{ color: '#666' }}>Computer:</span><span>{cur.computer}</span>
                    </div>
                  </>
                ) : (
                  <pre style={{ fontFamily: 'Consolas, monospace', fontSize: 11.5, whiteSpace: 'pre-wrap' }}>{eventXml(cur)}</pre>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {filter && (
        <Dialog title="Filter Current Log" onClose={() => setFilter(null)} width={480}
          footer={<><button className="winos-btn primary" onClick={() => { setActive(filter); setFilter(null); setSel(0) }}>OK</button><button className="winos-btn" onClick={() => setFilter(null)}>Cancel</button></>}>
          <div style={{ fontSize: 12.5 }}>
            <div style={{ marginBottom: 10 }}>Logged: <select className="winos-input"><option>Any time</option><option>Last hour</option><option>Last 24 hours</option><option>Last 7 days</option></select></div>
            <div style={{ marginBottom: 6, color: '#666' }}>Event level:</div>
            {['Critical', 'Warning', 'Error', 'Information', 'Verbose'].map((lv) => (
              <label key={lv} style={{ marginRight: 14 }}>
                <input type="checkbox" checked={filter.levels.includes(lv)} onChange={(e) => setFilter((f) => ({ ...f, levels: e.target.checked ? [...f.levels, lv] : f.levels.filter((x) => x !== lv) }))} /> {lv}
              </label>
            ))}
            <div style={{ marginTop: 12 }}>Includes/Excludes Event IDs:</div>
            <input className="winos-input" style={{ width: '100%', marginTop: 4 }} placeholder="e.g. 4624,4625,7036" value={filter.ids} onChange={(e) => setFilter((f) => ({ ...f, ids: e.target.value }))} />
          </div>
        </Dialog>
      )}
    </div>
  )
}
