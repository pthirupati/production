import { useState } from 'react'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, ConfirmDialog, DataTable, IDCopy, Modal } from '../../ui/primitives'

function Page({ title, action, children }) {
  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>{title}</h1>
        {action}
      </div>
      {children}
    </div>
  )
}

export function SecurityGroupList() {
  const region = useAwsStore((s) => s.region)
  const sgs = scoped(useAwsStore((s) => s.securityGroups), region)
  const createSecurityGroup = useAwsStore((s) => s.createSecurityGroup)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'id', label: 'Security group ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'description', label: 'Description' },
    { key: 'vpcId', label: 'VPC ID', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
    { key: 'inbound', label: 'Inbound rules', render: (r) => r.inbound.length },
    { key: 'outbound', label: 'Outbound rules', render: (r) => r.outbound.length },
  ]

  return (
    <Page title={`Security groups (${sgs.length})`} action={<Button variant="primary" onClick={() => setCreating(true)}>Create security group</Button>}>
      <DataTable columns={columns} rows={sgs} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} />
      {creating && (
        <Modal title="Create security group" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!name} onClick={() => { createSecurityGroup({ name, description: desc, vpcId: vpcs[0]?.id, inbound: [] }); pushFlash('success', `Security group ${name} created`); setCreating(false); setName(''); setDesc('') }}>Create</Button></>}>
          <label className="aws-label">Security group name</label>
          <input className="aws-input" value={name} onChange={(e) => setName(e.target.value)} style={{ marginBottom: 12 }} />
          <label className="aws-label">Description</label>
          <input className="aws-input" value={desc} onChange={(e) => setDesc(e.target.value)} />
        </Modal>
      )}
    </Page>
  )
}

