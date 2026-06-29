import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Folder, File, Upload } from 'lucide-react'
import { useAwsStore } from '../../store/awsStore'
import { Button, ConfirmDialog, DataTable, IDCopy, Modal, Tabs, Breadcrumb, EmptyState } from '../../ui/primitives'
import { isValidBucketName } from '../../lib/validators'
import { BASE } from '../../layout/serviceNav'

function fmtSize(b) {
  if (b < 1024) return `${b} B`
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1073741824) return `${(b / 1048576).toFixed(1)} MB`
  return `${(b / 1073741824).toFixed(2)} GB`
}

export function BucketList() {
  const navigate = useNavigate()
  const buckets = useAwsStore((s) => s.s3Buckets)
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
          body="Deleting a bucket removes it from this local AWS simulation. AWS requires buckets to be empty before deletion; this simulator removes the seeded objects as part of the local delete."
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
  const bucket = useAwsStore((s) => s.s3Buckets.find((b) => b.name === name))
  const putObject = useAwsStore((s) => s.putObject)
  const deleteObject = useAwsStore((s) => s.deleteObject)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [tab, setTab] = useState('objects')
  const [prefix, setPrefix] = useState('')
  const [uploading, setUploading] = useState(false)
  const [selected, setSelected] = useState([])
  const [deleteObjectsTarget, setDeleteObjectsTarget] = useState(null)

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
    ...Array.from(folders).map((f) => ({ type: 'folder', key: f, name: f })),
    ...files.map((o) => ({ type: 'file', ...o, name: o.key.slice(prefix.length) })),
  ]

  const columns = [
    { key: 'name', label: 'Name', render: (r) => (r.type === 'folder'
      ? <a onClick={() => setPrefix(`${prefix}${r.name}/`)}><Folder size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--aws-orange)' }} />{r.name}/</a>
      : <span><File size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--aws-text-muted)' }} />{r.name}</span>) },
    { key: 'storageClass', label: 'Type', render: (r) => (r.type === 'folder' ? 'Folder' : r.storageClass) },
    { key: 'modified', label: 'Last modified', render: (r) => (r.type === 'folder' ? '—' : new Date(r.modified).toLocaleString()) },
    { key: 'size', label: 'Size', render: (r) => (r.type === 'folder' ? '—' : fmtSize(r.size)) },
  ]

  return (
    <div>
      <Breadcrumb items={[{ label: 'S3', onClick: () => navigate(`${BASE}/s3`) }, { label: 'Buckets', onClick: () => navigate(`${BASE}/s3`) }, { label: bucket.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <h1 style={{ marginBottom: 16 }}>{bucket.name}</h1>
        <Tabs tabs={[{ key: 'objects', label: 'Objects' }, { key: 'properties', label: 'Properties' }, { key: 'permissions', label: 'Permissions' }, { key: 'metrics', label: 'Metrics' }]} active={tab} onChange={setTab} />
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
                  { label: 'Open folder', onClick: () => setPrefix(`${prefix}${r.name}/`) },
                ] : [
                  { label: 'Copy S3 URI', onClick: () => navigator.clipboard?.writeText(`s3://${bucket.name}/${r.key}`) },
                  { label: 'Delete', danger: true, onClick: () => setDeleteObjectsTarget([r.key]) },
                ]}
                tableId={`s3:objects:${bucket.name}`}
                emptyTitle="This bucket is empty" emptyBody="Upload objects to get started." />
            </>
          )}
          {tab === 'properties' && (
            <div className="aws-card">
              <div className="aws-kv" style={{ marginBottom: 10 }}><span className="k">Bucket ARN</span><IDCopy value={`arn:aws:s3:::${bucket.name}`} /></div>
              <div className="aws-kv" style={{ marginBottom: 10 }}><span className="k">AWS Region</span><span className="v">{bucket.region}</span></div>
              <div className="aws-kv" style={{ marginBottom: 10 }}><span className="k">Versioning</span><span className="v">{bucket.versioning ? 'Enabled' : 'Disabled'}</span></div>
              <div className="aws-kv" style={{ marginBottom: 10 }}><span className="k">Default encryption</span><span className="v">{bucket.encryption}</span></div>
              <div className="aws-kv"><span className="k">Static website hosting</span><span className="v">{bucket.website ? 'Enabled' : 'Disabled'}</span></div>
            </div>
          )}
          {tab === 'permissions' && (
            <div className="aws-card">
              <div className="aws-kv" style={{ marginBottom: 10 }}><span className="k">Block Public Access</span><span className="v">{bucket.publicAccess}</span></div>
              <p style={{ color: 'var(--aws-text-secondary)' }}>Bucket policy and CORS JSON editors are part of the S3 roadmap increment.</p>
            </div>
          )}
          {tab === 'metrics' && <div className="aws-card"><p style={{ color: 'var(--aws-text-secondary)' }}>Total objects: {bucket.objects.length} · Total size: {fmtSize(bucket.objects.reduce((a, o) => a + o.size, 0))}</p></div>}
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
          onConfirm={() => { deleteObjectsTarget.forEach((k) => deleteObject(bucket.name, k)); pushFlash('success', `Deleted ${deleteObjectsTarget.length} object(s)`); setSelected([]); setDeleteObjectsTarget(null) }}
        />
      )}
    </div>
  )
}
