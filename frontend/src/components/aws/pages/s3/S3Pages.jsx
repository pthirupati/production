import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Folder, File, Upload, ShieldCheck, Code2, Settings2 } from 'lucide-react'
import { useAwsStore } from '../../store/awsStore'
import { Badge, Button, ConfirmDialog, DataTable, IDCopy, Modal, Tabs, Breadcrumb, EmptyState, SectionLabel } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'
import { isValidBucketName } from '../../lib/validators'
import { BASE } from '../../layout/serviceNav'

function fmtSize(b) {
  if (b < 1024) return `${b} B`
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1073741824) return `${(b / 1048576).toFixed(1)} MB`
  return `${(b / 1073741824).toFixed(2)} GB`
}

function defaultBucketPolicy(bucketName) {
  return JSON.stringify({
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'AllowCloudFrontReadOnly',
        Effect: 'Allow',
        Principal: { Service: 'cloudfront.amazonaws.com' },
        Action: ['s3:GetObject'],
        Resource: `arn:aws:s3:::${bucketName}/*`,
      },
    ],
  }, null, 2)
}

function defaultCors() {
  return JSON.stringify([
    {
      AllowedHeaders: ['*'],
      AllowedMethods: ['GET', 'HEAD'],
      AllowedOrigins: ['https://example.com'],
      ExposeHeaders: ['ETag'],
      MaxAgeSeconds: 3000,
    },
  ], null, 2)
}

export function BucketList() {
  const navigate = useNavigate()
  const buckets = useAwsStore((s) => s.s3Buckets) || []
  const region = useAwsStore((s) => s.region)
  const createBucket = useAwsStore((s) => s.createBucket)
  const deleteBucket = useAwsStore((s) => s.deleteBucket)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [versioning, setVersioning] = useState(false)
  const [blockPublic, setBlockPublic] = useState(true)
  const [selected, setSelected] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)

  const error = name && !isValidBucketName(name) ? 'Bucket name must be 3–63 chars, lowercase letters, numbers, dots and hyphens, and DNS-compatible.' : (buckets.some((b) => b.name === name) ? 'A bucket with this name already exists.' : '')

  const columns = [
    { key: 'name', label: 'Name', render: (r) => <a onClick={() => navigate(`${BASE}/s3/buckets/${r.name}`)}>{r.name}</a> },
    { key: 'region', label: 'AWS Region' },
    { key: 'publicAccess', label: 'Access' },
    { key: 'versioning', label: 'Versioning', render: (r) => (r.versioning ? 'Enabled' : 'Disabled') },
    { key: 'created', label: 'Creation date', render: (r) => new Date(r.created).toLocaleString() },
  ]

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>General purpose buckets ({buckets.length})</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button disabled={selected.length !== 1} onClick={() => setDeleteTarget(selected[0])}>Delete</Button>
          <Button variant="primary" onClick={() => setCreating(true)}>Create bucket</Button>
        </div>
      </div>
      <DataTable
        columns={columns}
        rows={buckets}
        getRowKey={(r) => r.name}
        selectable
        selected={selected}
        onSelect={setSelected}
        onRowClick={(r) => navigate(`${BASE}/s3/buckets/${r.name}`)}
        rowActions={(r) => [
          { label: 'Open bucket', onClick: () => navigate(`${BASE}/s3/buckets/${r.name}`) },
          { label: 'Copy S3 URI', onClick: () => navigator.clipboard?.writeText(`s3://${r.name}`) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r.name) },
        ]}
        tableId="s3:buckets"
      />
      {creating && (
        <Modal title="Create bucket" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!name || !!error} onClick={() => { createBucket({ name, region, versioning, blockPublic }); pushFlash('success', `Successfully created bucket "${name}"`); setCreating(false); setName('') }}>Create bucket</Button></>}>
          <label className="aws-label">Bucket name</label>
          <input className={`aws-input ${error ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="my-unique-bucket-name" />
          {error && <div className="aws-field-error">{error}</div>}
          <div className="aws-hint">AWS Region: {region}</div>
          <label style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center' }}><input type="checkbox" checked={blockPublic} onChange={(e) => setBlockPublic(e.target.checked)} /> Block all public access</label>
          <label style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}><input type="checkbox" checked={versioning} onChange={(e) => setVersioning(e.target.checked)} /> Enable bucket versioning</label>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete bucket ${deleteTarget}?`}
          body="Deleting a bucket removes it from this environment. AWS requires buckets to be empty before deletion; the console removes the seeded objects as part of the delete."
          confirmLabel="Delete bucket"
          confirmText={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteBucket(deleteTarget); pushFlash('success', `Deleted bucket ${deleteTarget}`); setSelected([]); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}

