import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { useAwsStore, scoped } from '../../store/awsStore'
import { Button, Badge, DataTable, IDCopy, SearchBar } from '../../ui/primitives'
import ConnectModal from './ConnectModal'
import { BASE } from '../../layout/serviceNav'

const ACTIONS = [
  { key: 'start', label: 'Start instance' },
  { key: 'stop', label: 'Stop instance' },
  { key: 'reboot', label: 'Reboot instance' },
  { key: 'terminate', label: 'Terminate (delete) instance' },
]

export default function InstanceList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const instances = scoped(useAwsStore((s) => s.instances) || [], region)
  const instanceAction = useAwsStore((s) => s.instanceAction)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [selected, setSelected] = useState([])
  const [query, setQuery] = useState('')
  const [stateFilter, setStateFilter] = useState('all')
  const [actionsOpen, setActionsOpen] = useState(false)
  const [connectInst, setConnectInst] = useState(null)

  const STATE_CHIPS = [
    { key: 'all', label: 'All' },
    { key: 'running', label: 'Running' },
    { key: 'stopped', label: 'Stopped' },
    { key: 'pending', label: 'Pending' },
    { key: 'terminated', label: 'Terminated' },
  ]

  // Terminated instances are hidden by default (matches the EC2 console). The
  // "All" chip shows everything except terminated; the Terminated chip reveals
  // them. Selecting a specific state filters to that state.
  const visible = instances
    .filter((i) => {
      if (stateFilter === 'all') return i.state !== 'terminated'
      if (stateFilter === 'pending') return ['pending', 'rebooting'].includes(i.state)
      return i.state === stateFilter
    })
    .filter((i) => !query || i.id.includes(query) || (i.name || '').toLowerCase().includes(query.toLowerCase()) || i.type.includes(query) || i.state.includes(query))

  const stateCount = (key) => instances.filter((i) => {
    if (key === 'all') return i.state !== 'terminated'
    if (key === 'pending') return ['pending', 'rebooting'].includes(i.state)
    return i.state === key
  }).length

  const doAction = (action) => {
    setActionsOpen(false)
    instanceAction(selected, action)
    pushFlash('success', `${action === 'terminate' ? 'Terminating' : action.charAt(0).toUpperCase() + action.slice(1) + 'ing'} ${selected.length} instance(s): ${selected.join(', ')}`)
    if (action === 'terminate') setSelected([])
  }

  const columns = [
    { key: 'name', label: 'Name', render: (r) => r.name || <span style={{ color: 'var(--aws-text-muted)' }}>—</span> },
    { key: 'id', label: 'Instance ID', render: (r) => <IDCopy value={r.id} onClick={() => navigate(`${BASE}/ec2/instances/${r.id}`)} /> },
    { key: 'state', label: 'Instance state', render: (r) => <Badge state={r.state} /> },
    { key: 'type', label: 'Instance type' },
    { key: 'statusChecks', label: 'Status check', render: (r) => (r.statusChecks === '2/2' ? '✓ 2/2 checks passed' : r.statusChecks) },
    { key: 'az', label: 'Availability Zone' },
    { key: 'publicIp', label: 'Public IPv4', render: (r) => (r.publicIp ? <IDCopy value={r.publicIp} mono /> : '—') },
    { key: 'privateIp', label: 'Private IPv4', render: (r) => <span className="aws-mono">{r.privateIp}</span> },
    { key: 'keyName', label: 'Key name', render: (r) => r.keyName || '—' },
  ]

  return (
    <div className="aws-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1>Instances ({visible.length})</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button onClick={() => window.location.reload && navigate(0)} icon={RefreshCw} />
          <div style={{ position: 'relative' }}>
            <Button onClick={() => setActionsOpen((o) => !o)} disabled={!selected.length}>Actions <ChevronDown size={13} /></Button>
            {actionsOpen && selected.length > 0 && (
              <div style={{ position: 'absolute', top: 32, left: 0, background: '#fff', border: '1px solid var(--aws-border)', borderRadius: 4, boxShadow: 'var(--aws-shadow-md)', zIndex: 50, minWidth: 200 }}>
                {ACTIONS.map((a) => (
                  <div key={a.key} onClick={() => doAction(a.key)} style={{ padding: '8px 16px', cursor: 'pointer', fontSize: 13, color: a.key === 'terminate' ? 'var(--aws-error)' : undefined }}>{a.label}</div>
                ))}
              </div>
            )}
          </div>
          <Button disabled={selected.length !== 1} onClick={() => setConnectInst(visible.find((i) => i.id === selected[0]))}>Connect</Button>
          <Button variant="primary" onClick={() => navigate(`${BASE}/ec2/launch`)}>Launch instances</Button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <SearchBar value={query} onChange={setQuery} placeholder="Find instance by attribute or tag (case-sensitive)" />
        <div style={{ display: 'flex', gap: 6 }}>
          {STATE_CHIPS.map((c) => (
            <button
              key={c.key}
              onClick={() => setStateFilter(c.key)}
              className={`aws-btn ${stateFilter === c.key ? 'aws-btn-primary' : 'aws-btn-secondary'}`}
              style={{ height: 30 }}
            >
              {c.label} ({stateCount(c.key)})
            </button>
          ))}
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={visible}
        getRowKey={(r) => r.id}
        selectable
        selected={selected}
        onSelect={setSelected}
        onRowClick={(r) => navigate(`${BASE}/ec2/instances/${r.id}`)}
        emptyTitle="No instances in this Region"
        emptyBody="Launch an instance to get started."
      />

      <div style={{ marginTop: 8, fontSize: 12, color: 'var(--aws-text-secondary)' }}>Viewing 1 to {visible.length} of {visible.length} Instances</div>

      {connectInst && <ConnectModal instance={connectInst} onClose={() => setConnectInst(null)} />}
    </div>
  )
}
