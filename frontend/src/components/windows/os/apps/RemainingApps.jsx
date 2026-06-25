import { useMemo, useState } from 'react'
import { ChevronRight, Plus, Shield, Globe, Gauge, Calculator as CalcIcon, Palette, FileText } from 'lucide-react'
import { useOS } from '../store'
import { Dialog, Tabs } from '../ui'

const gpos = [
  'Default Domain Policy', 'Default Domain Controllers Policy', 'Workstation-Baseline-Security',
  'Server-Baseline-Security', 'Password-Policy-Strict', 'Account-Lockout-Policy',
  'IE-Settings', 'Windows-Update-Policy', 'Software-Deployment', 'Drive-Mappings',
  'Printers-Policy', 'Desktop-Wallpaper', 'Screen-Saver-Lock', 'USB-Restriction',
  'BitLocker-Policy', 'Windows-Firewall-Policy', 'Audit-Policy', 'AppLocker-Policy',
  'Remote-Desktop-Policy', 'Software-Restriction-Policies',
]

const policySettings = [
  ['Enforce password history', 'Enabled', '24 passwords remembered'],
  ['Maximum password age', 'Enabled', '90 days'],
  ['Minimum password age', 'Enabled', '1 day'],
  ['Minimum password length', 'Enabled', '14 characters'],
  ['Password must meet complexity requirements', 'Enabled', 'Enabled'],
  ['Store passwords using reversible encryption', 'Disabled', 'Disabled'],
  ['Account lockout duration', 'Enabled', '30 minutes'],
  ['Account lockout threshold', 'Enabled', '5 invalid logon attempts'],
  ['Reset account lockout counter after', 'Enabled', '30 minutes'],
]

export function GPMC() {
  const os = useOS()
  const [selected, setSelected] = useState('Default Domain Policy')
  const [tab, setTab] = useState('Scope')
  const [editor, setEditor] = useState(null)
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Window &nbsp; Help</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 310 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}>Group Policy Management</div>
          <TreeLine d={1} label="Forest: lab.local" open />
          <TreeLine d={2} label="Domains" open />
          <TreeLine d={3} label="lab.local" open />
          {['Default Domain Policy', 'Corp', 'Domain Controllers'].map((n) => (
            <div key={n} className={`winos-tree-row ${selected === n ? 'sel' : ''}`} style={{ paddingLeft: 50 }} onClick={() => setSelected(n)}>{n}</div>
          ))}
          <TreeLine d={4} label="Group Policy Objects" open />
          {gpos.map((g) => (
            <div key={g} className={`winos-tree-row ${selected === g ? 'sel' : ''}`} style={{ paddingLeft: 66 }} onClick={() => setSelected(g)} onDoubleClick={() => setEditor(g)}>📜 {g}</div>
          ))}
          <TreeLine d={2} label="Sites" />
          <TreeLine d={2} label="Group Policy Modeling" />
        </div>
        <div className="winos-main" style={{ display: 'flex', flexDirection: 'column' }}>
          <Tabs tabs={['Scope', 'Details', 'Settings', 'Delegation']} active={tab} onChange={setTab} />
          <div style={{ padding: 14, overflow: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
              <h2 style={{ fontSize: 16, margin: 0, fontWeight: 600 }}>{selected}</h2>
              <span style={{ flex: 1 }} />
              {gpos.includes(selected) && <button className="winos-btn primary" onClick={() => setEditor(selected)}>Edit…</button>}
            </div>
            {tab === 'Scope' && (
              <>
                <Panel title="Links">
                  <table className="winos-table"><thead><tr><th>Location</th><th>Enforced</th><th>Link Enabled</th><th>Path</th></tr></thead>
                    <tbody><tr><td>lab.local</td><td>No</td><td>Yes</td><td>lab.local</td></tr><tr><td>Corp</td><td>No</td><td>Yes</td><td>lab.local/Corp</td></tr></tbody></table>
                </Panel>
                <Panel title="Security Filtering">
                  {['Authenticated Users', 'Domain Computers', 'IT-Admins'].map((g) => <div key={g} className="winos-tree-row">👥 {g}</div>)}
                </Panel>
              </>
            )}
            {tab === 'Details' && (
              <div className="winos-grid2">
                <span>GPO Status</span><span>All settings enabled</span>
                <span>Unique ID</span><span>{`{${selected.toUpperCase().replaceAll(' ', '-')}-2024}`}</span>
                <span>Created</span><span>8/15/2023 10:42:11 AM</span>
                <span>Modified</span><span>1/17/2024 8:14:22 AM</span>
                <span>User version</span><span>AD: 12, SysVol: 12</span>
                <span>Computer version</span><span>AD: 28, SysVol: 28</span>
              </div>
            )}
            {tab === 'Settings' && (
              <Panel title="Computer Configuration (Enabled)">
                <table className="winos-table"><thead><tr><th>Policy</th><th>State</th><th>Setting</th></tr></thead>
                  <tbody>{policySettings.map((p) => <tr key={p[0]}><td>{p[0]}</td><td>{p[1]}</td><td>{p[2]}</td></tr>)}</tbody></table>
              </Panel>
            )}
            {tab === 'Delegation' && (
              <table className="winos-table"><thead><tr><th>Name</th><th>Allowed Permissions</th><th>Inherited</th></tr></thead>
                <tbody>{['Domain Admins', 'Enterprise Admins', 'SYSTEM', 'Group Policy Creator Owners'].map((g) => <tr key={g}><td>{g}</td><td>Read, Edit settings, Delete, Modify security</td><td>No</td></tr>)}</tbody></table>
            )}
          </div>
        </div>
      </div>
      {editor && <GPOEditor name={editor} os={os} onClose={() => setEditor(null)} />}
    </div>
  )
}

