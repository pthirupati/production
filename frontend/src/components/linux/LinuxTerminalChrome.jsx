import { useEffect, useState } from 'react'
import { Plus, X } from 'lucide-react'

/**
 * Tab strip + 24px status bar for simulated Linux guests (VMware console / SSH).
 * Tabs are independent shell sessions; status reflects the active session.
 */
export function LinuxTerminalTabs({ tabs, activeId, onSelect, onClose, onNew, maxTabs = 6 }) {
  if (!tabs?.length) return null
  return (
    <div className="linux-term-tabs shrink-0 flex items-stretch gap-0.5 px-2 py-1 bg-[#0d1117] border-b border-[#2D3A4A] overflow-x-auto">
      {tabs.map((tab) => {
        const active = tab.id === activeId
        return (
          <div
            key={tab.id}
            className={`linux-term-tab group flex items-center gap-1.5 px-2.5 py-1 rounded-t text-[11px] font-mono cursor-pointer shrink-0 border border-b-0 ${
              active
                ? 'bg-[#05090f] text-[#E8EDF2] border-[#2D3A4A]'
                : 'bg-[#1B2A3B] text-[#8FA5B8] border-transparent hover:text-[#cdd7e1]'
            }`}
            onClick={() => onSelect(tab.id)}
            title={tab.title}
          >
            <span className="truncate max-w-[120px]">{tab.label}</span>
            {tabs.length > 1 && (
              <button
                type="button"
                className="opacity-50 group-hover:opacity-100 hover:text-white p-0.5 rounded"
                onClick={(e) => { e.stopPropagation(); onClose(tab.id) }}
                aria-label={`Close ${tab.label}`}
              >
                <X size={10} />
              </button>
            )}
          </div>
        )
      })}
      {tabs.length < maxTabs && (
        <button
          type="button"
          className="flex items-center justify-center min-h-[44px] min-w-[44px] w-11 h-11 rounded text-[#8FA5B8] hover:text-white hover:bg-[#2D3A4A] shrink-0"
          onClick={onNew}
          title="New terminal tab"
          aria-label="New terminal tab"
        >
          <Plus size={14} />
        </button>
      )}
    </div>
  )
}

export function LinuxTerminalStatusBar({ status, hint }) {
  const s = status || {}
  const clock = s.clock || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  return (
    <div className="linux-term-status shrink-0 h-6 min-h-[24px] flex items-center gap-2 px-3 bg-[#0d1117] border-t border-[#2D3A4A] text-[10px] font-mono text-[#8FA5B8] overflow-hidden">
      <span className="truncate shrink-0" title="Server">
        <span className="text-[#5DB85D]">Server:</span> {s.hostname || 'linux-guest'}
      </span>
      <span className="text-[#2D3A4A]">|</span>
      <span className="truncate shrink-0" title="User">
        <span className="text-[#5DB85D]">User:</span> {s.user || 'root'}
      </span>
      <span className="text-[#2D3A4A] hidden sm:inline">|</span>
      <span className="truncate hidden sm:inline max-w-[180px]" title="Working directory">
        <span className="text-[#5DB85D]">CWD:</span> {s.cwd || '/'}
      </span>
      <span className="flex-1 hidden md:flex items-center justify-center gap-3 truncate text-center">
        <span title="Load average">Load: {s.load || '0.23 0.18 0.12'}</span>
        <span className="text-[#2D3A4A]">|</span>
        <span title="Memory">Mem: {s.mem || '—'}</span>
        <span className="text-[#2D3A4A]">|</span>
        <span title="Root disk">Disk: {s.disk || '—'}</span>
      </span>
      <span className="ml-auto flex items-center gap-2 shrink-0">
        {s.uptime && <span className="hidden lg:inline" title="Uptime">Up: {s.uptime}</span>}
        <span title="Clock">{clock}</span>
      </span>
      {hint && <span className="hidden xl:inline text-[#5d7a93] truncate max-w-[200px] ml-2">{hint}</span>}
    </div>
  )
}

/** Status bar for backend WebSocket terminals (LabRunner) — mirrors guest chrome without shell hooks. */
export function LabBackendTerminalStatusBar({ host, hint }) {
  const [clock, setClock] = useState(() =>
    new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  )
  useEffect(() => {
    const id = setInterval(() => {
      setClock(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }, 1000)
    return () => clearInterval(id)
  }, [])
  const name = host?.hostname || host?.name || 'rhel-server-01'
  const hostname = name === 'primary' ? 'rhel-server-01' : String(host?.role || name).replace(/\s+/g, '-').toLowerCase()
  const user = host?.ssh_user || 'root'
  return (
    <LinuxTerminalStatusBar
      status={{
        hostname,
        user,
        cwd: user === 'labuser' ? '/home/labuser' : '/root',
        load: '0.23 0.18 0.12',
        mem: '3.2G/16G',
        disk: '45G/500G',
        uptime: '14d 3h 22m',
        clock,
      }}
      hint={hint}
    />
  )
}
