import { useNavigate } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, SectionLabel } from '../../ui/primitives'
import { BASE } from '../../layout/serviceNav'

export default function Ec2Dashboard() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const instances = scoped(useAwsStore((s) => s.instances), region)
  const volumes = scoped(useAwsStore((s) => s.volumes), region)
  const sgs = scoped(useAwsStore((s) => s.securityGroups), region)
  const keyPairs = scoped(useAwsStore((s) => s.keyPairs), region)
  const eips = scoped(useAwsStore((s) => s.elasticIps), region)
  const amis = scoped(useAwsStore((s) => s.amis), region)

  const counts = [
    ['Instances (running)', instances.filter((i) => i.state === 'running').length, `${BASE}/ec2/instances`],
    ['Instances (stopped)', instances.filter((i) => i.state === 'stopped').length, `${BASE}/ec2/instances`],
    ['Dedicated Hosts', 0, `${BASE}/ec2/instances`],
    ['Elastic IPs', eips.length, `${BASE}/ec2/elastic-ips`],
    ['Key pairs', keyPairs.length, `${BASE}/ec2/key-pairs`],
    ['Security groups', sgs.length, `${BASE}/ec2/security-groups`],
    ['Volumes', volumes.length, `${BASE}/ec2/volumes`],
    ['AMIs', amis.length, `${BASE}/ec2/amis`],
  ]

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>EC2 Dashboard</h1>
        <Button variant="primary" onClick={() => navigate(`${BASE}/ec2/launch`)}>Launch instance</Button>
      </div>

      <div className="aws-card" style={{ marginBottom: 16 }}>
        <SectionLabel>Resources</SectionLabel>
        <div className="aws-summary-grid" style={{ marginTop: 8 }}>
          {counts.map(([label, n, path]) => (
            <div key={label} className="aws-kv" style={{ cursor: 'pointer' }} onClick={() => navigate(path)}>
              <span className="v" style={{ fontSize: 24, fontWeight: 700, color: 'var(--aws-text-link)' }}>{n}</span>
              <span className="k">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="aws-card">
        <SectionLabel>Service health</SectionLabel>
        {['EC2', 'EBS', 'VPC'].map((s) => (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
            <CheckCircle2 size={16} style={{ color: 'var(--aws-success)' }} /> <span>{s} — <strong>Healthy</strong></span>
          </div>
        ))}
      </div>
    </div>
  )
}