function GPOEditor({ name, os, onClose }) {
  const [node, setNode] = useState('Password Policy')
  const [edit, setEdit] = useState(null)
  const nodes = ['Password Policy', 'Account Lockout Policy', 'Kerberos Policy', 'Audit Policy', 'User Rights Assignment', 'Security Options', 'Windows Firewall with Advanced Security', 'Administrative Templates', 'File Explorer', 'Start Menu and Taskbar', 'Remote Desktop Services', 'Windows Update']
  const rows = node === 'Account Lockout Policy' ? policySettings.slice(6) : node === 'Password Policy' ? policySettings.slice(0, 6) : policySettings
  return (
    <Dialog title={`Group Policy Management Editor - ${name}`} onClose={onClose} width={920}
      footer={<button className="winos-btn primary" onClick={onClose}>Close</button>}>
      <div className="winos-split" style={{ height: 470, border: '1px solid #ddd' }}>
        <div className="winos-tree" style={{ width: 330 }}>
          <TreeLine d={0} label={`GPO: ${name} [SERVER01.lab.local]`} open />
          <TreeLine d={1} label="Computer Configuration" open />
          <TreeLine d={2} label="Policies" open />
          <TreeLine d={3} label="Windows Settings" open />
          <TreeLine d={4} label="Security Settings" open />
          <TreeLine d={5} label="Account Policies" open />
          {nodes.map((n) => <div key={n} className={`winos-tree-row ${node === n ? 'sel' : ''}`} style={{ paddingLeft: 78 }} onClick={() => setNode(n)}>📁 {n}</div>)}
          <TreeLine d={1} label="User Configuration" open />
          <TreeLine d={2} label="Preferences" />
        </div>
        <div className="winos-main">
          <table className="winos-table"><thead><tr><th>Policy</th><th>Setting</th></tr></thead>
            <tbody>{rows.map((r) => <tr key={r[0]} onDoubleClick={() => setEdit(r)}><td>{r[0]}</td><td>{r[2]}</td></tr>)}</tbody></table>
        </div>
      </div>
      {edit && <Dialog title={edit[0]} onClose={() => setEdit(null)} width={460}
        footer={<><button className="winos-btn primary" onClick={() => setEdit(null)}>OK</button><button className="winos-btn" onClick={() => setEdit(null)}>Cancel</button><button className="winos-btn">Apply</button></>}>
        <div style={{ fontSize: 12.5 }}>
          <label style={{ display: 'block' }}><input type="radio" name="pol" /> Not Configured</label>
          <label style={{ display: 'block' }}><input type="radio" name="pol" defaultChecked /> Enabled</label>
          <label style={{ display: 'block' }}><input type="radio" name="pol" /> Disabled</label>
          <div style={{ marginTop: 12 }}><b>Options:</b></div>
          <input className="winos-input" style={{ width: '100%', marginTop: 6 }} defaultValue={edit[2]} />
          <div style={{ marginTop: 12, color: '#666' }}>Supported on: Windows Server 2008 and above</div>
          <textarea className="winos-input" rows={4} style={{ width: '100%', marginTop: 8 }} defaultValue={`This setting controls ${edit[0].toLowerCase()} for domain computers and users.`} />
        </div>
      </Dialog>}
    </Dialog>
  )
}

