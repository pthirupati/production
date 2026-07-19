import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Bell, LayoutDashboard, LineChart, Plus, Trash2 } from 'lucide-react'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Badge, Breadcrumb, Button, ConfirmDialog, DataTable, EmptyState, IDCopy, Modal, SectionLabel } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'
import { BASE } from '../../layout/serviceNav'

function Page({ title, children, action, crumbs }) {
  return (
    <div>
      {crumbs && <Breadcrumb items={crumbs} />}
      <div className="aws-page" style={crumbs ? { paddingTop: 0 } : undefined}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1>{title}</h1>
          {action}
        </div>
        {children}
      </div>
    </div>
  )
}

function alarmStateBadge(state) {
  if (state === 'OK') return 'running'
  if (state === 'ALARM') return 'stopped'
  return 'terminated'
}

// Catalog of common namespaces/metrics for the alarm wizard + metrics explorer.
const METRIC_CATALOG = {
  'AWS/EC2': ['CPUUtilization', 'NetworkIn', 'NetworkOut', 'DiskReadOps', 'StatusCheckFailed'],
  'AWS/RDS': ['CPUUtilization', 'DatabaseConnections', 'FreeableMemory', 'ReadIOPS', 'WriteIOPS'],
  'AWS/Lambda': ['Invocations', 'Errors', 'Duration', 'Throttles', 'ConcurrentExecutions'],
  'AWS/DynamoDB': ['ConsumedReadCapacityUnits', 'ConsumedWriteCapacityUnits', 'ThrottledRequests'],
  'AWS/S3': ['BucketSizeBytes', 'NumberOfObjects', 'AllRequests', '4xxErrors', '5xxErrors'],
  'AWS/ApplicationELB': ['RequestCount', 'TargetResponseTime', 'HTTPCode_Target_5XX_Count'],
}
const STATISTICS = ['Average', 'Sum', 'Minimum', 'Maximum', 'SampleCount']
const OPERATORS = [
  { key: 'GreaterThanThreshold', label: '>' },
  { key: 'GreaterThanOrEqualToThreshold', label: '>=' },
  { key: 'LessThanThreshold', label: '<' },
  { key: 'LessThanOrEqualToThreshold', label: '<=' },
]

// Parse a numeric threshold out of a stored condition string like "> 80% for 2/3 datapoints".
function parseThreshold(cond) {
  const m = String(cond || '').match(/-?\d+(\.\d+)?/)
  return m ? Number(m[0]) : null
}

