import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Trash2, Plus } from 'lucide-react'
import { useAwsStore } from '../../store/awsStore'
import { Button, Badge, Tabs, IDCopy, Breadcrumb, Modal, EmptyState } from '../../ui/primitives'
import { isValidCidr } from '../../lib/validators'
import { BASE } from '../../layout/serviceNav'

// Rule "type" presets auto-fill protocol + port range (mirrors the EC2 console).
const RULE_TYPES = [
  { type: 'SSH', protocol: 'TCP', from: 22, to: 22 },
  { type: 'HTTP', protocol: 'TCP', from: 80, to: 80 },
  { type: 'HTTPS', protocol: 'TCP', from: 443, to: 443 },
  { type: 'MySQL/Aurora', protocol: 'TCP', from: 3306, to: 3306 },
  { type: 'PostgreSQL', protocol: 'TCP', from: 5432, to: 5432 },
  { type: 'RDP', protocol: 'TCP', from: 3389, to: 3389 },
  { type: 'Custom TCP', protocol: 'TCP', from: 0, to: 0, custom: true },
  { type: 'Custom UDP', protocol: 'UDP', from: 0, to: 0, custom: true },
  { type: 'Custom ICMP - IPv4', protocol: 'ICMP', from: -1, to: -1 },
  { type: 'All traffic', protocol: 'All', from: 0, to: 65535 },
]

const SOURCE_PRESETS = [
  { key: 'anywhere-ipv4', label: 'Anywhere-IPv4 (0.0.0.0/0)', value: '0.0.0.0/0' },
  { key: 'my-ip', label: 'My IP', value: '203.0.113.25/32' },
  { key: 'custom', label: 'Custom', value: '' },
]

let draftSeq = 1
const draftId = () => `sgr-draft-${draftSeq += 1}`

function portDisplay(r) {
  if (r.protocol === 'ICMP' || r.from === -1) return 'All'
  if (r.protocol === 'All') return 'All'
  return r.from === r.to ? String(r.from) : `${r.from}-${r.to}`
}

function EditRulesModal({ sg, direction, onClose }) {
  const setSgRules = useAwsStore((s) => s.setSgRules)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const existing = (direction === 'outbound' ? sg.outbound : sg.inbound) || []
  const [rows, setRows] = useState(() => existing.map((r) => {
    const preset = SOURCE_PRESETS.find((p) => p.value === r.source)
    return { ...r, _sourceMode: preset ? preset.key : (r.source ? 'custom' : 'custom') }
  }))
  const [errors, setErrors] = useState({})

  const setRow = (i, patch) => setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  const removeRow = (i) => setRows((rs) => rs.filter((_, idx) => idx !== i))
  const addRow = () => setRows((rs) => [...rs, { id: draftId(), type: 'Custom TCP', protocol: 'TCP', from: 0, to: 0, source: '0.0.0.0/0', description: '', _sourceMode: 'anywhere-ipv4' }])

  const onTypeChange = (i, typeName) => {
    const preset = RULE_TYPES.find((t) => t.type === typeName)
    if (!preset) return
    setRow(i, { type: preset.type, protocol: preset.protocol, from: preset.from, to: preset.to })
  }

  const onSourceModeChange = (i, mode) => {
    const preset = SOURCE_PRESETS.find((p) => p.key === mode)
    setRow(i, { _sourceMode: mode, source: mode === 'custom' ? (rows[i].source || '') : preset.value })
  }

  const validateSource = (r) => {
    const src = String(r.source || '').trim()
    if (!src) return 'Source required'
    // Security-group reference (sg-...) or self are valid non-CIDR sources.
    if (src === 'self' || /^sg-[0-9a-f]+$/i.test(src)) return null
    if (!isValidCidr(src)) return 'Enter a valid CIDR (e.g. 10.0.0.0/24) or sg-id'
    return null
  }

  const save = () => {
    const errs = {}
    rows.forEach((r, i) => { const e = validateSource(r); if (e) errs[i] = e })
    if (Object.keys(errs).length) { setErrors(errs); return }
    const clean = rows.map(({ _sourceMode, ...r }) => r)
    const res = setSgRules(sg.id, direction, clean)
    if (res && res.ok === false) return
    pushFlash('success', `Updated ${direction} rules for ${sg.name}`)
    onClose()
  }

  return (
    <Modal
      title={`Edit ${direction} rules`}
      width={900}
      onClose={onClose}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" onClick={save}>Save rules</Button></>}
    >
      <table className="aws-table">
        <thead>
          <tr>
            <th>Type</th><th>Protocol</th><th>Port range</th><th>Source</th><th>Description</th><th style={{ width: 44 }} />
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const preset = RULE_TYPES.find((t) => t.type === r.type)
            const isCustom = preset?.custom
            const portEditable = isCustom
            return (
              <tr key={r.id}>
                <td>
                  <select className="aws-select" style={{ width: 160 }} value={r.type} onChange={(e) => onTypeChange(i, e.target.value)}>
                    {RULE_TYPES.map((t) => <option key={t.type} value={t.type}>{t.type}</option>)}
                    {!RULE_TYPES.some((t) => t.type === r.type) && <option value={r.type}>{r.type}</option>}
                  </select>
                </td>
                <td>{r.protocol}</td>
                <td>
                  {portEditable ? (
                    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                      <input className="aws-input" type="number" style={{ width: 70 }} value={r.from} onChange={(e) => setRow(i, { from: Number(e.target.value), to: Number(e.target.value) })} />
                    </div>
                  ) : portDisplay(r)}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <select className="aws-select" style={{ width: 130 }} value={r._sourceMode} onChange={(e) => onSourceModeChange(i, e.target.value)}>
                      {SOURCE_PRESETS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
                    </select>
                    <input className={`aws-input ${errors[i] ? 'aws-invalid' : ''}`} style={{ width: 150 }} value={r.source} disabled={r._sourceMode !== 'custom'} onChange={(e) => setRow(i, { source: e.target.value })} placeholder="0.0.0.0/0 or sg-id" />
                  </div>
                  {errors[i] && <div className="aws-field-error">{errors[i]}</div>}
                </td>
                <td><input className="aws-input" value={r.description || ''} onChange={(e) => setRow(i, { description: e.target.value })} placeholder="Optional" /></td>
                <td><Button icon={Trash2} onClick={() => removeRow(i)} title="Delete rule" /></td>
              </tr>
            )
          })}
          {!rows.length && <tr><td colSpan={6} className="aws-hint" style={{ padding: 12 }}>No rules. Add a rule to allow traffic.</td></tr>}
        </tbody>
      </table>
      <Button icon={Plus} onClick={addRow} style={{ marginTop: 10 }}>Add rule</Button>
    </Modal>
  )
}

