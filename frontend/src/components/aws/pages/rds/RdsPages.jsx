import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Database, Plus, RefreshCw, Settings2, Trash2 } from 'lucide-react'
import { ACCOUNT, useAwsStore, scoped } from '../../store/awsStore'
import { arn } from '../../lib/ids'
import { Badge, Breadcrumb, Button, ConfirmDialog, DataTable, EmptyState, IDCopy, Modal, SectionLabel, Tabs } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'
import { BASE } from '../../layout/serviceNav'
import { getResourceConfig } from '../generic/serviceConfigs'

const SERVICE = 'rds'
const RESOURCE = 'databases'

// RDS DB identifier: lowercase, start with a letter, 1-63 chars, letters/digits/hyphens.
function validateDbId(name, existing) {
  if (!name) return 'DB instance identifier is required.'
  if (!/^[a-z][a-z0-9-]{0,62}$/.test(name)) return 'Must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens (1-63 chars).'
  if (name.endsWith('-') || name.includes('--')) return 'Cannot end with a hyphen or contain two consecutive hyphens.'
  if (existing.some((d) => d.name === name)) return 'A DB instance with this identifier already exists in this Region.'
  return ''
}

function rdsBadge(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'available') return 'available'
  if (['creating', 'backing-up', 'modifying', 'rebooting', 'starting'].includes(s)) return 'pending'
  if (['stopped', 'deleting', 'failed'].includes(s)) return 'stopped'
  return 'available'
}

const ENGINES = [
  { key: 'PostgreSQL 15.4', label: 'PostgreSQL', port: 5432, family: 'postgres' },
  { key: 'PostgreSQL 16.1', label: 'PostgreSQL', port: 5432, family: 'postgres' },
  { key: 'MySQL 8.0.35', label: 'MySQL', port: 3306, family: 'mysql' },
  { key: 'MariaDB 10.11', label: 'MariaDB', port: 3306, family: 'mariadb' },
  { key: 'Aurora PostgreSQL', label: 'Aurora PostgreSQL', port: 5432, family: 'aurora-postgresql' },
  { key: 'Aurora MySQL', label: 'Aurora MySQL', port: 3306, family: 'aurora-mysql' },
  { key: 'Oracle 19c', label: 'Oracle', port: 1521, family: 'oracle-ee' },
  { key: 'SQL Server 2022', label: 'SQL Server', port: 1433, family: 'sqlserver-ex' },
]
const CLASSES = ['db.t3.micro', 'db.t3.small', 'db.t3.medium', 'db.m5.large', 'db.m5.xlarge', 'db.r5.large', 'db.r5.xlarge']
const TEMPLATES = {
  Production: { class: 'db.m5.large', storage: 100, multiAz: true },
  'Dev/Test': { class: 'db.t3.small', storage: 20, multiAz: false },
  'Free tier': { class: 'db.t3.micro', storage: 20, multiAz: false },
}

function enginePort(engine) {
  return (ENGINES.find((e) => e.key === engine) || {}).port || 5432
}

function dbArn(row, region) {
  return arn('rds', region, ACCOUNT, `db:${row.name}`)
}

