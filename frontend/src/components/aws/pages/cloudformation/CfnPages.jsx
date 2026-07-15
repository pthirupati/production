import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { ACCOUNT, useAwsStore, scoped } from '../../store/awsStore'
import { arn } from '../../lib/ids'
import { Badge, Breadcrumb, Button, ConfirmDialog, DataTable, EmptyState, IDCopy, SectionLabel, Tabs } from '../../ui/primitives'
import { BASE } from '../../layout/serviceNav'

const SERVICE = 'cloudformation'
const RESOURCE = 'stacks'

const SAMPLE_TEMPLATE = JSON.stringify({
  AWSTemplateFormatVersion: '2010-09-09',
  Description: 'Sample stack: an S3 bucket and a security group',
  Parameters: {
    Environment: { Type: 'String', Default: 'dev', Description: 'Deployment environment' },
  },
  Resources: {
    AppBucket: { Type: 'AWS::S3::Bucket', Properties: { VersioningConfiguration: { Status: 'Enabled' } } },
    AppSecurityGroup: { Type: 'AWS::EC2::SecurityGroup', Properties: { GroupDescription: 'App SG' } },
    AppTable: { Type: 'AWS::DynamoDB::Table', Properties: { BillingMode: 'PAY_PER_REQUEST' } },
  },
  Outputs: {
    BucketName: { Value: 'app-bucket-abc123', Description: 'Name of the app bucket' },
  },
}, null, 2)

// Map CloudFormation status strings to a known badge state class.
function cfnBadge(status) {
  const s = String(status || '').toUpperCase()
  if (s.endsWith('COMPLETE') && !s.includes('ROLLBACK')) return 'available'
  if (s.endsWith('IN_PROGRESS')) return 'pending'
  if (s.includes('FAILED') || s.includes('ROLLBACK')) return 'failed'
  return 'available'
}

function stackArn(row, region) {
  return arn('cloudformation', region, ACCOUNT, `stack/${row.name}/${row.id}`)
}