const appPools = ['DefaultAppPool', '.NET v4.5', '.NET v4.5 Classic', 'Classic .NET AppPool', 'api-pool', 'legacy-pool']
const sites = [
  ['Default Web Site', 'Started', 'http', '*:80:'],
  ['API-Site', 'Started', 'https', '*:443:api.lab.local'],
  ['Intranet', 'Started', 'http', '*:8081:'],
  ['Legacy-App', 'Stopped', 'http', '*:8082:'],
]
const iisFeatures = ['Authentication', 'Authorization Rules', 'Compression', 'Default Document', 'Directory Browsing', 'Error Pages', 'Handler Mappings', 'HTTP Response Headers', 'Logging', 'MIME Types', 'Modules', 'Request Filtering', 'SSL Settings']

export function IISManager() {
  const [sel, setSel] = useState('SERVER01')
  const [dialog, setDialog] = useState(null)
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; View &nbsp; Help</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 260 }}>
          <div className="winos-tree-row">Start Page</div>
          <TreeLine d={0} label="SERVER01 (local computer)" open />
          <TreeLine d={1} label="Application Pools" open />
          {appPools.map((p) => <div key={p} className={`winos-tree-row ${sel === p ? 'sel' : ''}`} style={{ paddingLeft: 36 }} onClick={() => setSel(p)}>⚙️ {p}</div>)}
          <TreeLine d={1} label="Sites" open />
          {sites.map((s) => <div key={s[0]} className={`winos-tree-row ${sel === s[0] ? 'sel' : ''}`} style={{ paddingLeft: 36 }} onClick={() => setSel(s[0])}>🌐 {s[0]}</div>)}
        </div>
        <div className="winos-main" style={{ padding: 14 }}>
          {appPools.includes(sel) ? <AppPoolView name={sel} onOpen={() => setDialog('pool')} />
            : sites.some((s) => s[0] === sel) ? <SiteView site={sites.find((s) => s[0] === sel)} onBindings={() => setDialog('bindings')} />
              : <FeatureGrid title="SERVER01 Home" />}
        </div>
        <div style={{ width: 190, borderLeft: '1px solid #ddd', padding: 10, fontSize: 12 }}>
          <b>Actions</b>
          {sites.some((s) => s[0] === sel) && <><Action onClick={() => setDialog('bindings')}>Edit Bindings…</Action><Action>Basic Settings…</Action><Action>Browse Website</Action><Action>Restart</Action><Action>Stop</Action></>}
          {appPools.includes(sel) && <><Action onClick={() => setDialog('pool')}>Advanced Settings…</Action><Action>Start</Action><Action>Stop</Action><Action>Recycle…</Action></>}
          {!appPools.includes(sel) && !sites.some((s) => s[0] === sel) && <><Action>Restart</Action><Action>Start</Action><Action>Stop</Action></>}
        </div>
      </div>
      {dialog === 'bindings' && <BindingsDialog onClose={() => setDialog(null)} />}
      {dialog === 'pool' && <PoolDialog pool={sel} onClose={() => setDialog(null)} />}
    </div>
  )
}

function FeatureGrid({ title }) {
  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 600 }}>{title}</h2>
      <div className="winos-sm-section">IIS</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
        {iisFeatures.map((f) => <div key={f} className="winos-card" style={{ padding: 12, textAlign: 'center', fontSize: 12 }}><Globe size={26} color="#2b88d8" /><div>{f}</div></div>)}
      </div>
    </div>
  )
}

function SiteView({ site }) {
  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 600 }}>{site[0]} Home</h2>
      <div className="winos-grid2" style={{ marginBottom: 14 }}>
        <span>Status</span><span>{site[1]}</span><span>Binding</span><span>{site[2]} {site[3]}</span><span>Physical Path</span><span>C:\inetpub\wwwroot</span>
      </div>
      <FeatureGrid title="Features View" />
    </div>
  )
}

