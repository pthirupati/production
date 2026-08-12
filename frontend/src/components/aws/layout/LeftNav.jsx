import { useNavigate, useLocation } from 'react-router-dom'
import * as Icons from 'lucide-react'
import { LEFT_NAV } from './serviceNav'

// LeftNav renders the per-service navigation. When `collapsed` is true it does
// NOT unmount — it renders a ~48px icon rail instead, so AwsConsole's
// serviceFromPath mount logic (which keys off the same DOM subtree lifecycle)
// is unaffected and page state survives a collapse/expand toggle.
export default function LeftNav({ service, collapsed = false, onExpand }) {
  const navigate = useNavigate()
  const location = useLocation()
  const cfg = LEFT_NAV[service]
  if (!cfg) return null
  const Icon = Icons[cfg.icon] || Icons.Box

  if (collapsed) {
    // Icon rail: service icon + the first clickable item per group as a compact
    // set of jump targets. Clicking any icon expands back to the full nav.
    const railItems = cfg.items.filter((it) => !it.group).slice(0, 12)
    return (
      <nav className="aws-leftnav aws-leftnav-collapsed" aria-label={`${cfg.title} navigation (collapsed)`}>
        <button
          type="button"
          className="aws-leftnav-rail-toggle"
          title={`Expand ${cfg.title} navigation`}
          aria-label={`Expand ${cfg.title} navigation`}
          onClick={() => onExpand?.()}
        >
          <Icons.PanelLeft size={16} />
        </button>
        <div className="aws-leftnav-rail-icon" title={cfg.title}><Icon size={18} /></div>
        {railItems.map((item, i) => {
          const active = location.pathname === item.path
          const ItemIcon = Icons[item.icon] || Icons.Dot
          return (
            <button
              key={i}
              className={`aws-leftnav-rail-item ${active ? 'aws-active' : ''}`}
              title={item.label}
              aria-label={item.label}
              onClick={() => navigate(item.path)}
            >
              <ItemIcon size={16} />
            </button>
          )
        })}
      </nav>
    )
  }

  return (
    <nav className="aws-leftnav">
      <div className="aws-leftnav-title">
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Icon size={16} /> {cfg.title}</span>
        {onExpand && (
          <button type="button" className="aws-leftnav-collapse-btn" title="Collapse navigation" aria-label="Collapse navigation" onClick={() => onExpand(true)}>
            <Icons.PanelLeftClose size={15} />
          </button>
        )}
      </div>
      {cfg.items.map((item, i) => {
        if (item.group) return <div key={i} className="aws-leftnav-group">{item.group}</div>
        const active = location.pathname === item.path
        return (
          <a key={i} className={`aws-leftnav-item ${active ? 'aws-active' : ''}`} onClick={() => navigate(item.path)}>{item.label}</a>
        )
      })}
    </nav>
  )
}
