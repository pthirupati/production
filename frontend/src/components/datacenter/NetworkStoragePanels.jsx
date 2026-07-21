import { useState } from 'react'
import { Router, Terminal, HardDrive, Cable } from 'lucide-react'

/** Switch CLI terminal + port blink counters */
export function SwitchCliPanel({ network, busy, onCli, onFixProtocol }) {
  const switches = network?.switches || []
  const [switchId, setSwitchId] = useState(switches[0]?.id || '')
  const [cmd, setCmd] = useState('show interfaces')
  const [output, setOutput] = useState([])
  const sw = switches.find((s) => s.id === switchId) || switches[0]

  const run = async () => {
    if (!sw || !onCli) return
    const res = await onCli(sw.id, cmd)
    if (res?.output) setOutput(res.output)
  }

  return (
    <div className="dc-net-phase3">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Terminal size={13} /> Switch CLI</span>
        <select className="dc-input" value={sw?.id || switchId} onChange={(e) => setSwitchId(e.target.value)}>
          {switches.map((s) => (
            <option key={s.id} value={s.id}>{s.hostname} · {s.vendor} {s.os}</option>
          ))}
        </select>
      </div>
      {sw && (
        <div className="dc-muted">{sw.model} · mgmt {sw.mgmt_ip} · BGP AS {sw.protocols?.bgp?.asn}</div>
      )}
      <div className="dc-cli-row">
        <input className="dc-input dc-cli-input" value={cmd}
          onChange={(e) => setCmd(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') run() }}
          placeholder="show interfaces | help" />
        <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={run}>Run</button>
      </div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap', marginBottom: '0.4rem' }}>
        {[
          'show mpls',
          'show bgp l2vpn evpn summary',
          'mpls ip',
          'nv overlay evpn',
          'show evpn vni',
        ].map((c) => (
          <button key={c} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => setCmd(c)}>{c}</button>
        ))}
      </div>
      <div className="dc-cli-screen">
        {(output.length ? output : (sw?.cli_output || ['Type a command and press Run. Try: help'])).map((line, i) => (
          <div key={i} className="dc-cli-line">{line}</div>
        ))}
      </div>
      {sw && (
        <table className="dc-port-table mt-2">
          <thead>
            <tr><th>Port</th><th>LED</th><th>Status</th><th>Speed</th><th>VLAN</th><th>RX</th><th>TX</th><th>Err</th><th>Util</th></tr>
          </thead>
          <tbody>
            {(sw.ports || []).map((p) => (
              <tr key={p.port}>
                <td>{p.port}</td>
                <td><span className={`dc-port-led ${p.blink ? 'dc-led-green dc-led-blink' : 'dc-led-red'}`} /></td>
                <td><span className={`dc-port-badge ${p.status === 'up' ? 'dc-port-up' : 'dc-port-down'}`}>{p.status}</span></td>
                <td>{p.speed}</td>
                <td>{p.vlan ?? '—'}</td>
                <td>{p.rx_pps ?? 0}</td>
                <td>{p.tx_pps ?? 0}</td>
                <td>{p.errors ?? 0}</td>
                <td>{p.util_pct ?? 0}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="dc-drawer-label mt-2">Protocols</div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {['bgp', 'ospf', 'vlan', 'lacp', 'mpls', 'evpn'].map((p) => (
          <button key={p} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onFixProtocol?.(p)}>Restore {p.toUpperCase()}</button>
        ))}
      </div>
      {sw?.protocols && (
        <div className="dc-proto-chips">
          <span className="dc-topology-chip">BGP {sw.protocols.bgp?.status}</span>
          <span className="dc-topology-chip">OSPF {sw.protocols.ospf?.status}</span>
          <span className="dc-topology-chip">STP {sw.protocols.stp?.mode}</span>
          <span className="dc-topology-chip">VXLAN {sw.protocols.vxlan?.enabled ? 'on' : 'off'}</span>
          <span className="dc-topology-chip">EVPN {sw.protocols.evpn?.status}</span>
          <span className="dc-topology-chip">MPLS {sw.protocols.mpls?.enabled ? 'on' : 'off'}</span>
        </div>
      )}
    </div>
  )
}

/** ping / traceroute / iperf tools */
export function NetToolsPanel({ tools, busy, onPing, onTrace, onIperf }) {
  const [host, setHost] = useState('10.0.0.1')
  const [out, setOut] = useState([])
  const run = async (fn) => {
    const res = await fn()
    if (res?.output) setOut(res.output)
  }
  return (
    <div className="dc-net-phase3">
      <div className="dc-twin-title"><Router size={13} /> Traffic tools</div>
      <div className="dc-cli-row">
        <input className="dc-input dc-cli-input" value={host} onChange={(e) => setHost(e.target.value)} />
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => run(() => onPing?.(host))}>ping</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => run(() => onTrace?.(host))}>traceroute</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => run(() => onIperf?.('srv-r01-u12', 'srv-r04-u06'))}>iperf</button>
      </div>
      <div className="dc-cli-screen">
        {(out.length ? out : ['Run ping, traceroute, or iperf']).map((line, i) => (
          <div key={i} className="dc-cli-line">{line}</div>
        ))}
      </div>
      {tools?.last_iperf && (
        <div className="dc-muted mt-1">
          Last iperf: {tools.last_iperf.throughput_gbps} Gbps · retrans {tools.last_iperf.retransmits}
        </div>
      )}
    </div>
  )
}

/** Cable catalog ops: damage, label, route, replace, bend */
export function CableOpsPanel({ cables, busy, catalog, onOp }) {
  const types = (catalog || []).map((c) => c.type)
  if (!cables?.length) return <p className="dc-muted">No cables.</p>
  return (
    <div className="dc-cable-list">
      {cables.map((c) => {
        const seated = c.status === 'seated'
        const damaged = c.status === 'damaged' || c.damaged
        return (
          <div key={c.id} className={`dc-cable-row ${damaged ? 'dc-cable-loose' : seated ? 'dc-cable-ok' : 'dc-cable-loose'}`}>
            <span className={`dc-port-led ${seated && !damaged ? 'dc-led-green' : 'dc-led-red'}`} />
            <div className="dc-cable-info">
              <strong>{c.label || c.id}</strong>
              <span>
                {c.catalog_type || c.type} · {c.connector} · {c.length_m}m · bend {c.bend_radius_mm}mm · {c.tension_n}N
              </span>
              <span className="dc-cable-route">Route: {(c.route || []).join(' → ')}</span>
            </div>
            <div className="dc-cable-ops">
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                onClick={() => onOp?.('label', c.id, { label: `${c.id}-LAB` })}>Label</button>
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                onClick={() => onOp?.('route', c.id, { route: 'server-rear > tray > tor' })}>Route</button>
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                onClick={() => onOp?.('bend', c.id, { bend_radius_mm: 35, tension_n: 4 })}>Bend</button>
              <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs"
                onClick={() => onOp?.('damage', c.id)}>Damage</button>
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                onClick={() => onOp?.('repair', c.id)}>Repair</button>
              {types[0] && (
                <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                  onClick={() => onOp?.('replace', c.id, { cable_type: types.includes('Fiber-LC') ? 'Fiber-LC' : types[0] })}>
                  Replace
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** SAN/NAS/Ceph/ZFS + local bays */
export function StorageStackPanel({ storage, busy, onOp }) {
  if (!storage) return <p className="dc-muted">No storage stack.</p>
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-title"><HardDrive size={13} /> Storage stack · mode {storage.mode}</div>
      <div className="dc-drawer-label">Local bays (NVMe / SATA / SAS / EDSFF)</div>
      <table className="dc-port-table">
        <thead><tr><th>Bay</th><th>Form</th><th>Bus</th><th>Model</th><th>Size</th><th>Status</th><th /></tr></thead>
        <tbody>
          {(storage.local_bays || []).map((b) => (
            <tr key={b.id}>
              <td>{b.id}</td><td>{b.form}</td><td>{b.bus}</td><td>{b.model || '—'}</td>
              <td>{b.size_gb ? `${b.size_gb}G` : '—'}</td>
              <td><span className={`dc-port-badge ${b.status === 'online' ? 'dc-port-up' : 'dc-port-down'}`}>{b.status}</span></td>
              <td>
                {b.status === 'online' && (
                  <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('fail_bay', { bay_id: b.id })}>Fail</button>
                )}
                {b.status === 'failed' && (
                  <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('replace_bay', { bay_id: b.id })}>Replace</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="dc-storage-grid">
        <div className="dc-crac-card">
          <div className="dc-crac-id">SAN ({storage.san?.fabric})</div>
          <div className="dc-crac-zone">{storage.san?.status}</div>
          {(storage.san?.luns || []).map((l) => (
            <div key={l.id} className="dc-muted" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>{l.id} {l.size_gb}G · mapped={String(l.mapped)}</span>
              {!l.mapped && (
                <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                  onClick={() => onOp?.('map_lun', { lun_id: l.id })}>Map</button>
              )}
            </div>
          ))}
        </div>
        <div className="dc-crac-card">
          <div className="dc-crac-id">NAS</div>
          <div className="dc-crac-zone">{(storage.nas?.protocol || []).join('/')} · {storage.nas?.status}</div>
          {(storage.nas?.exports || []).map((e) => (
            <div key={e.path} className="dc-muted">{e.path} → {e.clients}</div>
          ))}
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs mt-1"
            onClick={() => onOp?.('export_nfs', { path: '/vol/lab' })}>Export NFS</button>
        </div>
        <div className="dc-crac-card">
          <div className="dc-crac-id">ZFS</div>
          {(storage.zfs?.pools || []).map((p) => (
            <div key={p.name} className="dc-muted">{p.name} {p.raid} {p.size_tb}TB · {p.health} · scrub {p.scrub}</div>
          ))}
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs mt-1"
            onClick={() => onOp?.('zfs_scrub')}>Scrub</button>
        </div>
        <div className="dc-crac-card">
          <div className="dc-crac-id">Ceph</div>
          <div className="dc-crac-zone">{storage.ceph?.cluster} · {storage.ceph?.health}</div>
          <div className="dc-muted">mons {storage.ceph?.mons} · osds {storage.ceph?.osds}</div>
          <div className="dc-muted">pools: {(storage.ceph?.pools || []).join(', ') || '—'}</div>
        </div>
        <div className="dc-crac-card">
          <div className="dc-crac-id">JBOD</div>
          <div className="dc-crac-zone">{storage.jbod?.id} · {storage.jbod?.status} · {storage.jbod?.drives} drives</div>
        </div>
      </div>
      <div className="dc-action-row mt-2">
        {['raid', 'jbod', 'san', 'nas'].map((m) => (
          <button key={m} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onOp?.('set_mode', { mode: m })}>Mode {m}</button>
        ))}
      </div>
    </div>
  )
}

export function NetworkRoomPhase3({ network, servers, busy, onSelectServer, onCli, onPing, onTrace, onIperf, onFixProtocol }) {
  return (
    <div className="dc-network-room">
      <div className="dc-net-grid">
        <SwitchCliPanel network={network} busy={busy} onCli={onCli} onFixProtocol={onFixProtocol} />
        <NetToolsPanel tools={network?.tools} busy={busy} onPing={onPing} onTrace={onTrace} onIperf={onIperf} />
      </div>
      {(network.topology || []).length > 0 && (
        <div className="dc-topology-strip">
          <span className="dc-topology-label">Uplinks:</span>
          {network.topology.map((link, i) => (
            <span key={i} className="dc-topology-chip">
              {link.from} → {link.to} ({link.speed}
              {link.latency_us != null ? ` · ${link.latency_us}µs` : ''}
              {link.util_pct != null ? ` · ${link.util_pct}%` : ''})
            </span>
          ))}
        </div>
      )}
      {(network.faults || []).length > 0 && (
        <div className="dc-objective-note">
          Active network faults: {network.faults.slice(0, 3).map((f) => f.label || f.type).join(', ')}
        </div>
      )}
      <div className="dc-muted" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Cable size={12} /> Click a connected port endpoint below to open the server twin.
      </div>
      {(network.switches || []).map((sw) => (
        <div key={sw.id} className="dc-switch-card">
          <div className="dc-switch-head">
            <Router size={14} />
            <span className="dc-switch-name">{sw.hostname}</span>
            <span className="dc-switch-loc">{sw.vendor} · {sw.rack} U{sw.u_slot}</span>
            <span className="dc-switch-model">{sw.model}</span>
          </div>
          <table className="dc-port-table">
            <thead>
              <tr><th>Port</th><th>Status</th><th>Speed</th><th>VLAN</th><th>Connected to</th></tr>
            </thead>
            <tbody>
              {(sw.ports || []).map((p) => {
                const host = servers.find((s) => s.id === p.connected_to)
                return (
                  <tr key={p.port}>
                    <td>
                      <span className={`dc-port-led inline ${p.blink ? 'dc-led-green dc-led-blink' : 'dc-led-red'}`} />
                      {' '}{p.port}
                    </td>
                    <td><span className={`dc-port-badge ${p.status === 'up' ? 'dc-port-up' : 'dc-port-down'}`}>{p.status}</span></td>
                    <td>{p.speed}</td>
                    <td>{p.vlan ?? '—'}</td>
                    <td>
                      {p.connected_to ? (
                        <button type="button" className="dc-port-link"
                          onClick={() => host && onSelectServer(p.connected_to)}>
                          {host?.hostname || p.connected_to}
                        </button>
                      ) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}