function AppPoolView({ name, onOpen }) {
  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 600 }}>{name}</h2>
      <div className="winos-grid2">
        <span>.NET CLR version</span><span>{name.includes('Classic') ? 'v2.0' : 'v4.0'}</span>
        <span>Managed pipeline mode</span><span>{name.includes('Classic') ? 'Classic' : 'Integrated'}</span>
        <span>Status</span><span>{name === 'legacy-pool' ? 'Stopped' : 'Started'}</span>
      </div>
      <button className="winos-btn primary" style={{ marginTop: 12 }} onClick={onOpen}>Advanced Settings…</button>
    </div>
  )
}

function BindingsDialog({ onClose }) {
  return (
    <Dialog title="Site Bindings" onClose={onClose} width={540}
      footer={<><button className="winos-btn primary" onClick={onClose}>Close</button></>}>
      <table className="winos-table"><thead><tr><th>Type</th><th>Host Name</th><th>Port</th><th>IP Address</th><th>Binding Information</th></tr></thead>
        <tbody><tr><td>http</td><td></td><td>80</td><td>*</td><td>*:80:</td></tr><tr><td>https</td><td>api.lab.local</td><td>443</td><td>*</td><td>*:443:api.lab.local</td></tr></tbody></table>
      <div style={{ marginTop: 10, display: 'flex', gap: 6 }}><button className="winos-btn">Add…</button><button className="winos-btn">Edit…</button><button className="winos-btn">Remove</button><button className="winos-btn">Browse</button></div>
    </Dialog>
  )
}

function PoolDialog({ pool, onClose }) {
  const rows = [['General', '.NET CLR Version', 'v4.0'], ['General', 'Managed Pipeline Mode', 'Integrated'], ['Process Model', 'Identity', 'ApplicationPoolIdentity'], ['Process Model', 'Idle Time-out', '20'], ['Recycling', 'Regular Time Interval', '1740'], ['Rapid Fail Protection', 'Enabled', 'True']]
  return (
    <Dialog title={`Advanced Settings - ${pool}`} onClose={onClose} width={520}
      footer={<><button className="winos-btn primary" onClick={onClose}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button></>}>
      <table className="winos-table"><thead><tr><th>Section</th><th>Name</th><th>Value</th></tr></thead><tbody>{rows.map((r) => <tr key={r.join()}><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>)}</tbody></table>
    </Dialog>
  )
}

const leases = Array.from({ length: 80 }, (_, i) => [`192.168.10.${101 + i}`, `00:50:56:ab:${(20 + i).toString(16).padStart(2, '0')}:${(40 + i).toString(16).padStart(2, '0')}`, `ws-${i < 25 ? 'eng' : 'mkt'}-${String((i % 25) + 1).padStart(2, '0')}.lab.local`, `1/18/2024 ${8 + (i % 10)}:45 AM`, 'DHCP'])

