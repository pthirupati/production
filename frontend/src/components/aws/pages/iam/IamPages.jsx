import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAwsStore } from '../../store/awsStore'
import { Badge, Button, ConfirmDialog, DataTable, IDCopy, Modal, SectionLabel } from '../../ui/primitives'
import { ACCOUNT } from '../../store/awsStore'
import { BASE } from '../../layout/serviceNav'

const DEFAULT_POLICY = {
  Version: '2012-10-17',
  Statement: [
    {
      Effect: 'Allow',
      Action: ['ec2:Describe*', 's3:ListBucket'],
      Resource: '*',
    },
  ],
}

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

export function IamDashboard() {
  const navigate = useNavigate()
  const users = useAwsStore((s) => s.iamUsers)
  const groups = useAwsStore((s) => s.iamGroups)
  const roles = useAwsStore((s) => s.iamRoles)
  const policies = useAwsStore((s) => s.iamPolicies)
  const cards = [
    ['Users', users.length, `${BASE}/iam/users`],
    ['User groups', groups.length, `${BASE}/iam/groups`],
    ['Roles', roles.length, `${BASE}/iam/roles`],
    ['Policies', policies.length, `${BASE}/iam/policies`],
  ]
  return (
    <Page title="IAM Dashboard">
      <div className="aws-card" style={{ marginBottom: 16 }}>
        <SectionLabel>IAM resources</SectionLabel>
        <div className="aws-summary-grid" style={{ marginTop: 8 }}>
          {cards.map(([label, n, path]) => (
            <div key={label} className="aws-kv" style={{ cursor: 'pointer' }} onClick={() => navigate(path)}>
              <span className="v" style={{ fontSize: 24, fontWeight: 700, color: 'var(--aws-text-link)' }}>{n}</span>
              <span className="k">{label}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="aws-card">
        <SectionLabel>Sign-in details</SectionLabel>
        <div className="aws-kv" style={{ marginTop: 8 }}><span className="k">Account ID</span><IDCopy value={ACCOUNT} mono /></div>
      </div>
    </Page>
  )
}

export function UserList() {
  const navigate = useNavigate()
  const users = useAwsStore((s) => s.iamUsers)
  const createIamUser = useAwsStore((s) => s.createIamUser)
  const deleteIamUser = useAwsStore((s) => s.deleteIamUser)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [consoleAccess, setConsoleAccess] = useState(true)
  const [selected, setSelected] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)
  const error = name && !/^[\w+=,.@-]{1,64}$/.test(name) ? 'User name may contain alphanumeric and + = , . @ - _ characters (max 64).' : (users.some((u) => u.name === name) ? 'User already exists.' : '')

  const columns = [
    { key: 'name', label: 'User name', render: (r) => <a onClick={() => navigate(`${BASE}/iam/users/${r.name}`)}>{r.name}</a> },
    { key: 'groups', label: 'Groups', render: (r) => r.groups.join(', ') || 'None' },
    { key: 'consoleAccess', label: 'Console access', render: (r) => (r.consoleAccess ? 'Enabled' : 'Disabled') },
    { key: 'keys', label: 'Access keys', render: (r) => r.accessKeys.length },
    { key: 'created', label: 'Created', render: (r) => new Date(r.created).toLocaleDateString() },
  ]
  return (
    <Page title={`Users (${users.length})`} action={
      <div style={{ display: 'flex', gap: 8 }}>
        <Button disabled={!selected.length} onClick={() => setDeleteTarget([...selected])}>Delete</Button>
        <Button variant="primary" onClick={() => setCreating(true)}>Create user</Button>
      </div>
    }>
      <DataTable
        columns={columns}
        rows={users}
        getRowKey={(r) => r.name}
        selectable
        selected={selected}
        onSelect={setSelected}
        onRowClick={(r) => navigate(`${BASE}/iam/users/${r.name}`)}
        rowActions={(r) => [
          { label: 'View user', onClick: () => navigate(`${BASE}/iam/users/${r.name}`) },
          { label: 'Copy user ARN', onClick: () => navigator.clipboard?.writeText(`arn:aws:iam::${ACCOUNT}:user/${r.name}`) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget([r.name]) },
        ]}
        tableId="iam:users"
      />
      {creating && (
        <Modal title="Create IAM user" onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!name || !!error} onClick={() => { createIamUser({ name, consoleAccess, policies: [] }); pushFlash('success', `Created user ${name}`); setCreating(false); setName('') }}>Create user</Button></>}>
          <label className="aws-label">User name</label>
          <input className={`aws-input ${error ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} />
          {error && <div className="aws-field-error">{error}</div>}
          <label style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center' }}><input type="checkbox" checked={consoleAccess} onChange={(e) => setConsoleAccess(e.target.checked)} /> Provide user access to the AWS Management Console</label>
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.length} IAM user${deleteTarget.length === 1 ? '' : 's'}?`}
          body="Deleting an IAM user removes its local console access, programmatic credentials, and group membership."
          confirmLabel="Delete"
          confirmText={deleteTarget.length === 1 ? deleteTarget[0] : String(deleteTarget.length)}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteTarget.forEach((n) => deleteIamUser(n)); pushFlash('success', `Deleted ${deleteTarget.length} user(s)`); setSelected([]); setDeleteTarget(null) }}
        />
      )}
    </Page>
  )
}

