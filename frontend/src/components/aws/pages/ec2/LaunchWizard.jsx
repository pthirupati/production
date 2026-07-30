import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Minus, Plus, Trash2, Search, Check } from 'lucide-react'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, Breadcrumb, SectionLabel } from '../../ui/primitives'
import { AMI_CATALOG, INSTANCE_TYPES, INSTANCE_FAMILIES, getInstanceType, VOLUME_TYPES } from '../../lib/instanceTypes'
import { BASE } from '../../layout/serviceNav'

const STEPS = [
  { key: 'name', label: 'Name and tags' },
  { key: 'ami', label: 'Application and OS Images' },
  { key: 'type', label: 'Instance type' },
  { key: 'keypair', label: 'Key pair (login)' },
  { key: 'network', label: 'Network settings' },
  { key: 'storage', label: 'Configure storage' },
  { key: 'advanced', label: 'Advanced details' },
]

let volSeq = 1
const newVolKey = () => `vol-draft-${volSeq += 1}`

// gp3 baseline is 3000 IOPS / 125 MiB/s; provisioned volumes charge per-IOPS.
function volMonthlyCost(v) {
  const meta = VOLUME_TYPES.find((t) => t.type === v.type)
  const perGiB = meta?.price ?? 0.08
  let cost = (v.size || 0) * perGiB
  if ((v.type === 'io1' || v.type === 'io2') && v.iops) cost += Math.max(0, v.iops) * 0.065
  return cost
}