export function DHCPManager() {
  const [node, setNode] = useState('Address Leases')
  const [props, setProps] = useState(false)
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Help</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 280 }}>
          <TreeLine d={0} label="DHCP" open />
          <TreeLine d={1} label="server01.lab.local [authorized]" open />
          <TreeLine d={2} label="IPv4" open />
          <TreeLine d={3} label="Scope [192.168.10.0] LAN Scope" open />
          {['Address Pool', 'Address Leases', 'Reservations', 'Scope Options', 'Policies'].map((n) => <div key={n} className={`winos-tree-row ${node === n ? 'sel' : ''}`} style={{ paddingLeft: 64 }} onClick={() => setNode(n)}>{n}</div>)}
          <TreeLine d={3} label="Scope [10.0.0.0] Management Network" />
          <TreeLine d={2} label="IPv6" />
        </div>
        <div className="winos-main">
          <div className="winos-toolbar"><b>{node}</b><span style={{ flex: 1 }} /><button className="winos-btn" onClick={() => setProps(true)}>Properties…</button></div>
          {node === 'Address Leases' && <table className="winos-table"><thead><tr><th>IP Address</th><th>Client Unique ID</th><th>Name</th><th>Lease Expiration</th><th>Type</th></tr></thead><tbody>{leases.map((r) => <tr key={r[0]}>{r.map((c) => <td key={c}>{c}</td>)}</tr>)}</tbody></table>}
          {node === 'Address Pool' && <table className="winos-table"><tbody><tr><td>192.168.10.100 - 192.168.10.200</td><td>Distribution range</td></tr><tr><td>192.168.10.1 - 192.168.10.99</td><td>Exclusion range</td></tr></tbody></table>}
          {node === 'Reservations' && <table className="winos-table"><tbody>{['server01', 'server02', 'print01', 'nas01', 'backup01'].map((n, i) => <tr key={n}><td>192.168.10.{50 + i}</td><td>00:50:56:ab:cd:{(239 + i).toString(16)}</td><td>{n}</td><td>Reservation (both)</td></tr>)}</tbody></table>}
          {node === 'Scope Options' && <table className="winos-table"><tbody><tr><td>003 Router</td><td>192.168.10.1</td></tr><tr><td>006 DNS Servers</td><td>192.168.10.10, 192.168.10.11</td></tr><tr><td>015 DNS Domain Name</td><td>lab.local</td></tr></tbody></table>}
        </div>
      </div>
      {props && <Dialog title="Scope [192.168.10.0] LAN Scope Properties" onClose={() => setProps(false)} width={500}
        footer={<><button className="winos-btn primary" onClick={() => setProps(false)}>OK</button><button className="winos-btn" onClick={() => setProps(false)}>Cancel</button></>}>
        <Tabs tabs={['General', 'DNS', 'Advanced']} active="General" onChange={() => {}} />
        <div className="winos-grid2" style={{ marginTop: 12 }}><span>Name</span><input className="winos-input" defaultValue="LAN Scope" /><span>Start IP</span><input className="winos-input" defaultValue="192.168.10.100" /><span>End IP</span><input className="winos-input" defaultValue="192.168.10.200" /><span>Subnet mask</span><input className="winos-input" defaultValue="255.255.255.0" /><span>Lease duration</span><span><input className="winos-input" defaultValue="8" style={{ width: 60 }} /> days</span></div>
      </Dialog>}
    </div>
  )
}

const firewallRules = [
  ['Remote Desktop (TCP-In)', 'Remote Desktop', 'Domain, Private', 'Yes', 'Allow', 'TCP', '3389'],
  ['Windows Remote Management (HTTP-In)', 'Windows Remote Management', 'Domain', 'Yes', 'Allow', 'TCP', '5985'],
  ['World Wide Web Services (HTTP Traffic-In)', 'IIS', 'Any', 'Yes', 'Allow', 'TCP', '80'],
  ['World Wide Web Services (HTTPS Traffic-In)', 'IIS', 'Any', 'Yes', 'Allow', 'TCP', '443'],
  ['File and Printer Sharing (SMB-In)', 'File and Printer Sharing', 'Domain', 'Yes', 'Allow', 'TCP', '445'],
  ['Core Networking - DNS (UDP-In)', 'Core Networking', 'Any', 'Yes', 'Allow', 'UDP', '53'],
  ...Array.from({ length: 44 }, (_, i) => [`Windows Service Rule ${i + 1}`, 'Windows Services', 'Domain', i % 3 ? 'Yes' : 'No', 'Allow', i % 2 ? 'TCP' : 'UDP', String(5000 + i)]),
]

