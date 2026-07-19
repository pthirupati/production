import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Play, Plus, Save, Trash2, Zap } from 'lucide-react'
import { ACCOUNT, useAwsStore, scoped } from '../../store/awsStore'
import { arn } from '../../lib/ids'
import { Badge, Breadcrumb, Button, ConfirmDialog, DataTable, EmptyState, IDCopy, SectionLabel, Tabs } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'
import { BASE } from '../../layout/serviceNav'
import { getResourceConfig } from '../generic/serviceConfigs'

const SERVICE = 'lambda'
const RESOURCE = 'functions'

const RUNTIMES = ['Python 3.12', 'Python 3.11', 'Node.js 20.x', 'Node.js 18.x', 'Java 21', 'Go 1.x', 'Ruby 3.3', '.NET 8']
const ARCHS = ['x86_64', 'arm64']

// Seed a runtime-appropriate handler stub for the Code editor.
function seedCode(runtime) {
  const r = String(runtime || '')
  if (r.startsWith('Node')) return 'export const handler = async (event) => {\n  return { statusCode: 200, body: JSON.stringify("Hello from Lambda!") };\n};'
  if (r.startsWith('Go')) return 'package main\n\nimport "github.com/aws/aws-lambda-go/lambda"\n\nfunc handler() (string, error) {\n  return "Hello from Lambda!", nil\n}\n\nfunc main() { lambda.Start(handler) }'
  if (r.startsWith('Ruby')) return 'def lambda_handler(event:, context:)\n  { statusCode: 200, body: "Hello from Lambda!" }\nend'
  if (r.startsWith('Java')) return 'public class Handler implements RequestHandler<Object, String> {\n  public String handleRequest(Object event, Context context) {\n    return "Hello from Lambda!";\n  }\n}'
  return 'def lambda_handler(event, context):\n    return {"statusCode": 200, "body": "Hello from Lambda!"}'
}

function lambdaBadge(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'active') return 'available'
  if (s === 'pending') return 'pending'
  if (s === 'inactive') return 'stopped'
  return 'available'
}

function fnArn(row, region) {
  return arn('lambda', region, ACCOUNT, `function:${row.name}`)
}

