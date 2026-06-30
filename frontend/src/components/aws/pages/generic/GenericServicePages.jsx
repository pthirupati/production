import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Activity, Plus, Trash2 } from 'lucide-react'
import { ACCOUNT, useAwsStore } from '../../store/awsStore'
import { arn } from '../../lib/ids'
import { Badge, Breadcrumb, Button, ConfirmDialog, DataTable, EmptyState, IDCopy, Modal, SectionLabel, Tabs } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'
import { BASE } from '../../layout/serviceNav'
import { getResourceConfig, SERVICE_CONFIGS } from './serviceConfigs'

function statusToBadge(status) {
  const s = String(status || '').toLowerCase()
  if (['active', 'available', 'enabled', 'issued', 'healthy', 'ok', 'deployed', 'running', 'create_complete'].includes(s)) return 'running'
  if (['creating', 'updating', 'pending', 'in-progress'].includes(s)) return 'pending'
  if (['disabled', 'stopped'].includes(s)) return 'stopped'
  if (['failed', 'error', 'alarm', 'delete_failed'].includes(s)) return 'failed'
  return 'available'
}

function fieldValue(row, field) {
  const value = row[field.key]
  if (value === undefined || value === null || value === '') return '—'
  if (field.badge) return <Badge state={statusToBadge(value)}>{value}</Badge>
  return `${field.prefix || ''}${value}${field.suffix || ''}`
}

function resourceArn(serviceKey, resourceKey, row, region, cfg) {
  if (cfg.arnService === 'cloudfront' || cfg.arnService === 'route53') {
    return `arn:aws:${cfg.arnService}::${ACCOUNT}:${cfg.arnResource(row)}`
  }
  return arn(cfg.arnService || serviceKey, region, ACCOUNT, cfg.arnResource ? cfg.arnResource(row) : `${resourceKey}/${row.name}`)
}

function PageHeader({ title, action }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <h1>{title}</h1>
      {action}
    </div>
  )
}

function createDraftFromConfig(cfg) {
  const draft = {}
  cfg.fields
    .filter((f) => f.key !== 'name' && f.key !== 'status')
    .forEach((f) => {
      draft[f.key] = cfg.defaults?.[f.key] ?? ''
    })
  return draft
}

function coerceDraftValue(value, original) {
  if (typeof original === 'number') {
    const n = Number(value)
    return Number.isFinite(n) ? n : original
  }
  if (typeof original === 'boolean') return !!value
  return value
}

