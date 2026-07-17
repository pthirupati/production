import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronDown, Info } from 'lucide-react'
import { useAwsStore } from '../../store/awsStore'
import { Button, Badge, Tabs, IDCopy, Breadcrumb, EmptyState } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'
import ConnectModal from './ConnectModal'
import { getInstanceType, getAmi } from '../../lib/instanceTypes'
import { publicDns, privateDns } from '../../lib/ids'
import { BASE } from '../../layout/serviceNav'

function KV({ k, children }) {
  return <div className="aws-kv" style={{ marginBottom: 10 }}><span className="k">{k}</span><span className="v">{children}</span></div>
}

// Map a single structured check value to a labeled badge.
function checkDisplay(v) {
  if (v === 'passed') return <Badge state="running">Passed</Badge>
  if (v === 'initializing') return <Badge state="initializing">Initializing</Badge>
  if (v === '1/2') return <Badge state="initializing">1/2</Badge>
  return <span style={{ color: 'var(--aws-text-muted)' }}>— (not running)</span>
}

function consoleOutput(instance, ami) {
  const isWindows = instance.os?.includes('windows')
  if (isWindows) {
    return [
      'Windows Boot Manager',
      `Booting ${ami?.name || 'Windows Server'} on EC2 Nitro hypervisor`,
      'UEFI: Secure Boot enabled',
      'EC2Launch v2: initializing network adapters',
      `Hostname: ${instance.name || instance.id}`,
      `Private IPv4: ${instance.privateIp}`,
      'Cloudbase-Init: user data execution completed',
      'Windows Server is ready for RDP / PowerShell session',
    ].join('\n')
  }
  return [
    'Amazon EC2 console output',
    `Booting ${ami?.name || instance.os} on EC2 Nitro hypervisor`,
    'cloud-init[boot]: datasource DataSourceEc2Local',
    `hostname: ip-${instance.privateIp.replace(/\./g, '-')}`,
    `private-ipv4: ${instance.privateIp}`,
    instance.publicIp ? `public-ipv4: ${instance.publicIp}` : 'public-ipv4: not assigned',
    'sshd: Server listening on 0.0.0.0 port 22',
    'cloud-init[final]: finished at ' + new Date(instance.launchTime).toUTCString(),
  ].join('\n')
}

