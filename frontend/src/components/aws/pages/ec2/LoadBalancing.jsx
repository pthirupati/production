import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, Tabs, DataTable, IDCopy, Breadcrumb, Modal, ConfirmDialog, EmptyState } from '../../ui/primitives'
import { BASE } from '../../layout/serviceNav'

function healthBadge(h) {
  const map = { healthy: 'available', unhealthy: 'failed', initial: 'pending', draining: 'stopping' }
  return <Badge state={map[h] || 'pending'}>{h}</Badge>
}

// ---------- Load Balancers ----------
export function LoadBalancerList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const lbs = scoped(useAwsStore((s) => s.loadBalancers), region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const createLoadBalancer = useAwsStore((s) => s.createLoadBalancer)
  const deleteLoadBalancer = useAwsStore((s) => s.deleteLoadBalancer)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [form, setForm] = useState({ name: '', type: 'application', scheme: 'internet-facing' })

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'id', label: 'Load balancer ID', render: (r) => <IDCopy value={r.id} onClick={() => navigate(`${BASE}/ec2/load-balancers/${r.id}`)} /> },
    { key: 'dnsName', label: 'DNS name', render: (r) => <span className="aws-mono" style={{ fontSize: 12 }}>{r.dnsName}</span> },
    { key: 'state', label: 'State', render: (r) => <Badge state={r.state}>{r.state}</Badge> },
    { key: 'type', label: 'Type' },
    { key: 'scheme', label: 'Scheme' },
    { key: 'vpcId', label: 'VPC', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
  ]

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>Load balancers ({lbs.length})</h1>
        <Button variant="primary" onClick={() => setCreating(true)}>Create load balancer</Button>
      </div>
      <DataTable
        columns={columns}
        rows={lbs}
        getRowKey={(r) => r.id}
        onRowClick={(r) => navigate(`${BASE}/ec2/load-balancers/${r.id}`)}
        rowActions={(r) => [
          { label: 'View details', onClick: () => navigate(`${BASE}/ec2/load-balancers/${r.id}`) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
        ]}
        tableId="ec2:load-balancers"
        emptyTitle="No load balancers"
        emptyBody="Create a load balancer to distribute traffic across targets."
      />
      {creating && (
        <Modal title="Create load balancer" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!form.name} onClick={() => { const lb = createLoadBalancer({ ...form, vpcId: vpcs[0]?.id }); pushFlash('success', `Load balancer ${lb.name} created`); setCreating(false); setForm({ name: '', type: 'application', scheme: 'internet-facing' }) }}>Create</Button></>}>
          <label className="aws-label">Name</label>
          <input className="aws-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ marginBottom: 12 }} placeholder="my-alb" />
          <label className="aws-label">Type</label>
          <select className="aws-select" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} style={{ marginBottom: 12 }}>
            <option value="application">Application Load Balancer</option>
            <option value="network">Network Load Balancer</option>
            <option value="gateway">Gateway Load Balancer</option>
          </select>
          <label className="aws-label">Scheme</label>
          <select className="aws-select" value={form.scheme} onChange={(e) => setForm({ ...form, scheme: e.target.value })}>
            <option value="internet-facing">Internet-facing</option>
            <option value="internal">Internal</option>
          </select>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.name}?`}
          body="Deleting a load balancer removes it and stops distributing traffic. Target groups are not deleted."
          confirmLabel="Delete"
          confirmText={deleteTarget.name}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteLoadBalancer(deleteTarget.id); pushFlash('success', `Deleted ${deleteTarget.name}`); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}

export function LoadBalancerDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const lb = useAwsStore((s) => (s.loadBalancers || []).find((x) => x.id === id))
  const targetGroups = useAwsStore((s) => s.targetGroups) || []
  const [tab, setTab] = useState('details')

  if (!lb) {
    return <div className="aws-page"><EmptyState title="Load balancer not found" action={<Button onClick={() => navigate(`${BASE}/ec2/load-balancers`)}>Back to load balancers</Button>} /></div>
  }
  const tgs = targetGroups.filter((tg) => (lb.targetGroups || []).includes(tg.id))

  return (
    <div>
      <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Load Balancers', onClick: () => navigate(`${BASE}/ec2/load-balancers`) }, { label: lb.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>{lb.name} <Badge state={lb.state}>{lb.state}</Badge></h1>
        <Tabs tabs={[{ key: 'details', label: 'Details' }, { key: 'listeners', label: 'Listeners & target groups' }]} active={tab} onChange={setTab} />
        <div style={{ marginTop: 16 }}>
          {tab === 'details' && (
            <div className="aws-card">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                <div className="aws-kv"><span className="k">Load balancer ID</span><span className="v"><IDCopy value={lb.id} /></span></div>
                <div className="aws-kv"><span className="k">DNS name</span><span className="v aws-mono" style={{ fontSize: 12 }}>{lb.dnsName}</span></div>
                <div className="aws-kv"><span className="k">Type</span><span className="v">{lb.type}</span></div>
                <div className="aws-kv"><span className="k">Scheme</span><span className="v">{lb.scheme}</span></div>
                <div className="aws-kv"><span className="k">State</span><span className="v"><Badge state={lb.state}>{lb.state}</Badge></span></div>
                <div className="aws-kv"><span className="k">VPC ID</span><span className="v"><IDCopy value={lb.vpcId} /></span></div>
              </div>
            </div>
          )}
          {tab === 'listeners' && (
            <div className="aws-card">
              <div className="aws-section-label">Target groups routed by this load balancer</div>
              {tgs.length ? (
                <table className="aws-table" style={{ marginTop: 8 }}>
                  <thead><tr><th>Target group</th><th>Protocol</th><th>Port</th><th>Targets</th></tr></thead>
                  <tbody>
                    {tgs.map((tg) => (
                      <tr key={tg.id}>
                        <td><IDCopy value={tg.name} onClick={() => navigate(`${BASE}/ec2/target-groups/${tg.id}`)} /></td>
                        <td>{tg.protocol}</td>
                        <td>{tg.port}</td>
                        <td>{(tg.targets || []).length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div className="aws-hint" style={{ marginTop: 8 }}>No target groups attached.</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------- Target Groups ----------
export function TargetGroupList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const tgs = scoped(useAwsStore((s) => s.targetGroups), region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const createTargetGroup = useAwsStore((s) => s.createTargetGroup)
  const deleteTargetGroup = useAwsStore((s) => s.deleteTargetGroup)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [form, setForm] = useState({ name: '', protocol: 'HTTP', port: 80, targetType: 'instance' })

  const columns = [
    { key: 'name', label: 'Name', render: (r) => <IDCopy value={r.name} onClick={() => navigate(`${BASE}/ec2/target-groups/${r.id}`)} /> },
    { key: 'id', label: 'Target group ID', render: (r) => <span className="aws-mono" style={{ fontSize: 12 }}>{r.id}</span> },
    { key: 'protocol', label: 'Protocol' },
    { key: 'port', label: 'Port' },
    { key: 'targetType', label: 'Target type' },
    { key: 'targets', label: 'Registered targets', render: (r) => (r.targets || []).length },
    { key: 'health', label: 'Healthy', render: (r) => `${(r.targets || []).filter((t) => t.health === 'healthy').length}/${(r.targets || []).length}` },
  ]

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>Target groups ({tgs.length})</h1>
        <Button variant="primary" onClick={() => setCreating(true)}>Create target group</Button>
      </div>
      <DataTable
        columns={columns}
        rows={tgs}
        getRowKey={(r) => r.id}
        onRowClick={(r) => navigate(`${BASE}/ec2/target-groups/${r.id}`)}
        rowActions={(r) => [
          { label: 'View details', onClick: () => navigate(`${BASE}/ec2/target-groups/${r.id}`) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
        ]}
        tableId="ec2:target-groups"
        emptyTitle="No target groups"
        emptyBody="Create a target group and register instances to receive traffic."
      />
      {creating && (
        <Modal title="Create target group" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!form.name} onClick={() => { const tg = createTargetGroup({ ...form, port: Number(form.port), vpcId: vpcs[0]?.id }); pushFlash('success', `Target group ${tg.name} created`); setCreating(false); setForm({ name: '', protocol: 'HTTP', port: 80, targetType: 'instance' }) }}>Create</Button></>}>
          <label className="aws-label">Name</label>
          <input className="aws-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ marginBottom: 12 }} placeholder="web-targets" />
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <label className="aws-label">Protocol</label>
              <select className="aws-select" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })}>
                <option value="HTTP">HTTP</option><option value="HTTPS">HTTPS</option><option value="TCP">TCP</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label className="aws-label">Port</label>
              <input className="aws-input" type="number" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            </div>
          </div>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.name}?`}
          body="Deleting a target group deregisters all of its targets."
          confirmLabel="Delete"
          confirmText={deleteTarget.name}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteTargetGroup(deleteTarget.id); pushFlash('success', `Deleted ${deleteTarget.name}`); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}

