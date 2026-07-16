import { useState } from 'react'
import { Modal, Tabs, Button, IDCopy } from '../../ui/primitives'
import AwsTerminal from '../../terminal/AwsTerminal'
import Ec2RdpSession from './Ec2RdpSession'
import { defaultUser } from '../../terminal/vfs'
import { resolveEc2Workload, workloadHint } from '../../terminal/ec2Workload'
import { publicDns } from '../../lib/ids'
import { useAwsStore } from '../../store/awsStore'
import { instanceAllowsInbound } from '../../terminal/sgReachability'

export default function ConnectModal({ instance, onClose }) {
  const workload = resolveEc2Workload(instance)
  const isWindows = workload === 'windows'
  // Windows instances default to the RDP tab + Administrator, just like the
  // real console; Linux/K8s default to EC2 Instance Connect.
  const [tab, setTab] = useState(isWindows ? 'rdp' : 'eic')
  const [connected, setConnected] = useState(false)
  const [user, setUser] = useState(defaultUser(instance.os))
  const store = useAwsStore.getState()
  const dns = instance.publicIp ? publicDns(instance.publicIp, instance.region) : `${instance.privateIp} (private)`
  const sshHost = instance.publicIp ? publicDns(instance.publicIp, instance.region) : instance.privateIp
  const sshCommand = `ssh -i "${instance.keyName || 'my-key'}.pem" ${user}@${sshHost}`
  const port = isWindows ? 3389 : 22
  const sgOpen = instanceAllowsInbound(store, instance, port, 'TCP')
  // Session Manager does not need inbound SSH/RDP — match real AWS.
  const needsInbound = tab !== 'ssm' && tab !== 'serial'
  const canConnect = instance.state === 'running' && (!needsInbound || sgOpen)
  const useRdpDesktop = isWindows && tab === 'rdp'

  if (connected && useRdpDesktop) {
    return (
      <Ec2RdpSession
        instance={instance}
        onClose={onClose}
        onReconnect={() => setConnected(false)}
      />
    )
  }

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
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!canConnect} onClick={() => setConnected(true)}>{tab === 'ssm' ? 'Start session' : useRdpDesktop ? 'Launch RDP session' : 'Connect'}</Button></>}>
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
            {instance.state !== 'running' ? (
              <>Instance state is <strong>{instance.state}</strong>. Start the instance before opening a browser terminal.</>
            ) : (
              <>Security group does not allow inbound TCP/{port} from 0.0.0.0/0. Add an SSH/RDP rule, or use Session Manager.</>
            )}
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
            {isWindows ? (
              <>
                <p>Download the remote desktop file or connect in-browser. The session opens the Windows Server PowerShell/Server Manager engine.</p>
                <div className="aws-card" style={{ marginTop: 12 }}>
                  <div><strong>Public DNS:</strong> <span className="aws-mono">{dns}</span></div>
                  <div style={{ marginTop: 6 }}><strong>User name:</strong> Administrator</div>
                  <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <strong>Password:</strong>
                    <span className="aws-mono">{`Lab-${instance.id.replace('i-', '').slice(0, 8)}!Aws`}</span>
                    <span className="aws-hint" style={{ margin: 0 }}>(decrypted with your key pair)</span>
                  </div>
                </div>
                <div className="aws-hint" style={{ marginTop: 10 }}><strong>Lab engine:</strong> {workloadHint(workload)}</div>
              </>
            ) : (
              <>
                <p>RDP is for Windows instances. This instance is {instance.os}, so use EC2 Instance Connect, Session Manager, or an SSH client instead.</p>
                <div className="aws-card" style={{ marginTop: 12 }}>
                  <div><strong>RDP file:</strong> Not generated for Linux AMIs</div>
                  <div><strong>Administrator password:</strong> Not applicable</div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