export function GenericServiceHome() {
  const { service } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const resources = useAwsStore((s) => s.genericResources?.[service] || {})
  const cfg = SERVICE_CONFIGS[service]

  if (!cfg) {
    return <div className="aws-page"><EmptyState title="Service not found" action={<Button onClick={() => navigate(`${BASE}/console/home`)}>Back to console home</Button>} /></div>
  }

  const cards = Object.entries(cfg.resources).map(([resourceKey, rcfg]) => {
    const rows = (resources[resourceKey] || []).filter((r) => !r.region || r.region === region)
    return { resourceKey, cfg: rcfg, count: rows.length }
  })

  return (
    <div>
      <Breadcrumb items={[{ label: 'AWS', onClick: () => navigate(`${BASE}/console/home`) }, { label: cfg.title }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <PageHeader title={`${cfg.title} Dashboard`} action={<Button variant="primary" icon={Plus} onClick={() => navigate(`${BASE}/${service}/${cfg.primary}`)}>{cfg.resources[cfg.primary]?.createLabel || 'Create resource'}</Button>} />
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <SectionLabel>{cfg.title} resources · {region}</SectionLabel>
          <div className="aws-summary-grid" style={{ marginTop: 8 }}>
            {cards.map((c) => (
              <div key={c.resourceKey} className="aws-kv" style={{ cursor: 'pointer' }} onClick={() => navigate(`${BASE}/${service}/${c.resourceKey}`)}>
                <span className="v" style={{ fontSize: 24, fontWeight: 700, color: 'var(--aws-text-link)' }}>{c.count}</span>
                <span className="k">{c.cfg.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
          <MetricChart title={`${cfg.title} Requests`} unit="" color="#0073bb" base={120} variance={500} />
          <MetricChart title={`${cfg.title} Errors`} unit="" color="#d13212" base={0} variance={6} />
          <MetricChart title={`${cfg.title} Estimated cost (USD)`} unit="" color="#1d8102" base={4} variance={22} />
        </div>
      </div>
    </div>
  )
}

export function GenericResourceList() {
  const { service, resource } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const rows = (useAwsStore((s) => s.genericResources?.[service]?.[resource]) || []).filter((r) => !r.region || r.region === region)
  const createGenericResource = useAwsStore((s) => s.createGenericResource)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const serviceCfg = SERVICE_CONFIGS[service]
  const cfg = getResourceConfig(service, resource)
  const [selected, setSelected] = useState([])
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [name, setName] = useState('')
  const [draft, setDraft] = useState({})
  const [filter, setFilter] = useState('')

  const visible = useMemo(() => {
    if (!filter) return rows
    const q = filter.toLowerCase()
    return rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q))
  }, [rows, filter])

  if (!serviceCfg || !cfg) {
    return <div className="aws-page"><EmptyState title="Resource page not found" action={<Button onClick={() => navigate(`${BASE}/console/home`)}>Back to console home</Button>} /></div>
  }

  const columns = [
    { key: 'name', label: cfg.idLabel || 'Name', render: (r) => <a onClick={() => navigate(`${BASE}/${service}/${resource}/${r.id}`)}>{r.name}</a> },
    { key: 'id', label: 'Resource ID', render: (r) => <IDCopy value={r.id} /> },
    ...cfg.fields.filter((f) => f.key !== 'name').map((f) => ({ key: f.key, label: f.label, render: (r) => fieldValue(r, f) })),
    { key: 'arn', label: 'ARN', sortable: false, render: (r) => <IDCopy value={resourceArn(service, resource, r, region, cfg)} /> },
  ]

  const validationError = !name
    ? ''
    : rows.some((r) => r.name === name)
      ? `${cfg.idLabel || 'Name'} already exists in ${region}.`
      : !/^[A-Za-z0-9._:/+=,@ -]{1,128}$/.test(name)
        ? 'Use 1-128 valid AWS identifier characters.'
        : ''

  const openCreate = () => {
    setName('')
    setDraft(createDraftFromConfig(cfg))
    setCreating(true)
  }

  const submitCreate = () => {
    const resolved = Object.fromEntries(
      Object.entries(draft).map(([key, value]) => [key, coerceDraftValue(value, cfg.defaults?.[key])])
    )
    const created = createGenericResource(service, resource, { name, ...cfg.defaults, ...resolved })
    pushFlash('success', `${cfg.label.replace(/s$/, '')} ${created.name} created`)
    setCreating(false)
    setName('')
    setDraft({})
    navigate(`${BASE}/${service}/${resource}/${created.id}`)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: serviceCfg.title, onClick: () => navigate(`${BASE}/${service}/home`) }, { label: cfg.label }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <PageHeader
          title={`${cfg.label} (${visible.length})`}
          action={(
            <div style={{ display: 'flex', gap: 8 }}>
              <Button disabled={!selected.length} icon={Trash2} onClick={() => {
                setDeleteTarget({ ids: selected, label: `${selected.length} ${cfg.label.toLowerCase()}`, confirmText: String(selected.length) })
              }}>Delete</Button>
              <Button variant="primary" icon={Plus} onClick={openCreate}>{cfg.createLabel}</Button>
            </div>
          )}
        />
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input className="aws-input" style={{ maxWidth: 420 }} value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={`Search ${cfg.label.toLowerCase()}`} />
          <Button onClick={() => setFilter('')}>Clear filters</Button>
        </div>
        <DataTable
          columns={columns}
          rows={visible}
          getRowKey={(r) => r.id}
          selectable
          selected={selected}
          onSelect={setSelected}
          onRowClick={(r) => navigate(`${BASE}/${service}/${resource}/${r.id}`)}
          rowActions={(r) => [
            { label: 'View details', onClick: () => navigate(`${BASE}/${service}/${resource}/${r.id}`) },
            { label: 'Copy resource ID', onClick: () => navigator.clipboard?.writeText(r.id) },
            { label: 'Delete', danger: true, onClick: () => setDeleteTarget({ ids: [r.id], label: r.name, confirmText: r.name }) },
          ]}
          tableId={`${service}:${resource}`}
          emptyTitle={`No ${cfg.label.toLowerCase()} in this Region`}
          emptyBody={`Use ${cfg.createLabel} to add one.`}
        />
      </div>
      {creating && (
        <Modal
          title={cfg.createLabel}
          onClose={() => setCreating(false)}
          footer={(
            <>
              <Button onClick={() => setCreating(false)}>Cancel</Button>
              <Button variant="primary" disabled={!name || !!validationError} onClick={submitCreate}>{cfg.createLabel}</Button>
            </>
          )}
        >
          <div className="aws-card" style={{ marginBottom: 12 }}>
            <SectionLabel>Basic configuration</SectionLabel>
            <label className="aws-label" style={{ marginTop: 10 }}>{cfg.idLabel || 'Name'}</label>
            <input className={`aws-input ${validationError ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder={`my-${resource.replace(/s$/, '')}`} />
            {validationError && <div className="aws-field-error">{validationError}</div>}
            <div className="aws-hint">The resource will be created in {region} and persisted locally.</div>
          </div>
          <div className="aws-card">
            <SectionLabel>Service configuration</SectionLabel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginTop: 10 }}>
              {cfg.fields.filter((f) => f.key !== 'name' && f.key !== 'status').map((f) => (
                <div key={f.key}>
                  <label className="aws-label">{f.label}</label>
                  <input
                    className="aws-input"
                    value={draft[f.key] ?? ''}
                    onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                  />
                </div>
              ))}
              {cfg.fields.filter((f) => f.key !== 'name' && f.key !== 'status').length === 0 && (
                <div className="aws-hint">This resource type uses the AWS defaults for its initial configuration.</div>
              )}
            </div>
          </div>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.label}?`}
          body={`This permanently removes ${deleteTarget.label} from the local ${serviceCfg.title} simulation state in ${region}. This action cannot be undone.`}
          confirmLabel="Delete"
          confirmText={deleteTarget.confirmText}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => {
            deleteTarget.ids.forEach((id) => deleteGenericResource(service, resource, id))
            pushFlash('success', `Deleted ${deleteTarget.label}`)
            setSelected([])
            setDeleteTarget(null)
          }}
        />
      )}
    </div>
  )
}

export function GenericResourceDetail() {
  const { service, resource, id } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const rows = useAwsStore((s) => s.genericResources?.[service]?.[resource] || [])
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const updateGenericResource = useAwsStore((s) => s.updateGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const serviceCfg = SERVICE_CONFIGS[service]
  const cfg = getResourceConfig(service, resource)
  const row = rows.find((r) => r.id === id)
  const [tab, setTab] = useState('overview')

  if (!serviceCfg || !cfg || !row) {
    return <div className="aws-page"><EmptyState title="Resource not found" action={<Button onClick={() => navigate(`${BASE}/${service}/home`)}>Back to service</Button>} /></div>
  }

  const rowStatus = row.status || 'Active'
  const normalizedStatus = String(rowStatus).toLowerCase()
  const canPause = !['disabled', 'stopped', 'inactive'].includes(normalizedStatus)
  const toggleStatus = () => {
    const disabled = canPause
    const next = disabled ? (service === 'rds' ? 'stopped' : 'Disabled') : (service === 'rds' ? 'available' : 'Active')
    updateGenericResource(service, resource, row.id, { status: next, lastModified: new Date().toISOString() })
    pushFlash('success', `${row.name} ${disabled ? 'disabled/stopped' : 'enabled/started'}`)
  }

  const simulateRun = () => {
    const patch = {
      lastRun: new Date().toISOString(),
      status: rowStatus,
      invocations: (row.invocations || row.executions || row.runs || 0) + 1,
    }
    if (service === 'lambda') patch.lastResult = 'Succeeded'
    if (service === 'states') patch.executions = (row.executions || 0) + 1
    if (service === 'glue') patch.runs = (row.runs || 0) + 1
    updateGenericResource(service, resource, row.id, patch)
    pushFlash('success', `Test action completed for ${row.name}`)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: serviceCfg.title, onClick: () => navigate(`${BASE}/${service}/home`) }, { label: cfg.label, onClick: () => navigate(`${BASE}/${service}/${resource}`) }, { label: row.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <PageHeader
          title={row.name}
          action={(
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={simulateRun}>{service === 'lambda' ? 'Test' : service === 'rds' ? 'Reboot' : 'Run action'}</Button>
              <Button onClick={toggleStatus}>{canPause ? 'Disable / stop' : 'Enable / start'}</Button>
              <Button variant="danger" onClick={() => { deleteGenericResource(service, resource, row.id); pushFlash('success', `Deleted ${row.name}`); navigate(`${BASE}/${service}/${resource}`) }}>Delete</Button>
            </div>
          )}
        />
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <div className="aws-summary-grid">
            <div className="aws-kv"><span className="k">Resource ID</span><span className="v"><IDCopy value={row.id} /></span></div>
            <div className="aws-kv"><span className="k">ARN</span><span className="v"><IDCopy value={resourceArn(service, resource, row, region, cfg)} /></span></div>
            <div className="aws-kv"><span className="k">Region</span><span className="v">{row.region || region}</span></div>
            <div className="aws-kv"><span className="k">Status</span><span className="v"><Badge state={statusToBadge(row.status)}>{row.status || 'Active'}</Badge></span></div>
          </div>
        </div>
        <Tabs tabs={[{ key: 'overview', label: 'Overview' }, { key: 'configuration', label: 'Configuration' }, { key: 'monitoring', label: 'Monitoring' }, { key: 'activity', label: 'Activity' }, { key: 'integrations', label: 'Integrations' }, { key: 'tags', label: 'Tags' }]} active={tab} onChange={setTab} />
        <div style={{ marginTop: 16 }}>
          {tab === 'overview' && (
            <div className="aws-card">
              {cfg.fields.map((f) => (
                <div className="aws-kv" style={{ marginBottom: 10 }} key={f.key}>
                  <span className="k">{f.label}</span>
                  <span className="v">{fieldValue(row, f)}</span>
                </div>
              ))}
            </div>
          )}
          {tab === 'configuration' && (
            <div className="aws-card">
              <SectionLabel>Configuration JSON</SectionLabel>
              <pre className="aws-mono" style={{ background: 'var(--aws-page-bg)', padding: 12, overflowX: 'auto', borderRadius: 4 }}>{JSON.stringify(row, null, 2)}</pre>
            </div>
          )}
          {tab === 'activity' && (
            <div className="aws-card">
              <SectionLabel>Recent activity</SectionLabel>
              <DataTable
                columns={[
                  { key: 'time', label: 'Time' },
                  { key: 'event', label: 'Event' },
                  { key: 'status', label: 'Status', render: (r) => <Badge state={r.status}>{r.status}</Badge> },
                  { key: 'source', label: 'Source' },
                ]}
                rows={[
                  { time: row.lastRun ? new Date(row.lastRun).toLocaleString() : 'Just now', event: service === 'lambda' ? 'Test invocation' : 'Describe resource', status: row.lastResult || row.status || 'Succeeded', source: 'FixitLab simulation' },
                  { time: new Date(row.created).toLocaleString(), event: 'Create resource', status: 'Succeeded', source: 'AWS Console' },
                ]}
                getRowKey={(r) => `${r.time}:${r.event}`}
                tableId={`${service}:${resource}:${row.id}:activity`}
              />
            </div>
          )}
          {tab === 'integrations' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <SectionLabel>CLI and SDK integration</SectionLabel>
                <div className="aws-hint" style={{ margin: '8px 0 12px' }}>
                  These commands mirror the shape used by the real AWS CLI and operate against the local simulation where implemented.
                </div>
                <pre className="aws-mono" style={{ background: 'var(--aws-page-bg)', padding: 12, overflowX: 'auto', borderRadius: 4, margin: 0 }}>{`aws ${serviceCfg.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')} list-${resource}
aws ${serviceCfg.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')} describe-${resource.replace(/s$/, '')} --${cfg.idLabel || 'name'} ${row.name}
terraform import ${service}_${resource.replace(/-/g, '_')}.${row.name.replace(/[^A-Za-z0-9_]/g, '_')} ${row.id}`}</pre>
              </div>
              <div className="aws-card">
                <SectionLabel>Related console workflows</SectionLabel>
                <DataTable
                  columns={[
                    { key: 'workflow', label: 'Workflow' },
                    { key: 'purpose', label: 'Purpose' },
                    { key: 'status', label: 'Simulation support', render: (r) => <Badge state={r.status}>{r.status}</Badge> },
                  ]}
                  rows={[
                    { workflow: 'Create / update resource', purpose: 'Exercise resource lifecycle controls from the console', status: 'Supported' },
                    { workflow: 'Monitor metrics and activity', purpose: 'Inspect realistic CloudWatch-style charts and recent events', status: 'Supported' },
                    { workflow: 'Terraform import/apply', purpose: 'Use IaC commands from CloudShell or EC2 SSH against the same AWS store', status: 'Supported' },
                  ]}
                  getRowKey={(r) => r.workflow}
                  tableId={`${service}:${resource}:${row.id}:integrations`}
                />
              </div>
            </div>
          )}
          {tab === 'monitoring' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              <MetricChart title={`${row.name} Requests`} unit="" color="#0073bb" base={80} variance={400} />
              <MetricChart title={`${row.name} Errors`} unit="" color="#d13212" base={0} variance={8} />
              <MetricChart title={`${row.name} Latency (ms)`} unit="ms" color="#9d5025" base={30} variance={120} />
            </div>
          )}
          {tab === 'tags' && (
            <div className="aws-card">
              <DataTable
                columns={[{ key: 'key', label: 'Key' }, { key: 'value', label: 'Value' }]}
                rows={Object.entries(row.tags || { Environment: 'demo', Project: 'fixitlab' }).map(([key, value]) => ({ key, value }))}
                getRowKey={(r) => r.key}
                emptyTitle="No tags"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function BillingDashboard() {
  const costs = [
    { service: 'EC2', cost: 28.5 },
    { service: 'RDS', cost: 12.4 },
    { service: 'S3', cost: 3.1 },
    { service: 'Data Transfer', cost: 2.15 },
    { service: 'CloudWatch', cost: 1.17 },
  ]
  const total = costs.reduce((sum, c) => sum + c.cost, 0)
  return (
    <div className="aws-page">
      <PageHeader title="Billing and Cost Management" />
      <div className="aws-card" style={{ marginBottom: 16 }}>
        <SectionLabel>Month-to-date costs</SectionLabel>
        <div style={{ fontSize: 32, fontWeight: 700 }}>${total.toFixed(2)}</div>
        <div className="aws-hint">Forecasted month-end spend: ${(total * 1.22).toFixed(2)}</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
        <MetricChart title="Daily cost" unit="$" color="#0073bb" base={2} variance={5} />
        <div className="aws-card">
          <SectionLabel>Service breakdown</SectionLabel>
          {costs.map((c) => (
            <div key={c.service} style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
              <span style={{ width: 100 }}>{c.service}</span>
              <div style={{ flex: 1, height: 8, background: 'var(--aws-page-bg)', borderRadius: 4 }}>
                <div style={{ width: `${(c.cost / total) * 100}%`, height: '100%', background: 'var(--aws-orange)', borderRadius: 4 }} />
              </div>
              <strong>${c.cost.toFixed(2)}</strong>
            </div>
          ))}
        </div>
        <div className="aws-card">
          <SectionLabel>Free Tier usage</SectionLabel>
          {[
            ['EC2 instance hours', 720, 750],
            ['S3 storage GB', 4.2, 5],
            ['Lambda requests', 0.18, 1],
          ].map(([label, used, limit]) => (
            <div key={label} style={{ marginTop: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}><span>{label}</span><span>{used}/{limit}</span></div>
              <div style={{ height: 8, background: 'var(--aws-page-bg)', borderRadius: 4 }}>
                <div style={{ width: `${Math.min(100, (used / limit) * 100)}%`, height: '100%', background: used / limit > 0.9 ? 'var(--aws-error)' : used / limit > 0.75 ? 'var(--aws-warning)' : 'var(--aws-success)', borderRadius: 4 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <Button icon={Activity}>Open Cost Explorer</Button>
      </div>
    </div>
  )
}
