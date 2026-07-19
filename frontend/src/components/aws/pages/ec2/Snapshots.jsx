import { useState } from 'react'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, DataTable, IDCopy, Modal, ConfirmDialog } from '../../ui/primitives'

export default function Snapshots() {
  const region = useAwsStore((s) => s.region)
  const snapshots = scoped(useAwsStore((s) => s.snapshots), region)
  const volumes = scoped(useAwsStore((s) => s.volumes), region)
  const createSnapshot = useAwsStore((s) => s.createSnapshot)
  const deleteSnapshot = useAwsStore((s) => s.deleteSnapshot)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [volId, setVolId] = useState(volumes[0]?.id || '')
  const [desc, setDesc] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

  const columns = [
    { key: 'id', label: 'Snapshot ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'volumeId', label: 'Volume ID', render: (r) => <span className="aws-mono">{r.volumeId}</span> },
    { key: 'size', label: 'Size', render: (r) => `${r.size} GiB` },
    { key: 'state', label: 'Status', render: (r) => <Badge state={r.state === 'completed' ? 'available' : r.state}>{r.state}</Badge> },
    { key: 'progress', label: 'Progress' },
    { key: 'encrypted', label: 'Encryption', render: (r) => (r.encrypted ? 'Encrypted' : 'Not encrypted') },
    { key: 'started', label: 'Started', render: (r) => new Date(r.started).toLocaleString() },
    { key: 'description', label: 'Description', render: (r) => r.description || '—' },
  ]

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>Snapshots ({snapshots.length})</h1>
        <Button variant="primary" disabled={!volumes.length} onClick={() => { setVolId(volumes[0]?.id || ''); setCreating(true) }}>Create snapshot</Button>
      </div>
      <DataTable
        columns={columns}
        rows={snapshots}
        getRowKey={(r) => r.id}
        rowActions={(r) => [
          { label: 'Copy snapshot ID', onClick: () => navigator.clipboard?.writeText(r.id) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
        ]}
        tableId="ec2:snapshots"
        emptyTitle="No snapshots"
        emptyBody="Create a snapshot from an EBS volume to back it up."
      />
      {creating && (
        <Modal title="Create snapshot" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!volId} onClick={() => {
            const res = createSnapshot(volId, desc)
            if (res && res.ok === false) return
            pushFlash('success', `Snapshot ${res.id} created from ${volId}`)
            setCreating(false); setDesc('')
          }}>Create snapshot</Button></>}>
          <label className="aws-label">Volume</label>
          <select className="aws-select" value={volId} onChange={(e) => setVolId(e.target.value)} style={{ marginBottom: 12 }}>
            {volumes.map((v) => <option key={v.id} value={v.id}>{v.id} — {v.size} GiB {v.type} ({v.state})</option>)}
          </select>
          <label className="aws-label">Description</label>
          <input className="aws-input" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Optional" />
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.id}?`}
          body="Deleting a snapshot is permanent and cannot be undone."
          confirmLabel="Delete"
          confirmText={deleteTarget.id}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteSnapshot(deleteTarget.id); pushFlash('success', `Deleted ${deleteTarget.id}`); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}