export default function InstanceDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const instance = useAwsStore((s) => (s.instances || []).find((i) => i.id === id))
  const securityGroups = useAwsStore((s) => s.securityGroups) || []
  const volumes = useAwsStore((s) => s.volumes) || []
  const instanceAction = useAwsStore((s) => s.instanceAction)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [tab, setTab] = useState('details')
  const [stateOpen, setStateOpen] = useState(false)
  const [connect, setConnect] = useState(false)

  if (!instance) {
    return <div className="aws-page"><EmptyState title="Instance not found" body="It may have been terminated or belongs to another Region." action={<Button onClick={() => navigate(`${BASE}/ec2/instances`)}>Back to instances</Button>} /></div>
  }

  const it = getInstanceType(instance.type)
  const ami = getAmi(instance.amiId)
  const sgs = securityGroups.filter((s) => instance.securityGroups.includes(s.id))
  const vols = volumes.filter((v) => v.attachedTo === instance.id)
  const isWindows = instance.os?.includes('windows')
  // Structured two-phase checks (system/instance/reachability/summary).
  const checks = instance.checks || { system: '-', instance: '-', reachability: '-', summary: instance.statusChecks || '-' }
  const isActive = instance.state === 'running'
  // Re-key charts on state change so the flat/no-data series regenerate.
  const monKey = instance.state
  const defaultUser = isWindows ? 'Administrator' : (ami.user || 'ec2-user')
  const host = instance.publicIp ? publicDns(instance.publicIp, instance.region) : instance.privateIp
  const sshCommand = `ssh -i "${instance.keyName || 'lab-key-pair'}.pem" ${defaultUser}@${host}`
  const rdpCommand = `mstsc /v:${host}`
  const terraformImport = `terraform import aws_instance.${(instance.name || instance.id).replace(/[^A-Za-z0-9_]/g, '_')} ${instance.id}`

  const stateAction = (a) => { setStateOpen(false); instanceAction([instance.id], a); pushFlash('success', `${a} requested for ${instance.id}`) }

  return (
    <div>
      <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Instances', onClick: () => navigate(`${BASE}/ec2/instances`) }, { label: instance.id }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 12 }}>{instance.id} <Badge state={instance.state} /></h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="primary" onClick={() => setConnect(true)}>Connect</Button>
            <div style={{ position: 'relative' }}>
              <Button onClick={() => setStateOpen((o) => !o)}>Instance state <ChevronDown size={13} /></Button>
              {stateOpen && (
                <div style={{ position: 'absolute', top: 32, right: 0, background: '#fff', border: '1px solid var(--aws-border)', borderRadius: 4, boxShadow: 'var(--aws-shadow-md)', zIndex: 50, minWidth: 160 }}>
                  {['start', 'stop', 'reboot', 'terminate'].map((a) => (
                    <div key={a} onClick={() => stateAction(a)} style={{ padding: '8px 16px', cursor: 'pointer', fontSize: 13, textTransform: 'capitalize', color: a === 'terminate' ? 'var(--aws-error)' : undefined }}>{a} instance</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <Tabs tabs={[
          { key: 'details', label: 'Details' },
          { key: 'security', label: 'Security' },
          { key: 'networking', label: 'Networking' },
          { key: 'storage', label: 'Storage' },
          { key: 'status', label: 'Status checks' },
          { key: 'monitoring', label: 'Monitoring' },
          { key: 'console', label: 'Console output' },
          { key: 'tags', label: 'Tags' },
        ]} active={tab} onChange={setTab} />

        <div style={{ marginTop: 16 }}>
          {tab === 'details' && (
            <div className="aws-card">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                <KV k="Instance ID"><IDCopy value={instance.id} /></KV>
                <KV k="Instance state"><Badge state={instance.state} /></KV>
                <KV k="Instance type">{instance.type} ({it.vcpu} vCPU, {it.memGiB} GiB)</KV>
                <KV k="Public IPv4 address">{instance.publicIp ? <IDCopy value={instance.publicIp} /> : '—'}</KV>
                <KV k="Private IPv4 address"><IDCopy value={instance.privateIp} /></KV>
                <KV k="Public IPv4 DNS">{instance.publicIp ? publicDns(instance.publicIp, instance.region) : '—'}</KV>
                <KV k="Private IPv4 DNS">{privateDns(instance.privateIp, instance.region)}</KV>
                <KV k="AMI ID"><IDCopy value={instance.amiId} /></KV>
                <KV k="AMI name">{ami.name}</KV>
                <KV k="Availability Zone">{instance.az}</KV>
                <KV k="VPC ID"><IDCopy value={instance.vpcId} /></KV>
                <KV k="Subnet ID"><IDCopy value={instance.subnetId} /></KV>
                <KV k="Key pair name">{instance.keyName || '—'}</KV>
                <KV k="IAM role">{instance.iamRole || '—'}</KV>
                <KV k="Launch time">{new Date(instance.launchTime).toUTCString()}</KV>
                <KV k="Monitoring">{instance.monitoring}</KV>
                <KV k="Tenancy">{instance.tenancy}</KV>
                <KV k="Architecture">{instance.architecture}</KV>
                <KV k="Platform details">{isWindows ? 'Windows Server' : 'Linux/UNIX'}</KV>
                <KV k="Lab engine">{instance.workload || ami.workload || (isWindows ? 'windows' : 'linux')}</KV>
              </div>
            </div>
          )}

          {tab === 'security' && (
            <div className="aws-card">
              <KV k="IAM role">{instance.iamRole || '—'}</KV>
              <div className="aws-section-label" style={{ marginTop: 12 }}>Security groups</div>
              {sgs.map((sg) => (
                <div key={sg.id} style={{ marginTop: 12 }}>
                  <strong>{sg.name}</strong> (<a className="aws-mono" onClick={() => navigate(`${BASE}/ec2/security-groups/${sg.id}`)}>{sg.id}</a>)
                  <div className="aws-hint" style={{ marginTop: 6 }}>Inbound rules</div>
                  <table className="aws-table" style={{ marginTop: 4 }}>
                    <thead><tr><th>Type</th><th>Protocol</th><th>Port range</th><th>Source</th></tr></thead>
                    <tbody>{(sg.inbound || []).map((r) => <tr key={r.id}><td>{r.type}</td><td>{r.protocol}</td><td>{r.from === r.to ? r.from : `${r.from}-${r.to}`}</td><td className="aws-mono">{r.source}</td></tr>)}</tbody>
                  </table>
                  <div className="aws-hint" style={{ marginTop: 8 }}>Outbound rules</div>
                  <table className="aws-table" style={{ marginTop: 4 }}>
                    <thead><tr><th>Type</th><th>Protocol</th><th>Port range</th><th>Destination</th></tr></thead>
                    <tbody>{(sg.outbound || []).map((r) => <tr key={r.id}><td>{r.type}</td><td>{r.protocol}</td><td>{r.from === r.to ? r.from : `${r.from}-${r.to}`}</td><td className="aws-mono">{r.source}</td></tr>)}</tbody>
                  </table>
                </div>
              ))}
            </div>
          )}

          {tab === 'networking' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                  <KV k="VPC ID"><IDCopy value={instance.vpcId} /></KV>
                  <KV k="Subnet ID"><IDCopy value={instance.subnetId} /></KV>
                  <KV k="Availability Zone">{instance.az}</KV>
                  <KV k="Private IPv4 address"><IDCopy value={instance.privateIp} /></KV>
                  <KV k="Public IPv4 address">{instance.publicIp || '—'}</KV>
                  <KV k="Network performance">{it.net}</KV>
                </div>
              </div>
              <div className="aws-card">
                <div className="aws-section-label">Network interface and connection commands</div>
                <table className="aws-table" style={{ marginTop: 8 }}>
                  <thead><tr><th>Interface ID</th><th>Private IP</th><th>Public IP / DNS</th><th>Security groups</th></tr></thead>
                  <tbody>
                    <tr>
                      <td><IDCopy value={`eni-${instance.id.replace('i-', '').slice(0, 17)}`} /></td>
                      <td><IDCopy value={instance.privateIp} /></td>
                      <td>{instance.publicIp ? <IDCopy value={publicDns(instance.publicIp, instance.region)} /> : 'Private only'}</td>
                      <td>{sgs.map((sg) => sg.name).join(', ') || '—'}</td>
                    </tr>
                  </tbody>
                </table>
                <pre className="aws-mono" style={{ marginTop: 12, background: 'var(--aws-page-bg)', borderRadius: 4, padding: 12, overflowX: 'auto' }}>{`${isWindows ? rdpCommand : sshCommand}
aws ec2 describe-instances --instance-ids ${instance.id}
${terraformImport}`}</pre>
              </div>
            </div>
          )}

          {tab === 'storage' && (
            <div className="aws-card">
              <table className="aws-table">
                <thead><tr><th>Volume ID</th><th>Device</th><th>Size</th><th>Type</th><th>Encrypted</th><th>Delete on termination</th></tr></thead>
                <tbody>{vols.map((v) => <tr key={v.id}><td><IDCopy value={v.id} /></td><td>{v.device}</td><td>{v.size} GiB</td><td>{v.type}</td><td>{v.encrypted ? 'Yes' : 'No'}</td><td>Yes</td></tr>)}</tbody>
              </table>
            </div>
          )}

          {tab === 'status' && (
            <div className="aws-card">
              <div className="aws-hint" style={{ marginBottom: 12 }}>Status checks run automatically. After launch, a new instance shows <strong>initializing</strong> and completes a two-phase check (system reachability, then instance reachability) before reaching 2/2.</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                <KV k="System reachability check">{checkDisplay(checks.system)}</KV>
                <KV k="Instance reachability check">{checkDisplay(checks.instance)}</KV>
                <KV k="Reachability">{checkDisplay(checks.reachability)}</KV>
                <KV k="Combined summary">
                  {checks.summary === '2/2'
                    ? <Badge state="running">2/2 checks passed</Badge>
                    : checks.summary === '-'
                      ? <span style={{ color: 'var(--aws-text-muted)' }}>Not running</span>
                      : <Badge state="initializing">{checks.summary === '1/2' ? '1/2 checks passed' : 'Initializing'}</Badge>}
                </KV>
              </div>
            </div>
          )}

          {tab === 'monitoring' && (
            <>
              {!isActive && (
                <div className="aws-flash aws-flash-info" style={{ marginBottom: 12 }}>
                  <Info size={18} style={{ marginTop: 1, flexShrink: 0 }} />
                  <div>Instance is <strong>{instance.state}</strong>. CloudWatch reports no data for a non-running instance — series are flat at zero.</div>
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
                {/* When not running, base/variance collapse to 0 so the chart is flat (no data). */}
                <MetricChart key={`cpu-${monKey}`} title="CPU Utilization (%)" unit="%" color="#0073bb" base={isActive ? 8 : 0} variance={isActive ? 20 : 0} />
                <MetricChart key={`ni-${monKey}`} title="Network In (Bytes)" unit="" color="#1d8102" base={isActive ? 50000 : 0} variance={isActive ? 400000 : 0} />
                <MetricChart key={`no-${monKey}`} title="Network Out (Bytes)" unit="" color="#9d5025" base={isActive ? 40000 : 0} variance={isActive ? 300000 : 0} />
                <MetricChart key={`dr-${monKey}`} title="Disk Read Ops (Count)" unit="" color="#d13212" base={isActive ? 5 : 0} variance={isActive ? 40 : 0} />
                <MetricChart key={`dw-${monKey}`} title="Disk Write Ops (Count)" unit="" color="#7d3ac1" base={isActive ? 10 : 0} variance={isActive ? 60 : 0} />
                <MetricChart key={`scf-${monKey}`} title="Status Check Failed (Count)" unit="" color="#545b64" base={0} variance={isActive ? 1 : 0} />
              </div>
            </>
          )}

          {tab === 'console' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <div className="aws-section-label">Instance console output</div>
                <div className="aws-hint" style={{ margin: '8px 0 12px' }}>This mirrors the EC2 "Get system log" troubleshooting view used for boot, cloud-init, and Windows EC2Launch issues.</div>
                <pre className="aws-mono" style={{ background: '#111827', color: '#d1fae5', borderRadius: 4, padding: 14, minHeight: 220, overflowX: 'auto' }}>{consoleOutput(instance, ami)}</pre>
              </div>
              <div className="aws-card">
                <div className="aws-section-label">Full-stack lab path</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginTop: 10 }}>
                  <KV k="1. Provision">Launch wizard, CloudShell AWS CLI, or Terraform apply</KV>
                  <KV k="2. Connect">{isWindows ? 'RDP / PowerShell' : 'EC2 Instance Connect / SSH'}</KV>
                  <KV k="3. Operate">Run Linux, Windows, Kubernetes, Docker, or Terraform commands</KV>
                </div>
              </div>
            </div>
          )}

          {tab === 'tags' && (
            <div className="aws-card">
              <table className="aws-table">
                <thead><tr><th>Key</th><th>Value</th></tr></thead>
                <tbody>{Object.entries(instance.tags).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      {connect && <ConnectModal instance={instance} onClose={() => setConnect(false)} />}
    </div>
  )
}
