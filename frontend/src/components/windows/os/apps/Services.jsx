import { useState } from 'react'
import { Play, Square, RotateCw } from 'lucide-react'
import { useOS } from '../store'
import { useCtxMenu, Dialog, Tabs } from '../ui'

export default function Services() {
  const os = useOS()
  const ctx = useCtxMenu()
  const [sel, setSel] = useState(null)
  const [props, setProps] = useState(null)
  const [sort, setSort] = useState('display')

  const svcs = [...os.services].sort((a, b) => String(a[sort]).localeCompare(String(b[sort])))
  const selected = os.services.find((s) => s.name === sel)

  const rowCtx = (s) => (e) => {
    e.preventDefault(); setSel(s.name)
    ctx.open(e.clientX, e.clientY, [
      { label: 'Start', disabled: s.status === 'Running' || s.startup === 'Disabled', onClick: () => os.startService(s.name) },
      { label: 'Stop', disabled: s.status !== 'Running', onClick: () => os.stopService(s.name) },
      { label: 'Pause', disabled: true }, { label: 'Resume', disabled: true },
      { label: 'Restart', disabled: s.status !== 'Running', onClick: () => { os.stopService(s.name); setTimeout(() => os.startService(s.name), 50) } },
      { sep: true }, { label: 'Refresh' }, { label: 'Properties', onClick: () => setProps(s) },
    ])
  }

  return (
    <div className="winos-app">
      <div className="winos-toolbar">
        <strong style={{ fontSize: 13 }}>Services</strong>
        <span style={{ flex: 1 }} />
        <button className="winos-btn" disabled={!selected || selected.status === 'Running' || selected.startup === 'Disabled'} onClick={() => os.startService(sel)}><Play size={13} /> Start</button>
        <button className="winos-btn" disabled={!selected || selected.status !== 'Running'} onClick={() => os.stopService(sel)}><Square size={13} /> Stop</button>
        <button className="winos-btn" disabled={!selected || selected.status !== 'Running'} onClick={() => { os.stopService(sel); setTimeout(() => os.startService(sel), 50) }}><RotateCw size={13} /> Restart</button>
      </div>
      <div className="winos-split">
        {selected && (
          <div style={{ width: 230, flex: 'none', borderRight: '1px solid #e2e2e2', padding: 12, fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>{selected.display}</div>
            <div style={{ color: '#555', marginBottom: 10, lineHeight: 1.4 }}>{selected.desc}</div>
            {selected.status === 'Running'
              ? <><a style={{ color: '#06c', cursor: 'default' }} onClick={() => os.stopService(sel)}>Stop the service</a><br /><a style={{ color: '#06c', cursor: 'default' }} onClick={() => { os.stopService(sel); setTimeout(() => os.startService(sel), 50) }}>Restart the service</a></>
              : <a style={{ color: '#06c', cursor: 'default' }} onClick={() => selected.startup !== 'Disabled' && os.startService(sel)}>Start the service</a>}
          </div>
        )}
        <div className="winos-main">
          <table className="winos-table">
            <thead><tr>
              <th onClick={() => setSort('display')}>Name</th><th>Description</th><th onClick={() => setSort('status')}>Status</th><th onClick={() => setSort('startup')}>Startup Type</th><th onClick={() => setSort('logon')}>Log On As</th>
            </tr></thead>
            <tbody>
              {svcs.map((s) => (
                <tr key={s.name} className={sel === s.name ? 'sel' : ''} onClick={() => setSel(s.name)} onDoubleClick={() => setProps(s)} onContextMenu={rowCtx(s)}>
                  <td>{s.display}</td>
                  <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.desc}</td>
                  <td>{s.status === 'Running' ? <span className="winos-badge ok">Running</span> : ''}</td>
                  <td>{s.startup}</td><td>{s.logon}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="winos-status"><span>{os.services.length} services</span><span>Standard / Extended</span></div>
      {props && <ServiceProps svc={props} onClose={() => setProps(null)} />}
    </div>
  )
}

function ServiceProps({ svc, onClose }) {
  const os = useOS()
  const [tab, setTab] = useState('General')
  const live = os.services.find((s) => s.name === svc.name) || svc
  const [startup, setStartup] = useState(live.startup)
  return (
    <Dialog title={`${live.display} Properties (Local Computer)`} onClose={onClose} width={460}
      footer={<><button className="winos-btn primary" onClick={() => { os.setService(svc.name, { startup }); onClose() }}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button><button className="winos-btn" onClick={() => os.setService(svc.name, { startup })}>Apply</button></>}>
      <Tabs tabs={['General', 'Log On', 'Recovery', 'Dependencies']} active={tab} onChange={setTab} />
      <div style={{ paddingTop: 12, fontSize: 12.5 }}>
        {tab === 'General' && (
          <div className="winos-grid2">
            <span style={{ color: '#666' }}>Service name:</span><span>{live.name}</span>
            <span style={{ color: '#666' }}>Display name:</span><span>{live.display}</span>
            <span style={{ color: '#666', alignSelf: 'start' }}>Description:</span><textarea className="winos-input" rows={3} readOnly value={live.desc} />
            <span style={{ color: '#666' }}>Path to executable:</span><span style={{ fontSize: 11 }}>C:\Windows\system32\svchost.exe -k netsvcs -p</span>
            <span style={{ color: '#666' }}>Startup type:</span>
            <select className="winos-input" value={startup} onChange={(e) => setStartup(e.target.value)}>
              {['Automatic (Delayed)', 'Automatic', 'Manual', 'Disabled'].map((o) => <option key={o}>{o}</option>)}
            </select>
            <span style={{ color: '#666' }}>Service status:</span><span>{live.status === 'Running' ? 'Running' : 'Stopped'}</span>
            <span /><div style={{ display: 'flex', gap: 6 }}>
              <button className="winos-btn" disabled={live.status === 'Running'} onClick={() => os.startService(live.name)}>Start</button>
              <button className="winos-btn" disabled={live.status !== 'Running'} onClick={() => os.stopService(live.name)}>Stop</button>
              <button className="winos-btn" disabled>Pause</button><button className="winos-btn" disabled>Resume</button>
            </div>
          </div>
        )}
        {tab === 'Log On' && (
          <div>
            <label style={{ display: 'block', marginBottom: 8 }}><input type="radio" name="logon" defaultChecked={live.logon === 'Local System'} /> Local System account</label>
            <label style={{ display: 'block', marginLeft: 22, marginBottom: 8 }}><input type="checkbox" /> Allow service to interact with desktop</label>
            <label style={{ display: 'block', marginBottom: 6 }}><input type="radio" name="logon" defaultChecked={live.logon !== 'Local System'} /> This account:</label>
            <div style={{ marginLeft: 22 }}>
              <input className="winos-input" defaultValue={`NT AUTHORITY\\${live.logon}`} style={{ width: 240 }} />
              <div style={{ marginTop: 6 }}>Password: <input className="winos-input" type="password" defaultValue="********" /></div>
            </div>
          </div>
        )}
        {tab === 'Recovery' && (
          <div className="winos-grid2">
            <span style={{ color: '#666' }}>First failure:</span><select className="winos-input"><option>Restart the Service</option><option>Take No Action</option><option>Run a Program</option><option>Restart the Computer</option></select>
            <span style={{ color: '#666' }}>Second failure:</span><select className="winos-input"><option>Restart the Service</option><option>Take No Action</option></select>
            <span style={{ color: '#666' }}>Subsequent failures:</span><select className="winos-input"><option>Take No Action</option><option>Restart the Service</option></select>
            <span style={{ color: '#666' }}>Reset fail count after:</span><span><input className="winos-input" defaultValue="1" style={{ width: 50 }} /> days</span>
            <span style={{ color: '#666' }}>Restart service after:</span><span><input className="winos-input" defaultValue="1" style={{ width: 50 }} /> minutes</span>
          </div>
        )}
        {tab === 'Dependencies' && (
          <div>
            <div style={{ color: '#666', marginBottom: 6 }}>This service depends on the following system components:</div>
            <div style={{ border: '1px solid #ddd', height: 90, overflow: 'auto', marginBottom: 10 }}>
              <div className="winos-tree-row">⊞ Remote Procedure Call (RPC)</div>
              <div className="winos-tree-row" style={{ paddingLeft: 24 }}>DCOM Server Process Launcher</div>
            </div>
            <div style={{ color: '#666', marginBottom: 6 }}>The following system components depend on this service:</div>
            <div style={{ border: '1px solid #ddd', height: 90, overflow: 'auto' }}>
              <div className="winos-tree-row">&lt;No dependencies&gt;</div>
            </div>
          </div>
        )}
      </div>
    </Dialog>
  )
}
