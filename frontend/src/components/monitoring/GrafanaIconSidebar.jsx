import {
  Home, LayoutGrid, Compass, Bell, Plug, Settings, HelpCircle, ChevronRight,
} from 'lucide-react'

const NAV = [
  { key: 'home', icon: Home, label: 'Home', tooltip: 'Home' },
  { key: 'dashboards', icon: LayoutGrid, label: 'Dashboards', tooltip: 'Dashboards', children: ['Browse', 'Playlists', 'Snapshots', 'Library panels'] },
  { key: 'explore', icon: Compass, label: 'Explore', tooltip: 'Explore' },
  { key: 'alerting', icon: Bell, label: 'Alerting', tooltip: 'Alerting', children: ['Alert rules', 'Contact points', 'Notification policies', 'Silences'] },
  { key: 'connections', icon: Plug, label: 'Connections', tooltip: 'Connections', children: ['Data sources', 'Plugins'] },
  { key: 'admin', icon: Settings, label: 'Administration', tooltip: 'Administration', children: ['Users', 'Teams', 'Settings'] },
]

export default function GrafanaIconSidebar({ active, onSelect, expanded, onToggleExpand, onChildSelect }) {
  return (
    <aside className="w-14 lg:w-52 shrink-0 bg-[#0b0c1e] border-r border-[#262a45] flex flex-col py-2">
      <div className="px-2 mb-2 flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-[#f7913b]/20 flex items-center justify-center shrink-0" title="Grafana">
          <span className="text-[#f7913b] font-bold text-sm">G</span>
        </div>
        {expanded && <span className="text-sm font-semibold text-white hidden lg:inline">Grafana</span>}
      </div>
      {NAV.map(({ key, icon: Icon, label, tooltip, children }) => (
        <div key={key}>
          <button type="button" title={tooltip} onClick={() => { onSelect(key); onToggleExpand?.(key) }}
            className={`w-full flex items-center gap-2 px-2 lg:px-3 py-2.5 text-left text-sm ${active === key ? 'bg-white/10 text-[#f7913b]' : 'text-[#8a93b2] hover:bg-white/5 hover:text-white'}`}>
            <Icon size={18} className="shrink-0 mx-auto lg:mx-0" />
            <span className="hidden lg:inline truncate">{label}</span>
            {children && expanded && <ChevronRight size={12} className="ml-auto hidden lg:inline opacity-50" />}
          </button>
          {children && expanded === key && (
            <div className="hidden lg:block pl-10 pb-1">
              {children.map((c) => (
                <button key={c} type="button" onClick={() => onChildSelect?.(key, c)}
                  className="block w-full text-left text-xs py-1 text-[#8a93b2] hover:text-white">{c}</button>
              ))}
            </div>
          )}
        </div>
      ))}
      <div className="mt-auto px-2 pt-2 border-t border-[#262a45]">
        <button type="button" title="Help" className="w-full flex items-center justify-center lg:justify-start gap-2 py-2 text-[#8a93b2] hover:text-white">
          <HelpCircle size={18} /><span className="hidden lg:inline text-sm">Help</span>
        </button>
      </div>
    </aside>
  )
}