export function CfnList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const stacks = scoped(useAwsStore((s) => s.genericResources?.cloudformation?.stacks), region)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [selected, setSelected] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)

  const columns = [
    { key: 'name', label: 'Stack name', render: (r) => <a onClick={() => navigate(`${BASE}/cloudformation/stacks/${r.id}`)}>{r.name}</a> },
    { key: 'status', label: 'Status', render: (r) => <Badge state={cfnBadge(r.status)}>{r.status}</Badge> },
    { key: 'resources', label: 'Resources', render: (r) => r.resources ?? (r.resourceList || []).length },
    { key: 'created', label: 'Created', render: (r) => new Date(r.created).toLocaleString() },
  ]

  return (
    <div>
      <Breadcrumb items={[{ label: 'CloudFormation', onClick: () => navigate(`${BASE}/cloudformation/home`) }, { label: 'Stacks' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1>Stacks ({stacks.length})</h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button disabled={selected.length !== 1} icon={Trash2} onClick={() => setDeleteTarget(stacks.find((s) => s.id === selected[0]))}>Delete</Button>
            <Button variant="primary" icon={Plus} onClick={() => navigate(`${BASE}/cloudformation/stacks/create`)}>Create stack</Button>
          </div>
        </div>
        <DataTable
          columns={columns}
          rows={stacks}
          getRowKey={(r) => r.id}
          selectable
          selected={selected}
          onSelect={setSelected}
          onRowClick={(r) => navigate(`${BASE}/cloudformation/stacks/${r.id}`)}
          rowActions={(r) => [
            { label: 'View details', onClick: () => navigate(`${BASE}/cloudformation/stacks/${r.id}`) },
            { label: 'Copy stack ID', onClick: () => navigator.clipboard?.writeText(r.id) },
            { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
          ]}
          tableId="cloudformation:stacks"
          emptyTitle="No stacks in this Region"
          emptyBody="Create a stack to get started."
        />
      </div>
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.name}?`}
          body={`This permanently removes stack ${deleteTarget.name} from the local CloudFormation simulation. In real AWS, deleting a stack deletes its managed resources.`}
          confirmLabel="Delete"
          confirmText={deleteTarget.name}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteGenericResource(SERVICE, RESOURCE, deleteTarget.id); pushFlash('success', `Deleting stack ${deleteTarget.name}`); setSelected([]); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}

export function CfnCreate() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const stacks = scoped(useAwsStore((s) => s.genericResources?.cloudformation?.stacks), region)
  const createCfnStack = useAwsStore((s) => s.createCfnStack)
  const pushFlash = useAwsStore((s) => s.pushFlash)

  const [name, setName] = useState('')
  const [template, setTemplate] = useState(SAMPLE_TEMPLATE)
  const [params, setParams] = useState('')
  const [templateError, setTemplateError] = useState('')

  const nameError = !name ? '' : !/^[a-zA-Z][a-zA-Z0-9-]{0,127}$/.test(name) ? 'Stack name must start with a letter and contain only letters, numbers, and hyphens.' : stacks.some((s) => s.name === name) ? 'A stack with this name already exists in this Region.' : ''

  // Parse the template's Parameters into editable rows when a valid template is present.
  let parsedParams = []
  try {
    const t = JSON.parse(template)
    parsedParams = Object.entries(t.Parameters || {}).map(([k, def]) => ({ key: k, def: def?.Default ?? '', description: def?.Description || '' }))
  } catch { /* ignore, surfaced on submit */ }

  const canCreate = !!name && !nameError

  const submit = () => {
    let t
    try { t = JSON.parse(template) } catch { setTemplateError('Template must be valid JSON.'); return }
    setTemplateError('')
    const created = createCfnStack(name, t)
    pushFlash('success', `Creating stack ${name}. Resources are provisioning.`)
    navigate(`${BASE}/cloudformation/stacks/${created.id}`)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'CloudFormation', onClick: () => navigate(`${BASE}/cloudformation/home`) }, { label: 'Stacks', onClick: () => navigate(`${BASE}/cloudformation/stacks`) }, { label: 'Create stack' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <h1 style={{ marginBottom: 16 }}>Create stack</h1>
        <div className="aws-card" style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <SectionLabel>Template</SectionLabel>
            <Button onClick={() => setTemplate(SAMPLE_TEMPLATE)}>Use sample template</Button>
          </div>
          <div className="aws-hint" style={{ margin: '6px 0 8px' }}>Paste a JSON CloudFormation template. Resources under <span className="aws-mono">Resources</span> are provisioned and streamed as events.</div>
          <textarea className={`aws-input aws-mono ${templateError ? 'aws-invalid' : ''}`} value={template} onChange={(e) => setTemplate(e.target.value)} spellCheck={false} style={{ minHeight: 300, lineHeight: 1.5, width: '100%', resize: 'vertical' }} />
          {templateError && <div className="aws-field-error">{templateError}</div>}
        </div>
        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Specify stack details</SectionLabel>
          <label className="aws-label" style={{ marginTop: 10 }}>Stack name</label>
          <input className={`aws-input ${nameError ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="my-stack" style={{ maxWidth: 420 }} />
          {nameError && <div className="aws-field-error">{nameError}</div>}
        </div>
        {parsedParams.length > 0 && (
          <div className="aws-card" style={{ marginBottom: 12 }}>
            <SectionLabel>Parameters</SectionLabel>
            <DataTable
              columns={[
                { key: 'key', label: 'Parameter' },
                { key: 'def', label: 'Default' },
                { key: 'description', label: 'Description' },
              ]}
              rows={parsedParams}
              getRowKey={(r) => r.key}
              tableId="cloudformation:create:params"
            />
          </div>
        )}
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <SectionLabel>Parameter overrides (optional)</SectionLabel>
          <div className="aws-hint" style={{ margin: '6px 0 8px' }}>Notes recorded with the stack for reference.</div>
          <textarea className="aws-input aws-mono" value={params} onChange={(e) => setParams(e.target.value)} spellCheck={false} style={{ minHeight: 80, lineHeight: 1.5, width: '100%', resize: 'vertical' }} placeholder="Environment=prod" />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button onClick={() => navigate(`${BASE}/cloudformation/stacks`)}>Cancel</Button>
          <Button variant="primary" disabled={!canCreate} onClick={submit}>Create stack</Button>
        </div>
      </div>
    </div>
  )
}

export function CfnDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const stack = useAwsStore((s) => (s.genericResources?.cloudformation?.stacks || []).find((x) => x.id === id))
  const updateGenericResource = useAwsStore((s) => s.updateGenericResource)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [tab, setTab] = useState('events')
  const [templateDraft, setTemplateDraft] = useState('')
  const [editing, setEditing] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!stack) return <div className="aws-page"><EmptyState title="Stack not found" action={<Button onClick={() => navigate(`${BASE}/cloudformation/stacks`)}>Back to stacks</Button>} /></div>

  // Streamed events: newest first.
  const events = [...(stack.events || [])].sort((a, b) => new Date(b.at) - new Date(a.at))
  let parsedTemplate = {}
  try { parsedTemplate = typeof stack.template === 'string' ? JSON.parse(stack.template) : (stack.template || {}) } catch { parsedTemplate = {} }
  const parameters = Object.entries(parsedTemplate.Parameters || {}).map(([k, def]) => ({ key: k, value: def?.Default ?? '', type: def?.Type || 'String' }))

  return (
    <div>
      <Breadcrumb items={[{ label: 'CloudFormation', onClick: () => navigate(`${BASE}/cloudformation/home`) }, { label: 'Stacks', onClick: () => navigate(`${BASE}/cloudformation/stacks`) }, { label: stack.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{stack.name} <Badge state={cfnBadge(stack.status)}>{stack.status}</Badge></h1>
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>Delete</Button>
        </div>
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <div className="aws-summary-grid">
            <div className="aws-kv"><span className="k">Stack ID</span><span className="v"><IDCopy value={stack.id} /></span></div>
            <div className="aws-kv"><span className="k">ARN</span><span className="v"><IDCopy value={stackArn(stack, region)} /></span></div>
            <div className="aws-kv"><span className="k">Created</span><span className="v">{new Date(stack.created).toLocaleString()}</span></div>
            <div className="aws-kv"><span className="k">Region</span><span className="v">{stack.region || region}</span></div>
          </div>
        </div>

        <Tabs tabs={[
          { key: 'events', label: 'Events' },
          { key: 'resources', label: 'Resources' },
          { key: 'outputs', label: 'Outputs' },
          { key: 'parameters', label: 'Parameters' },
          { key: 'template', label: 'Template' },
        ]} active={tab} onChange={setTab} />

        <div style={{ marginTop: 16 }}>
          {tab === 'events' && (
            <div className="aws-card">
              <SectionLabel>Events</SectionLabel>
              <DataTable
                columns={[
                  { key: 'at', label: 'Timestamp', render: (r) => new Date(r.at).toLocaleString() },
                  { key: 'logicalId', label: 'Logical ID' },
                  { key: 'type', label: 'Type' },
                  { key: 'status', label: 'Status', render: (r) => <Badge state={cfnBadge(r.status)}>{r.status}</Badge> },
                  { key: 'reason', label: 'Status reason', render: (r) => r.reason || '—' },
                ]}
                rows={events}
                getRowKey={(r) => `${r.at}:${r.logicalId}:${r.status}`}
                tableId={`cloudformation:events:${stack.id}`}
                emptyTitle="No events"
              />
            </div>
          )}
          {tab === 'resources' && (
            <div className="aws-card">
              <SectionLabel>Resources</SectionLabel>
              <DataTable
                columns={[
                  { key: 'logicalId', label: 'Logical ID' },
                  { key: 'physicalId', label: 'Physical ID', render: (r) => <IDCopy value={r.physicalId} /> },
                  { key: 'type', label: 'Type' },
                  { key: 'status', label: 'Status', render: (r) => <Badge state={cfnBadge(r.status)}>{r.status}</Badge> },
                ]}
                rows={stack.resourceList || []}
                getRowKey={(r) => r.logicalId}
                tableId={`cloudformation:resources:${stack.id}`}
                emptyTitle="No resources"
                emptyBody="This template did not declare any resources."
              />
            </div>
          )}
          {tab === 'outputs' && (
            <div className="aws-card">
              <SectionLabel>Outputs</SectionLabel>
              <DataTable
                columns={[
                  { key: 'key', label: 'Key' },
                  { key: 'value', label: 'Value', render: (r) => <IDCopy value={r.value} /> },
                  { key: 'description', label: 'Description', render: (r) => r.description || '—' },
                ]}
                rows={stack.outputs || []}
                getRowKey={(r) => r.key}
                tableId={`cloudformation:outputs:${stack.id}`}
                emptyTitle="No outputs"
              />
            </div>
          )}
          {tab === 'parameters' && (
            <div className="aws-card">
              <SectionLabel>Parameters</SectionLabel>
              <DataTable
                columns={[
                  { key: 'key', label: 'Key' },
                  { key: 'value', label: 'Value', render: (r) => (r.value === '' ? '—' : String(r.value)) },
                  { key: 'type', label: 'Type' },
                ]}
                rows={parameters}
                getRowKey={(r) => r.key}
                tableId={`cloudformation:parameters:${stack.id}`}
                emptyTitle="No parameters"
              />
            </div>
          )}
          {tab === 'template' && (
            <div className="aws-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <SectionLabel>Template</SectionLabel>
                {editing ? (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Button onClick={() => setEditing(false)}>Cancel</Button>
                    <Button variant="primary" onClick={() => { try { JSON.parse(templateDraft); updateGenericResource(SERVICE, RESOURCE, stack.id, { template: templateDraft }); pushFlash('success', 'Template updated'); setEditing(false) } catch { pushFlash('error', 'Template must be valid JSON') } }}>Save</Button>
                  </div>
                ) : (
                  <Button onClick={() => { setTemplateDraft(typeof stack.template === 'string' ? stack.template : JSON.stringify(stack.template || {}, null, 2)); setEditing(true) }}>Edit template</Button>
                )}
              </div>
              {editing ? (
                <textarea className="aws-input aws-mono" value={templateDraft} onChange={(e) => setTemplateDraft(e.target.value)} spellCheck={false} style={{ minHeight: 360, lineHeight: 1.5, width: '100%', resize: 'vertical' }} />
              ) : (
                <pre className="aws-mono" style={{ background: 'var(--aws-page-bg)', padding: 12, borderRadius: 4, overflowX: 'auto', margin: 0 }}>{typeof stack.template === 'string' ? stack.template : JSON.stringify(stack.template || {}, null, 2)}</pre>
              )}
            </div>
          )}
        </div>
      </div>
      {deleteOpen && (
        <ConfirmDialog
          title={`Delete ${stack.name}?`}
          body={`This permanently removes stack ${stack.name} from the local CloudFormation simulation.`}
          confirmLabel="Delete"
          confirmText={stack.name}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => { deleteGenericResource(SERVICE, RESOURCE, stack.id); pushFlash('success', `Deleting stack ${stack.name}`); navigate(`${BASE}/cloudformation/stacks`) }}
        />
      )}
    </div>
  )
}