export function CloudWatchOverview() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const alarms = scoped(useAwsStore((s) => s.cwAlarms), region)
  const inAlarm = alarms.filter((a) => a.state === 'ALARM').length
  return (
    <Page title="CloudWatch Overview">
      <div className="aws-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <SectionLabel>Alarms by state</SectionLabel>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button icon={LineChart} onClick={() => navigate(`${BASE}/cloudwatch/metrics`)}>Metrics</Button>
            <Button icon={LayoutDashboard} onClick={() => navigate(`${BASE}/cloudwatch/dashboards`)}>Dashboards</Button>
            <Button variant="primary" icon={Bell} onClick={() => navigate(`${BASE}/cloudwatch/alarms`)}>Alarms</Button>
          </div>
        </div>
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
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const alarms = scoped(useAwsStore((s) => s.cwAlarms), region)
  const createCwAlarm = useAwsStore((s) => s.createCwAlarm)
  const deleteCwAlarm = useAwsStore((s) => s.deleteCwAlarm)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [selected, setSelected] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [creating, setCreating] = useState(false)

  // Wizard state
  const [name, setName] = useState('')
  const [namespace, setNamespace] = useState('AWS/EC2')
  const [metric, setMetric] = useState('CPUUtilization')
  const [statistic, setStatistic] = useState('Average')
  const [period, setPeriod] = useState('300')
  const [operator, setOperator] = useState('GreaterThanThreshold')
  const [threshold, setThreshold] = useState(80)
  const [datapoints, setDatapoints] = useState(2)
  const [evalPeriods, setEvalPeriods] = useState(3)

  const nameError = !name ? '' : alarms.some((a) => a.name === name) ? 'An alarm with this name already exists in this Region.' : ''
  const canCreate = !!name && !nameError

  const openCreate = () => {
    setName(''); setNamespace('AWS/EC2'); setMetric('CPUUtilization'); setStatistic('Average')
    setPeriod('300'); setOperator('GreaterThanThreshold'); setThreshold(80); setDatapoints(2); setEvalPeriods(3)
    setCreating(true)
  }

  const submit = () => {
    const opLabel = (OPERATORS.find((o) => o.key === operator) || {}).label || '>'
    const conditionStr = `${opLabel} ${threshold} for ${datapoints}/${evalPeriods} datapoints`
    createCwAlarm({ name, metric, namespace, threshold: conditionStr, region })
    // Persist wizard details onto the alarm for the detail page.
    useAwsStore.setState((s) => ({
      cwAlarms: (s.cwAlarms || []).map((a) => (a.name === name && (a.region === region || !a.region)
        ? { ...a, statistic, period: Number(period), operator, thresholdValue: Number(threshold), datapoints: Number(datapoints), evalPeriods: Number(evalPeriods) }
        : a)),
    }))
    pushFlash('success', `Alarm ${name} created`)
    setCreating(false)
    navigate(`${BASE}/cloudwatch/alarms/${encodeURIComponent(name)}`)
  }

  const columns = [
    { key: 'name', label: 'Name', render: (r) => <a onClick={() => navigate(`${BASE}/cloudwatch/alarms/${encodeURIComponent(r.name)}`)}>{r.name}</a> },
    { key: 'state', label: 'State', render: (r) => <Badge state={alarmStateBadge(r.state)}>{r.state}</Badge> },
    { key: 'metric', label: 'Metric' },
    { key: 'namespace', label: 'Namespace' },
    { key: 'threshold', label: 'Condition' },
  ]

  return (
    <Page
      title={`Alarms (${alarms.length})`}
      action={(
        <div style={{ display: 'flex', gap: 8 }}>
          <Button disabled={selected.length !== 1} icon={Trash2} onClick={() => setDeleteTarget(selected[0])}>Delete</Button>
          <Button variant="primary" icon={Plus} onClick={openCreate}>Create alarm</Button>
        </div>
      )}
    >
      <DataTable
        columns={columns}
        rows={alarms}
        getRowKey={(r) => r.name}
        selectable
        selected={selected}
        onSelect={setSelected}
        onRowClick={(r) => navigate(`${BASE}/cloudwatch/alarms/${encodeURIComponent(r.name)}`)}
        rowActions={(r) => [
          { label: 'View details', onClick: () => navigate(`${BASE}/cloudwatch/alarms/${encodeURIComponent(r.name)}`) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r.name) },
        ]}
        tableId="cloudwatch:alarms"
        emptyTitle="No alarms in this Region"
        emptyBody="Create an alarm to monitor a metric."
      />
      {creating && (
        <Modal
          title="Create alarm"
          width={720}
          onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!canCreate} onClick={submit}>Create alarm</Button></>}
        >
          <div className="aws-card" style={{ marginBottom: 12 }}>
            <SectionLabel>Metric</SectionLabel>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
              <div>
                <label className="aws-label">Namespace</label>
                <select className="aws-input" value={namespace} onChange={(e) => { setNamespace(e.target.value); setMetric(METRIC_CATALOG[e.target.value][0]) }}>
                  {Object.keys(METRIC_CATALOG).map((ns) => <option key={ns} value={ns}>{ns}</option>)}
                </select>
              </div>
              <div>
                <label className="aws-label">Metric name</label>
                <select className="aws-input" value={metric} onChange={(e) => setMetric(e.target.value)}>
                  {METRIC_CATALOG[namespace].map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="aws-label">Statistic</label>
                <select className="aws-input" value={statistic} onChange={(e) => setStatistic(e.target.value)}>
                  {STATISTICS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="aws-label">Period (seconds)</label>
                <select className="aws-input" value={period} onChange={(e) => setPeriod(e.target.value)}>
                  {['60', '300', '900', '3600'].map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            </div>
          </div>
          <div className="aws-card" style={{ marginBottom: 12 }}>
            <SectionLabel>Conditions</SectionLabel>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
              <div>
                <label className="aws-label">Whenever {metric} is</label>
                <select className="aws-input" value={operator} onChange={(e) => setOperator(e.target.value)}>
                  {OPERATORS.map((o) => <option key={o.key} value={o.key}>{o.label} ({o.key})</option>)}
                </select>
              </div>
              <div>
                <label className="aws-label">than threshold</label>
                <input type="number" className="aws-input" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
              </div>
              <div>
                <label className="aws-label">Datapoints to alarm</label>
                <input type="number" min={1} className="aws-input" value={datapoints} onChange={(e) => setDatapoints(Number(e.target.value))} />
              </div>
              <div>
                <label className="aws-label">Evaluation periods</label>
                <input type="number" min={1} className="aws-input" value={evalPeriods} onChange={(e) => setEvalPeriods(Number(e.target.value))} />
              </div>
            </div>
          </div>
          <div className="aws-card">
            <SectionLabel>Name</SectionLabel>
            <label className="aws-label" style={{ marginTop: 10 }}>Alarm name</label>
            <input className={`aws-input ${nameError ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="High-CPU-alarm" />
            {nameError && <div className="aws-field-error">{nameError}</div>}
          </div>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete alarm ${deleteTarget}?`}
          body={`This removes alarm ${deleteTarget} from this CloudWatch environment.`}
          confirmLabel="Delete"
          confirmText={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteCwAlarm(deleteTarget); pushFlash('success', `Deleted alarm ${deleteTarget}`); setSelected([]); setDeleteTarget(null) }}
        />
      )}
    </Page>
  )
}

