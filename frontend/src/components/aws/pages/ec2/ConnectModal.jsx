import { useState } from 'react'
import { Modal, Tabs, Button, IDCopy } from '../../ui/primitives'
import AwsTerminal from '../../terminal/AwsTerminal'
import { defaultUser } from '../../terminal/vfs'
import { resolveEc2Workload, workloadHint } from '../../terminal/ec2Workload'
import { publicDns } from '../../lib/ids'

export default function ConnectModal({ instance, onClose }) {
  const [tab, setTab] = useState('eic')
  const [connected, setConnected] = useState(false)
  const workload = resolveEc2Workload(instance)
  const [user, setUser] = useState(defaultUser(instance.os))
  const dns = instance.publicIp ? publicDns(instance.publicIp, instance.region) : `${instance.privateIp} (private)`
  const sshHost = instance.publicIp ? publicDns(instance.publicIp, instance.region) : instance.privateIp
  const sshCommand = `ssh -i "${instance.keyName || 'my-key'}.pem" ${user}@${sshHost}`
  const canConnect = instance.state === 'running'

  if (connected) {
    return (
      <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: '#16191f', display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: 36, background: 'var(--aws-dark-blue)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', fontSize: 13 }}>
          <span>EC2 Instance Connect — {instance.id} — {workload} — {user}@{instance.privateIp} — {instance.region} — {instance.az}</span>
          <span style={{ display: 'flex', gap: 8 }}>
            <Button onClick={() => setConnected(false)}>Reconnect options</Button>
            <Button variant="danger" onClick={onClose}>Disconnect</Button>
          </span>
        </div>
        <div style={{ flex: 1 }}><AwsTerminal instance={instance} username={user} /></div>
      </div>
    )
  }

  return (
    <Modal title={`Connect to instance ${instance.id}`} onClose={onClose} width={820}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!canConnect} onClick={() => setConnected(true)}>{tab === 'ssm' ? 'Start session' : 'Connect'}</Button></>}>
      <Tabs tabs={[
        { key: 'eic', label: 'EC2 Instance Connect' },
        { key: 'ssm', label: 'Session Manager' },
        { key: 'ssh', label: 'SSH client' },
        { key: 'serial', label: 'EC2 Serial Console' },
        { key: 'rdp', label: 'RDP client' },
      ]} active={tab} onChange={setTab} />
      <div style={{ marginTop: 16 }}>
        {!canConnect && (
          <div className="aws-flash aws-flash-warning" style={{ marginBottom: 12 }}>
            Instance state is <strong>{instance.state}</strong>. Start the instance before opening a browser terminal.
          </div>
        )}
        {tab === 'eic' && (
          <div>
            <p style={{ marginBottom: 12, color: 'var(--aws-text-secondary)' }}>Connect using EC2 Instance Connect with a browser-based SSH session.</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
              <div>
                <label className="aws-label">Instance ID</label>
                <div className="aws-input" style={{ display: 'flex', alignItems: 'center' }}><IDCopy value={instance.id} /></div>
              </div>
              <div>
                <label className="aws-label">Public IP address</label>
                <input className="aws-input" value={instance.publicIp || '(none — using private IP)'} readOnly />
              </div>
            </div>
            <label className="aws-label">User name</label>
            <input className="aws-input" value={user} onChange={(e) => setUser(e.target.value)} />
            <div className="aws-hint">Suggested user for {instance.os}: {defaultUser(instance.os)}. This simulation creates the matching home directory and prompt.</div>
            <div className="aws-hint" style={{ marginTop: 8 }}><strong>Lab engine:</strong> {workloadHint(workload)}</div>
          </div>
        )}
        {tab === 'ssm' && (
          <div style={{ color: 'var(--aws-text-secondary)', lineHeight: 1.6 }}>
            <p>Connect via Session Manager. No inbound SSH port is required; sessions are audited and use the same in-browser terminal engine.</p>
            <div className="aws-card" style={{ marginTop: 12 }}>
              <div><strong>Target:</strong> {instance.id}</div>
              <div><strong>Agent:</strong> amazon-ssm-agent running</div>
              <div><strong>Session document:</strong> AWS-StartInteractiveCommand</div>
            </div>
          </div>
        )}
        {tab === 'ssh' && (
          <div>
            <p style={{ color: 'var(--aws-text-secondary)' }}>Use your own terminal with the private key that matches this instance key pair.</p>
            <div className="aws-mono" style={{ background: '#f8f8f8', padding: 12, borderRadius: 4, fontSize: 13, lineHeight: 1.8 }}>
              <div># 1. Set key permissions</div>
              <IDCopy value={`chmod 400 "${instance.keyName || 'my-key'}.pem"`} mono />
              <div style={{ marginTop: 8 }}># 2. Connect</div>
              <IDCopy value={sshCommand} mono />
              <div style={{ marginTop: 8 }}># Host</div>
              <span>{dns}</span>
            </div>
          </div>
        )}
        {tab === 'serial' && (
          <div style={{ color: 'var(--aws-text-secondary)', lineHeight: 1.6 }}>
            <p>EC2 Serial Console connects to the instance serial port for boot and network troubleshooting.</p>
            <div className="aws-card" style={{ marginTop: 12 }}>
              <div><strong>Serial console access:</strong> Enabled in simulation</div>
              <div><strong>Port:</strong> ttyS0</div>
              <div><strong>Login user:</strong> {user}</div>
            </div>
          </div>
        )}
        {tab === 'rdp' && (
          <div style={{ color: 'var(--aws-text-secondary)', lineHeight: 1.6 }}>
            <p>RDP is available for Windows instances. This instance is {instance.os}, so SSH-based connection methods are recommended.</p>
            <div className="aws-card" style={{ marginTop: 12 }}>
              <div><strong>RDP file:</strong> Not generated for Linux AMIs</div>
              <div><strong>Administrator password:</strong> Not applicable</div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
