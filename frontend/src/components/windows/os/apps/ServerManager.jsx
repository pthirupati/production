import { useState } from 'react'
import { LayoutDashboard, Server, Database, Network, HardDrive, Globe, Box } from 'lucide-react'
import { useOS } from '../store'
import { Dialog } from '../ui'

const NAV = [
  { id: 'Dashboard', icon: <LayoutDashboard size={15} /> },
  { id: 'Local Server', icon: <Server size={15} /> },
  { id: 'All Servers', icon: <Server size={15} /> },
  { id: 'AD DS', icon: <Database size={15} /> },
  { id: 'DHCP', icon: <Network size={15} /> },
  { id: 'DNS', icon: <Globe size={15} /> },
  { id: 'File and Storage Services', icon: <HardDrive size={15} /> },
  { id: 'Hyper-V', icon: <Box size={15} /> },
  { id: 'IIS', icon: <Globe size={15} /> },
]

export default function ServerManager() {
  const os = useOS()
  const [nav, setNav] = useState('Dashboard')
  const [menu, setMenu] = useState(null)
  const [wizard, setWizard] = useState(false)
  const installed = os.roles.filter((r) => r.installed)

  return (
    <div className="winos-app">
      <div className="winos-toolbar" style={{ background: '#2d2d30', color: '#fff', borderColor: '#1b1b1b' }}>
        <strong>Server Manager</strong>
        <span style={{ flex: 1 }} />
        {['Manage', 'Tools', 'View', 'Help'].map((m) => (
          <div key={m} style={{ position: 'relative' }}>
            <span style={{ padding: '4px 10px', cursor: 'default', background: menu === m ? '#3f3f46' : 'transparent' }} onClick={() => setMenu(menu === m ? null : m)}>{m}</span>
            {menu === m && m === 'Manage' && (
              <div className="winos-ctx" style={{ position: 'absolute', top: 26, right: 0 }} onMouseLeave={() => setMenu(null)}>
                <div className="winos-ctx-item" onClick={() => { setWizard(true); setMenu(null) }}>Add Roles and Features</div>
                <div className="winos-ctx-item">Remove Roles and Features</div>
                <div className="winos-ctx-item">Add Servers</div>
                <div className="winos-ctx-item">Create Server Group</div>
              </div>
            )}
            {menu === m && m === 'Tools' && (
              <div className="winos-ctx" style={{ position: 'absolute', top: 26, right: 0, maxHeight: 320, overflow: 'auto' }} onMouseLeave={() => setMenu(null)}>
                {[['Active Directory Users and Computers', 'ADUC'], ['DHCP', 'DHCPManager'], ['DNS', 'DNSManager'], ['Group Policy Management', 'GPMC'], ['Internet Information Services (IIS) Manager', 'IISManager'], ['Windows Defender Firewall with Advanced Security', 'FirewallAdvanced'], ['Computer Management', 'ComputerManagement'], ['Disk Management', 'DiskManagement'], ['Event Viewer', 'EventViewer'], ['Performance Monitor', 'PerformanceMonitor'], ['Services', 'Services'], ['Task Scheduler', 'TaskScheduler'], ['Task Manager', 'TaskManager'], ['Device Manager', 'DeviceManager'], ['Registry Editor', 'RegistryEditor'], ['Windows PowerShell', 'Terminal'], ['System Information', 'SystemInformation'], ['Control Panel', 'ControlPanel']].map(([label, app]) => (
                  <div key={app} className="winos-ctx-item" onClick={() => { os.openApp(app, app === 'Terminal' ? { shell: 'ps' } : {}, { title: label }); setMenu(null) }}>{label}</div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 200, background: '#f0f0f0' }}>
          {NAV.map((n) => (
            <div key={n.id} className={`winos-tree-row ${nav === n.id ? 'sel' : ''}`} style={{ padding: '8px 10px' }} onClick={() => setNav(n.id)}>{n.icon} {n.id}</div>
          ))}
        </div>
        <div className="winos-main" style={{ padding: 16, background: '#f7f7f7' }}>
          {nav === 'Dashboard' && (
            <div>
              <div className="winos-card" style={{ marginBottom: 16, background: 'linear-gradient(90deg,#0078d4,#2b88d8)', color: '#fff' }}>
                <div style={{ padding: 16 }}>
                  <div style={{ fontSize: 16, marginBottom: 8 }}>Welcome to Server Manager</div>
                  <div style={{ fontSize: 12, opacity: 0.9 }}>1. Configure this local server &nbsp;·&nbsp; 2. Add roles and features &nbsp;·&nbsp; 3. Add other servers to manage</div>
                </div>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>ROLES AND SERVER GROUPS</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
                {installed.map((r) => (
                  <div key={r.id} className="winos-card">
                    <div className="winos-card-h" style={{ background: '#5a8fc7', color: '#fff' }}>{r.name} <span style={{ float: 'right' }}>1</span></div>
                    <div style={{ padding: '8px 12px', fontSize: 12 }}>
                      <Row label="Manageability" val="●" color="#107c10" />
                      <Row label="Events" val={r.events} color={r.events ? '#9d5d00' : '#666'} />
                      <Row label="Services" val={r.services ? `${r.services} stopped` : 'OK'} color={r.services ? '#c42b1c' : '#107c10'} />
                      <Row label="Performance" val={r.perf} color="#107c10" />
                      <Row label="BPA results" val={r.bpa} color={r.bpa ? '#9d5d00' : '#666'} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {nav === 'Local Server' && <LocalServer os={os} />}
          {nav === 'All Servers' && (
            <div className="winos-card"><div className="winos-card-h">SERVERS · All servers | 1 total</div>
              <table className="winos-table"><thead><tr><th>Server Name</th><th>IPv4 Address</th><th>Manageability</th><th>Last Update</th><th>Windows Activation</th></tr></thead>
                <tbody><tr><td>SERVER01</td><td>192.168.10.50, 10.0.0.50</td><td>Online - Performance counters not started</td><td>1/17/2024 11:30:42 AM</td><td>00454-20000 (Activated)</td></tr></tbody></table>
            </div>
          )}
          {['AD DS', 'DHCP', 'DNS', 'File and Storage Services', 'Hyper-V', 'IIS'].includes(nav) && (
            <div className="winos-card"><div className="winos-card-h">{nav} · SERVERS | 1 total</div>
              <table className="winos-table"><thead><tr><th>Server Name</th><th>IPv4 Address</th><th>Manageability</th><th>Last Update</th></tr></thead>
                <tbody><tr><td>SERVER01</td><td>192.168.10.50</td><td>Online</td><td>1/17/2024 11:30:42 AM</td></tr></tbody></table>
              <div style={{ padding: 12, fontSize: 12, color: '#555' }}>
                {nav === 'DNS' && <button className="winos-btn" onClick={() => os.openApp('DNSManager', {}, { title: 'DNS Manager' })}>Open DNS Manager</button>}
                {nav === 'DHCP' && <span>IPv4 scope 192.168.10.0 — 80 active leases. Use Tools → DHCP for full management.</span>}
                {nav === 'Hyper-V' && <button className="winos-btn" onClick={() => os.openApp('HyperV', {}, { title: 'Hyper-V Manager' })}>Open Hyper-V Manager</button>}
                {nav === 'AD DS' && <button className="winos-btn" onClick={() => os.openApp('ADUC', {}, { title: 'Active Directory Users and Computers' })}>Open ADUC</button>}
              </div>
            </div>
          )}
        </div>
      </div>
      {wizard && <AddRolesWizard onClose={() => setWizard(false)} />}
    </div>
  )
}

const Row = ({ label, val, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid #f0f0f0' }}>
    <span>{label}</span><span style={{ color }}>{val}</span>
  </div>
)

function LocalServer({ os }) {
  const rows = [
    ['Computer name', os.computer.name], ['Domain', os.computer.domain],
    ['Windows Firewall', 'Domain: Active'], ['Remote management', 'Enabled'], ['Remote Desktop', 'Enabled'],
    ['NIC Teaming', 'Disabled'], ['Ethernet0', '192.168.10.50, IPv6 enabled'], ['Ethernet1', '10.0.0.50'],
    ['Operating system version', 'Microsoft Windows Server 2022 Standard Evaluation'], ['Hardware information', 'VMware, Inc. VMware Virtual Platform'],
    ['Last installed updates', '1/15/2024'], ['Windows Update', 'Download updates only, using Windows Update'],
    ['Windows Defender Antivirus', 'Real-Time Protection: On'], ['Windows Error Reporting', 'Off'],
    ['IE Enhanced Security Configuration', 'On'], ['Time zone', '(UTC-05:00) Eastern Time (US & Canada)'],
    ['Product ID', os.computer.productId], ['Processors', os.computer.cpu], ['Installed memory (RAM)', `${os.computer.ramGB} GB`],
    ['Total disk space', '756.0 GB'],
  ]
  return (
    <div className="winos-card"><div className="winos-card-h">PROPERTIES · For SERVER01</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', padding: 12, gap: '6px 24px', fontSize: 12 }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f1f1f1', padding: '3px 0' }}>
            <span style={{ color: '#666' }}>{k}</span><span style={{ color: '#06c', textAlign: 'right', maxWidth: '60%' }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const ALL_ROLES = [
  'Active Directory Certificate Services', 'Active Directory Domain Services', 'Active Directory Federation Services',
  'Active Directory Lightweight Directory Services', 'Active Directory Rights Management Services', 'Device Health Attestation',
  'DHCP Server', 'DNS Server', 'Fax Server', 'File and Storage Services', 'Host Guardian Service', 'Hyper-V',
  'Network Controller', 'Network Policy and Access Services', 'Print and Document Services', 'Remote Access',
  'Remote Desktop Services', 'Volume Activation Services', 'Web Server (IIS)', 'Windows Deployment Services',
  'Windows Server Update Services',
]

function AddRolesWizard({ onClose }) {
  const os = useOS()
  const [page, setPage] = useState(1)
  const [checked, setChecked] = useState(() => new Set(os.roles.filter((r) => r.installed).map((r) => r.name)))
  const [installing, setInstalling] = useState(false)
  const [done, setDone] = useState(false)
  const pages = ['Before You Begin', 'Installation Type', 'Server Selection', 'Server Roles', 'Features', 'Confirmation', 'Results']

  const toggle = (r) => setChecked((s) => { const n = new Set(s); n.has(r) ? n.delete(r) : n.add(r); return n })
  const newRoles = [...checked].filter((r) => !os.roles.find((x) => x.name === r && x.installed))

  const install = async () => {
    setInstalling(true)
    try {
      for (const rn of newRoles) {
        const role = os.roles.find((r) => r.name === rn)
        if (!role) continue
        if (os.labAction) {
          await os.labAction('install_role', { role: role.id })
        }
        os.setRoleInstalled(role.id, true)
      }
      setDone(true)
      setPage(7)
    } finally {
      setInstalling(false)
    }
  }

  return (
    <Dialog title="Add Roles and Features Wizard" onClose={onClose} width={640}
      footer={<>
        <span style={{ flex: 1, fontSize: 11, color: '#888', alignSelf: 'center' }}>{pages[page - 1]}</span>
        {page > 1 && page < 7 && <button className="winos-btn" onClick={() => setPage(page - 1)}>&lt; Previous</button>}
        {page < 6 && <button className="winos-btn primary" onClick={() => setPage(page + 1)}>Next &gt;</button>}
        {page === 6 && <button className="winos-btn primary" disabled={installing} onClick={install}>{installing ? 'Installing…' : 'Install'}</button>}
        {page === 7 && <button className="winos-btn primary" onClick={onClose}>Close</button>}
        {page < 7 && <button className="winos-btn" onClick={onClose}>Cancel</button>}
      </>}>
      <div style={{ display: 'flex', gap: 14, minHeight: 320 }}>
        <div style={{ width: 160, flex: 'none', fontSize: 12 }}>
          {pages.map((p, i) => (
            <div key={p} style={{ padding: '5px 8px', color: page === i + 1 ? '#0078d4' : '#666', fontWeight: page === i + 1 ? 600 : 400 }}>{p}</div>
          ))}
        </div>
        <div style={{ flex: 1, fontSize: 12.5, borderLeft: '1px solid #eee', paddingLeft: 14 }}>
          {page === 1 && <p>This wizard helps you install roles, role services, or features. You determine which roles, role services, or features to install based on the computing needs of your organization.</p>}
          {page === 2 && <>
            <p style={{ fontWeight: 600 }}>Select the installation type.</p>
            <label style={{ display: 'block', marginTop: 8 }}><input type="radio" name="it" defaultChecked /> Role-based or feature-based installation</label>
            <label style={{ display: 'block', marginTop: 6 }}><input type="radio" name="it" /> Remote Desktop Services installation</label>
          </>}
          {page === 3 && <>
            <p style={{ fontWeight: 600 }}>Select a server from the server pool.</p>
            <div style={{ border: '1px solid #ddd', marginTop: 8 }}>
              <table className="winos-table"><thead><tr><th>Name</th><th>IP Address</th><th>Operating System</th></tr></thead>
                <tbody><tr className="sel"><td>SERVER01.lab.local</td><td>192.168.10.50</td><td>Windows Server 2022 Standard Eval</td></tr></tbody></table>
            </div>
          </>}
          {page === 4 && <>
            <p style={{ fontWeight: 600 }}>Select one or more roles to install.</p>
            <div style={{ border: '1px solid #ddd', height: 250, overflow: 'auto', marginTop: 6 }}>
              {ALL_ROLES.map((r) => {
                const inst = os.roles.find((x) => x.name === r && x.installed)
                return (
                  <label key={r} style={{ display: 'block', padding: '3px 8px' }}>
                    <input type="checkbox" checked={checked.has(r)} disabled={inst} onChange={() => toggle(r)} /> {r} {inst && <span style={{ color: '#888', fontSize: 11 }}>(Installed)</span>}
                  </label>
                )
              })}
            </div>
          </>}
          {page === 5 && <>
            <p style={{ fontWeight: 600 }}>Select one or more features to install.</p>
            <div style={{ border: '1px solid #ddd', height: 250, overflow: 'auto', marginTop: 6 }}>
              {['.NET Framework 3.5 Features', '.NET Framework 4.8 Features', 'BitLocker Drive Encryption', 'Data Center Bridging', 'Failover Clustering', 'Group Policy Management', 'Network Load Balancing', 'Remote Server Administration Tools', 'SMB 1.0/CIFS File Sharing Support', 'SNMP Service', 'Telnet Client', 'Windows PowerShell', 'Windows Server Backup', 'WoW64 Support'].map((feat) => (
                <label key={feat} style={{ display: 'block', padding: '3px 8px' }}><input type="checkbox" defaultChecked={['Group Policy Management', '.NET Framework 4.8 Features', 'Windows PowerShell', 'WoW64 Support', 'Remote Server Administration Tools'].includes(feat)} /> {feat}</label>
              ))}
            </div>
          </>}
          {page === 6 && <>
            <p style={{ fontWeight: 600 }}>Confirm installation selections.</p>
            <label style={{ display: 'block', margin: '8px 0' }}><input type="checkbox" /> Restart the destination server automatically if required</label>
            <div style={{ border: '1px solid #ddd', padding: 10, minHeight: 120 }}>
              {newRoles.length ? newRoles.map((r) => <div key={r}>• {r}</div>) : <span style={{ color: '#888' }}>No new roles selected. Select roles on the Server Roles page.</span>}
            </div>
          </>}
          {page === 7 && <>
            <p style={{ fontWeight: 600 }}>Installation progress</p>
            {newRoles.length === 0 ? <p>No changes were made.</p> : newRoles.map((r) => (
              <div key={r} style={{ marginTop: 8 }}>
                <div>{r}</div>
                <div style={{ height: 8, background: '#e6e6e6', borderRadius: 3, overflow: 'hidden' }}><div style={{ width: '100%', height: '100%', background: '#107c10' }} /></div>
                <div style={{ color: '#107c10', fontSize: 11 }}>Installation succeeded</div>
              </div>
            ))}
          </>}
        </div>
      </div>
    </Dialog>
  )
}
