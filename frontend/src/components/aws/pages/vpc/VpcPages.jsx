import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Badge, Button, DataTable, IDCopy, Modal, SectionLabel } from '../../ui/primitives'
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

export function VpcDashboard() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const subnets = scoped(useAwsStore((s) => s.subnets), region)
  const rts = scoped(useAwsStore((s) => s.routeTables), region)
  const igws = scoped(useAwsStore((s) => s.internetGateways), region)
  const sgs = scoped(useAwsStore((s) => s.securityGroups), region)
  const cards = [
    ['VPCs', vpcs.length, `${BASE}/vpc/vpcs`],
    ['Subnets', subnets.length, `${BASE}/vpc/subnets`],
    ['Route tables', rts.length, `${BASE}/vpc/route-tables`],
    ['Internet gateways', igws.length, `${BASE}/vpc/internet-gateways`],
    ['Security groups', sgs.length, `${BASE}/vpc/security-groups`],
  ]
  const primaryVpc = vpcs[0]
  const primarySubnets = primaryVpc ? subnets.filter((s) => s.vpcId === primaryVpc.id) : []
  const publicSubnets = primarySubnets.filter((s) => s.mapPublicIp)
  const privateSubnets = primarySubnets.filter((s) => !s.mapPublicIp)
  const primaryRt = primaryVpc ? rts.find((rt) => rt.vpcId === primaryVpc.id) : null
  const primaryIgw = primaryVpc ? igws.find((igw) => igw.vpcId === primaryVpc.id) : null
  return (
    <Page title="VPC Dashboard">
      <div className="aws-card" style={{ marginBottom: 16 }}>
        <SectionLabel>Resources by Region · {region}</SectionLabel>
        <div className="aws-summary-grid" style={{ marginTop: 8 }}>
          {cards.map(([label, n, path]) => (
            <div key={label} className="aws-kv" style={{ cursor: 'pointer' }} onClick={() => navigate(path)}>
              <span className="v" style={{ fontSize: 24, fontWeight: 700, color: 'var(--aws-text-link)' }}>{n}</span>
              <span className="k">{label}</span>
            </div>
          ))}
        </div>
      </div>
      {primaryVpc && (
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <SectionLabel>Network topology · {primaryVpc.name || primaryVpc.id}</SectionLabel>
          <div className="aws-hint" style={{ marginTop: 6 }}>Real AWS VPC maps show how public/private subnets, route tables, internet gateways, and security groups relate. This console mirrors that mental model for lab troubleshooting.</div>
          <div style={{ marginTop: 14, border: '1px solid var(--aws-border)', borderRadius: 8, padding: 16, background: 'var(--aws-page-bg)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 180px', gap: 16, alignItems: 'stretch' }}>
              <TopologyNode title="Internet" subtitle="0.0.0.0/0" tone="edge" />
              <div style={{ border: '2px solid #7aa116', borderRadius: 10, padding: 14, position: 'relative', background: 'var(--aws-content-bg)' }}>
                <div style={{ position: 'absolute', top: -12, left: 14, background: 'var(--aws-content-bg)', padding: '0 8px', fontWeight: 700, color: '#3f6b00' }}>VPC {primaryVpc.cidr}</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 12 }}>
                  <SubnetColumn title="Public subnets" subnets={publicSubnets} route={primaryRt} />
                  <SubnetColumn title="Private subnets" subnets={privateSubnets} route={primaryRt} />
                </div>
              </div>
              <TopologyNode title="Internet gateway" subtitle={primaryIgw?.id || 'Not attached'} tone={primaryIgw ? 'ok' : 'warn'} />
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap', fontSize: 12 }}>
              <span><Badge state="available">VPC available</Badge></span>
              <span>Route table: <span className="aws-mono">{primaryRt?.id || '—'}</span></span>
              <span>Security groups: {sgs.length}</span>
              <span>DNS hostnames: enabled</span>
            </div>
          </div>
        </div>
      )}
    </Page>
  )
}

function TopologyNode({ title, subtitle, tone }) {
  const colors = {
    edge: ['#146eb4', 'rgba(20,110,180,0.08)'],
    ok: ['#1d8102', 'rgba(29,129,2,0.08)'],
    warn: ['#d13212', 'rgba(209,50,18,0.08)'],
  }[tone] || ['#687078', 'rgba(104,112,120,0.08)']
  return (
    <div style={{ border: `1px solid ${colors[0]}`, borderRadius: 8, background: colors[1], padding: 14, display: 'flex', flexDirection: 'column', justifyContent: 'center', minHeight: 110 }}>
      <strong style={{ color: colors[0] }}>{title}</strong>
      <span className="aws-mono" style={{ fontSize: 12, marginTop: 6 }}>{subtitle}</span>
    </div>
  )
}

