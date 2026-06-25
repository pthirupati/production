import { useState } from 'react'
import { ChevronRight, Globe, Box, Network, Settings as Cog } from 'lucide-react'
import { useOS } from '../store'
import { Dialog, Tabs } from '../ui'

// ── DNS Manager ─────────────────────────────────────────────────────────────
const DNS_RECORDS = [
  ['(same as parent folder)', 'Start of Authority (SOA)', '[42], server01.lab.local., hostmaster.lab.local.'],
  ['(same as parent folder)', 'Name Server (NS)', 'server01.lab.local.'],
  ['(same as parent folder)', 'Host (A)', '192.168.10.50'],
  ['_gc._tcp.Default-First-Site-Name._sites', 'Service Location (SRV)', '[0][100][3268] server01.lab.local.'],
  ['_kerberos._tcp', 'Service Location (SRV)', '[0][100][88] server01.lab.local.'],
  ['_ldap._tcp', 'Service Location (SRV)', '[0][100][389] server01.lab.local.'],
  ['dc01', 'Host (A)', '192.168.10.10'],
  ['server01', 'Host (A)', '192.168.10.50'],
  ['server02', 'Host (A)', '192.168.10.51'],
  ['web01', 'Host (A)', '192.168.10.60'],
  ['db01', 'Host (A)', '192.168.10.70'],
  ['mail', 'Host (A)', '192.168.10.20'],
  ['api', 'Alias (CNAME)', 'web01.lab.local.'],
  ['ftp', 'Alias (CNAME)', 'server02.lab.local.'],
  ['vpn', 'Host (A)', '192.168.10.40'],
  ['@', 'Mail Exchanger (MX)', '[10] mail.lab.local.'],
]

