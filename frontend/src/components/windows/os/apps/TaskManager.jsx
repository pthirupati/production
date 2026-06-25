import { useEffect, useRef, useState } from 'react'
import { useOS } from '../store'
import { useCtxMenu } from '../ui'

function useSeries(gen, len = 60) {
  const [data, setData] = useState(() => Array.from({ length: len }, gen))
  useEffect(() => {
    const t = setInterval(() => setData((d) => [...d.slice(1), gen()]), 1000)
    return () => clearInterval(t)
  }, []) // eslint-disable-line
  return data
}

function Graph({ data, color, max = 100, h = 160 }) {
  const W = 600
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * W},${h - (Math.min(v, max) / max) * (h - 4) - 2}`).join(' ')
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none" style={{ background: '#f3f8ff', border: '1px solid #d8e6f5' }}>
      {[0.25, 0.5, 0.75].map((f) => <line key={f} x1="0" y1={h * f} x2={W} y2={h * f} stroke="#dde8f2" strokeWidth="1" />)}
      <polyline points={`0,${h} ${pts} ${W},${h}`} fill={color + '22'} stroke="none" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}

export default function TaskManager({ win }) {
  const os = useOS()
  const ctx = useCtxMenu()
  const [tab, setTab] = useState('Processes')
  const [sel, setSel] = useState(null)
  const [perfSel, setPerfSel] = useState('CPU')

  const cpu = useSeries(() => 8 + Math.random() * 14)
  const mem = useSeries(() => 38 + Math.random() * 6)
  const disk = useSeries(() => Math.random() * 12)
  const net = useSeries(() => Math.random() * 30)

  const procCtx = (p) => (e) => {
    e.preventDefault(); setSel(p.pid)
    ctx.open(e.clientX, e.clientY, [
      { label: 'Expand' }, { sep: true },
      { label: 'End task', onClick: () => os.endProcess(p.pid) },
      { label: 'Set priority', sub: ['Realtime', 'High', 'Above normal', 'Normal', 'Below normal', 'Low'].map((pr) => ({ label: (p.priority === pr ? '● ' : '') + pr, onClick: () => os.setProcessPriority(p.pid, pr) })) },
      { label: 'Set affinity' }, { sep: true },
      { label: 'Open file location' }, { label: 'Search online' }, { label: 'Properties' }, { label: 'Go to details' },
    ])
  }

  const apps = os.processes.filter((p) => p.type === 'app')
  const bg = os.processes.filter((p) => p.type === 'background')

  return (
    <div className="winos-app">
      <div className="winos-tabs">
        {['Processes', 'Performance', 'App history', 'Startup', 'Users', 'Details', 'Services'].map((t) => (
          <div key={t} className={`winos-tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</div>
        ))}
      </div>

      {tab === 'Processes' && (
        <div className="winos-scroll" style={{ flex: 1 }}>
          <table className="winos-table">
            <thead><tr><th style={{ width: '46%' }}>Name</th><th style={{ textAlign: 'right' }}>CPU</th><th style={{ textAlign: 'right' }}>Memory</th><th style={{ textAlign: 'right' }}>Disk</th><th style={{ textAlign: 'right' }}>Network</th></tr></thead>
            <tbody>
              <tr><td colSpan={5} style={{ fontWeight: 600, background: '#fafafa' }}>Apps ({apps.length})</td></tr>
              {apps.map((p) => (
                <tr key={p.pid} className={sel === p.pid ? 'sel' : ''} onClick={() => setSel(p.pid)} onContextMenu={procCtx(p)}>
                  <td>📋 {p.desc}</td><td style={{ textAlign: 'right' }}>{p.cpu.toFixed(1)}%</td><td style={{ textAlign: 'right' }}>{p.mem.toFixed(1)} MB</td><td style={{ textAlign: 'right' }}>0 MB/s</td><td style={{ textAlign: 'right' }}>0 Mbps</td>
                </tr>
              ))}
              <tr><td colSpan={5} style={{ fontWeight: 600, background: '#fafafa' }}>Background processes ({bg.length})</td></tr>
              {bg.map((p) => (
                <tr key={p.pid} className={sel === p.pid ? 'sel' : ''} onClick={() => setSel(p.pid)} onContextMenu={procCtx(p)}>
                  <td>{p.desc}</td><td style={{ textAlign: 'right' }}>{p.cpu.toFixed(1)}%</td><td style={{ textAlign: 'right' }}>{p.mem.toFixed(1)} MB</td><td style={{ textAlign: 'right' }}>0 MB/s</td><td style={{ textAlign: 'right' }}>0 Mbps</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', justifyContent: 'flex-end', padding: 8 }}>
            <button className="winos-btn primary" disabled={!sel} onClick={() => { os.endProcess(sel); setSel(null) }}>End task</button>
          </div>
        </div>
      )}

      {tab === 'Performance' && (
        <div className="winos-split">
          <div className="winos-tree" style={{ width: 180 }}>
            {[['CPU', cpu, '#0078d4', `${cpu[cpu.length - 1].toFixed(0)}%  3.00 GHz`], ['Memory', mem, '#9b59b6', `${(mem[mem.length - 1] / 100 * 16).toFixed(1)}/16.0 GB`], ['Disk 0 (C: D:)', disk, '#1abc9c', `${disk[disk.length - 1].toFixed(0)}%`], ['Ethernet0', net, '#e67e22', `S: ${net[net.length - 1].toFixed(0)} R: ${(net[net.length - 1] * 2).toFixed(0)} Kbps`]].map(([name, d, color, sub]) => (
              <div key={name} className={`winos-tree-row ${perfSel === name ? 'sel' : ''}`} style={{ height: 56, flexDirection: 'column', alignItems: 'stretch', padding: 8 }} onClick={() => setPerfSel(name)}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <div style={{ width: 56, height: 30 }}><Graph data={d} color={color} h={30} /></div>
                  <div><div style={{ fontWeight: 600 }}>{String(name).split(' ')[0]}</div><div style={{ fontSize: 11, color: '#666' }}>{sub}</div></div>
                </div>
              </div>
            ))}
          </div>
          <div className="winos-main" style={{ padding: 16 }}>
            {perfSel === 'CPU' && <PerfPanel title="CPU" sub={os.computer.cpu} data={cpu} color="#0078d4" stats={[['Utilization', `${cpu[cpu.length - 1].toFixed(0)}%`], ['Speed', '3.00 GHz'], ['Processes', String(os.processes.length)], ['Threads', '1,204'], ['Handles', '52,847'], ['Up time', '2:14:35:22'], ['Sockets', '1'], ['Cores', '8'], ['Logical processors', '8'], ['Virtualization', 'Enabled'], ['L1 cache', '512 KB'], ['L2 cache', '2.0 MB'], ['L3 cache', '12.0 MB']]} />}
            {perfSel === 'Memory' && <PerfPanel title="Memory" sub="16.0 GB DDR4" data={mem} color="#9b59b6" stats={[['In use', `${(mem[mem.length - 1] / 100 * 16).toFixed(1)} GB`], ['Available', `${(16 - mem[mem.length - 1] / 100 * 16).toFixed(1)} GB`], ['Committed', '8.2/34.0 GB'], ['Cached', '5.1 GB'], ['Paged pool', '458 MB'], ['Non-paged pool', '189 MB'], ['Speed', '3200 MHz'], ['Slots used', '2 of 4'], ['Form factor', 'DIMM'], ['Hardware reserved', '83.6 MB']]} />}
            {perfSel.startsWith('Disk') && <PerfPanel title="Disk 0" sub="VMware Virtual disk" data={disk} color="#1abc9c" stats={[['Active time', `${disk[disk.length - 1].toFixed(0)}%`], ['Read speed', '2.4 MB/s'], ['Write speed', '1.1 MB/s'], ['Avg. response time', '2.4 ms'], ['Capacity', '256 GB'], ['Formatted', 'NTFS'], ['System disk', 'Yes'], ['Page file', 'Yes']]} />}
            {perfSel === 'Ethernet0' && <PerfPanel title="Ethernet0" sub="vmxnet3 Ethernet Adapter" data={net} color="#e67e22" stats={[['Send', `${net[net.length - 1].toFixed(0)} Kbps`], ['Receive', `${(net[net.length - 1] * 2).toFixed(0)} Kbps`], ['Adapter name', 'Ethernet0'], ['Connection type', 'Ethernet'], ['IPv4 address', '192.168.10.50'], ['IPv6 address', 'fe80::a1b2:c3d4:e5f6:7890'], ['DNS name', 'SERVER01.lab.local']]} />}
          </div>
        </div>
      )}

      {tab === 'Startup' && (
        <table className="winos-table"><thead><tr><th>Name</th><th>Publisher</th><th>Status</th><th>Startup impact</th></tr></thead>
          <tbody>{os.startupItems.map((i) => (
            <tr key={i.name}><td>{i.name}</td><td>{i.publisher}</td><td><span className={`winos-badge ${i.enabled ? 'ok' : 'err'}`}>{i.enabled ? 'Enabled' : 'Disabled'}</span></td>
              <td><button className="winos-btn" onClick={() => os.toggleStartup(i.name)}>{i.enabled ? 'Disable' : 'Enable'}</button> {i.impact}</td></tr>
          ))}</tbody></table>
      )}

      {tab === 'Users' && (
        <div style={{ padding: 12 }}>
          <table className="winos-table"><thead><tr><th>User</th><th>Status</th><th style={{ textAlign: 'right' }}>CPU</th><th style={{ textAlign: 'right' }}>Memory</th></tr></thead>
            <tbody><tr><td>👤 Administrator</td><td>Active</td><td style={{ textAlign: 'right' }}>{cpu[cpu.length - 1].toFixed(1)}%</td><td style={{ textAlign: 'right' }}>1.2 GB</td></tr></tbody></table>
          <div style={{ marginTop: 10, display: 'flex', gap: 8 }}><button className="winos-btn">Disconnect</button><button className="winos-btn">Sign out</button></div>
        </div>
      )}

      {tab === 'Details' && (
        <div className="winos-scroll" style={{ flex: 1 }}>
          <table className="winos-table"><thead><tr><th>Name</th><th>PID</th><th>Status</th><th>User name</th><th style={{ textAlign: 'right' }}>CPU</th><th style={{ textAlign: 'right' }}>Memory</th></tr></thead>
            <tbody>{os.processes.map((p) => (
              <tr key={p.pid} className={sel === p.pid ? 'sel' : ''} onClick={() => setSel(p.pid)} onContextMenu={procCtx(p)}>
                <td>{p.name}</td><td>{p.pid}</td><td>{p.status}</td><td>{p.user}</td><td style={{ textAlign: 'right' }}>{p.cpu.toFixed(0)}</td><td style={{ textAlign: 'right' }}>{Math.round(p.mem * 1024).toLocaleString()} K</td></tr>
            ))}</tbody></table>
        </div>
      )}

      {tab === 'Services' && (
        <div className="winos-scroll" style={{ flex: 1 }}>
          <table className="winos-table"><thead><tr><th>Name</th><th>PID</th><th>Description</th><th>Status</th><th>Group</th></tr></thead>
            <tbody>{os.services.map((s) => (
              <tr key={s.name}><td>{s.name}</td><td>{s.status === 'Running' ? 672 + (s.name.length % 4000) : ''}</td><td>{s.display}</td>
                <td><span className={`winos-badge ${s.status === 'Running' ? 'ok' : 'err'}`}>{s.status}</span></td><td>{s.logon}</td></tr>
            ))}</tbody></table>
        </div>
      )}

      {tab === 'App history' && (
        <table className="winos-table"><thead><tr><th>Name</th><th>CPU time</th><th>Network</th><th>Metered network</th><th>Tile updates</th></tr></thead>
          <tbody>{['Server Manager', 'Microsoft Edge', 'Windows Security', 'Settings'].map((n) => (
            <tr key={n}><td>{n}</td><td>0:0{Math.floor(Math.random() * 9)}:{String(Math.floor(Math.random() * 59)).padStart(2, '0')}</td><td>{(Math.random() * 50).toFixed(1)} MB</td><td>0 MB</td><td>0 MB</td></tr>
          ))}</tbody></table>
      )}
    </div>
  )
}

function PerfPanel({ title, sub, data, color, stats }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h2 style={{ fontSize: 20, fontWeight: 400, margin: 0 }}>{title}</h2>
        <span style={{ fontSize: 12, color: '#666' }}>{sub}</span>
      </div>
      <div style={{ margin: '12px 0' }}><Graph data={data} color={color} /></div>
      <div className="winos-grid2" style={{ maxWidth: 520 }}>
        {stats.map(([k, v]) => (<><span style={{ color: '#666' }}>{k}</span><strong>{v}</strong></>))}
      </div>
    </div>
  )
}