export function FirewallAdvanced() {
  const [node, setNode] = useState('Inbound Rules')
  const [rule, setRule] = useState(null)
  const [wizard, setWizard] = useState(false)
  return (
    <div className="winos-app">
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 240 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}><Shield size={14} /> Windows Defender Firewall</div>
          {['Inbound Rules', 'Outbound Rules', 'Connection Security Rules', 'Monitoring'].map((n) => <div key={n} className={`winos-tree-row ${node === n ? 'sel' : ''}`} style={{ paddingLeft: 28 }} onClick={() => setNode(n)}>{n}</div>)}
        </div>
        <div className="winos-main">
          <div className="winos-toolbar"><b>{node}</b><span style={{ flex: 1 }} /><button className="winos-btn primary" onClick={() => setWizard(true)}><Plus size={13} /> New Rule…</button></div>
          {node === 'Inbound Rules' ? <table className="winos-table"><thead><tr><th>Name</th><th>Group</th><th>Profile</th><th>Enabled</th><th>Action</th><th>Protocol</th><th>Local Port</th></tr></thead><tbody>{firewallRules.map((r) => <tr key={r[0]} onDoubleClick={() => setRule(r)}>{r.map((c) => <td key={c}>{c}</td>)}</tr>)}</tbody></table>
            : <div style={{ padding: 16, color: '#555' }}>{node} status and policy details are available from the Actions pane.</div>}
        </div>
      </div>
      {rule && <FirewallRuleDialog rule={rule} onClose={() => setRule(null)} />}
      {wizard && <Dialog title="New Inbound Rule Wizard" onClose={() => setWizard(false)} width={520}
        footer={<><button className="winos-btn primary" onClick={() => setWizard(false)}>Finish</button><button className="winos-btn" onClick={() => setWizard(false)}>Cancel</button></>}>
        <div style={{ fontSize: 12.5 }}><b>Rule Type</b><br /><label><input type="radio" defaultChecked /> Program</label><br /><label><input type="radio" /> Port</label><br /><label><input type="radio" /> Predefined</label><br /><label><input type="radio" /> Custom</label><div className="winos-grid2" style={{ marginTop: 12 }}><span>Name</span><input className="winos-input" defaultValue="Allow Custom App" /><span>Action</span><select className="winos-input"><option>Allow the connection</option><option>Block the connection</option></select></div></div>
      </Dialog>}
    </div>
  )
}

function FirewallRuleDialog({ rule, onClose }) {
  const [tab, setTab] = useState('General')
  return (
    <Dialog title={`${rule[0]} Properties`} onClose={onClose} width={520}
      footer={<><button className="winos-btn primary" onClick={onClose}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button><button className="winos-btn">Apply</button></>}>
      <Tabs tabs={['General', 'Programs and Services', 'Protocols and Ports', 'Scope', 'Advanced']} active={tab} onChange={setTab} />
      <div className="winos-grid2" style={{ marginTop: 12 }}><span>Name</span><input className="winos-input" defaultValue={rule[0]} /><span>Enabled</span><label><input type="checkbox" defaultChecked={rule[3] === 'Yes'} /> Enabled</label><span>Action</span><select className="winos-input" defaultValue={rule[4]}><option>Allow</option><option>Block</option></select><span>Protocol</span><span>{rule[5]}</span><span>Local port</span><span>{rule[6]}</span></div>
    </Dialog>
  )
}

export function PerformanceMonitor() {
  const [counter, setCounter] = useState('% Processor Time')
  const [add, setAdd] = useState(false)
  const points = useMemo(() => Array.from({ length: 60 }, (_, i) => 20 + Math.sin(i / 4) * 12 + (i % 7)), [counter])
  const path = points.map((p, i) => `${i * 10},${150 - p}`).join(' ')
  return (
    <div className="winos-app">
      <div className="winos-toolbar"><Gauge size={14} /><button className="winos-btn" onClick={() => setAdd(true)}><Plus size={13} /> Add Counters</button><button className="winos-btn">Freeze Display</button><span>{counter}</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 250 }}><TreeLine d={0} label="Performance" open /><TreeLine d={1} label="Monitoring Tools" open /><div className="winos-tree-row sel" style={{ paddingLeft: 34 }}>Performance Monitor</div><TreeLine d={1} label="Data Collector Sets" /><TreeLine d={1} label="Reports" /></div>
        <div className="winos-main" style={{ padding: 16 }}>
          <svg width="100%" viewBox="0 0 600 170" preserveAspectRatio="none" style={{ border: '1px solid #ccc', background: '#061d06' }}>
            {Array.from({ length: 10 }, (_, i) => <line key={i} x1={i * 60} y1="0" x2={i * 60} y2="170" stroke="#164316" />)}
            {Array.from({ length: 6 }, (_, i) => <line key={i} x1="0" y1={i * 34} x2="600" y2={i * 34} stroke="#164316" />)}
            <polyline points={path} fill="none" stroke="#84ff84" strokeWidth="2" />
          </svg>
          <table className="winos-table" style={{ marginTop: 12 }}><thead><tr><th>Counter</th><th>Color</th><th>Scale</th><th>Instance</th><th>Parent</th><th>Object</th><th>Computer</th></tr></thead><tbody><tr><td>{counter}</td><td>Green</td><td>1.0</td><td>_Total</td><td></td><td>Processor</td><td>\\SERVER01</td></tr></tbody></table>
        </div>
      </div>
      {add && <Dialog title="Add Counters" onClose={() => setAdd(false)} width={560}
        footer={<><button className="winos-btn primary" onClick={() => setAdd(false)}>Add</button><button className="winos-btn" onClick={() => setAdd(false)}>Close</button></>}>
        <div style={{ fontSize: 12.5 }}>Select counters from computer: <input className="winos-input" defaultValue="\\SERVER01" /></div>
        <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
          <select className="winos-input" size={12} style={{ flex: 1 }} value={counter} onChange={(e) => setCounter(e.target.value)}>
            {['% Processor Time', 'Available MBytes', 'Disk Bytes/sec', 'Current Disk Queue Length', 'Bytes Total/sec', 'Processor Queue Length', 'System Up Time', 'W3SVC_W3WP Requests/sec'].map((c) => <option key={c}>{c}</option>)}
          </select>
          <select className="winos-input" size={12} style={{ width: 150 }}><option>_Total</option><option>0</option><option>1</option><option>Ethernet0</option><option>C:</option></select>
        </div>
      </Dialog>}
    </div>
  )
}