export function BucketDetail() {
  const { name } = useParams()
  const navigate = useNavigate()
  const bucket = useAwsStore((s) => (s.s3Buckets || []).find((b) => b.name === name))
  const putObject = useAwsStore((s) => s.putObject)
  const deleteObject = useAwsStore((s) => s.deleteObject)
  const updateBucket = useAwsStore((s) => s.updateBucket)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [tab, setTab] = useState('objects')
  const [prefix, setPrefix] = useState('')
  const [uploading, setUploading] = useState(false)
  const [selected, setSelected] = useState([])
  const [deleteObjectsTarget, setDeleteObjectsTarget] = useState(null)
  const [policyDraft, setPolicyDraft] = useState('')
  const [corsDraft, setCorsDraft] = useState('')

  if (!bucket) return <div className="aws-page"><EmptyState title="Bucket not found" action={<Button onClick={() => navigate(`${BASE}/s3`)}>Back to buckets</Button>} /></div>

  // Object browser with folder (prefix) navigation.
  const inPrefix = bucket.objects.filter((o) => o.key.startsWith(prefix))
  const folders = new Set()
  const files = []
  inPrefix.forEach((o) => {
    const rest = o.key.slice(prefix.length)
    if (rest.includes('/')) folders.add(rest.split('/')[0])
    else files.push(o)
  })
  const rows = [
    ...Array.from(folders).map((f) => ({ type: 'folder', key: `${prefix}${f}/`, name: f })),
    ...files.map((o) => ({ type: 'file', ...o, name: o.key.slice(prefix.length) })),
  ]
  const totalSize = bucket.objects.reduce((a, o) => a + o.size, 0)
  const policy = bucket.bucketPolicy || ''
  const cors = bucket.cors || ''

  const columns = [
    { key: 'name', label: 'Name', render: (r) => (r.type === 'folder'
      ? <a onClick={() => setPrefix(r.key)}><Folder size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--aws-orange)' }} />{r.name}/</a>
      : <span><File size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--aws-text-muted)' }} />{r.name}</span>) },
    { key: 'storageClass', label: 'Type', render: (r) => (r.type === 'folder' ? 'Folder' : r.storageClass) },
    { key: 'modified', label: 'Last modified', render: (r) => (r.type === 'folder' ? '—' : new Date(r.modified).toLocaleString()) },
    { key: 'size', label: 'Size', render: (r) => (r.type === 'folder' ? '—' : fmtSize(r.size)) },
    { key: 'etag', label: 'ETag', render: (r) => (r.type === 'folder' ? '—' : <span className="aws-mono">{r.etag || '—'}</span>) },
  ]

  return (
    <div>
      <Breadcrumb items={[{ label: 'S3', onClick: () => navigate(`${BASE}/s3`) }, { label: 'Buckets', onClick: () => navigate(`${BASE}/s3`) }, { label: bucket.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <h1 style={{ marginBottom: 16 }}>{bucket.name}</h1>
        <Tabs tabs={[
          { key: 'objects', label: 'Objects' },
          { key: 'properties', label: 'Properties' },
          { key: 'permissions', label: 'Permissions' },
          { key: 'management', label: 'Management' },
          { key: 'metrics', label: 'Metrics' },
        ]} active={tab} onChange={setTab} />
        <div style={{ marginTop: 16 }}>
          {tab === 'objects' && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <Breadcrumb items={[{ label: bucket.name, onClick: () => setPrefix('') }, ...prefix.split('/').filter(Boolean).map((p, i, arr) => ({ label: p, onClick: () => setPrefix(`${arr.slice(0, i + 1).join('/')}/`) }))]} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button disabled={!selected.length} onClick={() => setDeleteObjectsTarget([...selected])}>Delete</Button>
                  <Button variant="primary" icon={Upload} onClick={() => setUploading(true)}>Upload</Button>
                </div>
              </div>
              <DataTable columns={columns} rows={rows} getRowKey={(r) => r.key} selectable selected={selected}
                onSelect={setSelected}
                rowActions={(r) => r.type === 'folder' ? [
                  { label: 'Open folder', onClick: () => setPrefix(r.key) },
                ] : [
                  { label: 'Copy S3 URI', onClick: () => navigator.clipboard?.writeText(`s3://${bucket.name}/${r.key}`) },
                  { label: 'Delete', danger: true, onClick: () => setDeleteObjectsTarget([r.key]) },
                ]}
                tableId={`s3:objects:${bucket.name}`}
                emptyTitle="This bucket is empty" emptyBody="Upload objects to get started." />
            </>
          )}
          {tab === 'properties' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <SectionLabel>Bucket overview</SectionLabel>
                <div className="aws-summary-grid" style={{ marginTop: 8 }}>
                  <div className="aws-kv"><span className="k">Bucket ARN</span><span className="v"><IDCopy value={`arn:aws:s3:::${bucket.name}`} /></span></div>
                  <div className="aws-kv"><span className="k">AWS Region</span><span className="v">{bucket.region}</span></div>
                  <div className="aws-kv"><span className="k">Objects</span><span className="v">{bucket.objects.length}</span></div>
                  <div className="aws-kv"><span className="k">Total size</span><span className="v">{fmtSize(totalSize)}</span></div>
                </div>
              </div>
              <div className="aws-card">
                <SectionLabel>Bucket settings</SectionLabel>
                <div style={{ display: 'grid', gap: 12, marginTop: 10 }}>
                  <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
                    <span><strong>Bucket Versioning</strong><div className="aws-hint">Keep multiple variants of an object in the same bucket.</div></span>
                    <input type="checkbox" checked={!!bucket.versioning} onChange={(e) => { updateBucket(bucket.name, { versioning: e.target.checked }); pushFlash('success', `Bucket versioning ${e.target.checked ? 'enabled' : 'disabled'}`) }} />
                  </label>
                  <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
                    <span><strong>Static website hosting</strong><div className="aws-hint">Serve index.html and error.html from the bucket website endpoint.</div></span>
                    <input type="checkbox" checked={!!bucket.website} onChange={(e) => { updateBucket(bucket.name, { website: e.target.checked }); pushFlash('success', `Static website hosting ${e.target.checked ? 'enabled' : 'disabled'}`) }} />
                  </label>
                  <div>
                    <label className="aws-label">Default encryption</label>
                    <select className="aws-input" value={bucket.encryption || 'SSE-S3'} onChange={(e) => updateBucket(bucket.name, { encryption: e.target.value })}>
                      <option>SSE-S3</option>
                      <option>SSE-KMS</option>
                      <option>DSSE-KMS</option>
                      <option>Disabled</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}
          {tab === 'permissions' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <SectionLabel>Block public access</SectionLabel>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginTop: 8 }}>
                  <div>
                    <div><Badge state={bucket.publicAccess?.includes('not public') ? 'running' : 'pending'}>{bucket.publicAccess}</Badge></div>
                    <div className="aws-hint" style={{ marginTop: 8 }}>Controls whether bucket policies, ACLs, or public grants can expose objects publicly.</div>
                  </div>
                  <Button onClick={() => updateBucket(bucket.name, { publicAccess: bucket.publicAccess?.includes('not public') ? 'Objects can be public' : 'Bucket and objects not public' })}>
                    {bucket.publicAccess?.includes('not public') ? 'Allow public access' : 'Block all public access'}
                  </Button>
                </div>
              </div>
              <div className="aws-card">
                <SectionLabel>Object Ownership and ACLs</SectionLabel>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
                  <div>
                    <label className="aws-label">Object Ownership</label>
                    <select className="aws-input" value={bucket.objectOwnership || 'Bucket owner enforced'} onChange={(e) => updateBucket(bucket.name, { objectOwnership: e.target.value })}>
                      <option>Bucket owner enforced</option>
                      <option>Bucket owner preferred</option>
                      <option>Object writer</option>
                    </select>
                  </div>
                  <div>
                    <label className="aws-label">ACL</label>
                    <select className="aws-input" value={bucket.acl || 'Private'} onChange={(e) => updateBucket(bucket.name, { acl: e.target.value })}>
                      <option>Private</option>
                      <option>Public read</option>
                      <option>Bucket owner full control</option>
                    </select>
                  </div>
                </div>
              </div>
              <div className="aws-card">
                <SectionLabel>Bucket policy</SectionLabel>
                <div style={{ display: 'flex', gap: 8, margin: '8px 0 10px' }}>
                  <Button icon={ShieldCheck} onClick={() => setPolicyDraft(policy || defaultBucketPolicy(bucket.name))}>Edit policy</Button>
                  <Button icon={Code2} onClick={() => { updateBucket(bucket.name, { bucketPolicy: defaultBucketPolicy(bucket.name) }); pushFlash('success', 'Applied sample CloudFront read-only bucket policy') }}>Apply sample policy</Button>
                </div>
                <pre className="aws-mono" style={{ background: 'var(--aws-page-bg)', padding: 12, borderRadius: 4, overflowX: 'auto', margin: 0 }}>{policy || '// No bucket policy configured'}</pre>
              </div>
              <div className="aws-card">
                <SectionLabel>Cross-origin resource sharing (CORS)</SectionLabel>
                <div style={{ display: 'flex', gap: 8, margin: '8px 0 10px' }}>
                  <Button icon={Settings2} onClick={() => setCorsDraft(cors || defaultCors())}>Edit CORS</Button>
                  <Button onClick={() => { updateBucket(bucket.name, { cors: defaultCors() }); pushFlash('success', 'Applied sample CORS configuration') }}>Apply sample CORS</Button>
                </div>
                <pre className="aws-mono" style={{ background: 'var(--aws-page-bg)', padding: 12, borderRadius: 4, overflowX: 'auto', margin: 0 }}>{cors || '// No CORS rules configured'}</pre>
              </div>
            </div>
          )}
          {tab === 'management' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <SectionLabel>Lifecycle rules</SectionLabel>
                <div className="aws-hint" style={{ margin: '8px 0 12px' }}>Lifecycle rules transition objects to lower-cost storage or expire old versions.</div>
                <DataTable
                  columns={[
                    { key: 'name', label: 'Rule name' },
                    { key: 'scope', label: 'Scope' },
                    { key: 'action', label: 'Action' },
                    { key: 'status', label: 'Status', render: (r) => <Badge state={r.status}>{r.status}</Badge> },
                  ]}
                  rows={(bucket.lifecycleRules?.length ? bucket.lifecycleRules : [{ name: 'transition-logs-to-ia', scope: 'logs/', action: 'Transition to STANDARD_IA after 30 days', status: 'Enabled' }])}
                  getRowKey={(r) => r.name}
                  tableId={`s3:lifecycle:${bucket.name}`}
                />
              </div>
              <div className="aws-card">
                <SectionLabel>Server access logging</SectionLabel>
                <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginTop: 8 }}>
                  <span><strong>Access logging</strong><div className="aws-hint">Record detailed request logs for security investigations and cost analysis.</div></span>
                  <input type="checkbox" checked={!!bucket.logging} onChange={(e) => updateBucket(bucket.name, { logging: e.target.checked })} />
                </label>
              </div>
            </div>
          )}
          {tab === 'metrics' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              <div className="aws-card">
                <SectionLabel>Storage summary</SectionLabel>
                <p style={{ color: 'var(--aws-text-secondary)' }}>Total objects: {bucket.objects.length} · Total size: {fmtSize(totalSize)}</p>
                <div className="aws-summary-grid">
                  <div className="aws-kv"><span className="k">4xx errors</span><span className="v">0</span></div>
                  <div className="aws-kv"><span className="k">5xx errors</span><span className="v">0</span></div>
                  <div className="aws-kv"><span className="k">Requests</span><span className="v">{Math.max(17, bucket.objects.length * 12)}</span></div>
                </div>
              </div>
              <MetricChart title="Bucket size bytes" unit="B" color="#1d8102" base={Math.max(1, totalSize)} variance={Math.max(1024, totalSize / 6)} />
              <MetricChart title="Number of objects" unit="" color="#0073bb" base={Math.max(1, bucket.objects.length)} variance={6} />
              <MetricChart title="All requests" unit="" color="#ff9900" base={Math.max(20, bucket.objects.length * 8)} variance={80} />
            </div>
          )}
        </div>
      </div>
      {uploading && (
        <Modal title="Upload" onClose={() => setUploading(false)}
          footer={<><Button onClick={() => setUploading(false)}>Cancel</Button></>}>
          <p style={{ color: 'var(--aws-text-secondary)', marginBottom: 12 }}>Add objects to <strong>{bucket.name}/{prefix}</strong></p>
          <label className="aws-btn aws-btn-secondary" style={{ cursor: 'pointer' }}>
            Add files
            <input type="file" multiple style={{ display: 'none' }} onChange={(e) => {
              Array.from(e.target.files || []).forEach((f) => putObject(bucket.name, prefix + f.name, f.size))
              pushFlash('success', `Uploaded ${e.target.files.length} object(s) to ${bucket.name}`)
              setUploading(false)
            }} />
          </label>
        </Modal>
      )}
      {deleteObjectsTarget && (
        <ConfirmDialog
          title={`Delete ${deleteObjectsTarget.length} object${deleteObjectsTarget.length === 1 ? '' : 's'}?`}
          body={`This removes the selected object${deleteObjectsTarget.length === 1 ? '' : 's'} from s3://${bucket.name}/${prefix} in the local simulation.`}
          confirmLabel="Delete"
          confirmText={deleteObjectsTarget.length === 1 ? deleteObjectsTarget[0] : String(deleteObjectsTarget.length)}
          onCancel={() => setDeleteObjectsTarget(null)}
          onConfirm={() => {
            deleteObjectsTarget.forEach((k) => {
              if (k.endsWith('/')) bucket.objects.filter((o) => o.key.startsWith(k)).forEach((o) => deleteObject(bucket.name, o.key))
              else deleteObject(bucket.name, k)
            })
            pushFlash('success', `Deleted ${deleteObjectsTarget.length} selected item(s)`)
            setSelected([])
            setDeleteObjectsTarget(null)
          }}
        />
      )}
      {policyDraft && (
        <Modal
          title="Edit bucket policy"
          width={860}
          onClose={() => setPolicyDraft('')}
          footer={<><Button onClick={() => setPolicyDraft('')}>Cancel</Button><Button variant="primary" onClick={() => { try { JSON.parse(policyDraft); updateBucket(bucket.name, { bucketPolicy: policyDraft }); pushFlash('success', 'Bucket policy saved'); setPolicyDraft('') } catch { pushFlash('error', 'Bucket policy must be valid JSON') } }}>Save changes</Button></>}
        >
          <textarea className="aws-input aws-mono" value={policyDraft} onChange={(e) => setPolicyDraft(e.target.value)} style={{ minHeight: 320, lineHeight: 1.5 }} />
        </Modal>
      )}
      {corsDraft && (
        <Modal
          title="Edit CORS configuration"
          width={760}
          onClose={() => setCorsDraft('')}
          footer={<><Button onClick={() => setCorsDraft('')}>Cancel</Button><Button variant="primary" onClick={() => { try { JSON.parse(corsDraft); updateBucket(bucket.name, { cors: corsDraft }); pushFlash('success', 'CORS configuration saved'); setCorsDraft('') } catch { pushFlash('error', 'CORS configuration must be valid JSON') } }}>Save changes</Button></>}
        >
          <textarea className="aws-input aws-mono" value={corsDraft} onChange={(e) => setCorsDraft(e.target.value)} style={{ minHeight: 260, lineHeight: 1.5 }} />
        </Modal>
      )}
    </div>
  )
}