function RuleTable({ rules }) {
  if (!rules.length) return <div className="aws-hint" style={{ marginTop: 8 }}>No rules.</div>
  return (
    <table className="aws-table" style={{ marginTop: 8 }}>
      <thead><tr><th>Rule ID</th><th>Type</th><th>Protocol</th><th>Port range</th><th>Source / Destination</th><th>Description</th></tr></thead>
      <tbody>
        {rules.map((r) => (
          <tr key={r.id}>
            <td className="aws-mono" style={{ fontSize: 12 }}>{r.id}</td>
            <td>{r.type}</td>
            <td>{r.protocol}</td>
            <td>{portDisplay(r)}</td>
            <td className="aws-mono">{r.source}</td>
            <td>{r.description || '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function SecurityGroupDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const sg = useAwsStore((s) => (s.securityGroups || []).find((g) => g.id === id))
  const instances = useAwsStore((s) => s.instances) || []
  const [tab, setTab] = useState('inbound')
  const [editing, setEditing] = useState(null) // 'inbound' | 'outbound'

  if (!sg) {
    return <div className="aws-page"><EmptyState title="Security group not found" body="It may have been deleted or belongs to another Region." action={<Button onClick={() => navigate(`${BASE}/ec2/security-groups`)}>Back to security groups</Button>} /></div>
  }

  const attachedInstances = instances.filter((i) => i.state !== 'terminated' && (i.securityGroups || []).includes(sg.id))

  return (
    <div>
      <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Security Groups', onClick: () => navigate(`${BASE}/ec2/security-groups`) }, { label: sg.id }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 12 }}>{sg.name} <Badge state="available">available</Badge></h1>
          <Button variant="primary" onClick={() => setEditing(tab === 'outbound' ? 'outbound' : 'inbound')}>Edit {tab === 'outbound' ? 'outbound' : 'inbound'} rules</Button>
        </div>

        <div className="aws-card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            <div className="aws-kv"><span className="k">Security group ID</span><span className="v"><IDCopy value={sg.id} /></span></div>
            <div className="aws-kv"><span className="k">Security group name</span><span className="v">{sg.name}</span></div>
            <div className="aws-kv"><span className="k">Description</span><span className="v">{sg.description || '—'}</span></div>
            <div className="aws-kv"><span className="k">VPC ID</span><span className="v"><IDCopy value={sg.vpcId} /></span></div>
            <div className="aws-kv"><span className="k">Inbound rules</span><span className="v">{(sg.inbound || []).length}</span></div>
            <div className="aws-kv"><span className="k">Outbound rules</span><span className="v">{(sg.outbound || []).length}</span></div>
          </div>
        </div>

        <Tabs tabs={[
          { key: 'inbound', label: `Inbound rules (${(sg.inbound || []).length})` },
          { key: 'outbound', label: `Outbound rules (${(sg.outbound || []).length})` },
          { key: 'associated', label: `Associated instances (${attachedInstances.length})` },
        ]} active={tab} onChange={setTab} />

        <div style={{ marginTop: 16 }}>
          {tab === 'inbound' && (
            <div className="aws-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="aws-section-label">Inbound rules</div>
                <Button onClick={() => setEditing('inbound')}>Edit inbound rules</Button>
              </div>
              <RuleTable rules={sg.inbound || []} />
            </div>
          )}
          {tab === 'outbound' && (
            <div className="aws-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="aws-section-label">Outbound rules</div>
                <Button onClick={() => setEditing('outbound')}>Edit outbound rules</Button>
              </div>
              <RuleTable rules={sg.outbound || []} />
            </div>
          )}
          {tab === 'associated' && (
            <div className="aws-card">
              {attachedInstances.length ? (
                <table className="aws-table">
                  <thead><tr><th>Instance ID</th><th>Name</th><th>State</th><th>Type</th></tr></thead>
                  <tbody>
                    {attachedInstances.map((i) => (
                      <tr key={i.id}>
                        <td><IDCopy value={i.id} onClick={() => navigate(`${BASE}/ec2/instances/${i.id}`)} /></td>
                        <td>{i.name || '—'}</td>
                        <td><Badge state={i.state} /></td>
                        <td>{i.type}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div className="aws-hint">No running instances use this security group.</div>}
            </div>
          )}
        </div>
      </div>
      {editing && <EditRulesModal sg={sg} direction={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}
