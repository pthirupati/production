import { X, Maximize2, Minimize2 } from 'lucide-react'
import { useState } from 'react'
import AwsTerminal from '../terminal/AwsTerminal'
import { useAwsStore } from '../store/awsStore'

// Bottom CloudShell drawer running the AWS CLI v2 against the simulation store.
export default function CloudShell({ onClose }) {
  const [maximized, setMaximized] = useState(false)
  const region = useAwsStore((s) => s.region)
  const height = maximized ? '70vh' : 320
  return (
    <div className="aws-cloudshell" style={{ height }}>
      <div style={{ height: 32, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 10px', color: '#cfd6dd', fontSize: 13, borderBottom: '1px solid #2a3b4d' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--aws-orange)', fontWeight: 700 }}>AWS CloudShell</span>
          <span style={{ opacity: 0.6 }}>{region} · /home/cloudshell-user</span>
        </span>
        <span style={{ display: 'flex', gap: 8 }}>
          <button className="aws-copy-btn" style={{ color: '#cfd6dd' }} onClick={() => setMaximized((m) => !m)}>{maximized ? <Minimize2 size={15} /> : <Maximize2 size={15} />}</button>
          <button className="aws-copy-btn" style={{ color: '#cfd6dd' }} onClick={onClose}><X size={16} /></button>
        </span>
      </div>
      <div style={{ height: `calc(${typeof height === 'number' ? `${height}px` : height} - 32px)` }}>
        <AwsTerminal cloudShell />
      </div>
    </div>
  )
}