export function TargetGroupDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const tg = useAwsStore((s) => (s.targetGroups || []).find((x) => x.id === id))
  const instances = scoped(useAwsStore((s) => s.instances), region)
  const registerTarget = useAwsStore((s) => s.registerTarget)
  const deregisterTarget = useAwsStore((s) => s.deregisterTarget)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [tab, setTab] = useState('targets')
  const [registering, setRegistering] = useState(false)
  const [pick, setPick] = useState('')

  if (!tg) {
    return <div className="aws-page"><EmptyState title="Target group not found" action={<Button onClick={() => navigate(`${BASE}/ec2/target-groups`)}>Back to target groups</Button>} /></div>
  }

  const registeredIds = new Set((tg.targets || []).map((t) => t.id))
  const registerable = instances.filter((i) => i.state !== 'terminated' && !registeredIds.has(i.id))

  return (
    <div>
      <Breadcrumb items={[{ label: 'EC2', onClick: () => navigate(`${BASE}/ec2/home`) }, { label: 'Target Groups', onClick: () => navigate(`${BASE}/ec2/target-groups`) }, { label: tg.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1>{tg.name}</h1>
          <Button variant="primary" disabled={!registerable.length} onClick={() => { setPick(registerable[0]?.id || ''); setRegistering(true) }}>Register targets</Button>
        </div>
        <Tabs tabs={[{ key: 'targets', label: `Targets (${(tg.targets || []).length})` }, { key: 'details', label: 'Details' }]} active={tab} onChange={setTab} />
        <div style={{ marginTop: 16 }}>
          {tab === 'targets' && (
            <div className="aws-card">
              <div className="aws-section-label">Registered targets</div>
              <div className="aws-hint" style={{ margin: '4px 0 8px' }}>Health status updates automatically as the load balancer runs health checks.</div>
              {(tg.targets || []).length ? (
                <table className="aws-table">
                  <thead><tr><th>Instance ID</th><th>Port</th><th>Health status</th><th /></tr></thead>
                  <tbody>
                    {tg.targets.map((t) => (
                      <tr key={t.id}>
                        <td><IDCopy value={t.id} onClick={() => navigate(`${BASE}/ec2/instances/${t.id}`)} /></td>
                        <td>{t.port}</td>
                        <td>{healthBadge(t.health)}</td>
                        <td><Button variant="link" onClick={() => { deregisterTarget(tg.id, t.id); pushFlash('success', `Deregistered ${t.id}`) }}>Deregister</Button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div className="aws-hint">No targets registered yet.</div>}
            </div>
          )}
          {tab === 'details' && (
            <div className="aws-card">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                <div className="aws-kv"><span className="k">Target group ID</span><span className="v"><IDCopy value={tg.id} /></span></div>
                <div className="aws-kv"><span className="k">Protocol : Port</span><span className="v">{tg.protocol} : {tg.port}</span></div>
                <div className="aws-kv"><span className="k">Target type</span><span className="v">{tg.targetType}</span></div>
                <div className="aws-kv"><span className="k">VPC ID</span><span className="v"><IDCopy value={tg.vpcId} /></span></div>
              </div>
            </div>
          )}
        </div>
      </div>
      {registering && (
        <Modal title="Register targets" onClose={() => setRegistering(false)}
          footer={<><Button onClick={() => setRegistering(false)}>Cancel</Button><Button variant="primary" disabled={!pick} onClick={() => { registerTarget(tg.id, pick, tg.port); pushFlash('success', `Registered ${pick} to ${tg.name}`); setRegistering(false) }}>Register</Button></>}>
          <label className="aws-label">Instance</label>
          <select className="aws-select" value={pick} onChange={(e) => setPick(e.target.value)}>
            {registerable.map((i) => <option key={i.id} value={i.id}>{i.id} {i.name ? `(${i.name})` : ''} — {i.state}</option>)}
          </select>
          <div className="aws-hint" style={{ marginTop: 8 }}>Newly registered targets begin as <strong>initial</strong> and transition to <strong>healthy</strong> after the first health check.</div>
        </Modal>
      )}
    </div>
  )
}