export function GroupList() {
  const groups = useAwsStore((s) => s.iamGroups)
  const columns = [
    { key: 'name', label: 'Group name' },
    { key: 'users', label: 'Users', render: (r) => r.users.length },
    { key: 'policies', label: 'Attached policies', render: (r) => r.policies.join(', ') },
    { key: 'created', label: 'Created', render: (r) => new Date(r.created).toLocaleDateString() },
  ]
  return <Page title={`User groups (${groups.length})`}><DataTable columns={columns} rows={groups} getRowKey={(r) => r.name} /></Page>
}

export function RoleList() {
  const roles = useAwsStore((s) => s.iamRoles)
  const columns = [
    { key: 'name', label: 'Role name' },
    { key: 'trustedEntity', label: 'Trusted entities' },
    { key: 'policies', label: 'Attached policies', render: (r) => r.policies.join(', ') },
    { key: 'created', label: 'Created', render: (r) => new Date(r.created).toLocaleDateString() },
  ]
  return <Page title={`Roles (${roles.length})`}><DataTable columns={columns} rows={roles} getRowKey={(r) => r.name} /></Page>
}

export function PolicyList() {
  const policies = useAwsStore((s) => s.iamPolicies)
  const createIamPolicy = useAwsStore((s) => s.createIamPolicy)
  const updateIamPolicy = useAwsStore((s) => s.updateIamPolicy)
  const deleteIamPolicy = useAwsStore((s) => s.deleteIamPolicy)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [selected, setSelected] = useState([])
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [documentText, setDocumentText] = useState(JSON.stringify(DEFAULT_POLICY, null, 2))

  const columns = [
    { key: 'name', label: 'Policy name', render: (r) => <a onClick={() => { setEditing(r); setDocumentText(JSON.stringify(r.document || DEFAULT_POLICY, null, 2)); setDescription(r.description || '') }}>{r.name}</a> },
    { key: 'type', label: 'Type' },
    { key: 'attached', label: 'Attached entities', render: (r) => <Badge state={r.attached ? 'running' : 'stopped'}>{r.attached}</Badge> },
    { key: 'description', label: 'Description' },
    { key: 'arn', label: 'ARN', render: (r) => <IDCopy value={`arn:aws:iam::${ACCOUNT}:policy/${r.name}`} /> },
  ]
  const error = name && !/^[\w+=,.@-]{1,128}$/.test(name)
    ? 'Policy name may contain alphanumeric and + = , . @ - _ characters (max 128).'
    : policies.some((p) => p.name === name)
      ? 'Policy already exists.'
      : ''

  const parseDocument = () => {
    const parsed = JSON.parse(documentText)
    if (!parsed.Version || !parsed.Statement) throw new Error('Policy must include Version and Statement')
    return parsed
  }

  return (
    <Page title={`Policies (${policies.length})`} action={
      <div style={{ display: 'flex', gap: 8 }}>
        <Button disabled={selected.length !== 1} onClick={() => setDeleteTarget(selected[0])}>Delete</Button>
        <Button variant="primary" onClick={() => { setCreating(true); setName(''); setDescription(''); setDocumentText(JSON.stringify(DEFAULT_POLICY, null, 2)) }}>Create policy</Button>
      </div>
    }>
      <div className="aws-card" style={{ marginBottom: 12 }}>
        <SectionLabel>IAM policy authoring</SectionLabel>
        <div className="aws-hint" style={{ marginTop: 8 }}>
          Create customer-managed policies, inspect ARNs, and edit JSON documents with AWS-style validation. Attach counts are simulated for users, groups, and roles.
        </div>
      </div>
      <DataTable
        columns={columns}
        rows={policies}
        getRowKey={(r) => r.name}
        selectable
        selected={selected}
        onSelect={setSelected}
        onRowClick={(r) => { setEditing(r); setDocumentText(JSON.stringify(r.document || DEFAULT_POLICY, null, 2)); setDescription(r.description || '') }}
        rowActions={(r) => [
          { label: 'Edit JSON policy', onClick: () => { setEditing(r); setDocumentText(JSON.stringify(r.document || DEFAULT_POLICY, null, 2)); setDescription(r.description || '') } },
          { label: 'Copy policy ARN', onClick: () => navigator.clipboard?.writeText(`arn:aws:iam::${ACCOUNT}:policy/${r.name}`) },
          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r.name) },
        ]}
        tableId="iam:policies"
      />
      {creating && (
        <Modal
          title="Create policy"
          width={860}
          onClose={() => setCreating(false)}
          footer={<><Button onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" disabled={!name || !!error} onClick={() => { try { const doc = parseDocument(); createIamPolicy({ name, description, document: doc }); pushFlash('success', `Created policy ${name}`); setCreating(false) } catch (e) { pushFlash('error', e.message || 'Policy document must be valid JSON') } }}>Create policy</Button></>}
        >
          <label className="aws-label">Policy name</label>
          <input className={`aws-input ${error ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="MyLeastPrivilegePolicy" />
          {error && <div className="aws-field-error">{error}</div>}
          <label className="aws-label" style={{ marginTop: 12 }}>Description</label>
          <input className="aws-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe what this policy allows" />
          <label className="aws-label" style={{ marginTop: 12 }}>Policy document</label>
          <textarea className="aws-input aws-mono" value={documentText} onChange={(e) => setDocumentText(e.target.value)} style={{ minHeight: 300, lineHeight: 1.5 }} />
        </Modal>
      )}
      {editing && (
        <Modal
          title={`Edit policy ${editing.name}`}
          width={860}
          onClose={() => setEditing(null)}
          footer={<><Button onClick={() => setEditing(null)}>Cancel</Button><Button variant="primary" onClick={() => { try { const doc = parseDocument(); updateIamPolicy(editing.name, { description, document: doc }); pushFlash('success', `Updated policy ${editing.name}`); setEditing(null) } catch (e) { pushFlash('error', e.message || 'Policy document must be valid JSON') } }}>Save changes</Button></>}
        >
          <div className="aws-kv" style={{ marginBottom: 12 }}><span className="k">Policy ARN</span><IDCopy value={`arn:aws:iam::${ACCOUNT}:policy/${editing.name}`} /></div>
          <label className="aws-label">Description</label>
          <input className="aws-input" value={description} onChange={(e) => setDescription(e.target.value)} />
          <label className="aws-label" style={{ marginTop: 12 }}>Policy document</label>
          <textarea className="aws-input aws-mono" value={documentText} onChange={(e) => setDocumentText(e.target.value)} style={{ minHeight: 340, lineHeight: 1.5 }} />
        </Modal>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete policy ${deleteTarget}?`}
          body="Deleting a customer managed policy removes it from this environment. AWS does not allow deleting AWS managed policies; this table contains customer-managed policies."
          confirmLabel="Delete policy"
          confirmText={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteIamPolicy(deleteTarget); pushFlash('success', `Deleted policy ${deleteTarget}`); setSelected([]); setDeleteTarget(null) }}
        />
      )}
    </Page>
  )
}