export function KeyPairList() {
  const region = useAwsStore((s) => s.region)
  const keyPairs = scoped(useAwsStore((s) => s.keyPairs), region)
  const createKeyPair = useAwsStore((s) => s.createKeyPair)
  const deleteKeyPair = useAwsStore((s) => s.deleteKeyPair)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [type, setType] = useState('rsa')
  const [deleteTarget, setDeleteTarget] = useState(null)

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'id', label: 'Key pair ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'type', label: 'Type', render: (r) => r.type.toUpperCase() },
    { key: 'fingerprint', label: 'Fingerprint', render: (r) => <span className="aws-mono" style={{ fontSize: 11 }}>{r.fingerprint.slice(0, 30)}…</span> },
    { key: 'actions', label: '', sortable: false, render: (r) => <Button variant="link" onClick={() => setDeleteTarget(r.name)}>Delete</Button> },
  ]

  return (
    <Page title={`Key pairs (${keyPairs.length})`} action={<Button variant="primary" onClick={() => setCreating(true)}>Create key pair</Button>}>
      <DataTable
        columns={columns}
        rows={keyPairs}
        getRowKey={(r) => r.id}
        rowActions={(r) => [
          { label: 'Copy key pair name', onClick: () => navigator.clipboard?.writeText(r.name) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r.name) },
        ]}
        tableId="ec2:key-pairs"
      />
      {creating && (
        <Modal title="Create key pair" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!name} onClick={() => { createKeyPair({ name, type }); pushFlash('success', `Key pair ${name} created — private key downloaded`); setCreating(false); setName('') }}>Create key pair</Button></>}>
          <label className="aws-label">Name</label>
          <input className="aws-input" value={name} onChange={(e) => setName(e.target.value)} style={{ marginBottom: 12 }} />
          <label className="aws-label">Key pair type</label>
          <select className="aws-select" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="rsa">RSA</option>
            <option value="ed25519">ED25519</option>
          </select>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete key pair ${deleteTarget}?`}
          body="Deleting a key pair removes it from this region in the local simulation. Existing instances keep their key pair name, but this key can no longer be selected for new launches."
          confirmLabel="Delete"
          confirmText={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteKeyPair(deleteTarget); pushFlash('success', `Deleted key pair ${deleteTarget}`); setDeleteTarget(null) }}
        />
      )}
    </Page>
  )
}

export function VolumeList() {
  const region = useAwsStore((s) => s.region)
  const volumes = scoped(useAwsStore((s) => s.volumes), region)
  const columns = [
    { key: 'id', label: 'Volume ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'type', label: 'Type' },
    { key: 'size', label: 'Size', render: (r) => `${r.size} GiB` },
    { key: 'state', label: 'State', render: (r) => <Badge state={r.state === 'in-use' ? 'available' : r.state}>{r.state}</Badge> },
    { key: 'az', label: 'Availability Zone' },
    { key: 'encrypted', label: 'Encryption', render: (r) => (r.encrypted ? 'Encrypted' : 'Not encrypted') },
    { key: 'attachedTo', label: 'Attached instance', render: (r) => (r.attachedTo ? <span className="aws-mono">{r.attachedTo}</span> : '—') },
  ]
  return <Page title={`Volumes (${volumes.length})`}><DataTable columns={columns} rows={volumes} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} /></Page>
}

export function ElasticIpList() {
  const region = useAwsStore((s) => s.region)
  const eips = scoped(useAwsStore((s) => s.elasticIps), region)
  const allocate = useAwsStore((s) => s.allocateEip)
  const release = useAwsStore((s) => s.releaseEip)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [releaseTarget, setReleaseTarget] = useState(null)
  const columns = [
    { key: 'publicIp', label: 'Allocated IPv4 address', render: (r) => <IDCopy value={r.publicIp} /> },
    { key: 'allocationId', label: 'Allocation ID', render: (r) => <span className="aws-mono">{r.allocationId}</span> },
    { key: 'instanceId', label: 'Associated instance', render: (r) => (r.instanceId ? <span className="aws-mono">{r.instanceId}</span> : '—') },
    { key: 'domain', label: 'Scope' },
    { key: 'actions', label: '', sortable: false, render: (r) => <Button variant="link" onClick={() => setReleaseTarget(r)}>Release</Button> },
  ]
  return (
    <Page title={`Elastic IP addresses (${eips.length})`} action={<Button variant="primary" onClick={() => { const e = allocate(); pushFlash('success', `Allocated Elastic IP ${e.publicIp}`) }}>Allocate Elastic IP address</Button>}>
      <DataTable
        columns={columns}
        rows={eips}
        getRowKey={(r) => r.allocationId}
        rowActions={(r) => [
          { label: 'Copy public IP', onClick: () => navigator.clipboard?.writeText(r.publicIp) },
          { label: 'Release address', danger: true, onClick: () => setReleaseTarget(r) },
        ]}
        tableId="ec2:elastic-ips"
      />
      {releaseTarget && (
        <ConfirmDialog
          title={`Release ${releaseTarget.publicIp}?`}
          body="Releasing an Elastic IP makes it unavailable in this region. In AWS, released public IPs usually cannot be recovered."
          confirmLabel="Release"
          confirmText={releaseTarget.allocationId}
          onCancel={() => setReleaseTarget(null)}
          onConfirm={() => { release(releaseTarget.allocationId); pushFlash('success', `Released ${releaseTarget.publicIp}`); setReleaseTarget(null) }}
        />
      )}
    </Page>
  )
}

export function AmiList() {
  const region = useAwsStore((s) => s.region)
  const amis = scoped(useAwsStore((s) => s.amis), region)
  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'id', label: 'AMI ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'visibility', label: 'Visibility' },
    { key: 'platform', label: 'Platform' },
    { key: 'arch', label: 'Architecture' },
    { key: 'created', label: 'Creation date', render: (r) => new Date(r.created).toLocaleDateString() },
  ]
  return <Page title={`AMIs (${amis.length})`}><DataTable columns={columns} rows={amis} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} /></Page>
}
