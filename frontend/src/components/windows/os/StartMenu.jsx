import { useMemo, useState } from 'react'
import { Power, Settings, FileText, User, Search } from 'lucide-react'
import { useOS } from './store'
import { APPS, AppIcon } from './apps/registry'

const PINNED = [
  { app: 'ServerManager', label: 'Server Manager', large: true },
  { app: 'Terminal', label: 'Windows PowerShell', props: { shell: 'ps' } },
  { app: 'TaskManager', label: 'Task Manager' },
  { app: 'EventViewer', label: 'Event Viewer' },
  { app: 'ComputerManagement', label: 'Computer Management' },
  { app: 'Services', label: 'Services' },
  { app: 'RegistryEditor', label: 'Registry Editor' },
  { app: 'ADUC', label: 'AD Users & Computers' },
  { app: 'GPMC', label: 'Group Policy' },
  { app: 'IISManager', label: 'IIS Manager' },
  { app: 'Notepad', label: 'Notepad' },
]

// Full A–Z app catalog
const CATALOG = [
  ['Active Directory Users and Computers', 'ADUC'],
  ['Command Prompt', 'Terminal', { shell: 'cmd' }],
  ['Computer Management', 'ComputerManagement'],
  ['Control Panel', 'ControlPanel'],
  ['Calculator', 'Calculator'],
  ['DHCP Manager', 'DHCPManager'],
  ['Device Manager', 'DeviceManager'],
  ['Disk Management', 'DiskManagement'],
  ['DNS Manager', 'DNSManager'],
  ['Event Viewer', 'EventViewer'],
  ['File Explorer', 'FileExplorer', { path: 'This PC' }],
  ['Group Policy Management', 'GPMC'],
  ['Hyper-V Manager', 'HyperV'],
  ['Internet Information Services (IIS) Manager', 'IISManager'],
  ['Network Connections', 'NetworkConnections'],
  ['Notepad', 'Notepad'],
  ['Paint', 'Paint'],
  ['Performance Monitor', 'PerformanceMonitor'],
  ['Registry Editor', 'RegistryEditor'],
  ['Server Manager', 'ServerManager'],
  ['Services', 'Services'],
  ['Settings', 'Settings'],
  ['System Information', 'SystemInformation'],
  ['Task Manager', 'TaskManager'],
  ['Task Scheduler', 'TaskScheduler'],
  ['Windows Defender Firewall with Advanced Security', 'FirewallAdvanced'],
  ['Windows PowerShell', 'Terminal', { shell: 'ps' }],
  ['WordPad', 'WordPad'],
]

export default function StartMenu() {
  const os = useOS()
  const [allApps, setAllApps] = useState(false)
  const [q, setQ] = useState('')

  const launch = (app, props, title) => { os.openApp(app, props || {}, { title: title || APPS[app]?.title }); os.setStartOpen(false) }

  const grouped = useMemo(() => {
    const filtered = CATALOG.filter(([label]) => label.toLowerCase().includes(q.toLowerCase()))
    const g = {}
    filtered.forEach((item) => { const L = item[0][0].toUpperCase(); (g[L] = g[L] || []).push(item) })
    return Object.entries(g).sort()
  }, [q])

  return (
    <div className="winos-startmenu" onMouseDown={(e) => e.stopPropagation()}>
      <div className="winos-sm-left">
        <div className="winos-sm-btn" title="Administrator"><User size={20} /></div>
        <div className="sp" />
        <div className="winos-sm-btn" onClick={() => launch('FileExplorer', { path: 'This PC' }, 'This PC')} title="File Explorer"><FileText size={20} /></div>
        <div className="winos-sm-btn" onClick={() => launch('Settings')} title="Settings"><Settings size={20} /></div>
        <PowerBtn />
      </div>
      <div className="winos-sm-main">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Search size={15} color="#9a9a9a" />
          <input className="winos-sm-search" style={{ flex: 1 }} placeholder="Type here to search" value={q} onChange={(e) => { setQ(e.target.value); setAllApps(true) }} autoFocus />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '4px 0' }}>
          <div className="winos-sm-section" style={{ margin: 0 }}>{allApps ? 'All apps' : 'Pinned'}</div>
          <span style={{ fontSize: 11, color: '#9ad1ff', cursor: 'default' }} onClick={() => { setAllApps(!allApps); setQ('') }}>{allApps ? 'Pinned ›' : 'All apps ›'}</span>
        </div>
        <div className="winos-sm-scroll">
          {!allApps ? (
            <div className="winos-tiles">
              {PINNED.map((p) => (
                <div key={p.label + p.app} className={`winos-tile ${p.large ? '' : 'sm'}`} onClick={() => launch(p.app, p.props, p.label)} style={p.large ? { gridColumn: 'span 2', height: 84 } : undefined}>
                  <AppIcon app={p.app} size={22} />
                  <div className="tt">{p.label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="winos-applist">
              {grouped.map(([letter, items]) => (
                <div key={letter}>
                  <div className="ltr">{letter}</div>
                  {items.map((it) => (
                    <div key={it[0]} className="ai" onClick={() => launch(it[1], it[2], it[0])}><AppIcon app={it[1]} size={18} />{it[0]}</div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function PowerBtn() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ position: 'relative' }}>
      <div className="winos-sm-btn" title="Power" onClick={() => setOpen((o) => !o)}><Power size={20} /></div>
      {open && (
        <div className="winos-ctx" style={{ position: 'absolute', bottom: 0, left: 48, width: 140 }} onMouseLeave={() => setOpen(false)}>
          <div className="winos-ctx-item">Sleep</div>
          <div className="winos-ctx-item">Shut down</div>
          <div className="winos-ctx-item">Restart</div>
        </div>
      )}
    </div>
  )
}
