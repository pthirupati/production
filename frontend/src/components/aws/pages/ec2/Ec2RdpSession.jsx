import { useEffect, useState } from 'react'
import WindowsServer2022 from '../../../windows/os/WindowsServer2022'
import { Button } from '../../ui/primitives'
import { publicDns } from '../../lib/ids'

/** Full-screen in-browser RDP session for Windows EC2 instances. */
export default function Ec2RdpSession({ instance, onClose, onReconnect }) {
  const [phase, setPhase] = useState('connecting') // connecting | desktop
  const dns = instance.publicIp ? publicDns(instance.publicIp, instance.region) : instance.privateIp
  const password = `Lab-${instance.id.replace('i-', '').slice(0, 8)}!Aws`

  useEffect(() => {
    const t = setTimeout(() => setPhase('desktop'), 1400)
    return () => clearTimeout(t)
  }, [])

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: '#0b0f14', display: 'flex', flexDirection: 'column' }}>
      <div style={{ height: 36, background: 'var(--aws-dark-blue)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', fontSize: 13, flexShrink: 0 }}>
        <span>
          Remote Desktop — {instance.id} — Administrator@{dns} — {instance.region}
        </span>
        <span style={{ display: 'flex', gap: 8 }}>
          <Button onClick={onReconnect}>Reconnect options</Button>
          <Button variant="danger" onClick={onClose}>Disconnect</Button>
        </span>
      </div>

      {phase === 'connecting' ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#cfd6dd', fontFamily: 'var(--aws-font)' }}>
          <div style={{ textAlign: 'center', maxWidth: 420 }}>
            <div className="aws-spinner" style={{ margin: '0 auto 16px', width: 32, height: 32 }} />
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Connecting to {dns}</div>
            <div style={{ fontSize: 13, color: '#8b96a5', lineHeight: 1.6 }}>
              Verifying credentials for <strong>Administrator</strong>
              <br />
              <span className="aws-mono" style={{ fontSize: 12 }}>{password}</span>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          <WindowsServer2022 autoOpen="Terminal" />
        </div>
      )}
    </div>
  )
}
