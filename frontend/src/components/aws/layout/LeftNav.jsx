import { useNavigate, useLocation } from 'react-router-dom'
import * as Icons from 'lucide-react'
import { LEFT_NAV } from './serviceNav'

export default function LeftNav({ service }) {
  const navigate = useNavigate()
  const location = useLocation()
  const cfg = LEFT_NAV[service]
  if (!cfg) return null
  const Icon = Icons[cfg.icon] || Icons.Box

  return (
    <nav className="aws-leftnav">
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, borderBottom: '1px solid var(--aws-sidebar-border)' }}>
        <Icon size={16} /> {cfg.title}
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
