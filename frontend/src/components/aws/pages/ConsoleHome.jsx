import { useNavigate } from 'react-router-dom'
import { Server, Database, Shield, Network, Activity, CheckCircle2, GraduationCap, ArrowRight } from 'lucide-react'
import { useAwsStore, scoped } from '../store/awsStore'
import { regionName } from '../lib/regions'
import { SectionLabel } from '../ui/primitives'
import { BASE } from '../layout/serviceNav'

const RECENT = [
  { key: 'ec2', name: 'EC2', icon: Server, path: `${BASE}/ec2/home`, color: '#ff9900' },
  { key: 's3', name: 'S3', icon: Database, path: `${BASE}/s3`, color: '#1d8102' },
  { key: 'iam', name: 'IAM', icon: Shield, path: `${BASE}/iam/home`, color: '#d13212' },
  { key: 'vpc', name: 'VPC', icon: Network, path: `${BASE}/vpc/home`, color: '#0073bb' },
  { key: 'cloudwatch', name: 'CloudWatch', icon: Activity, path: `${BASE}/cloudwatch/home`, color: '#9d5025' },
]

export default function ConsoleHome() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const instances = useAwsStore((s) => s.instances)
  const buckets = useAwsStore((s) => s.s3Buckets)
  const alarms = useAwsStore((s) => s.cwAlarms)

  const running = scoped(instances, region).filter((i) => i.state === 'running').length
  const monthCost = 47.32

  return (
    <div className="aws-page">
      <h1 style={{ marginBottom: 4 }}>Console Home</h1>
      <div style={{ color: 'var(--aws-text-secondary)', marginBottom: 20 }}>Region: {regionName(region)}</div>

      {/* Guided-lab CTA — the console is a practice environment, so surface the
          AWS hands-on labs prominently right on the home page. */}
      <div
        className="aws-card"
        style={{
          marginBottom: 16, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
          background: 'linear-gradient(90deg, rgba(255,153,0,0.12), rgba(0,115,187,0.10))',
          borderLeft: '4px solid var(--aws-orange)',
        }}
      >
        <GraduationCap size={32} style={{ color: 'var(--aws-orange)' }} />
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>AWS hands-on labs</div>
          <div style={{ fontSize: 13, color: 'var(--aws-text-secondary)' }}>
            Practice EC2, S3, IAM, VPC, RDS, EKS, Lambda and 40+ services in guided, validated scenarios.
          </div>
        </div>
        <button
          onClick={() => navigate('/technologies/aws')}
          style={{ background: 'var(--aws-orange)', color: '#16191f', border: 'none', borderRadius: 4, padding: '9px 16px', fontWeight: 700, fontSize: 13, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          Browse AWS labs <ArrowRight size={15} />
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        <div className="aws-card">
          <SectionLabel>Recently visited</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12, marginTop: 8 }}>
            {RECENT.map((s) => {
              const Icon = s.icon
              return (
                <div key={s.key} className="aws-card aws-card-hover" style={{ cursor: 'pointer', padding: 12, display: 'flex', alignItems: 'center', gap: 10 }} onClick={() => navigate(s.path)}>
                  <Icon size={22} style={{ color: s.color }} />
                  <span style={{ color: 'var(--aws-text-link)', fontWeight: 600 }}>{s.name}</span>
                </div>
              )
            })}
          </div>
        </div>

        <div className="aws-card">
          <SectionLabel>AWS Health</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <CheckCircle2 size={18} style={{ color: 'var(--aws-success)' }} />
            <span>Open and recent issues — <strong>No issues</strong></span>
          </div>
          <a style={{ display: 'inline-block', marginTop: 12 }}>View all AWS Health events</a>
        </div>

        <div className="aws-card">
          <SectionLabel>Cost and usage</SectionLabel>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
            <div className="aws-kv"><span className="k">Month-to-date cost</span><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>${monthCost.toFixed(2)}</span></div>
            <div className="aws-kv"><span className="k">Forecasted</span><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>$92.40</span></div>
          </div>
          <a style={{ display: 'inline-block', marginTop: 12 }}>View billing dashboard</a>
        </div>

        <div className="aws-card">
          <SectionLabel>Resources</SectionLabel>
          <div className="aws-summary-grid" style={{ marginTop: 8 }}>
            {[
              ['Running instances', running],
              ['S3 buckets', buckets.length],
              ['CloudWatch alarms', alarms.length],
            ].map(([l, v]) => (
              <div key={l} className="aws-kv"><span className="k">{l}</span><span className="v" style={{ fontSize: 22, fontWeight: 700 }}>{v}</span></div>
            ))}
          </div>
        </div>

        <div className="aws-card">
          <SectionLabel>CloudWatch alarms</SectionLabel>
          <table className="aws-table" style={{ marginTop: 4 }}>
            <thead><tr><th>Alarm</th><th>State</th><th>Metric</th></tr></thead>
            <tbody>
              {alarms.map((a) => (
                <tr key={a.name}><td>{a.name}</td><td>{a.state}</td><td className="aws-mono">{a.metric}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