export function AlarmDetail() {
  const { name } = useParams()
  const navigate = useNavigate()
  const decoded = decodeURIComponent(name)
  const region = useAwsStore((s) => s.region)
  const alarm = useAwsStore((s) => (s.cwAlarms || []).find((a) => a.name === decoded))
  const deleteCwAlarm = useAwsStore((s) => s.deleteCwAlarm)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!alarm) return <div className="aws-page"><EmptyState title="Alarm not found" action={<Button onClick={() => navigate(`${BASE}/cloudwatch/alarms`)}>Back to alarms</Button>} /></div>

  const thr = alarm.thresholdValue ?? parseThreshold(alarm.threshold)
  const base = alarm.state === 'ALARM' && thr != null ? thr + 15 : (thr != null ? Math.max(1, thr * 0.6) : 20)
  const variance = thr != null ? Math.max(10, thr * 0.5) : 40

  const setAlarmState = (next) => {
    useAwsStore.setState((s) => ({ cwAlarms: (s.cwAlarms || []).map((a) => (a.name === decoded ? { ...a, state: next } : a)) }))
    pushFlash('info', `Alarm ${decoded} set to ${next}`)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'CloudWatch', onClick: () => navigate(`${BASE}/cloudwatch/home`) }, { label: 'Alarms', onClick: () => navigate(`${BASE}/cloudwatch/alarms`) }, { label: decoded }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{decoded} <Badge state={alarmStateBadge(alarm.state)}>{alarm.state}</Badge></h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button onClick={() => setAlarmState(alarm.state === 'ALARM' ? 'OK' : 'ALARM')}>{alarm.state === 'ALARM' ? 'Set to OK' : 'Trigger alarm'}</Button>
            <Button variant="danger" onClick={() => setDeleteOpen(true)}>Delete</Button>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 12 }}>
          <MetricChart title={`${alarm.namespace} · ${alarm.metric}`} unit={alarm.metric === 'CPUUtilization' ? '%' : ''} color="#0073bb" base={base} variance={variance} threshold={thr} />
          <div className="aws-card">
            <SectionLabel>Details</SectionLabel>
            <div className="aws-summary-grid" style={{ marginTop: 8 }}>
              <div className="aws-kv"><span className="k">Metric</span><span className="v">{alarm.metric}</span></div>
              <div className="aws-kv"><span className="k">Namespace</span><span className="v">{alarm.namespace}</span></div>
              <div className="aws-kv"><span className="k">Statistic</span><span className="v">{alarm.statistic || 'Average'}</span></div>
              <div className="aws-kv"><span className="k">Period</span><span className="v">{alarm.period ? `${alarm.period} sec` : '300 sec'}</span></div>
              <div className="aws-kv"><span className="k">Condition</span><span className="v">{alarm.threshold}</span></div>
              <div className="aws-kv"><span className="k">Region</span><span className="v">{alarm.region || region}</span></div>
            </div>
          </div>
        </div>
      </div>
      {deleteOpen && (
        <ConfirmDialog
          title={`Delete alarm ${decoded}?`}
          body={`This removes alarm ${decoded} from this CloudWatch environment.`}
          confirmLabel="Delete"
          confirmText={decoded}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => { deleteCwAlarm(decoded); pushFlash('success', `Deleted alarm ${decoded}`); navigate(`${BASE}/cloudwatch/alarms`) }}
        />
      )}
    </div>
  )
}

