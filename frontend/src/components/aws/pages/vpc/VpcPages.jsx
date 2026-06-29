import { useNavigate } from 'react-router-dom'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Badge, DataTable, IDCopy, SectionLabel } from '../../ui/primitives'
import { BASE } from '../../layout/serviceNav'

function Page({ title, children }) {
  return (
    <div className="aws-page">
      <h1 style={{ marginBottom: 16 }}>{title}</h1>
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
  return (
    <Page title="VPC Dashboard">
      <div className="aws-card">
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
    </Page>
  )
}

export function VpcList() {
  const region = useAwsStore((s) => s.region)
  const vpcs = scoped(useAwsStore((s) => s.vpcs), region)
  const columns = [
    { key: 'id', label: 'VPC ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'name', label: 'Name', render: (r) => r.name || '—' },
    { key: 'state', label: 'State', render: (r) => <Badge state="available">{r.state}</Badge> },
    { key: 'cidr', label: 'IPv4 CIDR' },
    { key: 'isDefault', label: 'Default VPC', render: (r) => (r.isDefault ? 'Yes' : 'No') },
    { key: 'tenancy', label: 'Tenancy' },
  ]
  return <Page title={`Your VPCs (${vpcs.length})`}><DataTable columns={columns} rows={vpcs} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} /></Page>
}

export function SubnetList() {
  const region = useAwsStore((s) => s.region)
  const subnets = scoped(useAwsStore((s) => s.subnets), region)
  const columns = [
    { key: 'id', label: 'Subnet ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'state', label: 'State', render: () => <Badge state="available">available</Badge> },
    { key: 'vpcId', label: 'VPC', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
    { key: 'cidr', label: 'IPv4 CIDR' },
    { key: 'availableIps', label: 'Available IPv4 addresses' },
    { key: 'az', label: 'Availability Zone' },
    { key: 'mapPublicIp', label: 'Auto-assign public IP', render: (r) => (r.mapPublicIp ? 'Yes' : 'No') },
  ]
  return <Page title={`Subnets (${subnets.length})`}><DataTable columns={columns} rows={subnets} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} /></Page>
}

export function RouteTableList() {
  const region = useAwsStore((s) => s.region)
  const rts = scoped(useAwsStore((s) => s.routeTables), region)
  const columns = [
    { key: 'id', label: 'Route table ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'main', label: 'Main', render: (r) => (r.main ? 'Yes' : 'No') },
    { key: 'vpcId', label: 'VPC', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
    { key: 'routes', label: 'Routes', render: (r) => r.routes.map((rt) => `${rt.dest} → ${rt.target}`).join(', ') },
  ]
  return <Page title={`Route tables (${rts.length})`}><DataTable columns={columns} rows={rts} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} /></Page>
}

export function InternetGatewayList() {
  const region = useAwsStore((s) => s.region)
  const igws = scoped(useAwsStore((s) => s.internetGateways), region)
  const columns = [
    { key: 'id', label: 'Internet gateway ID', render: (r) => <IDCopy value={r.id} /> },
    { key: 'state', label: 'State', render: (r) => <Badge state="available">{r.state}</Badge> },
    { key: 'vpcId', label: 'VPC ID', render: (r) => <span className="aws-mono">{r.vpcId}</span> },
  ]
  return <Page title={`Internet gateways (${igws.length})`}><DataTable columns={columns} rows={igws} getRowKey={(r) => r.id} selectable selected={[]} onSelect={() => {}} /></Page>
}
