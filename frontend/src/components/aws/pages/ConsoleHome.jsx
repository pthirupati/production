import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Server, Database, Shield, Network, Activity, GraduationCap, ArrowRight,
  AppWindow, HeartPulse, Lightbulb, Compass, Plus, X, Box, Boxes, Workflow,
} from 'lucide-react'
import { useAwsStore, scoped } from '../store/awsStore'
import { regionName } from '../lib/regions'
import { SectionLabel, Modal, Button } from '../ui/primitives'
import { BASE, SERVICES } from '../layout/serviceNav'

const SERVICE_BY_KEY = Object.fromEntries(SERVICES.map((s) => [s.key, s]))

const CATEGORY_ICON = {
  Compute: Server,
  Containers: Boxes,
  Storage: Database,
  Database: Database,
  'Networking & Content Delivery': Network,
  'Security, Identity & Compliance': Shield,
  'Management & Governance': Activity,
  'Application Integration': Workflow,
}
function serviceIcon(svc) {
  if (svc?.key === 'ec2') return Server
  if (svc?.key === 's3') return Database
  if (svc?.key === 'iam') return Shield
  if (svc?.key === 'vpc') return Network
  if (svc?.key === 'cloudwatch') return Activity
  return CATEGORY_ICON[svc?.category] || Box
}

// Widget catalog. Keys match store.homeWidgets. Any key seeded by the store that
// isn't here is ignored gracefully.
const WIDGET_CATALOG = [
  { key: 'recently-visited', title: 'Recently visited', desc: 'Services you opened recently' },
  { key: 'welcome', title: 'Welcome to AWS', desc: 'Getting started resources' },
  { key: 'applications', title: 'Applications', desc: 'Your grouped resources' },
  { key: 'cost-and-usage', title: 'Cost and usage', desc: 'Month-to-date spend' },
  { key: 'resources', title: 'Resources', desc: 'Counts across core services' },
  { key: 'health', title: 'AWS Health', desc: 'Open and recent issues' },
  { key: 'trusted-advisor', title: 'Trusted Advisor', desc: 'Recommended checks' },
  { key: 'explore', title: 'Explore AWS', desc: 'Featured services to try' },
]
const CATALOG_BY_KEY = Object.fromEntries(WIDGET_CATALOG.map((w) => [w.key, w]))

