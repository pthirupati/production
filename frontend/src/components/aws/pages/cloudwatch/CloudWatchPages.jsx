import { useAwsStore, scoped } from '../../store/awsStore'
import { Badge, DataTable, SectionLabel } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'

function Page({ title, children }) {
  return (
    <div className="aws-page">
      <h1 style={{ marginBottom: 16 }}>{title}</h1>
      {children}
    </div>
  )
}

export function CloudWatchOverview() {
  const region = useAwsStore((s) => s.region)
  const alarms = scoped(useAwsStore((s) => s.cwAlarms), region)
  const inAlarm = alarms.filter((a) => a.state === 'ALARM').length
  return (
    <Page title="CloudWatch Overview">
      <div className="aws-card" style={{ marginBottom: 16 }}>
        <SectionLabel>Alarms by state</SectionLabel>
        <div className="aws-summary-grid" style={{ marginTop: 8 }}>
          <div className="aws-kv"><span className="v" style={{ fontSize: 24, fontWeight: 700, color: 'var(--aws-error)' }}>{inAlarm}</span><span className="k">In alarm</span></div>
          <div className="aws-kv"><span className="v" style={{ fontSize: 24, fontWeight: 700, color: 'var(--aws-success)' }}>{alarms.filter((a) => a.state === 'OK').length}</span><span className="k">OK</span></div>
          <div className="aws-kv"><span className="v" style={{ fontSize: 24, fontWeight: 700, color: 'var(--aws-text-muted)' }}>{alarms.filter((a) => a.state === 'INSUFFICIENT_DATA').length}</span><span className="k">Insufficient data</span></div>
        </div>
      </div>
      <SectionLabel>Account metrics (last 7 days)</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12, marginTop: 8 }}>
        <MetricChart title="EC2 CPUUtilization (%)" unit="%" color="#0073bb" base={12} variance={30} />
        <MetricChart title="EstimatedCharges (USD)" unit="" color="#1d8102" base={40} variance={10} />
        <MetricChart title="Lambda Invocations (Count)" unit="" color="#9d5025" base={20} variance={120} />
        <MetricChart title="NetworkIn (Bytes)" unit="" color="#d13212" base={50000} variance={400000} />
      </div>
    </Page>
  )
}

export function AlarmList() {
  const region = useAwsStore((s) => s.region)
  const alarms = scoped(useAwsStore((s) => s.cwAlarms), region)
  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'state', label: 'State', render: (r) => <Badge state={r.state === 'OK' ? 'running' : r.state === 'ALARM' ? 'stopped' : 'terminated'}>{r.state}</Badge> },
    { key: 'metric', label: 'Metric' },
    { key: 'namespace', label: 'Namespace' },
    { key: 'threshold', label: 'Condition' },
  ]
  return <Page title={`Alarms (${alarms.length})`}><DataTable columns={columns} rows={alarms} getRowKey={(r) => r.name} selectable selected={[]} onSelect={() => {}} /></Page>
}
