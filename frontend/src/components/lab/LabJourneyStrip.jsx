import { ExternalLink, Terminal, Server, Gauge, Layers } from 'lucide-react'

/**
 * Compact cross-tool lab journey strip — Terminal · vCenter · Grafana · AWX.
 */
export default function LabJourneyStrip({
  sessionId,
  scenarioSlug = '',
  showTerminal = true,
  showVmware = false,
  showGrafana = false,
  showAwx = false,
  terminalActive = true,
  vmwareHref = null,
  onOpenGrafana,
  onOpenAwx,
  guideText = '',
  className = '',
}) {
  const vmHref = vmwareHref || `/vmware/${sessionId}?scenario=${scenarioSlug}`

  const Item = ({ active, children, href, onClick, title }) => {
    const cls = `inline-flex items-center gap-1 px-2 py-1 rounded-md border text-[10px] font-medium transition-colors ${
      active
        ? 'border-accent-cyan/50 text-accent-cyan bg-accent-cyan/10'
        : 'border-surface-700 text-surface-400 hover:text-surface-200 hover:border-surface-500'
    }`
    if (href) {
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" title={title} className={cls}>
          {children}
        </a>
      )
    }
    if (onClick) {
      return (
        <button type="button" onClick={onClick} title={title} className={cls}>
          {children}
        </button>
      )
    }
    return <span className={cls}>{children}</span>
  }

  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`.trim()}>
      <span className="text-[10px] text-surface-500 mr-1">Lab journey</span>
      {showTerminal && (
        <Item active={terminalActive} title="Linux/Windows terminal — fix the issue here">
          <Terminal size={11} /> Terminal
        </Item>
      )}
      {showVmware && (
        <Item active={false} href={vmHref} title="Open vCenter — perform hypervisor-side steps">
          <Server size={11} className="text-[#4fa7e8]" /> vCenter
          <ExternalLink size={10} className="opacity-60" />
        </Item>
      )}
      {showGrafana && onOpenGrafana && (
        <Item active={false} onClick={onOpenGrafana} title="Open Grafana/Prometheus">
          <Gauge size={11} className="text-[#f7913b]" /> Monitoring
        </Item>
      )}
      {showAwx && onOpenAwx && (
        <Item active={false} onClick={onOpenAwx} title="Open Ansible AWX">
          <Layers size={11} className="text-[#EE0000]" /> AWX
        </Item>
      )}
      {guideText && (
        <span className="text-[10px] text-surface-500 ml-1 max-w-[340px] truncate" title={guideText}>
          {guideText}
        </span>
      )}
    </div>
  )
}
