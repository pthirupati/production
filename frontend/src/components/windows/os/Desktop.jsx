import { useState } from 'react'
import { Monitor, Trash2, Network, Server, MonitorCog, User } from 'lucide-react'
import { useOS } from './store'
import { useCtxMenu } from './ui'

const ICONS = [
  { id: 'thispc', label: 'This PC', icon: <Monitor size={34} color="#dbe7f5" />, open: (os) => os.openApp('FileExplorer', { path: 'This PC' }, { title: 'This PC' }) },
  { id: 'recycle', label: 'Recycle Bin', icon: <Trash2 size={34} color="#dbe7f5" />, open: (os) => os.openApp('FileExplorer', { path: 'C:\\$Recycle.Bin' }, { title: 'Recycle Bin' }) },
  { id: 'network', label: 'Network', icon: <Network size={34} color="#dbe7f5" />, open: (os) => os.openApp('FileExplorer', { path: 'Network' }, { title: 'Network' }) },
  { id: 'cpl', label: 'Control Panel', icon: <MonitorCog size={34} color="#dbe7f5" />, open: (os) => os.openApp('ControlPanel', {}, { title: 'Control Panel' }) },
  { id: 'admin', label: 'Administrator', icon: <User size={34} color="#dbe7f5" />, open: (os) => os.openApp('FileExplorer', { path: 'C:\\Users\\Administrator' }, { title: 'Administrator' }) },
  { id: 'srvmgr', label: 'Server Manager', icon: <Server size={34} color="#dbe7f5" />, open: (os) => os.openApp('ServerManager', {}, { title: 'Server Manager' }) },
]

export default function Desktop() {
  const os = useOS()
  const ctx = useCtxMenu()
  const [sel, setSel] = useState(null)

  const onCtx = (e) => {
    e.preventDefault()
    ctx.open(e.clientX, e.clientY, [
      { label: 'View', sub: [{ label: 'Large icons' }, { label: 'Medium icons', right: '●' }, { label: 'Small icons' }, { sep: true }, { label: 'Auto arrange icons' }, { label: 'Align icons to grid' }, { sep: true }, { label: 'Show desktop icons', right: '✓' }] },
      { label: 'Sort by', sub: [{ label: 'Name' }, { label: 'Size' }, { label: 'Item type' }, { label: 'Date modified' }] },
      { label: 'Refresh' },
      { sep: true },
      { label: 'New', sub: [{ label: 'Folder' }, { label: 'Shortcut' }, { label: 'Text Document' }, { label: 'Compressed (zipped) Folder' }] },
      { sep: true },
      { label: 'Display settings', onClick: () => os.openApp('Settings', { page: 'System' }, { title: 'Settings' }) },
      { label: 'Personalize', onClick: () => os.openApp('Settings', { page: 'Personalization' }, { title: 'Settings' }) },
    ])
  }

  return (
    <div className="winos-desktop" onContextMenu={onCtx} onMouseDown={() => { setSel(null); os.setStartOpen(false) }}>
      <div className="winos-icons">
        {ICONS.map((ic) => (
          <div key={ic.id} className={`winos-icon ${sel === ic.id ? 'sel' : ''}`}
            onMouseDown={(e) => { e.stopPropagation(); setSel(ic.id) }}
            onDoubleClick={() => ic.open(os)}>
            <div className="ic">{ic.icon}</div>
            <div className="lbl">{ic.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
