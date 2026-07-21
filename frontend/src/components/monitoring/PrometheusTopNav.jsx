/** Prometheus classic top navigation */
export default function PrometheusTopNav({ active, onSelect, statusSub, onStatusSelect }) {
  const items = [
    { key: 'alerts', label: 'Alerts' },
    { key: 'graph', label: 'Graph' },
    { key: 'status', label: 'Status', dropdown: ['Runtime & Build', 'TSDB Status', 'Configuration', 'Flags', 'Rules', 'Targets', 'Service Discovery', 'Exporters'] },
    { key: 'help', label: 'Help' },
  ]
  const statusKeys = {
    'Runtime & Build': 'runtime',
    'TSDB Status': 'tsdb',
    Configuration: 'configuration',
    Flags: 'flags',
    Rules: 'rules',
    Targets: 'targets',
    'Service Discovery': 'service-discovery',
    Exporters: 'exporters',
  }
  return (
    <nav className="flex items-center gap-1 px-4 py-2 bg-white border-b border-gray-200 text-sm">
      <span className="font-bold text-[#e6522c] mr-4 flex items-center gap-1">
        <span className="w-6 h-6 rounded-full bg-[#e6522c]/15 flex items-center justify-center text-xs">P</span>
        Prometheus
      </span>
      {items.map((item) => (
        <div key={item.key} className="relative group">
          <button type="button" onClick={() => onSelect(item.key)}
            className={`px-3 py-1.5 rounded ${active === item.key ? 'bg-gray-100 font-semibold text-gray-900' : 'text-gray-600 hover:bg-gray-50'}`}>
            {item.label}
          </button>
          {item.dropdown && active === 'status' && (
            <div className="absolute left-0 top-full mt-0.5 z-20 min-w-[180px] bg-white border border-gray-200 rounded shadow-lg py-1 hidden group-hover:block">
              {item.dropdown.map((d) => (
                <button key={d} type="button"
                  onClick={() => { onSelect('status'); onStatusSelect?.(statusKeys[d] || 'targets') }}
                  className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 ${statusSub === statusKeys[d] ? 'font-semibold text-gray-900 bg-gray-50' : 'text-gray-600'}`}>
                  {d}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
      <span className="ml-auto text-xs text-gray-400">v2.51.0</span>
    </nav>
  )
}