export function MetricsExplorer() {
  const navigate = useNavigate()
  const [namespace, setNamespace] = useState('AWS/EC2')
  const [selected, setSelected] = useState(['CPUUtilization'])
  const toggle = (m) => setSelected((cur) => (cur.includes(m) ? cur.filter((x) => x !== m) : [...cur, m]))
  const palette = ['#0073bb', '#1d8102', '#ff9900', '#d13212', '#8b5cf6']
  return (
    <Page title="Metrics explorer" crumbs={[{ label: 'CloudWatch', onClick: () => navigate(`${BASE}/cloudwatch/home`) }, { label: 'Metrics' }]}>
      <div className="aws-card" style={{ marginBottom: 12 }}>
        <SectionLabel>Browse metrics</SectionLabel>
        <div style={{ display: 'flex', gap: 12, marginTop: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <label className="aws-label">Namespace</label>
            <select className="aws-input" value={namespace} onChange={(e) => { setNamespace(e.target.value); setSelected([METRIC_CATALOG[e.target.value][0]]) }}>
              {Object.keys(METRIC_CATALOG).map((ns) => <option key={ns} value={ns}>{ns}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {METRIC_CATALOG[namespace].map((m) => (
              <label key={m} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="checkbox" checked={selected.includes(m)} onChange={() => toggle(m)} /> {m}
              </label>
            ))}
          </div>
        </div>
      </div>
      {selected.length === 0 ? (
        <EmptyState title="No metrics selected" body="Select one or more metrics to graph." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
          {selected.map((m, i) => (
            <MetricChart key={m} title={`${namespace} · ${m}`} unit={m === 'CPUUtilization' ? '%' : ''} color={palette[i % palette.length]} base={20 + i * 10} variance={40} />
          ))}
        </div>
      )}
    </Page>
  )
}

export function DashboardList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const dashboards = scoped(useAwsStore((s) => s.cwDashboards), region)
  const createCwDashboard = useAwsStore((s) => s.createCwDashboard)
  const deleteCwDashboard = useAwsStore((s) => s.deleteCwDashboard)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [widgets, setWidgets] = useState(4)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const nameError = !name ? '' : dashboards.some((d) => d.name === name) ? 'A dashboard with this name already exists.' : ''

  const columns = [
    { key: 'name', label: 'Name', render: (r) => <IDCopy value={r.name} mono={false} /> },
    { key: 'widgets', label: 'Widgets' },
    { key: 'region', label: 'Region', render: (r) => r.region || region },
    { key: 'created', label: 'Created', render: (r) => (r.created ? new Date(r.created).toLocaleString() : '—') },
  ]

  return (
    <Page
      title={`Dashboards (${dashboards.length})`}
      crumbs={[{ label: 'CloudWatch', onClick: () => navigate(`${BASE}/cloudwatch/home`) }, { label: 'Dashboards' }]}
      action={<Button variant="primary" icon={Plus} onClick={() => { setName(''); setWidgets(4); setCreating(true) }}>Create dashboard</Button>}
    >
      <DataTable
        columns={columns}
        rows={dashboards}
        getRowKey={(r) => r.name}
        rowActions={(r) => [
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r.name) },
        ]}
        tableId="cloudwatch:dashboards"
        emptyTitle="No dashboards"
        emptyBody="Create a dashboard to pin metric widgets."
      />
      {creating && (
        <Modal
          title="Create dashboard"
          onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!name || !!nameError} onClick={() => { createCwDashboard({ name, widgets: Number(widgets), region }); pushFlash('success', `Dashboard ${name} created`); setCreating(false) }}>Create dashboard</Button></>}
        >
          <label className="aws-label">Dashboard name</label>
          <input className={`aws-input ${nameError ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="Production-Overview" />
          {nameError && <div className="aws-field-error">{nameError}</div>}
          <label className="aws-label" style={{ marginTop: 12 }}>Initial widgets</label>
          <input type="number" min={0} max={50} className="aws-input" value={widgets} onChange={(e) => setWidgets(Number(e.target.value))} />
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete dashboard ${deleteTarget}?`}
          body={`This removes dashboard ${deleteTarget} from this CloudWatch environment.`}
          confirmLabel="Delete"
          confirmText={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteCwDashboard(deleteTarget); pushFlash('success', `Deleted dashboard ${deleteTarget}`); setDeleteTarget(null) }}
        />
      )}
    </Page>
  )
}