export function RdsList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const databases = scoped(useAwsStore((s) => s.genericResources?.rds?.databases), region)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const [selected, setSelected] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)

  const columns = [
    { key: 'name', label: 'DB identifier', render: (r) => <a onClick={() => navigate(`${BASE}/rds/databases/${r.id}`)}>{r.name}</a> },
    { key: 'status', label: 'Status', render: (r) => <Badge state={rdsBadge(r.status)}>{r.status}</Badge> },
    { key: 'engine', label: 'Engine', render: (r) => r.engine },
    { key: 'class', label: 'Size', render: (r) => r.class },
    { key: 'multiAz', label: 'Multi-AZ', render: (r) => (r.multiAz ? 'Yes' : 'No') },
    { key: 'endpoint', label: 'Region & AZ', render: (r) => `${r.region || region}${r.multiAz ? ' (Multi-AZ)' : 'a'}` },
  ]

  return (
    <div>
      <Breadcrumb items={[{ label: 'RDS', onClick: () => navigate(`${BASE}/rds/home`) }, { label: 'Databases' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1>Databases ({databases.length})</h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button disabled={selected.length !== 1} icon={Trash2} onClick={() => { const d = databases.find((x) => x.id === selected[0]); setDeleteTarget(d) }}>Delete</Button>
            <Button variant="primary" icon={Plus} onClick={() => navigate(`${BASE}/rds/databases/create`)}>Create database</Button>
          </div>
        </div>
        <DataTable
          columns={columns}
          rows={databases}
          getRowKey={(r) => r.id}
          selectable
          selected={selected}
          onSelect={setSelected}
          onRowClick={(r) => navigate(`${BASE}/rds/databases/${r.id}`)}
          rowActions={(r) => [
            { label: 'View details', onClick: () => navigate(`${BASE}/rds/databases/${r.id}`) },
            { label: 'Copy endpoint', onClick: () => navigator.clipboard?.writeText(r.endpoint || '') },
            { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
          ]}
          tableId="rds:databases"
          emptyTitle="No databases in this Region"
          emptyBody="Create a database to get started."
        />
      </div>
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.name}?`}
          body={`This permanently removes DB instance ${deleteTarget.name} from the local RDS simulation. In real AWS you would be prompted to create a final snapshot first.`}
          confirmLabel="Delete"
          confirmText={deleteTarget.name}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => {
            deleteGenericResource(SERVICE, RESOURCE, deleteTarget.id)
            useAwsStore.getState().pushFlash('success', `Deleting DB instance ${deleteTarget.name}`)
            setSelected([])
            setDeleteTarget(null)
          }}
        />
      )}
    </div>
  )
}

export function RdsCreate() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const databases = scoped(useAwsStore((s) => s.genericResources?.rds?.databases), region)
  const securityGroups = scoped(useAwsStore((s) => s.securityGroups), region)
  const createGenericResource = useAwsStore((s) => s.createGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)

  const [method, setMethod] = useState('Standard')
  const [engine, setEngine] = useState('PostgreSQL 15.4')
  const [template, setTemplate] = useState('Dev/Test')
  const [name, setName] = useState('')
  const [masterUser, setMasterUser] = useState('admin')
  const [masterPass, setMasterPass] = useState('')
  const [dbClass, setDbClass] = useState('db.t3.small')
  const [storage, setStorage] = useState(20)
  const [multiAz, setMultiAz] = useState(false)
  const [publiclyAccessible, setPubliclyAccessible] = useState(false)
  const [vpcSg, setVpcSg] = useState(securityGroups[0]?.id || '')

  const idError = name ? validateDbId(name, databases) : ''
  const passError = masterPass && masterPass.length < 8 ? 'Master password must be at least 8 characters.' : ''
  const storageError = storage < 20 || storage > 65536 ? 'Allocated storage must be between 20 and 65536 GiB.' : ''
  const canCreate = !!name && !idError && !passError && !storageError && (method === 'Easy' || !!masterPass)

  const applyTemplate = (t) => {
    setTemplate(t)
    const preset = TEMPLATES[t]
    if (preset) { setDbClass(preset.class); setStorage(preset.storage); setMultiAz(preset.multiAz) }
  }

  const submit = () => {
    const created = createGenericResource(SERVICE, RESOURCE, {
      name, engine, class: dbClass, storage: Number(storage), multiAz,
      masterUser, publiclyAccessible, vpcSg,
      port: enginePort(engine),
    })
    if (!created || created.ok === false) return
    pushFlash('success', `Creating DB instance ${name}. It will become available shortly.`)
    navigate(`${BASE}/rds/databases/${created.id}`)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'RDS', onClick: () => navigate(`${BASE}/rds/home`) }, { label: 'Databases', onClick: () => navigate(`${BASE}/rds/databases`) }, { label: 'Create database' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <h1 style={{ marginBottom: 16 }}>Create database</h1>

        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Choose a database creation method</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
            {[['Standard', 'Set all configuration options, including availability, security, backups, and maintenance.'], ['Easy', 'Use recommended best-practice configurations. Some options use defaults.']].map(([m, d]) => (
              <label key={m} className="aws-card aws-card-hover" style={{ cursor: 'pointer', borderColor: method === m ? 'var(--aws-orange)' : undefined }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="radio" name="method" checked={method === m} onChange={() => setMethod(m)} />
                  <strong>{m} create</strong>
                </div>
                <div className="aws-hint" style={{ marginTop: 6 }}>{d}</div>
              </label>
            ))}
          </div>
        </div>

        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Engine options</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10, marginTop: 10 }}>
            {ENGINES.map((e) => (
              <label key={e.key} className="aws-card aws-card-hover" style={{ cursor: 'pointer', padding: 12, borderColor: engine === e.key ? 'var(--aws-orange)' : undefined }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="radio" name="engine" checked={engine === e.key} onChange={() => setEngine(e.key)} />
                  <Database size={16} style={{ color: 'var(--aws-orange)' }} />
                  <span style={{ fontSize: 13 }}>{e.key}</span>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Templates</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 10 }}>
            {Object.keys(TEMPLATES).map((t) => (
              <label key={t} className="aws-card aws-card-hover" style={{ cursor: 'pointer', borderColor: template === t ? 'var(--aws-orange)' : undefined }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="radio" name="template" checked={template === t} onChange={() => applyTemplate(t)} />
                  <strong>{t}</strong>
                </div>
                <div className="aws-hint" style={{ marginTop: 6 }}>{TEMPLATES[t].class} · {TEMPLATES[t].storage} GiB{TEMPLATES[t].multiAz ? ' · Multi-AZ' : ''}</div>
              </label>
            ))}
          </div>
        </div>

        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Settings</SectionLabel>
          <div style={{ marginTop: 10 }}>
            <label className="aws-label">DB instance identifier</label>
            <input className={`aws-input ${idError ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="my-database-1" style={{ maxWidth: 420 }} />
            {idError && <div className="aws-field-error">{idError}</div>}
            <div className="aws-hint">Must be unique across all DB instances in your account in the current Region.</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
            <div>
              <label className="aws-label">Master username</label>
              <input className="aws-input" value={masterUser} onChange={(e) => setMasterUser(e.target.value)} />
            </div>
            <div>
              <label className="aws-label">Master password</label>
              <input type="password" className={`aws-input ${passError ? 'aws-invalid' : ''}`} value={masterPass} onChange={(e) => setMasterPass(e.target.value)} placeholder={method === 'Easy' ? 'Auto-generated' : 'At least 8 characters'} />
              {passError && <div className="aws-field-error">{passError}</div>}
            </div>
          </div>
        </div>

        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Instance configuration</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
            <div>
              <label className="aws-label">DB instance class</label>
              <select className="aws-input" value={dbClass} onChange={(e) => setDbClass(e.target.value)}>
                {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="aws-label">Allocated storage (GiB)</label>
              <input type="number" min={20} max={65536} className={`aws-input ${storageError ? 'aws-invalid' : ''}`} value={storage} onChange={(e) => setStorage(Number(e.target.value))} />
              {storageError && <div className="aws-field-error">{storageError}</div>}
            </div>
          </div>
          <label style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
            <input type="checkbox" checked={multiAz} onChange={(e) => setMultiAz(e.target.checked)} /> Create a standby instance (Multi-AZ deployment)
          </label>
        </div>

        <div className="aws-card" style={{ marginBottom: 16 }}>
          <SectionLabel>Connectivity</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
            <div>
              <label className="aws-label">VPC security group</label>
              <select className="aws-input" value={vpcSg} onChange={(e) => setVpcSg(e.target.value)}>
                {securityGroups.length === 0 && <option value="">(none)</option>}
                {securityGroups.map((sg) => <option key={sg.id} value={sg.id}>{sg.name} ({sg.id})</option>)}
              </select>
            </div>
            <div>
              <label className="aws-label">Public access</label>
              <label style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
                <input type="checkbox" checked={publiclyAccessible} onChange={(e) => setPubliclyAccessible(e.target.checked)} /> Publicly accessible
              </label>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button onClick={() => navigate(`${BASE}/rds/databases`)}>Cancel</Button>
          <Button variant="primary" disabled={!canCreate} onClick={submit}>Create database</Button>
        </div>
      </div>
    </div>
  )
}

export function RdsDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const db = useAwsStore((s) => (s.genericResources?.rds?.databases || []).find((d) => d.id === id))
  const snapshots = scoped(useAwsStore((s) => s.genericResources?.rds?.snapshots), region)
  const rebootDb = useAwsStore((s) => s.rebootDb)
  const modifyDb = useAwsStore((s) => s.modifyDb)
  const createGenericResource = useAwsStore((s) => s.createGenericResource)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const cfg = getResourceConfig(SERVICE, RESOURCE)
  const [tab, setTab] = useState('connectivity')
  const [modifyOpen, setModifyOpen] = useState(false)
  const [snapshotOpen, setSnapshotOpen] = useState(false)
  const [snapName, setSnapName] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [modClass, setModClass] = useState('')
  const [modStorage, setModStorage] = useState(0)
  const [modMultiAz, setModMultiAz] = useState(false)

  if (!db) return <div className="aws-page"><EmptyState title="DB instance not found" action={<Button onClick={() => navigate(`${BASE}/rds/databases`)}>Back to databases</Button>} /></div>

  const [host, port] = String(db.endpoint || '').split(':')
  const busy = ['creating', 'backing-up', 'modifying', 'rebooting', 'deleting'].includes(String(db.status).toLowerCase())
  const dbSnapshots = snapshots.filter((s) => s.name?.startsWith(db.name))

  const openModify = () => {
    setModClass(db.class); setModStorage(db.storage); setModMultiAz(!!db.multiAz)
    setModifyOpen(true)
  }

  const submitModify = () => {
    modifyDb(db.id, { class: modClass, storage: Number(modStorage), multiAz: modMultiAz })
    pushFlash('success', `Modifying ${db.name}. Changes will apply after the modification completes.`)
    setModifyOpen(false)
  }

  const submitSnapshot = () => {
    createGenericResource('rds', 'snapshots', { name: snapName || `${db.name}-snapshot`, engine: (db.engine || '').split(' ')[0], status: 'available', dbId: db.id })
    pushFlash('success', `Snapshot ${snapName || `${db.name}-snapshot`} created`)
    setSnapshotOpen(false); setSnapName('')
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'RDS', onClick: () => navigate(`${BASE}/rds/home`) }, { label: 'Databases', onClick: () => navigate(`${BASE}/rds/databases`) }, { label: db.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{db.name} <Badge state={rdsBadge(db.status)}>{db.status}</Badge></h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button icon={RefreshCw} disabled={busy} onClick={() => { rebootDb(db.id); pushFlash('info', `Rebooting ${db.name}`) }}>Reboot</Button>
            <Button icon={Settings2} disabled={busy} onClick={openModify}>Modify</Button>
            <Button variant="danger" onClick={() => setDeleteOpen(true)}>Delete</Button>
          </div>
        </div>

        <Tabs tabs={[
          { key: 'connectivity', label: 'Connectivity & security' },
          { key: 'configuration', label: 'Configuration' },
          { key: 'monitoring', label: 'Monitoring' },
          { key: 'maintenance', label: 'Maintenance & backups' },
        ]} active={tab} onChange={setTab} />

        <div style={{ marginTop: 16 }}>
          {tab === 'connectivity' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <SectionLabel>Endpoint & port</SectionLabel>
                <div className="aws-summary-grid" style={{ marginTop: 8 }}>
                  <div className="aws-kv"><span className="k">Endpoint</span><span className="v"><IDCopy value={host || '—'} /></span></div>
                  <div className="aws-kv"><span className="k">Port</span><span className="v">{port || enginePort(db.engine)}</span></div>
                  <div className="aws-kv"><span className="k">Availability</span><span className="v">{db.multiAz ? 'Multi-AZ' : 'Single-AZ'}</span></div>
                </div>
              </div>
              <div className="aws-card">
                <SectionLabel>Networking</SectionLabel>
                <div className="aws-summary-grid" style={{ marginTop: 8 }}>
                  <div className="aws-kv"><span className="k">VPC security group</span><span className="v">{db.vpcSg || 'default'}</span></div>
                  <div className="aws-kv"><span className="k">Publicly accessible</span><span className="v">{db.publiclyAccessible ? 'Yes' : 'No'}</span></div>
                  <div className="aws-kv"><span className="k">Region</span><span className="v">{db.region || region}</span></div>
                  <div className="aws-kv"><span className="k">ARN</span><span className="v"><IDCopy value={dbArn(db, region)} /></span></div>
                </div>
              </div>
            </div>
          )}
          {tab === 'configuration' && (
            <div className="aws-card">
              <SectionLabel>Configuration</SectionLabel>
              <div className="aws-summary-grid" style={{ marginTop: 8 }}>
                <div className="aws-kv"><span className="k">Engine</span><span className="v">{db.engine}</span></div>
                <div className="aws-kv"><span className="k">Engine version</span><span className="v">{(db.engine || '').split(' ').slice(1).join(' ') || '—'}</span></div>
                <div className="aws-kv"><span className="k">DB instance class</span><span className="v">{db.class}</span></div>
                <div className="aws-kv"><span className="k">Allocated storage</span><span className="v">{db.storage} GiB</span></div>
                <div className="aws-kv"><span className="k">Multi-AZ</span><span className="v">{db.multiAz ? 'Yes' : 'No'}</span></div>
                <div className="aws-kv"><span className="k">Master username</span><span className="v">{db.masterUser || 'admin'}</span></div>
                <div className="aws-kv"><span className="k">DB instance ID</span><span className="v"><IDCopy value={db.id} /></span></div>
              </div>
            </div>
          )}
          {tab === 'monitoring' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {(cfg.metrics || []).map((m) => (
                <MetricChart key={m.title} title={m.title} unit={m.unit} color={m.color} base={m.base} variance={m.variance} />
              ))}
            </div>
          )}
          {tab === 'maintenance' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <SectionLabel>Snapshots</SectionLabel>
                  <Button icon={Plus} onClick={() => setSnapshotOpen(true)}>Take snapshot</Button>
                </div>
                <DataTable
                  columns={[
                    { key: 'name', label: 'Snapshot name' },
                    { key: 'engine', label: 'Engine' },
                    { key: 'status', label: 'Status', render: (r) => <Badge state={rdsBadge(r.status)}>{r.status}</Badge> },
                    { key: 'created', label: 'Created', render: (r) => (r.created ? new Date(r.created).toLocaleString() : '—') },
                  ]}
                  rows={dbSnapshots}
                  getRowKey={(r) => r.id || r.name}
                  tableId={`rds:snapshots:${db.id}`}
                  emptyTitle="No snapshots"
                  emptyBody="Take a snapshot to create a point-in-time backup."
                />
              </div>
              <div className="aws-card">
                <SectionLabel>Backup</SectionLabel>
                <div className="aws-summary-grid" style={{ marginTop: 8 }}>
                  <div className="aws-kv"><span className="k">Automated backups</span><span className="v">Enabled (7 days)</span></div>
                  <div className="aws-kv"><span className="k">Backup window</span><span className="v">03:00-03:30 UTC</span></div>
                  <div className="aws-kv"><span className="k">Maintenance window</span><span className="v">sun:04:00-sun:04:30 UTC</span></div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {modifyOpen && (
        <Modal title={`Modify ${db.name}`} onClose={() => setModifyOpen(false)}
          footer={<><Button onClick={() => setModifyOpen(false)}>Cancel</Button><Button variant="primary" onClick={submitModify}>Modify DB instance</Button></>}>
          <label className="aws-label">DB instance class</label>
          <select className="aws-input" value={modClass} onChange={(e) => setModClass(e.target.value)}>
            {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <label className="aws-label" style={{ marginTop: 12 }}>Allocated storage (GiB)</label>
          <input type="number" min={20} max={65536} className="aws-input" value={modStorage} onChange={(e) => setModStorage(Number(e.target.value))} />
          <label style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
            <input type="checkbox" checked={modMultiAz} onChange={(e) => setModMultiAz(e.target.checked)} /> Multi-AZ deployment
          </label>
        </Modal>
      )}
      {snapshotOpen && (
        <Modal title="Take DB snapshot" onClose={() => setSnapshotOpen(false)}
          footer={<><Button onClick={() => setSnapshotOpen(false)}>Cancel</Button><Button variant="primary" onClick={submitSnapshot}>Take snapshot</Button></>}>
          <label className="aws-label">Snapshot name</label>
          <input className="aws-input" value={snapName} onChange={(e) => setSnapName(e.target.value)} placeholder={`${db.name}-snapshot`} />
        </Modal>
      )}
      {deleteOpen && (
        <ConfirmDialog
          title={`Delete ${db.name}?`}
          body={`This permanently removes DB instance ${db.name} from the local RDS simulation.`}
          confirmLabel="Delete"
          confirmText={db.name}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => { deleteGenericResource(SERVICE, RESOURCE, db.id); pushFlash('success', `Deleting DB instance ${db.name}`); navigate(`${BASE}/rds/databases`) }}
        />
      )}
    </div>
  )
}
