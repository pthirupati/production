import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Minus, Plus } from 'lucide-react'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, Breadcrumb } from '../../ui/primitives'
import { AMI_CATALOG, INSTANCE_TYPES, getInstanceType, VOLUME_TYPES } from '../../lib/instanceTypes'
import { BASE } from '../../layout/serviceNav'

export default function LaunchWizard() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const keyPairs = scoped(useAwsStore((s) => s.keyPairs), region)
  const subnets = scoped(useAwsStore((s) => s.subnets), region)
  const securityGroups = scoped(useAwsStore((s) => s.securityGroups), region)
  const launchInstances = useAwsStore((s) => s.launchInstances)
  const createKeyPair = useAwsStore((s) => s.createKeyPair)
  const pushFlash = useAwsStore((s) => s.pushFlash)

  const [name, setName] = useState('')
  const [amiId, setAmiId] = useState(AMI_CATALOG[0].id)
  const [type, setType] = useState('t2.micro')
  const [keyName, setKeyName] = useState(keyPairs[0]?.name || '')
  const [subnetId, setSubnetId] = useState('')
  const [sg, setSg] = useState(securityGroups[0]?.id || '')
  const [volumeSize, setVolumeSize] = useState(8)
  const [volumeType, setVolumeType] = useState('gp3')
  const [count, setCount] = useState(1)
  const [launched, setLaunched] = useState(null)
  const [errors, setErrors] = useState({})

  const it = getInstanceType(type)
  const vol = VOLUME_TYPES.find((v) => v.type === volumeType)
  const hourly = it.price + (volumeSize * (vol?.price || 0.08)) / 730
  const monthly = (hourly * 730 * count)

  const validate = () => {
    const e = {}
    if (count < 1 || count > 20) e.count = 'Number of instances must be 1–20'
    if (!sg) e.sg = 'Select a security group'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const launch = () => {
    if (!validate()) return
    const created = launchInstances({ name, amiId, type, count, keyName, subnetId, securityGroups: [sg], volumeSize, volumeType, monitoring: false, tags: {} })
    pushFlash('success', `Successfully initiated launch of ${created.length} instance(s)`)
    setLaunched(created)
  }

  if (launched) {
    return (
      <div className="aws-page">
        <div className="aws-flash aws-flash-success"><div><strong>Success</strong><div>Successfully initiated launch of instance {launched.map((i) => i.id).join(', ')}</div></div></div>
        <div className="aws-card" style={{ maxWidth: 600 }}>
          {launched.map((i) => <div key={i.id} style={{ marginBottom: 8 }}><a onClick={() => navigate(`${BASE}/ec2/instances/${i.id}`)} className="aws-mono">{i.id}</a> <Badge state="pending" /></div>)}
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <Button variant="primary" onClick={() => navigate(`${BASE}/ec2/instances`)}>View all instances</Button>
            <Button onClick={() => { setLaunched(null); setName('') }}>Launch more</Button>
          </div>
        </div>
      </div>
    )
  }

  const section = (label, children) => (
    <div className="aws-card" style={{ marginBottom: 16 }}>
      <h3 style={{ marginBottom: 12 }}>{label}</h3>
      {children}
    </div>
  )

  return (
    <div>
      <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Instances', onClick: () => navigate(`${BASE}/ec2/instances`) }, { label: 'Launch an instance' }]} />
      <div className="aws-page" style={{ paddingTop: 0, display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20 }}>
        <div>
          <h1 style={{ marginBottom: 16 }}>Launch an instance</h1>

          {section('Name and tags', (
            <>
              <label className="aws-label">Name</label>
              <input className="aws-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. my-web-server" />
            </>
          ))}

          {section('Application and OS Images (Amazon Machine Image)', (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
              {AMI_CATALOG.map((a) => (
                <div key={a.id} onClick={() => setAmiId(a.id)} className="aws-card" style={{ cursor: 'pointer', borderColor: amiId === a.id ? 'var(--aws-input-focus)' : undefined, borderWidth: amiId === a.id ? 2 : 1, padding: 12 }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{a.name}</div>
                  <div className="aws-mono" style={{ fontSize: 11, color: 'var(--aws-text-secondary)' }}>{a.id}</div>
                  <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <span className="aws-badge aws-badge-terminated" style={{ height: 18 }}>{a.arch}</span>
                    {a.freeTier && <span className="aws-badge aws-badge-running" style={{ height: 18 }}>Free tier eligible</span>}
                  </div>
                </div>
              ))}
            </div>
          ))}

          {section('Instance type', (
            <>
              <select className="aws-select" value={type} onChange={(e) => setType(e.target.value)}>
                {INSTANCE_TYPES.map((t) => (
                  <option key={t.type} value={t.type}>{t.type} — {t.vcpu} vCPU, {t.memGiB} GiB, {t.net} (${t.price.toFixed(4)}/hr){t.freeTier ? ' · Free tier' : ''}</option>
                ))}
              </select>
              <div className="aws-hint">{it.family} · {it.arch} · {it.net}</div>
            </>
          ))}

          {section('Key pair (login)', (
            <>
              <select className="aws-select" value={keyName} onChange={(e) => setKeyName(e.target.value)}>
                <option value="">Proceed without a key pair (Not recommended)</option>
                {keyPairs.map((k) => <option key={k.id} value={k.name}>{k.name} ({k.type})</option>)}
              </select>
              <a style={{ display: 'inline-block', marginTop: 8 }} onClick={() => { const kp = createKeyPair({ name: `key-${Date.now().toString(36)}`, type: 'rsa' }); setKeyName(kp.name); pushFlash('success', `Created key pair ${kp.name} (private key would download)`) }}>Create new key pair</a>
            </>
          ))}

          {section('Network settings', (
            <>
              <label className="aws-label">Subnet</label>
              <select className="aws-select" value={subnetId} onChange={(e) => setSubnetId(e.target.value)} style={{ marginBottom: 12 }}>
                <option value="">No preference (default subnet in any AZ)</option>
                {subnets.map((s) => <option key={s.id} value={s.id}>{s.id} | {s.az} | {s.cidr}</option>)}
              </select>
              <label className="aws-label">Firewall (security group)</label>
              <select className={`aws-select ${errors.sg ? 'aws-invalid' : ''}`} value={sg} onChange={(e) => setSg(e.target.value)}>
                {securityGroups.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.id})</option>)}
              </select>
              {errors.sg && <div className="aws-field-error">{errors.sg}</div>}
            </>
          ))}

          {section('Configure storage', (
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <label className="aws-label">Size (GiB)</label>
                <input className="aws-input" type="number" min={1} max={16384} value={volumeSize} onChange={(e) => setVolumeSize(Number(e.target.value))} />
              </div>
              <div style={{ flex: 2 }}>
                <label className="aws-label">Volume type</label>
                <select className="aws-select" value={volumeType} onChange={(e) => setVolumeType(e.target.value)}>
                  {VOLUME_TYPES.map((v) => <option key={v.type} value={v.type}>{v.label}</option>)}
                </select>
              </div>
            </div>
          ))}
        </div>

        {/* Summary panel */}
        <div style={{ position: 'sticky', top: 60, alignSelf: 'start' }}>
          <div className="aws-card">
            <h3 style={{ marginBottom: 12 }}>Summary</h3>
            <div className="aws-kv" style={{ marginBottom: 8 }}><span className="k">Number of instances</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <Button onClick={() => setCount((c) => Math.max(1, c - 1))} icon={Minus} />
                <input className="aws-input" style={{ width: 60, textAlign: 'center' }} value={count} onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))} />
                <Button onClick={() => setCount((c) => c + 1)} icon={Plus} />
              </div>
              {errors.count && <div className="aws-field-error">{errors.count}</div>}
            </div>
            <div style={{ borderTop: '1px solid var(--aws-border-light)', paddingTop: 8, fontSize: 13 }}>
              <div>AMI: {AMI_CATALOG.find((a) => a.id === amiId)?.name}</div>
              <div>Type: {type}</div>
              <div>Storage: {count}× {volumeSize} GiB {volumeType}</div>
            </div>
            <div style={{ marginTop: 12, fontSize: 13 }}>
              <div>Hourly: <strong>${hourly.toFixed(4)}</strong></div>
              <div>Est. monthly: <strong>${monthly.toFixed(2)}</strong></div>
            </div>
            <Button variant="primary" onClick={launch} style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}>Launch instance</Button>
            <a style={{ display: 'block', textAlign: 'center', marginTop: 8 }} onClick={() => navigate(`${BASE}/ec2/instances`)}>Cancel</a>
          </div>
        </div>
      </div>
    </div>
  )
}