export default function LaunchWizard() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const keyPairs = scoped(useAwsStore((s) => s.keyPairs), region)
  const subnets = scoped(useAwsStore((s) => s.subnets), region)
  const securityGroups = scoped(useAwsStore((s) => s.securityGroups), region)
  const storeAmis = scoped(useAwsStore((s) => s.amis), region)
  const iamRoles = useAwsStore((s) => s.iamRoles) || []
  const launchInstances = useAwsStore((s) => s.launchInstances)
  const setInstanceName = useAwsStore((s) => s.setInstanceName)
  const setDisableApiTermination = useAwsStore((s) => s.setDisableApiTermination)
  const createKeyPair = useAwsStore((s) => s.createKeyPair)
  const pushFlash = useAwsStore((s) => s.pushFlash)

  // My AMIs from the store, presented alongside the Quick Start catalog.
  const myAmis = useMemo(() => storeAmis.map((a) => ({ id: a.id, name: a.name, arch: a.arch, freeTier: false, my: true, platform: a.platform })), [storeAmis])
  const allAmis = useMemo(() => [
    ...AMI_CATALOG.map((a) => ({ ...a, my: false })),
    ...myAmis,
  ], [myAmis])

  const [name, setName] = useState('')
  const [tags, setTags] = useState([{ key: 'Name', value: '' }])
  const [amiFilter, setAmiFilter] = useState('all') // all | quick | my
  const [amiSearch, setAmiSearch] = useState('')
  const [amiId, setAmiId] = useState(AMI_CATALOG[0].id)
  const [family, setFamily] = useState('all')
  const [typeSearch, setTypeSearch] = useState('')
  const [type, setType] = useState('t3.micro')
  const [keyName, setKeyName] = useState(keyPairs[0]?.name || '')
  const [subnetId, setSubnetId] = useState('')
  const [sgIds, setSgIds] = useState(securityGroups[0] ? [securityGroups[0].id] : [])
  const [autoPublicIp, setAutoPublicIp] = useState(true)
  const [volumes, setVolumes] = useState([
    { key: newVolKey(), device: '/dev/xvda', size: 8, type: 'gp3', iops: 3000, throughput: 125, encrypted: false, deleteOnTermination: true },
  ])
  const [iamRole, setIamRole] = useState('')
  const [userData, setUserData] = useState('')
  const [detailedMonitoring, setDetailedMonitoring] = useState(false)
  const [termProtection, setTermProtection] = useState(false)
  const [count, setCount] = useState(1)
  const [launched, setLaunched] = useState(null)
  const [errors, setErrors] = useState({})

  const it = getInstanceType(type)

  // Running cost: instance-hours + per-volume monthly.
  const instanceHourly = it.price
  const storageMonthly = volumes.reduce((sum, v) => sum + volMonthlyCost(v), 0)
  const hourlyEach = instanceHourly + storageMonthly / 730
  const monthlyTotal = hourlyEach * 730 * count

  const selectedAmi = allAmis.find((a) => a.id === amiId) || allAmis[0]

  const filteredAmis = allAmis.filter((a) => {
    if (amiFilter === 'quick' && a.my) return false
    if (amiFilter === 'my' && !a.my) return false
    if (!amiSearch) return true
    const q = amiSearch.toLowerCase()
    return a.name.toLowerCase().includes(q) || a.id.toLowerCase().includes(q) || (a.os || '').toLowerCase().includes(q)
  })

  const filteredTypes = INSTANCE_TYPES.filter((t) => {
    if (family !== 'all' && t.family !== family) return false
    if (!typeSearch) return true
    const q = typeSearch.toLowerCase()
    return t.type.toLowerCase().includes(q) || t.family.toLowerCase().includes(q)
  })

  const setTag = (i, patch) => setTags((ts) => ts.map((t, idx) => (idx === i ? { ...t, ...patch } : t)))
  const addTag = () => setTags((ts) => [...ts, { key: '', value: '' }])
  const removeTag = (i) => setTags((ts) => ts.filter((_, idx) => idx !== i))

  const addVolume = () => setVolumes((vs) => {
    const nextLetter = String.fromCharCode('f'.charCodeAt(0) + Math.max(0, vs.length - 1))
    return [...vs, { key: newVolKey(), device: `/dev/sd${nextLetter}`, size: 8, type: 'gp3', iops: 3000, throughput: 125, encrypted: true, deleteOnTermination: true }]
  })
  const setVol = (i, patch) => setVolumes((vs) => vs.map((v, idx) => (idx === i ? { ...v, ...patch } : v)))
  const removeVol = (i) => setVolumes((vs) => (vs.length > 1 ? vs.filter((_, idx) => idx !== i) : vs))

  const toggleSg = (id) => setSgIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))

  const validate = () => {
    const e = {}
    if (count < 1 || count > 20) e.count = 'Number of instances must be 1–20'
    if (!sgIds.length) e.sg = 'Select at least one security group'
    if (!volumes.length) e.storage = 'Add at least one volume'
    if (volumes.some((v) => !v.size || v.size < 1)) e.storage = 'Every volume needs a size of at least 1 GiB'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const launch = () => {
    if (!validate()) return
    const root = volumes[0]
    const created = launchInstances({
      name,
      amiId,
      type,
      count,
      keyName,
      subnetId,
      securityGroups: sgIds,
      volumeSize: root?.size || 8,
      volumeType: root?.type || 'gp3',
      monitoring: detailedMonitoring,
      tags: Object.fromEntries(tags.filter((t) => t.key && t.value && t.key !== 'Name').map((t) => [t.key, t.value])),
    })
    // Post-launch attribute application matching the wizard's advanced options.
    created.forEach((inst, idx) => {
      if (count > 1 && name) setInstanceName(inst.id, `${name}-${idx + 1}`)
      if (termProtection) setDisableApiTermination(inst.id, true)
    })
    if (iamRole) {
      // Patch iamRole directly through the store's instance array.
      useAwsStore.setState((s) => ({ instances: s.instances.map((i) => (created.some((c) => c.id === i.id) ? { ...i, iamRole } : i)) }))
    }
    pushFlash('success', `Successfully initiated launch of ${created.length} instance(s)`)
    setLaunched(created)
  }

  if (launched) {
    return (
      <div>
        <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Instances', onClick: () => navigate(`${BASE}/ec2/instances`) }, { label: 'Launch an instance' }]} />
        <div className="aws-page" style={{ paddingTop: 0 }}>
          <div className="aws-flash aws-flash-success"><Check size={18} style={{ marginTop: 1 }} /><div><strong>Success</strong><div>Successfully initiated launch of instance {launched.map((i) => i.id).join(', ')}</div></div></div>
          <div className="aws-card" style={{ maxWidth: 600 }}>
            {launched.map((i) => <div key={i.id} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}><a onClick={() => navigate(`${BASE}/ec2/instances/${i.id}`)} className="aws-mono">{i.id}</a> <Badge state="pending" /></div>)}
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <Button variant="primary" onClick={() => navigate(`${BASE}/ec2/instances`)}>View all instances</Button>
              <Button onClick={() => { setLaunched(null); setName('') }}>Launch more</Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const Section = ({ id, label, children }) => (
    <div className="aws-card" id={`launch-${id}`} style={{ marginBottom: 16 }}>
      <h3 style={{ marginBottom: 12 }}>{label}</h3>
      {children}
    </div>
  )

  const showProvisioned = volumes.some((v) => v.type === 'io1' || v.type === 'io2')

  return (
    <div>
      <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Instances', onClick: () => navigate(`${BASE}/ec2/instances`) }, { label: 'Launch an instance' }]} />
      <div className="aws-page" style={{ paddingTop: 0, display: 'grid', gridTemplateColumns: '200px 1fr 300px', gap: 20 }}>
        {/* Step rail */}
        <div style={{ position: 'sticky', top: 60, alignSelf: 'start' }}>
          <div className="aws-card" style={{ padding: 12 }}>
            <SectionLabel>Steps</SectionLabel>
            {STEPS.map((s, i) => (
              <a
                key={s.key}
                onClick={() => { const el = document.getElementById(`launch-${s.key}`); el?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}
                style={{ display: 'block', padding: '6px 0', fontSize: 13 }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, borderRadius: '50%', border: '1px solid var(--aws-border)', fontSize: 11, marginRight: 8 }}>{i + 1}</span>
                {s.label}
              </a>
            ))}
          </div>
        </div>

        <div>
          <h1 style={{ marginBottom: 16 }}>Launch an instance</h1>

          <Section id="name" label="Name and tags">
            <label className="aws-label">Name</label>
            <input className="aws-input" value={name} onChange={(e) => { setName(e.target.value); setTag(0, { value: e.target.value }) }} placeholder="e.g. my-web-server" style={{ marginBottom: 14 }} />
            <SectionLabel>Additional tags</SectionLabel>
            <table className="aws-table" style={{ marginTop: 6 }}>
              <thead><tr><th>Key</th><th>Value</th><th style={{ width: 44 }} /></tr></thead>
              <tbody>
                {tags.map((t, i) => (
                  <tr key={i}>
                    <td><input className="aws-input" value={t.key} disabled={i === 0} onChange={(e) => setTag(i, { key: e.target.value })} placeholder="Key" /></td>
                    <td><input className="aws-input" value={t.value} onChange={(e) => setTag(i, { value: e.target.value })} placeholder="Value" /></td>
                    <td>{i > 0 && <Button icon={Trash2} onClick={() => removeTag(i)} title="Remove tag" />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <a style={{ display: 'inline-block', marginTop: 8 }} onClick={addTag}>Add tag</a>
          </Section>

          <Section id="ami" label="Application and OS Images (Amazon Machine Image)">
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
              <div className="aws-tabs" style={{ marginBottom: 0 }}>
                {[['all', 'All'], ['quick', 'Quick Start'], ['my', 'My AMIs']].map(([k, lbl]) => (
                  <button key={k} className={`aws-tab ${amiFilter === k ? 'aws-tab-active' : ''}`} onClick={() => setAmiFilter(k)}>{lbl}{k === 'my' ? ` (${myAmis.length})` : ''}</button>
                ))}
              </div>
              <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
                <Search size={15} style={{ position: 'absolute', left: 8, top: 8, color: 'var(--aws-text-muted)' }} />
                <input className="aws-input" style={{ paddingLeft: 28 }} value={amiSearch} placeholder="Search AMIs by name or ID" onChange={(e) => setAmiSearch(e.target.value)} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
              {filteredAmis.map((a) => (
                <div key={a.id} onClick={() => setAmiId(a.id)} className="aws-card" style={{ cursor: 'pointer', borderColor: amiId === a.id ? 'var(--aws-input-focus)' : undefined, borderWidth: amiId === a.id ? 2 : 1, padding: 12 }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{a.name}</div>
                  <div className="aws-mono" style={{ fontSize: 11, color: 'var(--aws-text-secondary)' }}>{a.id}</div>
                  <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <span className="aws-badge aws-badge-terminated" style={{ height: 18 }}>{a.arch}</span>
                    {a.my && <span className="aws-badge aws-badge-creating" style={{ height: 18 }}>My AMI</span>}
                    {a.freeTier && <span className="aws-badge aws-badge-running" style={{ height: 18 }}>Free tier eligible</span>}
                  </div>
                </div>
              ))}
              {!filteredAmis.length && <div className="aws-hint">No AMIs match this filter.</div>}
            </div>
          </Section>

          <Section id="type" label="Instance type">
            <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
              <select className="aws-select" style={{ maxWidth: 220 }} value={family} onChange={(e) => setFamily(e.target.value)}>
                <option value="all">All families</option>
                {INSTANCE_FAMILIES.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
              <div style={{ position: 'relative', flex: 1, maxWidth: 280 }}>
                <Search size={15} style={{ position: 'absolute', left: 8, top: 8, color: 'var(--aws-text-muted)' }} />
                <input className="aws-input" style={{ paddingLeft: 28 }} value={typeSearch} placeholder="Search instance types" onChange={(e) => setTypeSearch(e.target.value)} />
              </div>
            </div>
            <div style={{ maxHeight: 260, overflowY: 'auto', border: '1px solid var(--aws-table-border)', borderRadius: 'var(--aws-radius-md)' }}>
              <table className="aws-table">
                <thead><tr><th /><th>Type</th><th>vCPU</th><th>Memory</th><th>Network</th><th>On-demand price</th></tr></thead>
                <tbody>
                  {filteredTypes.map((t) => (
                    <tr key={t.type} onClick={() => setType(t.type)} className={type === t.type ? 'aws-row-selected' : ''} style={{ cursor: 'pointer' }}>
                      <td><input type="radio" checked={type === t.type} onChange={() => setType(t.type)} aria-label={`Select ${t.type}`} /></td>
                      <td className="aws-mono">{t.type}{t.freeTier ? ' ·' : ''}{t.freeTier && <span className="aws-badge aws-badge-running" style={{ height: 16, marginLeft: 4 }}>Free tier</span>}</td>
                      <td>{t.vcpu}</td>
                      <td>{t.memGiB} GiB</td>
                      <td>{t.net}</td>
                      <td>${t.price.toFixed(4)}/hr</td>
                    </tr>
                  ))}
                  {!filteredTypes.length && <tr><td colSpan={6} className="aws-hint" style={{ padding: 12 }}>No instance types match.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="aws-hint">Selected: {it.type} · {it.family} · {it.arch} · {it.net}</div>
          </Section>

          <Section id="keypair" label="Key pair (login)">
            <select className="aws-select" value={keyName} onChange={(e) => setKeyName(e.target.value)}>
              <option value="">Proceed without a key pair (Not recommended)</option>
              {keyPairs.map((k) => <option key={k.id} value={k.name}>{k.name} ({k.type})</option>)}
            </select>
            <a style={{ display: 'inline-block', marginTop: 8 }} onClick={() => { const kp = createKeyPair({ name: `key-${Date.now().toString(36)}`, type: 'rsa' }); setKeyName(kp.name); pushFlash('success', `Created key pair ${kp.name} (private key would download)`) }}>Create new key pair</a>
          </Section>

          <Section id="network" label="Network settings">
            <label className="aws-label">Subnet</label>
            <select className="aws-select" value={subnetId} onChange={(e) => setSubnetId(e.target.value)} style={{ marginBottom: 12 }}>
              <option value="">No preference (default subnet in any AZ)</option>
              {subnets.map((s) => <option key={s.id} value={s.id}>{s.id} | {s.az} | {s.cidr}</option>)}
            </select>
            <label className="aws-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={autoPublicIp} onChange={(e) => setAutoPublicIp(e.target.checked)} /> Auto-assign public IP
            </label>
            <SectionLabel>Firewall (security groups)</SectionLabel>
            <div className={`aws-card ${errors.sg ? 'aws-invalid' : ''}`} style={{ padding: 10, borderColor: errors.sg ? 'var(--aws-error)' : undefined }}>
              {securityGroups.map((s) => (
                <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', cursor: 'pointer' }}>
                  <input type="checkbox" checked={sgIds.includes(s.id)} onChange={() => toggleSg(s.id)} />
                  <span><strong>{s.name}</strong> <span className="aws-mono" style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>({s.id})</span> — {s.description}</span>
                </label>
              ))}
              {!securityGroups.length && <div className="aws-hint">No security groups in this Region.</div>}
            </div>
            {errors.sg && <div className="aws-field-error">{errors.sg}</div>}
          </Section>

          <Section id="storage" label="Configure storage">
            <table className="aws-table">
              <thead>
                <tr>
                  <th>Device name</th><th>Size (GiB)</th><th>Volume type</th>
                  {showProvisioned && <th>IOPS</th>}
                  <th>Throughput</th><th>Encrypted</th><th>Delete on term.</th><th style={{ width: 44 }} />
                </tr>
              </thead>
              <tbody>
                {volumes.map((v, i) => {
                  const meta = VOLUME_TYPES.find((t) => t.type === v.type)
                  const isGp3 = v.type === 'gp3'
                  const isProvisioned = v.type === 'io1' || v.type === 'io2'
                  return (
                    <tr key={v.key}>
                      <td><input className="aws-input" style={{ width: 120 }} value={v.device} onChange={(e) => setVol(i, { device: e.target.value })} /></td>
                      <td><input className="aws-input" type="number" min={1} max={16384} style={{ width: 84 }} value={v.size} onChange={(e) => setVol(i, { size: Number(e.target.value) })} /></td>
                      <td>
                        <select className="aws-select" style={{ width: 190 }} value={v.type} onChange={(e) => setVol(i, { type: e.target.value })}>
                          {VOLUME_TYPES.map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
                        </select>
                      </td>
                      {showProvisioned && (
                        <td>{isProvisioned ? <input className="aws-input" type="number" min={100} max={meta?.maxIops || 64000} style={{ width: 90 }} value={v.iops} onChange={(e) => setVol(i, { iops: Number(e.target.value) })} /> : <span className="aws-hint">—</span>}</td>
                      )}
                      <td>{isGp3 ? <input className="aws-input" type="number" min={125} max={1000} style={{ width: 90 }} value={v.throughput} onChange={(e) => setVol(i, { throughput: Number(e.target.value) })} /> : <span className="aws-hint">n/a</span>}</td>
                      <td><input type="checkbox" checked={v.encrypted} onChange={(e) => setVol(i, { encrypted: e.target.checked })} aria-label="Encrypted" /></td>
                      <td><input type="checkbox" checked={v.deleteOnTermination} onChange={(e) => setVol(i, { deleteOnTermination: e.target.checked })} aria-label="Delete on termination" /></td>
                      <td>{i > 0 && <Button icon={Trash2} onClick={() => removeVol(i)} title="Remove volume" />}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {errors.storage && <div className="aws-field-error">{errors.storage}</div>}
            <a style={{ display: 'inline-block', marginTop: 8 }} onClick={addVolume}>Add new volume</a>
          </Section>

          <Section id="advanced" label="Advanced details">
            <label className="aws-label">IAM instance profile</label>
            <select className="aws-select" value={iamRole} onChange={(e) => setIamRole(e.target.value)} style={{ marginBottom: 14 }}>
              <option value="">No IAM role attached</option>
              {iamRoles.map((r) => <option key={r.id} value={r.name}>{r.name}</option>)}
            </select>

            <label className="aws-label">User data</label>
            <textarea className="aws-input" style={{ minHeight: 90, fontFamily: 'var(--aws-mono-font, monospace)', marginBottom: 14 }} value={userData} onChange={(e) => setUserData(e.target.value)} placeholder={'#!/bin/bash\nyum install -y httpd\nsystemctl start httpd'} />

            <label className="aws-label" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <input type="checkbox" checked={detailedMonitoring} onChange={(e) => setDetailedMonitoring(e.target.checked)} /> Enable detailed CloudWatch monitoring
            </label>
            <label className="aws-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={termProtection} onChange={(e) => setTermProtection(e.target.checked)} /> Enable termination protection
            </label>
          </Section>
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
            <div style={{ borderTop: '1px solid var(--aws-border-light)', paddingTop: 8, fontSize: 13, display: 'grid', gap: 3 }}>
              <div>AMI: {selectedAmi?.name}</div>
              <div>Type: {type} ({it.vcpu} vCPU, {it.memGiB} GiB)</div>
              <div>Key pair: {keyName || 'None'}</div>
              <div>Security groups: {sgIds.length}</div>
              <div>Storage: {volumes.length} volume(s), {volumes.reduce((n, v) => n + (v.size || 0), 0)} GiB total</div>
              <div>IAM role: {iamRole || 'None'}</div>
              <div>Monitoring: {detailedMonitoring ? 'Detailed' : 'Basic'}</div>
              <div>Termination protection: {termProtection ? 'On' : 'Off'}</div>
            </div>
            <div style={{ marginTop: 12, fontSize: 13, borderTop: '1px solid var(--aws-border-light)', paddingTop: 8 }}>
              <div>Hourly (each): <strong>${hourlyEach.toFixed(4)}</strong></div>
              <div>Est. monthly ({count}×): <strong>${monthlyTotal.toFixed(2)}</strong></div>
            </div>
            <Button variant="primary" onClick={launch} style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}>Launch instance</Button>
            <a style={{ display: 'block', textAlign: 'center', marginTop: 8 }} onClick={() => navigate(`${BASE}/ec2/instances`)}>Cancel</a>
          </div>
        </div>
      </div>
    </div>
  )
}