function SubnetColumn({ title, subnets, route }) {
  return (
    <div style={{ border: '1px dashed var(--aws-border)', borderRadius: 8, padding: 10, minHeight: 150 }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>{title}</div>
      {subnets.length ? subnets.map((s) => (
        <div key={s.id} style={{ background: 'var(--aws-content-bg)', border: '1px solid var(--aws-border-light)', borderRadius: 6, padding: 8, marginBottom: 8 }}>
          <div><IDCopy value={s.id} /></div>
          <div className="aws-hint" style={{ marginTop: 4 }}>{s.az} · {s.cidr} · {s.availableIps} IPv4 left</div>
          <div className="aws-hint">Route: {route?.main ? 'main route table' : route?.id || '—'}</div>
        </div>
      )) : (
        <div className="aws-hint">No subnet in this tier.</div>
      )}
    </div>
  )
}

export function VpcList() {
  const region = useAwsStore((s) => s.region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const createVpc = useAwsStore((s) => s.createVpc)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const columns = [
    { key: 'id', label: 'VPC ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'name', label: 'Name', render: (r) => r.name || '—' },
    { key: 'state', label: 'State', render: (r) => <Badge state="available">{r.state}</Badge> },
    { key: 'cidr', label: 'IPv4 CIDR' },
    { key: 'isDefault', label: 'Default VPC', render: (r) => (r.isDefault ? 'Yes' : 'No') },
    { key: 'tenancy', label: 'Tenancy' },
  ]
  return (
    <Page
      title={`Your VPCs (${vpcs.length})`}
      action={<Button variant="primary" onClick={() => {
        const n = (vpcs.length || 0) + 1
        const res = createVpc({ name: `lab-vpc-${n}`, cidr: `10.${10 + n}.0.0/16` })
        if (res?.ok === false) return
        pushFlash('success', `Created VPC ${res.id}`)
      }}>Create VPC</Button>}
    >
      <DataTable columns={columns} rows={vpcs} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} />
    </Page>
  )
}

export function SubnetList() {
  const region = useAwsStore((s) => s.region)
  const subnets = scoped(useAwsStore((s) => s.subnets), region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const createSubnet = useAwsStore((s) => s.createSubnet)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const columns = [
    { key: 'id', label: 'Subnet ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'state', label: 'State', render: () => <Badge state="available">available</Badge> },
    { key: 'vpcId', label: 'VPC', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
    { key: 'cidr', label: 'IPv4 CIDR' },
    { key: 'availableIps', label: 'Available IPv4 addresses' },
    { key: 'az', label: 'Availability Zone' },
    { key: 'mapPublicIp', label: 'Auto-assign public IP', render: (r) => (r.mapPublicIp ? 'Yes' : 'No') },
  ]
  return (
    <Page
      title={`Subnets (${subnets.length})`}
      action={<Button variant="primary" onClick={() => {
        const vpc = vpcs[0]
        if (!vpc) { pushFlash('error', 'Create a VPC first'); return }
        const n = (subnets.filter((s) => s.vpcId === vpc.id).length || 0) + 1
        const res = createSubnet({ vpcId: vpc.id, cidr: `172.31.${n * 16}.0/20`, az: `${region}a`, mapPublicIp: true })
        if (res?.ok === false) return
        pushFlash('success', `Created subnet ${res.id}`)
      }}>Create subnet</Button>}
    >
      <DataTable columns={columns} rows={subnets} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} />
    </Page>
  )
}

export function RouteTableList() {
  const region = useAwsStore((s) => s.region)
  const rts = scoped(useAwsStore((s) => s.routeTables), region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const igws = scoped(useAwsStore((s) => s.internetGateways), region)
  const createRtb = useAwsStore((s) => s.createRouteTable)
  const createRoute = useAwsStore((s) => s.createRoute)
  const deleteRtb = useAwsStore((s) => s.deleteRouteTable)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const columns = [
    { key: 'id', label: 'Route table ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'main', label: 'Main', render: (r) => (r.main ? 'Yes' : 'No') },
    { key: 'vpcId', label: 'VPC', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
    { key: 'routes', label: 'Routes', render: (r) => r.routes.map((rt) => `${rt.dest} → ${rt.target}`).join(', ') },
    {
      key: 'actions', label: '', sortable: false,
      render: (r) => (
        <Button variant="link" onClick={() => {
          const igw = igws.find((g) => g.vpcId === r.vpcId && g.state === 'attached') || igws[0]
          const res = createRoute(r.id, { dest: '0.0.0.0/0', target: igw?.id || 'igw-local' })
          if (res?.ok === false) return
          pushFlash('success', `Added default route on ${r.id}`)
        }}>Add 0.0.0.0/0</Button>
      ),
    },
  ]
  return (
    <Page
      title={`Route tables (${rts.length})`}
      action={<Button variant="primary" onClick={() => {
        const res = createRtb({ vpcId: vpcs[0]?.id })
        if (res?.ok === false) return
        pushFlash('success', `Created ${res.id}`)
      }}>Create route table</Button>}
    >
      <DataTable
        columns={columns}
        rows={rts}
        getRowKey={(r) => r.id}
        selectable
        selected={[]}
        onSelect={() => {}}
        rowActions={(r) => (r.main ? [] : [
          { label: 'Delete', danger: true, onClick: () => { const res = deleteRtb(r.id); if (res?.ok === false) return; pushFlash('success', `Deleted ${r.id}`) } },
        ])}
      />
    </Page>
  )
}

export function InternetGatewayList() {
  const region = useAwsStore((s) => s.region)
  const igws = scoped(useAwsStore((s) => s.internetGateways), region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const createIgw = useAwsStore((s) => s.createInternetGateway)
  const attachIgw = useAwsStore((s) => s.attachInternetGateway)
  const detachIgw = useAwsStore((s) => s.detachInternetGateway)
  const deleteIgw = useAwsStore((s) => s.deleteInternetGateway)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [attachTarget, setAttachTarget] = useState(null)
  const [attachVpc, setAttachVpc] = useState('')

  const columns = [
    { key: 'id', label: 'Internet gateway ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'state', label: 'State', render: (r) => <Badge state="available">{r.state}</Badge> },
    { key: 'vpcId', label: 'VPC ID', render: (r) => <span className="aws-mono">{r.vpcId || '—'}</span> },
    {
      key: 'actions', label: '', sortable: false,
      render: (r) => (r.state === 'attached'
        ? <Button variant="link" onClick={() => { const res = detachIgw(r.id); if (res?.ok === false) return; pushFlash('success', `Detached ${r.id}`) }}>Detach</Button>
        : <Button variant="link" onClick={() => { setAttachVpc(vpcs[0]?.id || ''); setAttachTarget(r) }}>Attach to VPC</Button>),
    },
  ]
  return (
    <Page
      title={`Internet gateways (${igws.length})`}
      action={<Button variant="primary" onClick={() => { const g = createIgw({ name: `igw-${Date.now().toString(36).slice(-4)}` }); pushFlash('success', `Created ${g.id}`) }}>Create internet gateway</Button>}
    >
      <DataTable
        columns={columns}
        rows={igws}
        getRowKey={(r) => r.id}
        selectable
        selected={[]}
        onSelect={() => {}}
        rowActions={(r) => [
          ...(r.state === 'attached'
            ? [{ label: 'Detach from VPC', onClick: () => { detachIgw(r.id); pushFlash('success', `Detached ${r.id}`) } }]
            : [{ label: 'Attach to VPC', onClick: () => { setAttachVpc(vpcs[0]?.id || ''); setAttachTarget(r) } }]),
          { label: 'Delete', danger: true, onClick: () => { const res = deleteIgw(r.id); if (res?.ok === false) return; pushFlash('success', `Deleted ${r.id}`) } },
        ]}
      />
      {attachTarget && (
        <Modal title={`Attach ${attachTarget.id}`} onClose={() => setAttachTarget(null)}
          footer={(
            <>
              <Button onClick={() => setAttachTarget(null)}>Cancel</Button>
              <Button variant="primary" disabled={!attachVpc} onClick={() => {
                const res = attachIgw(attachTarget.id, attachVpc)
                if (res?.ok === false) return
                pushFlash('success', `Attached ${attachTarget.id} to ${attachVpc}`)
                setAttachTarget(null)
              }}>Attach</Button>
            </>
          )}>
          <label className="aws-label">VPC</label>
          <select className="aws-select" value={attachVpc} onChange={(e) => setAttachVpc(e.target.value)}>
            <option value="">Select a VPC</option>
            {vpcs.map((v) => <option key={v.id} value={v.id}>{v.id}{v.name ? ` (${v.name})` : ''} · {v.cidr}</option>)}
          </select>
        </Modal>
      )}
    </Page>
  )
}