export default function ConsoleHome() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const instances = useAwsStore((s) => s.instances) || []
  const buckets = useAwsStore((s) => s.s3Buckets) || []
  const alarms = useAwsStore((s) => s.cwAlarms) || []
  const recentServices = useAwsStore((s) => s.recentServices) || []
  const homeWidgets = useAwsStore((s) => s.homeWidgets) || []
  const setHomeWidgets = useAwsStore((s) => s.setHomeWidgets)
  const pushRecentService = useAwsStore((s) => s.pushRecentService)

  const [addOpen, setAddOpen] = useState(false)

  const running = scoped(instances, region).filter((i) => i.state === 'running').length
  const monthCost = 47.32

  const go = (path, key) => { if (key) pushRecentService(key); navigate(path) }

  // Recently-visited widget content — driven by store, with a sensible fallback
  // to the core services when the user hasn't navigated yet.
  const recentObjs = recentServices.map((k) => SERVICE_BY_KEY[k]).filter(Boolean)
  const fallbackRecent = ['ec2', 's3', 'iam', 'vpc', 'cloudwatch'].map((k) => SERVICE_BY_KEY[k]).filter(Boolean)
  const recentDisplay = recentObjs.length ? recentObjs : fallbackRecent

  const activeWidgets = homeWidgets.filter((k) => CATALOG_BY_KEY[k])
  const removeWidget = (key) => setHomeWidgets(homeWidgets.filter((k) => k !== key))
  const addWidget = (key) => { if (!homeWidgets.includes(key)) setHomeWidgets([...homeWidgets, key]) }

  const explore = ['lambda', 'rds', 'dynamodb', 'eks', 'cloudformation', 'route53'].map((k) => SERVICE_BY_KEY[k]).filter(Boolean)

  function WidgetShell({ wkey, title, children }) {
    return (
      <div className="aws-card aws-home-widget">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <SectionLabel>{title}</SectionLabel>
          <button className="aws-copy-btn aws-widget-remove" title="Remove widget" onClick={() => removeWidget(wkey)}><X size={15} /></button>
        </div>
        {children}
      </div>
    )
  }

  const renderWidget = (key) => {
    const meta = CATALOG_BY_KEY[key]
    if (!meta) return null
    switch (key) {
      case 'recently-visited':
        return (
          <WidgetShell key={key} wkey={key} title="Recently visited">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12, marginTop: 8 }}>
              {recentDisplay.map((s) => {
                const Icon = serviceIcon(s)
                return (
                  <div key={s.key} className="aws-card aws-card-hover" style={{ cursor: 'pointer', padding: 12, display: 'flex', alignItems: 'center', gap: 10 }} onClick={() => go(s.path, s.key)}>
                    <Icon size={20} style={{ color: 'var(--aws-orange)' }} />
                    <span style={{ color: 'var(--aws-text-link)', fontWeight: 600 }}>{s.name}</span>
                  </div>
                )
              })}
            </div>
          </WidgetShell>
        )
      case 'welcome':
        return (
          <WidgetShell key={key} wkey={key} title="Welcome to AWS">
            <div style={{ marginTop: 8, color: 'var(--aws-text-secondary)', fontSize: 13 }}>
              This is a hands-on AWS console. Launch resources, manage IAM, and complete guided labs.
            </div>
            <a onClick={() => navigate('/technologies/aws')} style={{ display: 'inline-block', marginTop: 10 }}>Browse AWS labs</a>
          </WidgetShell>
        )
      case 'applications':
        return (
          <WidgetShell key={key} wkey={key} title="Applications">
            <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
              <AppWindow size={18} style={{ color: 'var(--aws-info)' }} />
              <span style={{ color: 'var(--aws-text-secondary)' }}>No applications defined. Group resources into an application to track them together.</span>
            </div>
          </WidgetShell>
        )
      case 'cost-and-usage':
        return (
          <WidgetShell key={key} wkey={key} title="Cost and usage">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
              <div className="aws-kv"><span className="k">Month-to-date cost</span><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>${monthCost.toFixed(2)}</span></div>
              <div className="aws-kv"><span className="k">Forecasted</span><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>$92.40</span></div>
            </div>
            <a onClick={() => go(`${BASE}/billing/home`, 'billing')} style={{ display: 'inline-block', marginTop: 12 }}>View billing dashboard</a>
          </WidgetShell>
        )
      case 'resources':
        return (
          <WidgetShell key={key} wkey={key} title="Resources">
            <div className="aws-summary-grid" style={{ marginTop: 8 }}>
              {[
                ['Running instances', running],
                ['S3 buckets', buckets.length],
                ['CloudWatch alarms', alarms.length],
              ].map(([l, v]) => (
                <div key={l} className="aws-kv"><span className="k">{l}</span><span className="v" style={{ fontSize: 22, fontWeight: 700 }}>{v}</span></div>
              ))}
            </div>
          </WidgetShell>
        )
      case 'health':
        return (
          <WidgetShell key={key} wkey={key} title="AWS Health">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <HeartPulse size={18} style={{ color: 'var(--aws-success)' }} />
              <span>Open and recent issues — <strong>No issues</strong></span>
            </div>
            <a style={{ display: 'inline-block', marginTop: 12 }}>View all AWS Health events</a>
          </WidgetShell>
        )
      case 'trusted-advisor':
        return (
          <WidgetShell key={key} wkey={key} title="Trusted Advisor">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <Lightbulb size={18} style={{ color: 'var(--aws-warning)' }} />
              <span style={{ color: 'var(--aws-text-secondary)' }}>Recommended actions — <strong style={{ color: 'var(--aws-text-primary)' }}>All checks passing</strong></span>
            </div>
            <a onClick={() => go(`${BASE}/trustedadvisor/home`, 'trustedadvisor')} style={{ display: 'inline-block', marginTop: 12 }}>Go to Trusted Advisor</a>
          </WidgetShell>
        )
      case 'explore':
        return (
          <WidgetShell key={key} wkey={key} title="Explore AWS">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10, marginTop: 8 }}>
              {explore.map((s) => {
                const Icon = serviceIcon(s)
                return (
                  <div key={s.key} className="aws-card aws-card-hover" style={{ cursor: 'pointer', padding: 10, display: 'flex', alignItems: 'center', gap: 8 }} onClick={() => go(s.path, s.key)}>
                    <Icon size={16} style={{ color: 'var(--aws-text-secondary)' }} />
                    <span style={{ color: 'var(--aws-text-link)', fontWeight: 600, fontSize: 13 }}>{s.name}</span>
                  </div>
                )
              })}
            </div>
          </WidgetShell>
        )
      default:
        return null
    }
  }

  const availableToAdd = WIDGET_CATALOG.filter((w) => !homeWidgets.includes(w.key))

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>Console Home</h1>
          <div style={{ color: 'var(--aws-text-secondary)', marginBottom: 20 }}>Region: {regionName(region)}</div>
        </div>
        <Button icon={Plus} onClick={() => setAddOpen(true)}>Add widgets</Button>
      </div>

      {/* Guided-lab CTA */}
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

      {activeWidgets.length === 0 ? (
        <div className="aws-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
          <Compass size={32} style={{ color: 'var(--aws-text-muted)' }} />
          <div style={{ fontWeight: 700, marginTop: 10 }}>Your dashboard is empty</div>
          <div style={{ color: 'var(--aws-text-secondary)', marginTop: 4 }}>Add widgets to customize your Console Home.</div>
          <div style={{ marginTop: 14 }}><Button variant="primary" icon={Plus} onClick={() => setAddOpen(true)}>Add widgets</Button></div>
        </div>
      ) : (
        <div className="aws-home-grid">
          {activeWidgets.map((key) => renderWidget(key))}
        </div>
      )}

      {addOpen && (
        <Modal title="Add widgets" onClose={() => setAddOpen(false)} footer={<Button variant="primary" onClick={() => setAddOpen(false)}>Done</Button>}>
          {availableToAdd.length === 0 ? (
            <div style={{ color: 'var(--aws-text-secondary)' }}>All available widgets are already on your dashboard.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
              {availableToAdd.map((w) => (
                <div key={w.key} className="aws-card aws-card-hover" style={{ padding: 12, cursor: 'pointer' }} onClick={() => addWidget(w.key)}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 700 }}>{w.title}</span>
                    <Plus size={16} style={{ color: 'var(--aws-text-link)' }} />
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--aws-text-secondary)', marginTop: 4 }}>{w.desc}</div>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