export function Calculator() {
  const [v, setV] = useState('0')
  const press = (x) => setV((p) => x === 'C' ? '0' : x === '=' ? String(Function(`return (${p})`)()) : p === '0' ? x : p + x)
  return <div className="winos-app" style={{ padding: 10, background: '#f3f3f3' }}><div style={{ textAlign: 'right', fontSize: 28, padding: 14, background: '#fff', marginBottom: 8 }}>{v}</div><div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 6 }}>{['C','/','*','-','7','8','9','+','4','5','6','.','1','2','3','=','0'].map((b) => <button key={b} className="winos-btn" style={{ height: 42, justifyContent: 'center' }} onClick={() => press(b)}>{b}</button>)}</div></div>
}

export function WordPad() {
  const [text, setText] = useState('Rich text document\n\nUse the toolbar to format this document.')
  return <div className="winos-app"><div className="winos-toolbar"><button className="winos-btn"><b>B</b></button><button className="winos-btn"><i>I</i></button><button className="winos-btn"><u>U</u></button><select className="winos-input"><option>Calibri</option><option>Segoe UI</option><option>Consolas</option></select><select className="winos-input"><option>11</option><option>14</option><option>18</option></select></div><textarea value={text} onChange={(e) => setText(e.target.value)} style={{ flex: 1, border: 0, outline: 0, padding: 24, fontFamily: 'Calibri, Segoe UI, sans-serif', fontSize: 16 }} /></div>
}

export function Paint() {
  const [color, setColor] = useState('#0078d4')
  const [marks, setMarks] = useState([])
  return <div className="winos-app"><div className="winos-toolbar"><Palette size={14} /><input type="color" value={color} onChange={(e) => setColor(e.target.value)} /><button className="winos-btn" onClick={() => setMarks([])}>Clear</button><span>Pencil · Fill · Text · Shapes · Eraser</span></div><div style={{ flex: 1, background: '#ddd', padding: 16 }}><div onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMarks((m) => [...m, { x: e.clientX - r.left, y: e.clientY - r.top, color }]) }} style={{ height: '100%', background: '#fff', border: '1px solid #aaa', position: 'relative' }}>{marks.map((m, i) => <span key={i} style={{ position: 'absolute', left: m.x, top: m.y, width: 8, height: 8, background: m.color, borderRadius: 8 }} />)}</div></div></div>
}

function TreeLine({ d, label, open }) {
  return <div className="winos-tree-row" style={{ paddingLeft: 8 + d * 14 }}><ChevronRight size={12} style={{ transform: open ? 'rotate(90deg)' : '' }} />📁 {label}</div>
}

function Panel({ title, children }) {
  return <div className="winos-card" style={{ marginBottom: 12 }}><div className="winos-card-h">{title}</div><div style={{ padding: 10 }}>{children}</div></div>
}

function Action({ children, onClick }) {
  return <div style={{ color: '#06c', padding: '4px 0', cursor: 'default' }} onClick={onClick}>{children}</div>
}
