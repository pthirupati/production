import { Terminal, X } from 'lucide-react'
import LabTerminal from '../../LabTerminal'

/**
 * Split layout: simulator on top, optional lab terminal panel at bottom.
 * Toggle via lab chrome "Terminal" / onExit handler from LabRunner.
 */
export default function SimWithTerminal({
  open = false,
  onToggle,
  terminalSession,
  terminalHost = 'primary',
  blockedCommands = [],
  isMobile = false,
  children,
}) {
  return (
    <div className="flex flex-col flex-1 min-h-0 h-full w-full overflow-hidden">
      <div className={`flex flex-col min-h-0 overflow-hidden ${open ? 'flex-1' : 'flex-1'}`}>
        {children}
      </div>
      {open && (
        <div className="shrink-0 flex flex-col border-t border-surface-700 bg-surface-950 h-[min(42vh,400px)] min-h-[180px]">
          <div className="shrink-0 flex items-center justify-between gap-2 px-3 py-1.5 bg-surface-900 border-b border-surface-800">
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-surface-300">
              <Terminal size={13} className="text-accent-cyan" />
              Lab terminal — run commands (terraform apply, vim configs, etc.)
            </span>
            <button
              type="button"
              onClick={onToggle}
              className="inline-flex items-center gap-1 text-[10px] text-surface-500 hover:text-white px-2 py-1 rounded border border-surface-700 hover:border-surface-500"
            >
              <X size={12} /> Hide terminal
            </button>
          </div>
          <div className="flex-1 min-h-0">
            {terminalSession ? (
              <LabTerminal
                session={terminalSession}
                host={terminalHost}
                blockedCommands={blockedCommands}
                isMobile={isMobile}
              />
            ) : (
              <div className="flex h-full items-center justify-center px-4 text-center text-sm text-surface-500">
                Waiting for lab terminal — provisioning may still be in progress.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