export function LambdaList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const functions = scoped(useAwsStore((s) => s.genericResources?.lambda?.functions), region)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [selected, setSelected] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)

  const columns = [
    { key: 'name', label: 'Function name', render: (r) => <a onClick={() => navigate(`${BASE}/lambda/functions/${r.id}`)}>{r.name}</a> },
    { key: 'status', label: 'State', render: (r) => <Badge state={lambdaBadge(r.status)}>{r.status}</Badge> },
    { key: 'runtime', label: 'Runtime' },
    { key: 'memory', label: 'Memory', render: (r) => `${r.memory} MB` },
    { key: 'timeout', label: 'Timeout', render: (r) => `${r.timeout} sec` },
    { key: 'lastModified', label: 'Last modified', render: (r) => (r.lastModified ? new Date(r.lastModified).toLocaleString() : new Date(r.created).toLocaleString()) },
  ]

  return (
    <div>
      <Breadcrumb items={[{ label: 'Lambda', onClick: () => navigate(`${BASE}/lambda/home`) }, { label: 'Functions' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1>Functions ({functions.length})</h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button disabled={selected.length !== 1} icon={Trash2} onClick={() => setDeleteTarget(functions.find((f) => f.id === selected[0]))}>Delete</Button>
            <Button variant="primary" icon={Plus} onClick={() => navigate(`${BASE}/lambda/functions/create`)}>Create function</Button>
          </div>
        </div>
        <DataTable
          columns={columns}
          rows={functions}
          getRowKey={(r) => r.id}
          selectable
          selected={selected}
          onSelect={setSelected}
          onRowClick={(r) => navigate(`${BASE}/lambda/functions/${r.id}`)}
          rowActions={(r) => [
            { label: 'View details', onClick: () => navigate(`${BASE}/lambda/functions/${r.id}`) },
            { label: 'Copy ARN', onClick: () => navigator.clipboard?.writeText(fnArn(r, region)) },
            { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
          ]}
          tableId="lambda:functions"
          emptyTitle="No functions in this Region"
          emptyBody="Create a function to get started."
        />
      </div>
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.name}?`}
          body={`This permanently removes function ${deleteTarget.name} from this Lambda environment.`}
          confirmLabel="Delete"
          confirmText={deleteTarget.name}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteGenericResource(SERVICE, RESOURCE, deleteTarget.id); pushFlash('success', `Deleting function ${deleteTarget.name}`); setSelected([]); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}

export function LambdaCreate() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const functions = scoped(useAwsStore((s) => s.genericResources?.lambda?.functions), region)
  const roles = useAwsStore((s) => s.iamRoles) || []
  const createGenericResource = useAwsStore((s) => s.createGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)

  const [name, setName] = useState('')
  const [runtime, setRuntime] = useState('Python 3.12')
  const [arch, setArch] = useState('x86_64')
  const [execRole, setExecRole] = useState(roles.find((r) => r.trustedEntity === 'lambda.amazonaws.com')?.name || roles[0]?.name || '')

  const nameError = !name ? '' : !/^[a-zA-Z0-9-_]{1,64}$/.test(name) ? 'Function name must be 1-64 chars: letters, numbers, hyphens, underscores.' : functions.some((f) => f.name === name) ? 'A function with this name already exists in this Region.' : ''
  const canCreate = !!name && !nameError

  const submit = () => {
    const created = createGenericResource(SERVICE, RESOURCE, {
      name, runtime, arch, execRole,
      code: seedCode(runtime),
      handler: runtime.startsWith('Node') ? 'index.handler' : 'lambda_function.lambda_handler',
    })
    if (!created || created.ok === false) return
    pushFlash('success', `Creating function ${name}`)
    navigate(`${BASE}/lambda/functions/${created.id}`)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'Lambda', onClick: () => navigate(`${BASE}/lambda/home`) }, { label: 'Functions', onClick: () => navigate(`${BASE}/lambda/functions`) }, { label: 'Create function' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <h1 style={{ marginBottom: 16 }}>Create function</h1>
        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Author from scratch</SectionLabel>
          <div className="aws-hint" style={{ marginTop: 6 }}>Start with a simple Hello World example seeded for your selected runtime.</div>
          <label className="aws-label" style={{ marginTop: 12 }}>Function name</label>
          <input className={`aws-input ${nameError ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="my-function" style={{ maxWidth: 420 }} />
          {nameError && <div className="aws-field-error">{nameError}</div>}
        </div>
        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Runtime settings</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
            <div>
              <label className="aws-label">Runtime</label>
              <select className="aws-input" value={runtime} onChange={(e) => setRuntime(e.target.value)}>
                {RUNTIMES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="aws-label">Architecture</label>
              <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                {ARCHS.map((a) => (
                  <label key={a} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <input type="radio" name="arch" checked={arch === a} onChange={() => setArch(a)} /> {a}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <SectionLabel>Permissions</SectionLabel>
          <label className="aws-label" style={{ marginTop: 10 }}>Execution role</label>
          <select className="aws-input" value={execRole} onChange={(e) => setExecRole(e.target.value)} style={{ maxWidth: 420 }}>
            {roles.length === 0 && <option value="">(no IAM roles)</option>}
            {roles.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
          </select>
          <div className="aws-hint">Lambda assumes this role when your function runs.</div>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button onClick={() => navigate(`${BASE}/lambda/functions`)}>Cancel</Button>
          <Button variant="primary" disabled={!canCreate} onClick={submit}>Create function</Button>
        </div>
      </div>
    </div>
  )
}

export function LambdaDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const fn = useAwsStore((s) => (s.genericResources?.lambda?.functions || []).find((f) => f.id === id))
  const invokeLambdaFn = useAwsStore((s) => s.invokeLambdaFn)
  const setLambdaCode = useAwsStore((s) => s.setLambdaCode)
  const setLambdaEnv = useAwsStore((s) => s.setLambdaEnv)
  const updateGenericResource = useAwsStore((s) => s.updateGenericResource)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const cfg = getResourceConfig(SERVICE, RESOURCE)
  const [tab, setTab] = useState('code')
  const [codeDraft, setCodeDraft] = useState(fn?.code || '')
  const [payload, setPayload] = useState('{\n  "key": "value"\n}')
  const [result, setResult] = useState(null)
  const [payloadError, setPayloadError] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [envKey, setEnvKey] = useState('')
  const [envVal, setEnvVal] = useState('')

  if (!fn) return <div className="aws-page"><EmptyState title="Function not found" action={<Button onClick={() => navigate(`${BASE}/lambda/functions`)}>Back to functions</Button>} /></div>

  const invoke = () => {
    let parsed
    try { parsed = JSON.parse(payload) } catch { setPayloadError('Event payload must be valid JSON.'); return }
    setPayloadError('')
    const res = invokeLambdaFn(fn.id, parsed)
    setResult(res)
  }

  const env = fn.env || {}

  return (
    <div>
      <Breadcrumb items={[{ label: 'Lambda', onClick: () => navigate(`${BASE}/lambda/home`) }, { label: 'Functions', onClick: () => navigate(`${BASE}/lambda/functions`) }, { label: fn.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{fn.name} <Badge state={lambdaBadge(fn.status)}>{fn.status}</Badge></h1>
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>Delete</Button>
        </div>
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <div className="aws-summary-grid">
            <div className="aws-kv"><span className="k">Function ARN</span><span className="v"><IDCopy value={fnArn(fn, region)} /></span></div>
            <div className="aws-kv"><span className="k">Runtime</span><span className="v">{fn.runtime}</span></div>
            <div className="aws-kv"><span className="k">Memory</span><span className="v">{fn.memory} MB</span></div>
            <div className="aws-kv"><span className="k">Timeout</span><span className="v">{fn.timeout} sec</span></div>
          </div>
        </div>

        <Tabs tabs={[
          { key: 'code', label: 'Code' },
          { key: 'test', label: 'Test' },
          { key: 'monitor', label: 'Monitoring' },
          { key: 'configuration', label: 'Configuration' },
          { key: 'triggers', label: 'Triggers' },
        ]} active={tab} onChange={setTab} />

        <div style={{ marginTop: 16 }}>
          {tab === 'code' && (
            <div className="aws-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <SectionLabel>Code source</SectionLabel>
                <Button icon={Save} variant="primary" onClick={() => { setLambdaCode(fn.id, codeDraft); updateGenericResource(SERVICE, RESOURCE, fn.id, { lastModified: new Date().toISOString() }); pushFlash('success', 'Function code deployed') }}>Deploy</Button>
              </div>
              <textarea className="aws-input aws-mono" value={codeDraft} onChange={(e) => setCodeDraft(e.target.value)} spellCheck={false} style={{ minHeight: 360, lineHeight: 1.5, width: '100%', resize: 'vertical' }} />
            </div>
          )}
          {tab === 'test' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <SectionLabel>Event JSON</SectionLabel>
                  <Button icon={Play} variant="primary" onClick={invoke}>Test</Button>
                </div>
                <textarea className={`aws-input aws-mono ${payloadError ? 'aws-invalid' : ''}`} value={payload} onChange={(e) => setPayload(e.target.value)} spellCheck={false} style={{ minHeight: 160, lineHeight: 1.5, width: '100%', resize: 'vertical' }} />
                {payloadError && <div className="aws-field-error">{payloadError}</div>}
              </div>
              {result && (
                <div className="aws-card">
                  <SectionLabel>Execution result</SectionLabel>
                  <div className="aws-summary-grid" style={{ marginTop: 8 }}>
                    <div className="aws-kv"><span className="k">Status code</span><span className="v"><Badge state={result.statusCode === 200 ? 'available' : 'failed'}>{result.statusCode}</Badge></span></div>
                    <div className="aws-kv"><span className="k">Duration</span><span className="v">{result.durationMs} ms</span></div>
                    <div className="aws-kv"><span className="k">Billed duration</span><span className="v">{result.billedMs} ms</span></div>
                    <div className="aws-kv"><span className="k">Memory used</span><span className="v">{result.memoryUsed} MB</span></div>
                  </div>
                  <pre className="aws-mono" style={{ background: 'var(--aws-page-bg)', padding: 12, borderRadius: 4, overflowX: 'auto', marginTop: 10 }}>{JSON.stringify(result.body, null, 2)}</pre>
                </div>
              )}
              <div className="aws-card">
                <SectionLabel>Recent invocations</SectionLabel>
                <DataTable
                  columns={[
                    { key: 'at', label: 'Time', render: (r) => new Date(r.at).toLocaleString() },
                    { key: 'statusCode', label: 'Status', render: (r) => <Badge state={r.statusCode === 200 ? 'available' : 'failed'}>{r.statusCode}</Badge> },
                    { key: 'durationMs', label: 'Duration', render: (r) => `${r.durationMs} ms` },
                    { key: 'billedMs', label: 'Billed', render: (r) => `${r.billedMs} ms` },
                    { key: 'memoryUsed', label: 'Memory', render: (r) => `${r.memoryUsed} MB` },
                  ]}
                  rows={fn.invocationHistory || []}
                  getRowKey={(r) => r.at}
                  tableId={`lambda:invocations:${fn.id}`}
                  emptyTitle="No invocations yet"
                  emptyBody="Run a test to record an invocation."
                />
              </div>
            </div>
          )}
          {tab === 'monitor' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {(cfg.metrics || []).map((m) => (
                <MetricChart key={m.title} title={m.title} unit={m.unit} color={m.color} base={m.base} variance={m.variance} />
              ))}
            </div>
          )}
          {tab === 'configuration' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <SectionLabel>General configuration</SectionLabel>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginTop: 10 }}>
                  <div>
                    <label className="aws-label">Runtime</label>
                    <select className="aws-input" value={fn.runtime} onChange={(e) => updateGenericResource(SERVICE, RESOURCE, fn.id, { runtime: e.target.value, lastModified: new Date().toISOString() })}>
                      {RUNTIMES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="aws-label">Handler</label>
                    <input className="aws-input" value={fn.handler || ''} onChange={(e) => updateGenericResource(SERVICE, RESOURCE, fn.id, { handler: e.target.value })} />
                  </div>
                  <div>
                    <label className="aws-label">Memory (MB)</label>
                    <input type="number" min={128} max={10240} className="aws-input" value={fn.memory} onChange={(e) => updateGenericResource(SERVICE, RESOURCE, fn.id, { memory: Math.max(128, Math.min(10240, Number(e.target.value))) })} />
                  </div>
                  <div>
                    <label className="aws-label">Timeout (sec)</label>
                    <input type="number" min={1} max={900} className="aws-input" value={fn.timeout} onChange={(e) => updateGenericResource(SERVICE, RESOURCE, fn.id, { timeout: Math.max(1, Math.min(900, Number(e.target.value))) })} />
                  </div>
                </div>
              </div>
              <div className="aws-card">
                <SectionLabel>Environment variables</SectionLabel>
                <DataTable
                  columns={[
                    { key: 'key', label: 'Key' },
                    { key: 'value', label: 'Value' },
                    { key: 'actions', label: '', sortable: false, render: (r) => <Button icon={Trash2} onClick={() => { const next = { ...env }; delete next[r.key]; setLambdaEnv(fn.id, next) }}>Remove</Button> },
                  ]}
                  rows={Object.entries(env).map(([key, value]) => ({ key, value }))}
                  getRowKey={(r) => r.key}
                  tableId={`lambda:env:${fn.id}`}
                  emptyTitle="No environment variables"
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'flex-end' }}>
                  <div><label className="aws-label">Key</label><input className="aws-input" value={envKey} onChange={(e) => setEnvKey(e.target.value)} /></div>
                  <div><label className="aws-label">Value</label><input className="aws-input" value={envVal} onChange={(e) => setEnvVal(e.target.value)} /></div>
                  <Button icon={Plus} disabled={!envKey} onClick={() => { setLambdaEnv(fn.id, { ...env, [envKey]: envVal }); setEnvKey(''); setEnvVal(''); pushFlash('success', 'Environment variable saved') }}>Add</Button>
                </div>
              </div>
            </div>
          )}
          {tab === 'triggers' && (
            <div className="aws-card">
              <SectionLabel>Triggers</SectionLabel>
              <DataTable
                columns={[
                  { key: 'type', label: 'Type', render: (r) => <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Zap size={14} style={{ color: 'var(--aws-orange)' }} />{r.type}</span> },
                  { key: 'detail', label: 'Configuration' },
                ]}
                rows={fn.triggers || []}
                getRowKey={(r) => `${r.type}:${r.detail}`}
                tableId={`lambda:triggers:${fn.id}`}
                emptyTitle="No triggers configured"
                emptyBody="Add a trigger such as API Gateway, S3, or EventBridge to invoke this function."
              />
            </div>
          )}
        </div>
      </div>
      {deleteOpen && (
        <ConfirmDialog
          title={`Delete ${fn.name}?`}
          body={`This permanently removes function ${fn.name} from this Lambda environment.`}
          confirmLabel="Delete"
          confirmText={fn.name}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => { deleteGenericResource(SERVICE, RESOURCE, fn.id); pushFlash('success', `Deleting function ${fn.name}`); navigate(`${BASE}/lambda/functions`) }}
        />
      )}
    </div>
  )
}