export function DNSManager() {
  const [sel, setSel] = useState('lab.local')
  const [expand, setExpand] = useState({ SERVER01: true, fwd: true })
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Help</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 250 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}><Globe size={13} /> DNS</div>
          <div className="winos-tree-row" style={{ paddingLeft: 22 }} onClick={() => setExpand((x) => ({ ...x, SERVER01: !x.SERVER01 }))}><ChevronRight size={12} style={{ transform: expand.SERVER01 ? 'rotate(90deg)' : '' }} />SERVER01</div>
          {expand.SERVER01 && <>
            <div className="winos-tree-row" style={{ paddingLeft: 44 }} onClick={() => setExpand((x) => ({ ...x, fwd: !x.fwd }))}><ChevronRight size={12} style={{ transform: expand.fwd ? 'rotate(90deg)' : '' }} />Forward Lookup Zones</div>
            {expand.fwd && ['_msdcs.lab.local', 'lab.local', 'lab.internal'].map((z) => (
              <div key={z} className={`winos-tree-row ${sel === z ? 'sel' : ''}`} style={{ paddingLeft: 66 }} onClick={() => setSel(z)}>{z}</div>
            ))}
            <div className="winos-tree-row" style={{ paddingLeft: 44 }}><ChevronRight size={12} />Reverse Lookup Zones</div>
            <div className="winos-tree-row" style={{ paddingLeft: 44 }}><ChevronRight size={12} />Conditional Forwarders</div>
          </>}
        </div>
        <div className="winos-main">
          <table className="winos-table">
            <thead><tr><th>Name</th><th>Type</th><th>Data</th></tr></thead>
            <tbody>{(sel === 'lab.local' ? DNS_RECORDS : [['(same as parent folder)', 'Start of Authority (SOA)', `[1], server01.lab.local.`], ['(same as parent folder)', 'Name Server (NS)', 'server01.lab.local.']]).map((r, i) => (
              <tr key={i}><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </div>
      <div className="winos-status"><span>{sel}</span><span>{sel === 'lab.local' ? DNS_RECORDS.length : 2} record(s)</span></div>
    </div>
  )
}

// ── Hyper-V Manager ──────────────────────────────────────────────────────────
const VMS = [
  { name: 'DC01', state: 'Running', cpu: 12, mem: 4096, uptime: '2.14:23:11', status: 'Operating normally' },
  { name: 'WEB01', state: 'Running', cpu: 8, mem: 2048, uptime: '2.14:23:11', status: 'Operating normally' },
  { name: 'WEB02', state: 'Running', cpu: 6, mem: 2048, uptime: '2.14:23:11', status: 'Operating normally' },
  { name: 'DB01', state: 'Running', cpu: 24, mem: 8192, uptime: '2.14:23:11', status: 'Operating normally' },
  { name: 'APP01', state: 'Running', cpu: 15, mem: 4096, uptime: '2.14:23:11', status: 'Operating normally' },
  { name: 'BACKUP01', state: 'Saved', cpu: 0, mem: 0, uptime: '', status: 'Saved state' },
  { name: 'DEV-WIN', state: 'Off', cpu: 0, mem: 0, uptime: '', status: 'Off' },
  { name: 'TEST-VM', state: 'Running', cpu: 3, mem: 1024, uptime: '0.00:45:22', status: 'Operating normally' },
  { name: 'LEGACY-APP', state: 'Paused', cpu: 0, mem: 2048, uptime: '', status: 'Paused' },
]

export function HyperV() {
  const [sel, setSel] = useState('DC01')
  const [settings, setSettings] = useState(null)
  const cur = VMS.find((v) => v.name === sel)
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Help</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 150 }}>
          <div className="winos-tree-row sel"><Box size={13} /> SERVER01</div>
        </div>
        <div className="winos-main" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflow: 'auto' }}>
            <table className="winos-table">
              <thead><tr><th>Name</th><th>State</th><th>CPU Usage</th><th>Assigned Memory</th><th>Uptime</th><th>Status</th></tr></thead>
              <tbody>{VMS.map((v) => (
                <tr key={v.name} className={sel === v.name ? 'sel' : ''} onClick={() => setSel(v.name)} onDoubleClick={() => setSettings(v)}>
                  <td>{v.name}</td>
                  <td><span className={`winos-badge ${v.state === 'Running' ? 'ok' : v.state === 'Off' ? 'err' : 'warn'}`}>{v.state}</span></td>
                  <td>{v.state === 'Running' ? `${v.cpu}%` : ''}</td><td>{v.mem ? `${v.mem} MB` : ''}</td><td>{v.uptime}</td><td>{v.status}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {cur && (
            <div style={{ borderTop: '2px solid #ccc', padding: 12, fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>{cur.name}</div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="winos-btn">Connect</button>
                <button className="winos-btn" onClick={() => setSettings(cur)}>Settings…</button>
                <button className="winos-btn" disabled={cur.state === 'Running'}>Start</button>
                <button className="winos-btn" disabled={cur.state !== 'Running'}>Turn Off…</button>
                <button className="winos-btn">Checkpoint</button>
              </div>
            </div>
          )}
        </div>
      </div>
      {settings && <VMSettings vm={settings} onClose={() => setSettings(null)} />}
    </div>
  )
}

function VMSettings({ vm, onClose }) {
  const [tab, setTab] = useState('Memory')
  return (
    <Dialog title={`Settings for ${vm.name} on SERVER01`} onClose={onClose} width={580}
      footer={<><button className="winos-btn primary" onClick={onClose}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button><button className="winos-btn">Apply</button></>}>
      <div style={{ display: 'flex', gap: 12, minHeight: 280 }}>
        <div style={{ width: 170, flex: 'none', fontSize: 12, borderRight: '1px solid #eee' }}>
          <div style={{ fontWeight: 600, padding: '4px 6px' }}>Hardware</div>
          {['Add Hardware', 'Firmware', 'Security', 'Memory', 'Processor', 'SCSI Controller', 'Network Adapter'].map((h) => (
            <div key={h} className={`winos-tree-row ${tab === h ? 'sel' : ''}`} style={{ paddingLeft: 16 }} onClick={() => setTab(h)}>{h}</div>
          ))}
          <div style={{ fontWeight: 600, padding: '4px 6px' }}>Management</div>
          {['Name', 'Integration Services', 'Checkpoints', 'Automatic Start Action', 'Automatic Stop Action'].map((h) => (
            <div key={h} className={`winos-tree-row ${tab === h ? 'sel' : ''}`} style={{ paddingLeft: 16 }} onClick={() => setTab(h)}>{h}</div>
          ))}
        </div>
        <div style={{ flex: 1, fontSize: 12.5 }}>
          {tab === 'Memory' && <div className="winos-grid2">
            <span>RAM:</span><span><input className="winos-input" defaultValue={vm.mem || 2048} style={{ width: 90 }} /> MB</span>
            <span>Dynamic Memory:</span><label><input type="checkbox" /> Enable Dynamic Memory</label>
            <span>Minimum RAM:</span><span><input className="winos-input" defaultValue={512} style={{ width: 90 }} /> MB</span>
            <span>Maximum RAM:</span><span><input className="winos-input" defaultValue={1048576} style={{ width: 110 }} /> MB</span>
          </div>}
          {tab === 'Processor' && <div className="winos-grid2">
            <span>Number of virtual processors:</span><input className="winos-input" type="number" defaultValue={2} min={1} max={8} style={{ width: 70 }} />
            <span>Virtual machine reserve (%):</span><input className="winos-input" defaultValue={0} style={{ width: 70 }} />
            <span>Virtual machine limit (%):</span><input className="winos-input" defaultValue={100} style={{ width: 70 }} />
          </div>}
          {tab === 'Network Adapter' && <div className="winos-grid2">
            <span>Virtual switch:</span><select className="winos-input"><option>External Switch</option><option>Internal Switch</option><option>Private Switch</option><option>Default Switch</option></select>
            <span>VLAN ID:</span><label><input type="checkbox" /> Enable virtual LAN identification</label>
          </div>}
          {tab === 'Firmware' && <div><div style={{ marginBottom: 6 }}>Boot order:</div><ol style={{ paddingLeft: 20 }}><li>Hard Drive</li><li>DVD Drive</li><li>Network Adapter</li></ol><label style={{ marginTop: 8, display: 'block' }}><input type="checkbox" defaultChecked /> Enable Secure Boot</label></div>}
          {tab === 'Integration Services' && ['Operating system shutdown', 'Time synchronization', 'Data Exchange', 'Heartbeat', 'Backup (volume shadow copy)', 'Guest services'].map((s) => (
            <label key={s} style={{ display: 'block', padding: '2px 0' }}><input type="checkbox" defaultChecked={s !== 'Guest services'} /> {s}</label>
          ))}
          {tab === 'Name' && <div className="winos-grid2"><span>Name:</span><input className="winos-input" defaultValue={vm.name} /><span>Notes:</span><textarea className="winos-input" rows={3} /></div>}
          {['Add Hardware', 'Security', 'SCSI Controller', 'Checkpoints', 'Automatic Start Action', 'Automatic Stop Action'].includes(tab) && (
            <div style={{ color: '#555' }}>{tab === 'Automatic Start Action' ? <><label style={{ display: 'block' }}><input type="radio" name="sa" /> Nothing</label><label style={{ display: 'block' }}><input type="radio" name="sa" defaultChecked /> Automatically start if it was running when the service stopped</label><label style={{ display: 'block' }}><input type="radio" name="sa" /> Always start this virtual machine automatically</label></> : `${tab} settings for ${vm.name}.`}</div>
          )}
        </div>
      </div>
    </Dialog>
  )
}

// ── Computer Management ──────────────────────────────────────────────────────
export function ComputerManagement() {
  const os = useOS()
  const launch = (app, title, props = {}) => os.openApp(app, props, { title })
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Help</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 260 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}>🖥️ Computer Management (Local)</div>
          <div className="winos-tree-row" style={{ paddingLeft: 22, fontWeight: 600 }}>System Tools</div>
          {[['Task Scheduler', 'TaskScheduler'], ['Event Viewer', 'EventViewer'], ['Local Users and Groups', 'ADUC'], ['Performance', 'TaskManager'], ['Device Manager', 'DeviceManager']].map(([l, a]) => (
            <div key={l} className="winos-tree-row" style={{ paddingLeft: 44 }} onClick={() => launch(a, l)}>{l}</div>
          ))}
          <div className="winos-tree-row" style={{ paddingLeft: 22, fontWeight: 600 }}>Storage</div>
          <div className="winos-tree-row" style={{ paddingLeft: 44 }} onClick={() => launch('DiskManagement', 'Disk Management')}>Disk Management</div>
          <div className="winos-tree-row" style={{ paddingLeft: 22, fontWeight: 600 }}>Services and Applications</div>
          <div className="winos-tree-row" style={{ paddingLeft: 44 }} onClick={() => launch('Services', 'Services')}>Services</div>
        </div>
        <div className="winos-main" style={{ padding: 16 }}>
          <div className="winos-card"><div className="winos-card-h">Shared Folders · Shares</div>
            <table className="winos-table"><thead><tr><th>Share Name</th><th>Folder Path</th><th># Client Connections</th></tr></thead>
              <tbody>{[['ADMIN$', 'C:\\Windows', 1], ['C$', 'C:\\', 0], ['D$', 'D:\\', 0], ['IPC$', '', 3], ['NETLOGON', 'C:\\Windows\\SYSVOL\\sysvol\\lab.local\\SCRIPTS', 0], ['SYSVOL', 'C:\\Windows\\SYSVOL\\sysvol', 0], ['IT', 'D:\\Data\\Shares\\IT', 5], ['Finance', 'D:\\Data\\Shares\\Finance', 2]].map((r) => (
                <tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Network Connections (ncpa.cpl) ───────────────────────────────────────────
export function NetworkConnections() {
  const os = useOS()
  const [props, setProps] = useState(null)
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><Network size={14} /> <span style={{ fontSize: 12 }}>Network Connections</span></div>
      <div className="winos-main" style={{ padding: 16, display: 'flex', gap: 18, flexWrap: 'wrap' }}>
        {os.adapters.map((a) => (
          <div key={a.id} style={{ width: 160, textAlign: 'center', cursor: 'default' }} onDoubleClick={() => setProps(a)}>
            <div style={{ fontSize: 40 }}>{a.status === 'Connected' ? '🖧' : '🚫'}</div>
            <div style={{ fontSize: 12, fontWeight: 600 }}>{a.name}</div>
            <div style={{ fontSize: 11, color: '#666' }}>{a.status}<br />{a.desc}</div>
          </div>
        ))}
      </div>
      {props && <AdapterProps adapter={props} onClose={() => setProps(null)} />}
    </div>
  )
}

function AdapterProps({ adapter, onClose }) {
  const os = useOS()
  const [ipv4, setIpv4] = useState(false)
  const [form, setForm] = useState(adapter)
  const items = ['Client for Microsoft Networks', 'File and Printer Sharing for Microsoft Networks', 'QoS Packet Scheduler', 'Internet Protocol Version 4 (TCP/IPv4)', 'Microsoft LLDP Protocol Driver', 'Internet Protocol Version 6 (TCP/IPv6)']
  if (ipv4) {
    return (
      <Dialog title="Internet Protocol Version 4 (TCP/IPv4) Properties" onClose={() => setIpv4(false)} width={440}
        footer={<><button className="winos-btn primary" onClick={() => { os.setAdapter(adapter.id, { ipv4: form.ipv4, mask: form.mask, gateway: form.gateway, dns: form.dns, dhcp: form.dhcp }); setIpv4(false) }}>OK</button><button className="winos-btn" onClick={() => setIpv4(false)}>Cancel</button></>}>
        <div style={{ fontSize: 12.5 }}>
          <label style={{ display: 'block' }}><input type="radio" checked={form.dhcp} onChange={() => setForm((f) => ({ ...f, dhcp: true }))} /> Obtain an IP address automatically</label>
          <label style={{ display: 'block', marginBottom: 6 }}><input type="radio" checked={!form.dhcp} onChange={() => setForm((f) => ({ ...f, dhcp: false }))} /> Use the following IP address:</label>
          <div className="winos-grid2" style={{ marginLeft: 22, opacity: form.dhcp ? 0.5 : 1 }}>
            <span>IP address:</span><input className="winos-input" value={form.ipv4} disabled={form.dhcp} onChange={(e) => setForm((f) => ({ ...f, ipv4: e.target.value }))} />
            <span>Subnet mask:</span><input className="winos-input" value={form.mask} disabled={form.dhcp} onChange={(e) => setForm((f) => ({ ...f, mask: e.target.value }))} />
            <span>Default gateway:</span><input className="winos-input" value={form.gateway} disabled={form.dhcp} onChange={(e) => setForm((f) => ({ ...f, gateway: e.target.value }))} />
          </div>
          <label style={{ display: 'block', marginTop: 10 }}><input type="radio" checked={!form.dhcp} readOnly /> Use the following DNS server addresses:</label>
          <div className="winos-grid2" style={{ marginLeft: 22 }}>
            <span>Preferred DNS:</span><input className="winos-input" value={form.dns[0] || ''} onChange={(e) => setForm((f) => ({ ...f, dns: [e.target.value, f.dns[1] || ''] }))} />
            <span>Alternate DNS:</span><input className="winos-input" value={form.dns[1] || ''} onChange={(e) => setForm((f) => ({ ...f, dns: [f.dns[0] || '', e.target.value] }))} />
          </div>
        </div>
      </Dialog>
    )
  }
  return (
    <Dialog title={`${adapter.name} Properties`} onClose={onClose} width={420}
      footer={<><button className="winos-btn primary" onClick={onClose}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button></>}>
      <div style={{ fontSize: 12.5 }}>
        <div style={{ marginBottom: 6 }}>Connect using: <b>{adapter.desc}</b></div>
        <div style={{ marginBottom: 6 }}>This connection uses the following items:</div>
        <div style={{ border: '1px solid #ddd', height: 150, overflow: 'auto' }}>
          {items.map((it) => (
            <div key={it} className="winos-tree-row" onDoubleClick={() => it.includes('IPv4') && setIpv4(true)}>
              <input type="checkbox" defaultChecked /> {it}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <button className="winos-btn">Install…</button><button className="winos-btn">Uninstall</button>
          <button className="winos-btn" onClick={() => setIpv4(true)}>Properties</button>
        </div>
      </div>
    </Dialog>
  )
}

// ── Task Scheduler ───────────────────────────────────────────────────────────
export function TaskScheduler() {
  const os = useOS()
  const [sel, setSel] = useState(null)
  const [wizard, setWizard] = useState(false)
  const cur = os.scheduledTasks.find((t) => t.name === sel)
  return (
    <div className="winos-app">
      <div className="winos-toolbar">
        <span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Help</span>
        <span style={{ flex: 1 }} />
        <button className="winos-btn" onClick={() => setWizard(true)}>Create Basic Task…</button>
      </div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 220 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}>🕑 Task Scheduler (Local)</div>
          <div className="winos-tree-row sel" style={{ paddingLeft: 22 }}>Task Scheduler Library</div>
          <div className="winos-tree-row" style={{ paddingLeft: 44 }}>Microsoft</div>
          <div className="winos-tree-row" style={{ paddingLeft: 66 }}>Windows</div>
        </div>
        <div className="winos-main">
          <table className="winos-table">
            <thead><tr><th>Name</th><th>Status</th><th>Triggers</th><th>Next Run Time</th><th>Last Run Time</th><th>Last Run Result</th></tr></thead>
            <tbody>{os.scheduledTasks.map((t) => (
              <tr key={t.name} className={sel === t.name ? 'sel' : ''} onClick={() => setSel(t.name)}>
                <td>{t.name}</td><td>{t.status}</td><td>{t.triggers}</td><td>{t.nextRun}</td><td>{t.lastRun}</td>
                <td>The operation completed successfully. ({t.result})</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>
      <div className="winos-status"><span>{os.scheduledTasks.length} task(s)</span><span>{cur ? cur.name : ''}</span></div>
      {wizard && <Dialog title="Create Basic Task Wizard" onClose={() => setWizard(false)}
        footer={<><button className="winos-btn primary" onClick={() => setWizard(false)}>Finish</button><button className="winos-btn" onClick={() => setWizard(false)}>Cancel</button></>}>
        <div className="winos-grid2" style={{ fontSize: 12.5 }}>
          <span>Name:</span><input className="winos-input" defaultValue="New Task" />
          <span>Description:</span><textarea className="winos-input" rows={2} />
          <span>Trigger:</span><select className="winos-input"><option>Daily</option><option>Weekly</option><option>Monthly</option><option>One time</option><option>When the computer starts</option><option>When I log on</option></select>
          <span>Action:</span><select className="winos-input"><option>Start a program</option><option>Send an e-mail</option><option>Display a message</option></select>
          <span>Program/script:</span><input className="winos-input" defaultValue="powershell.exe" />
        </div>
      </Dialog>}
    </div>
  )
}

// ── Settings (minimal real) ─────────────────────────────────────────────────
export function SettingsApp() {
  const os = useOS()
  const [page, setPage] = useState('System')
  const pages = ['System', 'Network & Internet', 'Personalization', 'Apps', 'Accounts', 'Update & Security']
  return (
    <div className="winos-app">
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 220 }}>
          <div style={{ padding: 12, fontWeight: 600 }}><Cog size={16} style={{ verticalAlign: 'middle' }} /> Settings</div>
          {pages.map((p) => <div key={p} className={`winos-tree-row ${page === p ? 'sel' : ''}`} style={{ padding: '8px 12px' }} onClick={() => setPage(p)}>{p}</div>)}
        </div>
        <div className="winos-main" style={{ padding: 20 }}>
          <h2 style={{ fontWeight: 600, fontSize: 18 }}>{page}</h2>
          {page === 'System' && <div className="winos-grid2" style={{ marginTop: 12 }}>
            <span>Device name</span><span>{os.computer.name}</span>
            <span>Edition</span><span>{os.computer.edition}</span>
            <span>Version</span><span>21H2 (Build {os.computer.build})</span>
            <span>Processor</span><span>{os.computer.cpu}</span>
            <span>Installed RAM</span><span>{os.computer.ramGB}.0 GB</span>
          </div>}
          {page === 'Update & Security' && <div style={{ marginTop: 12 }}><div style={{ color: '#107c10', fontWeight: 600 }}>You're up to date</div><div style={{ color: '#666', fontSize: 12 }}>Last checked: Today, 6:00 AM</div><button className="winos-btn primary" style={{ marginTop: 10 }}>Check for updates</button></div>}
          {page === 'Network & Internet' && <div style={{ marginTop: 12 }}>{os.adapters.map((a) => <div key={a.id} style={{ marginBottom: 8 }}><b>{a.name}</b> — {a.ipv4}</div>)}</div>}
          {['Personalization', 'Apps', 'Accounts'].includes(page) && <div style={{ marginTop: 12, color: '#555' }}>{page === 'Apps' ? `${os.programs.length} apps installed.` : `${page} options for this server.`}</div>}
        </div>
      </div>
    </div>
  )
}
