import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, Tabs, DataTable, IDCopy, Breadcrumb, Modal, ConfirmDialog, EmptyState } from '../../ui/primitives'
import { BASE } from '../../layout/serviceNav'

export function AutoScalingGroupList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const asgs = scoped(useAwsStore((s) => s.autoScalingGroups), region)
  const subnets = scoped(useAwsStore((s) => s.subnets), region)
  const createAutoScalingGroup = useAwsStore((s) => s.createAutoScalingGroup)
  const deleteAutoScalingGroup = useAwsStore((s) => s.deleteAutoScalingGroup)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [form, setForm] = useState({ name: '', min: 1, max: 4, desired: 2, launchTemplate: 'web-lt', subnetId: '' })

  const columns = [
    { key: 'name', label: 'Name', render: (r) => <IDCopy value={r.name} onClick={() => navigate(`${BASE}/ec2/auto-scaling-groups/${r.id}`)} /> },
    { key: 'id', label: 'ASG ID', render: (r) => <span className="aws-mono" style={{ fontSize: 12 }}>{r.id}</span> },
    { key: 'launchTemplate', label: 'Launch template' },
    { key: 'instances', label: 'Instances', render: (r) => (r.instanceIds || []).length },
    { key: 'desired', label: 'Desired' },
    { key: 'min', label: 'Min' },
    { key: 'max', label: 'Max' },
    { key: 'status', label: 'Status', render: (r) => <Badge state={r.status === 'active' ? 'available' : r.status}>{r.status}</Badge> },
  ]

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>Auto Scaling groups ({asgs.length})</h1>
        <Button variant="primary" onClick={() => setCreating(true)}>Create Auto Scaling group</Button>
      </div>
      <DataTable
        columns={columns}
        rows={asgs}
        getRowKey={(r) => r.id}
        onRowClick={(r) => navigate(`${BASE}/ec2/auto-scaling-groups/${r.id}`)}
        rowActions={(r) => [
          { label: 'View details', onClick: () => navigate(`${BASE}/ec2/auto-scaling-groups/${r.id}`) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
        ]}
        tableId="ec2:auto-scaling-groups"
        emptyTitle="No Auto Scaling groups"
        emptyBody="Create a group to launch and maintain a fleet of instances."
      />
      {creating && (
        <Modal title="Create Auto Scaling group" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!form.name} onClick={() => {
            const asg = createAutoScalingGroup({ name: form.name, min: Number(form.min), max: Number(form.max), desired: Number(form.desired), launchTemplate: form.launchTemplate, subnetId: form.subnetId })
            pushFlash('success', `Auto Scaling group ${asg.name} created — launching ${asg.desired} instance(s)`)
            setCreating(false)
            setForm({ name: '', min: 1, max: 4, desired: 2, launchTemplate: 'web-lt', subnetId: '' })
          }}>Create</Button></>}>
          <label className="aws-label">Name</label>
          <input className="aws-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ marginBottom: 12 }} placeholder="web-asg" />
          <label className="aws-label">Launch template</label>
          <input className="aws-input" value={form.launchTemplate} onChange={(e) => setForm({ ...form, launchTemplate: e.target.value })} style={{ marginBottom: 12 }} />
          <label className="aws-label">Subnet</label>
          <select className="aws-select" value={form.subnetId} onChange={(e) => setForm({ ...form, subnetId: e.target.value })} style={{ marginBottom: 12 }}>
            <option value="">Any subnet in this Region</option>
            {subnets.map((s) => <option key={s.id} value={s.id}>{s.id} | {s.az} | {s.cidr}</option>)}
          </select>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><label className="aws-label">Min</label><input className="aws-input" type="number" min={0} value={form.min} onChange={(e) => setForm({ ...form, min: e.target.value })} /></div>
            <div style={{ flex: 1 }}><label className="aws-label">Desired</label><input className="aws-input" type="number" min={0} value={form.desired} onChange={(e) => setForm({ ...form, desired: e.target.value })} /></div>
            <div style={{ flex: 1 }}><label className="aws-label">Max</label><input className="aws-input" type="number" min={0} value={form.max} onChange={(e) => setForm({ ...form, max: e.target.value })} /></div>
          </div>
          <div className="aws-hint" style={{ marginTop: 10 }}>Creating the group launches {form.desired || 0} tagged instance(s) immediately.</div>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.name}?`}
          body="Deleting an Auto Scaling group terminates all of its instances."
          confirmLabel="Delete"
          confirmText={deleteTarget.name}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteAutoScalingGroup(deleteTarget.id); pushFlash('success', `Deleted ${deleteTarget.name}`); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}

export function AutoScalingGroupDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const asg = useAwsStore((s) => (s.autoScalingGroups || []).find((x) => x.id === id))
  const instances = useAwsStore((s) => s.instances) || []
  const scaleAutoScalingGroup = useAwsStore((s) => s.scaleAutoScalingGroup)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [tab, setTab] = useState('instances')
  const [editOpen, setEditOpen] = useState(false)
  const [capacity, setCapacity] = useState({ desired: 1, min: 1, max: 4 })

  if (!asg) {
    return <div className="aws-page"><EmptyState title="Auto Scaling group not found" action={<Button onClick={() => navigate(`${BASE}/ec2/auto-scaling-groups`)}>Back to Auto Scaling groups</Button>} /></div>
  }

  const asgInstances = instances.filter((i) => (asg.instanceIds || []).includes(i.id))
  // Derive an activity history from launched instances + the create event.
  const activity = [
    ...asgInstances.map((i) => ({
      at: i.launchTime,
      description: `Launching a new EC2 instance: ${i.id}`,
      status: i.state === 'terminated' ? 'Cancelled' : (i.state === 'running' ? 'Successful' : 'InProgress'),
      cause: `In response to a difference between desired and actual capacity, increasing the capacity for group ${asg.name}.`,
    })),
    { at: asg.created, description: `Auto Scaling group ${asg.name} created`, status: 'Successful', cause: `Group created with desired capacity ${asg.desired}.` },
  ].sort((a, b) => new Date(b.at) - new Date(a.at))

  const openEdit = () => {
    setCapacity({ desired: asg.desired, min: asg.min, max: asg.max })
    setEditOpen(true)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Auto Scaling Groups', onClick: () => navigate(`${BASE}/ec2/auto-scaling-groups`) }, { label: asg.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 12, margin: 0 }}>{asg.name} <Badge state={asg.status === 'active' ? 'available' : asg.status}>{asg.status}</Badge></h1>
          <Button onClick={openEdit}>Edit capacity</Button>
        </div>
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            <div className="aws-kv"><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>{asg.desired}</span><span className="k">Desired capacity</span></div>
            <div className="aws-kv"><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>{asg.min}</span><span className="k">Minimum</span></div>
            <div className="aws-kv"><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>{asg.max}</span><span className="k">Maximum</span></div>
            <div className="aws-kv"><span className="v" style={{ fontSize: 24, fontWeight: 700 }}>{asgInstances.filter((i) => i.state === 'running').length}</span><span className="k">Running instances</span></div>
          </div>
        </div>
        <Tabs tabs={[{ key: 'instances', label: `Instance management (${asgInstances.length})` }, { key: 'activity', label: 'Activity history' }, { key: 'details', label: 'Details' }]} active={tab} onChange={setTab} />
        <div style={{ marginTop: 16 }}>
          {tab === 'instances' && (
            <div className="aws-card">
              {asgInstances.length ? (
                <table className="aws-table">
                  <thead><tr><th>Instance ID</th><th>Lifecycle</th><th>State</th><th>Type</th><th>AZ</th></tr></thead>
                  <tbody>
                    {asgInstances.map((i) => (
                      <tr key={i.id}>
                        <td><IDCopy value={i.id} onClick={() => navigate(`${BASE}/ec2/instances/${i.id}`)} /></td>
                        <td>{i.state === 'running' ? 'InService' : i.state === 'pending' ? 'Pending' : i.state}</td>
                        <td><Badge state={i.state} /></td>
                        <td>{i.type}</td>
                        <td>{i.az}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div className="aws-hint">This group currently has no instances.</div>}
            </div>
          )}
          {tab === 'activity' && (
            <div className="aws-card">
              <div className="aws-section-label">Activity history</div>
              <table className="aws-table" style={{ marginTop: 8 }}>
                <thead><tr><th>Status</th><th>Description</th><th>Start time</th><th>Cause</th></tr></thead>
                <tbody>
                  {activity.map((a, i) => (
                    <tr key={i}>
                      <td><Badge state={a.status === 'Successful' ? 'available' : a.status === 'InProgress' ? 'pending' : 'stopped'}>{a.status}</Badge></td>
                      <td>{a.description}</td>
                      <td>{a.at ? new Date(a.at).toLocaleString() : '—'}</td>
                      <td style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>{a.cause}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === 'details' && (
            <div className="aws-card">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                <div className="aws-kv"><span className="k">Auto Scaling group ID</span><span className="v"><IDCopy value={asg.id} /></span></div>
                <div className="aws-kv"><span className="k">Launch template</span><span className="v">{asg.launchTemplate}</span></div>
                <div className="aws-kv"><span className="k">VPC ID</span><span className="v"><IDCopy value={asg.vpcId} /></span></div>
                <div className="aws-kv"><span className="k">Created</span><span className="v">{new Date(asg.created).toLocaleString()}</span></div>
              </div>
            </div>
          )}
        </div>
      </div>
      {editOpen && (
        <Modal onClose={() => setEditOpen(false)} title="Edit capacity"
          footer={(
            <>
              <Button onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button variant="primary" onClick={() => {
                const res = scaleAutoScalingGroup(asg.id, capacity)
                if (res?.ok === false) pushFlash('error', res.error)
                else pushFlash('success', `Scaled ${asg.name} desired=${capacity.desired}`)
                setEditOpen(false)
              }}>Update</Button>
            </>
          )}>
          <div style={{ display: 'grid', gap: 12 }}>
            <label className="aws-label">Desired<input className="aws-input" type="number" min={0} value={capacity.desired}
              onChange={(e) => setCapacity({ ...capacity, desired: Number(e.target.value) })} /></label>
            <label className="aws-label">Minimum<input className="aws-input" type="number" min={0} value={capacity.min}
              onChange={(e) => setCapacity({ ...capacity, min: Number(e.target.value) })} /></label>
            <label className="aws-label">Maximum<input className="aws-input" type="number" min={0} value={capacity.max}
              onChange={(e) => setCapacity({ ...capacity, max: Number(e.target.value) })} /></label>
          </div>
        </Modal>
      )}
    </div>
  )
}
