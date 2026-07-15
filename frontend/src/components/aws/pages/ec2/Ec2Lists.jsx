import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, ConfirmDialog, DataTable, IDCopy, Modal } from '../../ui/primitives'
import { BASE } from '../../layout/serviceNav'

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
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const sgs = scoped(useAwsStore((s) => s.securityGroups), region)
  const createSecurityGroup = useAwsStore((s) => s.createSecurityGroup)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')

  const columns = [
    { key: 'name', label: 'Name', render: (r) => <a onClick={() => navigate(`${BASE}/ec2/security-groups/${r.id}`)}>{r.name}</a> },
    { key: 'id', label: 'Security group ID', render: (r) => <IDCopy value={r.id} onClick={() => navigate(`${BASE}/ec2/security-groups/${r.id}`)} /> },
    { key: 'description', label: 'Description' },
    { key: 'vpcId', label: 'VPC ID', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
    { key: 'inbound', label: 'Inbound rules', render: (r) => (r.inbound || []).length },
    { key: 'outbound', label: 'Outbound rules', render: (r) => (r.outbound || []).length },
  ]

  return (
    <Page title={`Security groups (${sgs.length})`} action={<Button variant="primary" onClick={() => setCreating(true)}>Create security group</Button>}>
      <DataTable
        columns={columns}
        rows={sgs}
        getRowKey={(r) => r.id}
        onRowClick={(r) => navigate(`${BASE}/ec2/security-groups/${r.id}`)}
        rowActions={(r) => [
          { label: 'View / edit rules', onClick: () => navigate(`${BASE}/ec2/security-groups/${r.id}`) },
          { label: 'Copy security group ID', onClick: () => navigator.clipboard?.writeText(r.id) },
        ]}
        tableId="ec2:security-groups"
      />
      {creating && (
        <Modal title="Create security group" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!name} onClick={() => { const res = createSecurityGroup({ name, description: desc, vpcId: vpcs[0]?.id, inbound: [] }); if (res && res.ok === false) return; pushFlash('success', `Security group ${name} created`); setCreating(false); setName(''); setDesc('') }}>Create</Button></>}>
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
  const instances = scoped(useAwsStore((s) => s.instances), region)
  const attachVolume = useAwsStore((s) => s.attachVolume)
  const detachVolume = useAwsStore((s) => s.detachVolume)
  const createSnapshot = useAwsStore((s) => s.createSnapshot)
  const pushFlash = useAwsStore((s) => s.pushFlash)

  const [attachTarget, setAttachTarget] = useState(null)
  const [attachInst, setAttachInst] = useState('')
  const [attachDevice, setAttachDevice] = useState('/dev/sdf')
  const [detachTarget, setDetachTarget] = useState(null)
  const [snapTarget, setSnapTarget] = useState(null)
  const [snapDesc, setSnapDesc] = useState('')

  // Attaching requires the instance to be in the same Availability Zone as the volume.
  const attachInstance = attachTarget ? instances.find((i) => i.id === attachInst) : null
  const azMismatch = attachTarget && attachInstance && attachInstance.az !== attachTarget.az
  const eligibleInstances = attachTarget ? instances.filter((i) => i.state !== 'terminated') : []

  const columns = [
    { key: 'id', label: 'Volume ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'type', label: 'Type' },
    { key: 'size', label: 'Size', render: (r) => `${r.size} GiB` },
    { key: 'state', label: 'State', render: (r) => <Badge state={r.state === 'in-use' ? 'available' : r.state}>{r.state}</Badge> },
    { key: 'az', label: 'Availability Zone' },
    { key: 'encrypted', label: 'Encryption', render: (r) => (r.encrypted ? 'Encrypted' : 'Not encrypted') },
    { key: 'attachedTo', label: 'Attached instance', render: (r) => (r.attachedTo ? <span className="aws-mono">{r.attachedTo}</span> : '—') },
  ]

  const openAttach = (v) => {
    const firstInAz = instances.find((i) => i.state !== 'terminated' && i.az === v.az) || instances.find((i) => i.state !== 'terminated')
    setAttachInst(firstInAz?.id || '')
    setAttachDevice('/dev/sdf')
    setAttachTarget(v)
  }

  return (
    <Page title={`Volumes (${volumes.length})`}>
      <DataTable
        columns={columns}
        rows={volumes}
        getRowKey={(r) => r.id}
        rowActions={(r) => [
          ...(r.state === 'available' ? [{ label: 'Attach volume', onClick: () => openAttach(r) }] : []),
          ...(r.state === 'in-use' ? [{ label: 'Detach volume', danger: true, onClick: () => setDetachTarget(r) }] : []),
          { label: 'Create snapshot', onClick: () => { setSnapDesc(''); setSnapTarget(r) } },
          { label: 'Copy volume ID', onClick: () => navigator.clipboard?.writeText(r.id) },
        ]}
        tableId="ec2:volumes"
      />

      {attachTarget && (
        <Modal title={`Attach volume ${attachTarget.id}`} onClose={() => setAttachTarget(null)}
          footer={<><Button onClick={() => setAttachTarget(null)}>Cancel</Button><Button variant="primary" disabled={!attachInst || azMismatch} onClick={() => { const res = attachVolume(attachTarget.id, attachInst, attachDevice); if (res && res.ok === false) return; pushFlash('success', `Attached ${attachTarget.id} to ${attachInst} at ${attachDevice}`); setAttachTarget(null) }}>Attach</Button></>}>
          <label className="aws-label">Instance</label>
          <select className="aws-select" value={attachInst} onChange={(e) => setAttachInst(e.target.value)} style={{ marginBottom: 12 }}>
            <option value="">Select an instance</option>
            {eligibleInstances.map((i) => <option key={i.id} value={i.id}>{i.id} {i.name ? `(${i.name})` : ''} — {i.az}</option>)}
          </select>
          <label className="aws-label">Device name</label>
          <input className="aws-input" value={attachDevice} onChange={(e) => setAttachDevice(e.target.value)} />
          {azMismatch && <div className="aws-field-error">Volume is in {attachTarget.az} but the instance is in {attachInstance.az}. A volume can only attach to an instance in the same Availability Zone.</div>}
        </Modal>
      )}

      {detachTarget && (
        <ConfirmDialog
          title={`Detach ${detachTarget.id}?`}
          body={`This volume is attached to ${detachTarget.attachedTo}. Detaching a root volume of a running instance is not permitted.`}
          confirmLabel="Detach"
          danger
          onCancel={() => setDetachTarget(null)}
          onConfirm={() => { const res = detachVolume(detachTarget.id); if (res && res.ok === false) { setDetachTarget(null); return } pushFlash('success', `Detached ${detachTarget.id}`); setDetachTarget(null) }}
        />
      )}

      {snapTarget && (
        <Modal title={`Create snapshot of ${snapTarget.id}`} onClose={() => setSnapTarget(null)}
          footer={<><Button onClick={() => setSnapTarget(null)}>Cancel</Button><Button variant="primary" onClick={() => { const res = createSnapshot(snapTarget.id, snapDesc); if (res && res.ok === false) return; pushFlash('success', `Snapshot ${res.id} created from ${snapTarget.id}`); setSnapTarget(null) }}>Create snapshot</Button></>}>
          <label className="aws-label">Description</label>
          <input className="aws-input" value={snapDesc} onChange={(e) => setSnapDesc(e.target.value)} placeholder="Optional" />
        </Modal>
      )}
    </Page>
  )
}

export function ElasticIpList() {
  const region = useAwsStore((s) => s.region)
  const eips = scoped(useAwsStore((s) => s.elasticIps), region)
  const instances = scoped(useAwsStore((s) => s.instances), region)
  const allocate = useAwsStore((s) => s.allocateEip)
  const release = useAwsStore((s) => s.releaseEip)
  const associateEip = useAwsStore((s) => s.associateEip)
  const disassociateEip = useAwsStore((s) => s.disassociateEip)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [releaseTarget, setReleaseTarget] = useState(null)
  const [assocTarget, setAssocTarget] = useState(null)
  const [assocInst, setAssocInst] = useState('')

  const eligibleInstances = instances.filter((i) => i.state !== 'terminated')

  const columns = [
    { key: 'publicIp', label: 'Allocated IPv4 address', render: (r) => <IDCopy value={r.publicIp} /> },
    { key: 'allocationId', label: 'Allocation ID', render: (r) => <span className="aws-mono">{r.allocationId}</span> },
    { key: 'instanceId', label: 'Associated instance', render: (r) => (r.instanceId ? <span className="aws-mono">{r.instanceId}</span> : '—') },
    { key: 'domain', label: 'Scope' },
    { key: 'actions', label: '', sortable: false, render: (r) => (r.instanceId
      ? <Button variant="link" onClick={() => disassociateEip(r.allocationId) && pushFlash('success', `Disassociated ${r.publicIp}`)}>Disassociate</Button>
      : <Button variant="link" onClick={() => { setAssocInst(eligibleInstances[0]?.id || ''); setAssocTarget(r) }}>Associate</Button>) },
  ]

  return (
    <Page title={`Elastic IP addresses (${eips.length})`} action={<Button variant="primary" onClick={() => { const e = allocate(); pushFlash('success', `Allocated Elastic IP ${e.publicIp}`) }}>Allocate Elastic IP address</Button>}>
      <DataTable
        columns={columns}
        rows={eips}
        getRowKey={(r) => r.allocationId}
        rowActions={(r) => [
          { label: 'Copy public IP', onClick: () => navigator.clipboard?.writeText(r.publicIp) },
          ...(r.instanceId
            ? [{ label: 'Disassociate address', onClick: () => { disassociateEip(r.allocationId); pushFlash('success', `Disassociated ${r.publicIp}`) } }]
            : [{ label: 'Associate address', onClick: () => { setAssocInst(eligibleInstances[0]?.id || ''); setAssocTarget(r) } }]),
          { label: 'Release address', danger: true, onClick: () => setReleaseTarget(r) },
        ]}
        tableId="ec2:elastic-ips"
      />
      {assocTarget && (
        <Modal title={`Associate ${assocTarget.publicIp}`} onClose={() => setAssocTarget(null)}
          footer={<><Button onClick={() => setAssocTarget(null)}>Cancel</Button><Button variant="primary" disabled={!assocInst} onClick={() => { const res = associateEip(assocTarget.allocationId, assocInst); if (res && res.ok === false) return; pushFlash('success', `Associated ${assocTarget.publicIp} with ${assocInst}`); setAssocTarget(null) }}>Associate</Button></>}>
          <label className="aws-label">Instance</label>
          <select className="aws-select" value={assocInst} onChange={(e) => setAssocInst(e.target.value)}>
            <option value="">Select an instance</option>
            {eligibleInstances.map((i) => <option key={i.id} value={i.id}>{i.id} {i.name ? `(${i.name})` : ''} — {i.state}</option>)}
          </select>
          <div className="aws-hint" style={{ marginTop: 8 }}>Associating replaces the instance&apos;s current public IPv4 address with this Elastic IP.</div>
        </Modal>
      )}
      {releaseTarget && (
        <ConfirmDialog
          title={`Release ${releaseTarget.publicIp}?`}
          body="Releasing an Elastic IP makes it unavailable in this region. In AWS, released public IPs usually cannot be recovered. Associated addresses must be disassociated first."
          confirmLabel="Release"
          confirmText={releaseTarget.allocationId}
          onCancel={() => setReleaseTarget(null)}
          onConfirm={() => { const res = release(releaseTarget.allocationId); if (res && res.ok === false) { setReleaseTarget(null); return } pushFlash('success', `Released ${releaseTarget.publicIp}`); setReleaseTarget(null) }}
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
