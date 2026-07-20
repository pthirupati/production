import { useState } from 'react'
import { gcpApi } from '../../api/gcp'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Cloud, Server, Network, Shield, HardDrive, Plus, AlertTriangle,
  Terminal, Play, Square, RotateCw, Settings2, Link2, Unlink,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import CloudShellPanel from '../lab/CloudShellPanel'
import '../../styles/sim-products.css'
import './gcp.css'

const GCP_LAB_USER = 'admin@fixitlab.io'
const GCP_LAB_PASS = 'lab123'
const ACCENT = '#4285f4'

const SIDEBAR = [
  { key: 'overview', label: 'Overview', icon: Cloud },
  { key: 'instances', label: 'VM instances', icon: Server },
  { key: 'networking', label: 'VPC network', icon: Network },
  { key: 'disks', label: 'Disks', icon: HardDrive },
  { key: 'storage', label: 'Cloud Storage', icon: HardDrive },
  { key: 'iam', label: 'IAM & Admin', icon: Shield },
  { key: 'operations', label: 'Operations', icon: Settings2 },
]

const MACHINE_TYPE_OPTIONS = [
  { value: 'e2-micro', label: 'e2-micro (2 shared vCPU, 1 GiB) — cost-optimized' },
  { value: 'e2-small', label: 'e2-small (2 shared vCPU, 2 GiB) — cost-optimized' },
  { value: 'e2-medium', label: 'e2-medium (2 shared vCPU, 4 GiB) — cost-optimized' },
  { value: 'e2-standard-2', label: 'e2-standard-2 (2 vCPU, 8 GiB) — general purpose' },
  { value: 'e2-standard-4', label: 'e2-standard-4 (4 vCPU, 16 GiB) — general purpose' },
  { value: 'n2-standard-2', label: 'n2-standard-2 (2 vCPU, 8 GiB) — general purpose' },
  { value: 'n2-standard-4', label: 'n2-standard-4 (4 vCPU, 16 GiB) — general purpose' },
  { value: 'n2-highmem-2', label: 'n2-highmem-2 (2 vCPU, 16 GiB) — memory optimized' },
  { value: 'c2-standard-4', label: 'c2-standard-4 (4 vCPU, 16 GiB) — compute optimized' },
]

function statusBadge(status) {
  if (status === 'RUNNING') return 'success'
  if (status === 'TERMINATED') return 'error'
  return 'pending'
}

export default function GcpConsole({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, gcpApi)
  const [nav, setNav] = useState('overview')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [resizeTo, setResizeTo] = useState('')
  const [ruleModalOpen, setRuleModalOpen] = useState(false)
  const [ruleName, setRuleName] = useState('allow-rule')
  const [rulePort, setRulePort] = useState('22')
  const [rulePriority, setRulePriority] = useState(1000)
  const [ruleAction, setRuleAction] = useState('ALLOW')
  const [attachTarget, setAttachTarget] = useState(null)
  const [createDiskModal, setCreateDiskModal] = useState(false)
  const [newDiskName, setNewDiskName] = useState('disk-new')
  const [newDiskSize, setNewDiskSize] = useState(100)
  const [bucketName, setBucketName] = useState('fixitlab-new-bucket')
  const [iamMember, setIamMember] = useState('user:ops@fixitlab.io')
  const [iamRole, setIamRole] = useState('roles/viewer')
  const [createBucketOpen, setCreateBucketOpen] = useState(false)
  const [iamOpen, setIamOpen] = useState(false)
  const [cloudShellOpen, setCloudShellOpen] = useState(false)

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}
  const instances = st.instances || []
  const firewallRules = st.firewall_rules || []
  const disks = st.disks || []
  const networks = st.networks || []
  const buckets = st.buckets || []
  const iamBindings = st.iam_bindings || []
  const operations = st.operations || st.events || []
  const routes = st.routes || []
  const forwardingRules = st.forwarding_rules || []
  const snapshots = st.snapshots || []
  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const breadcrumbs = [{ label: st?.project?.name || 'Project', onClick: () => setNav('overview') }]
  if (nav !== 'overview') breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === GCP_LAB_USER && loginPass === GCP_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        run(() => gcpApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${GCP_LAB_USER} / ${GCP_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0d1117]')}>
        <LabChromeBar title="Google Cloud" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: ACCENT }}>
              <Cloud size={18} /> Sign in to Google Cloud
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Sign in to the FixItLab Enterprise Project.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Email</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={GCP_LAB_USER}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} autoComplete="current-password"
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none" />
              </div>
              {loginError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>
              )}
              <button type="submit" disabled={busy}
                className="gcp-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign in
              </button>
              <button type="button"
                onClick={() => { setLoginUser(GCP_LAB_USER); setLoginPass(GCP_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{GCP_LAB_USER}</span> / <span className="font-mono text-slate-700">{GCP_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const instancePower = (inst, op) => {
    const fn = op === 'start' ? gcpApi.startInstance : op === 'stop' ? gcpApi.stopInstance : gcpApi.resetInstance
    run(() => fn(sessionId, inst.name), `${op[0].toUpperCase()}${op.slice(1)} requested`)
  }

  const submitRule = () => {
    run(() => gcpApi.createFirewallRule(sessionId, {
      name: ruleName, priority: Number(rulePriority), protocols: `tcp:${rulePort}`,
      action: ruleAction, direction: 'INGRESS',
    }), 'Firewall rule created')
    setRuleModalOpen(false)
  }

  const renderOverview = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Project</h2>
      <div className="gcp-panel">
        <div className="text-sm"><span className="text-slate-500">Project ID:</span> <span className="font-mono">{st?.project?.id}</span></div>
        <div className="text-sm mt-1"><span className="text-slate-500">Name:</span> {st?.project?.name}</div>
      </div>
      <h2 className="text-lg font-semibold pt-2">Quick glance</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="gcp-tile"><Server size={16} /> <div><div className="gcp-tile-num">{instances.length}</div><div className="gcp-tile-label">VM instances</div></div></div>
        <div className="gcp-tile"><Network size={16} /> <div><div className="gcp-tile-num">{networks.length}</div><div className="gcp-tile-label">VPC networks</div></div></div>
        <div className="gcp-tile"><Shield size={16} /> <div><div className="gcp-tile-num">{firewallRules.length}</div><div className="gcp-tile-label">Firewall rules</div></div></div>
        <div className="gcp-tile"><HardDrive size={16} /> <div><div className="gcp-tile-num">{disks.length}</div><div className="gcp-tile-label">Disks</div></div></div>
      </div>
    </div>
  )

  const renderInstances = () => (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">VM instances</h2>
      {broken.vm_undersized && (
        <div className="gcp-banner">
          <AlertTriangle size={14} /> <strong>{broken.vm_undersized}</strong> looks undersized for its current workload — consider a larger machine type.
        </div>
      )}
      {broken.vm_stopped && (
        <div className="gcp-banner">
          <AlertTriangle size={14} /> <strong>{broken.vm_stopped}</strong> is stopped.
        </div>
      )}
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={statusBadge(r.status)} label={r.status} /> },
        { key: 'machine_type', label: 'Machine type', sortable: true },
        { key: 'internal_ip', label: 'Internal IP', sortable: true },
        { key: 'zone', label: 'Zone', sortable: true },
        { key: 'actions', label: 'Actions', render: (r) => (
          <div className="flex items-center gap-1">
            {r.status !== 'RUNNING' && (
              <button type="button" className="gcp-btn-sm" onClick={(e) => { e.stopPropagation(); instancePower(r, 'start') }}>
                <Play size={11} /> Start
              </button>
            )}
            {r.status === 'RUNNING' && (
              <button type="button" className="gcp-btn-sm" onClick={(e) => { e.stopPropagation(); instancePower(r, 'stop') }}>
                <Square size={11} /> Stop
              </button>
            )}
            <button type="button" className="gcp-btn-sm" onClick={(e) => { e.stopPropagation(); instancePower(r, 'reset') }}>
              <RotateCw size={11} /> Reset
            </button>
            <button type="button" className="gcp-btn-sm" disabled={r.status === 'RUNNING'}
              title={r.status === 'RUNNING' ? 'Stop the instance to change its machine type' : ''}
              onClick={(e) => { e.stopPropagation(); setInstanceDetail(r); setResizeTo(r.machine_type) }}>
              <Settings2 size={11} /> Machine type
            </button>
          </div>
        ) },
      ]} rows={instances} searchKeys={['name']} onRowClick={(r) => { setInstanceDetail(r); setResizeTo(r.machine_type) }} />
    </div>
  )

  const renderNetworking = () => (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-2">VPC networks</h2>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'mode', label: 'Subnet mode', sortable: true },
          { key: 'subnets', label: 'Subnets', render: (r) => (r.subnets || []).map((s) => `${s.name} (${s.range})`).join(', ') },
        ]} rows={networks} searchKeys={['name']} />
      </div>
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Firewall rules</h2>
          <button type="button" className="gcp-btn-sm" onClick={() => { setRuleModalOpen(true); setRuleName('allow-rule'); setRulePort('22'); setRulePriority(1000); setRuleAction('ALLOW') }}>
            <Plus size={11} /> Create firewall rule
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'priority', label: 'Priority', sortable: true },
          { key: 'name', label: 'Name', sortable: true },
          { key: 'direction', label: 'Direction', sortable: true },
          { key: 'protocols', label: 'Protocols', sortable: true },
          { key: 'action', label: 'Action', render: (r) => <SimStatusBadge status={r.action === 'ALLOW' ? 'success' : 'error'} label={r.action} /> },
          { key: 'actions', label: '', render: (r) => !r.system && (
            <button type="button" className="gcp-btn-sm gcp-btn-outline"
              onClick={() => run(() => gcpApi.deleteFirewallRule(sessionId, r.name), 'Firewall rule deleted')}>
              Delete
            </button>
          ) },
        ]} rows={firewallRules} pageSize={20} searchKeys={['name']} />
      </div>
    </div>
  )

  const renderDisks = () => (
    <div className="space-y-3">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Disks</h2>
        <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateDiskModal(true)}>
          <Plus size={14} /> Create disk
        </button>
      </div>
      {broken.disk_unattached && (
        <div className="gcp-banner">
          <AlertTriangle size={14} /> <strong>{broken.disk_unattached}</strong> is unattached.
        </div>
      )}
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GB` },
        { key: 'type', label: 'Type', sortable: true },
        { key: 'attached_to', label: 'In use by', render: (r) => r.attached_to ? <SimStatusBadge status="success" label={r.attached_to} /> : <SimStatusBadge status="warning" label="Not attached" /> },
        { key: 'actions', label: 'Actions', render: (r) => (
          <div className="flex gap-1">
            {r.attached_to && !r.boot ? (
              <button type="button" className="gcp-btn-sm" onClick={(e) => { e.stopPropagation(); run(() => gcpApi.detachDisk(sessionId, r.name), 'Disk detached') }}>
                <Unlink size={11} /> Detach
              </button>
            ) : !r.attached_to ? (
              <button type="button" className="gcp-btn-sm" onClick={(e) => { e.stopPropagation(); setAttachTarget(r.name) }}>
                <Link2 size={11} /> Attach to instance
              </button>
            ) : null}
            <button type="button" className="gcp-btn-sm" onClick={(e) => {
              e.stopPropagation()
              run(() => gcpApi.createSnapshot(sessionId, r.name, `${r.name}-snap`), 'Snapshot created')
            }}>
              Snapshot
            </button>
          </div>
        ) },
      ]} rows={disks} searchKeys={['name']} />
      {snapshots.length > 0 && (
        <>
          <h2 className="text-lg font-semibold pt-2">Snapshots</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'source_disk', label: 'Source disk' },
            { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GB` },
            { key: 'status', label: 'Status' },
          ]} rows={snapshots} searchKeys={['name']} />
        </>
      )}
    </div>
  )

  const renderStorage = () => (
    <div className="space-y-3">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Buckets</h2>
        <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateBucketOpen(true)}>
          <Plus size={14} /> Create bucket
        </button>
      </div>
      {buckets.map((b) => (
        <div key={b.name} className="border border-slate-200 rounded-lg p-3 bg-white mb-2">
          <div className="flex justify-between items-center mb-2">
            <div>
              <div className="font-semibold text-sm">gs://{b.name}</div>
              <div className="text-xs text-slate-500">{b.location} · {b.storage_class}</div>
            </div>
            <button type="button" className="gcp-btn-sm" onClick={() => run(() => gcpApi.deleteBucket(sessionId, b.name), 'Bucket deleted')}>
              Delete
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Object' },
            { key: 'size_kb', label: 'Size', render: (r) => `${r.size_kb} KB` },
          ]} rows={b.objects || []} pageSize={8} />
        </div>
      ))}
    </div>
  )

  const renderIam = () => (
    <div className="space-y-3">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">IAM principals</h2>
        <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setIamOpen(true)}>
          <Plus size={14} /> Grant access
        </button>
      </div>
      <SimDataTable columns={[
        { key: 'member', label: 'Principal', sortable: true },
        { key: 'role', label: 'Role', sortable: true },
        { key: 'actions', label: '', render: (r) => (
          <button type="button" className="gcp-btn-sm" onClick={() => run(() => gcpApi.removeIamBinding(sessionId, r.member, r.role), 'Binding removed')}>
            Remove
          </button>
        ) },
      ]} rows={iamBindings} searchKeys={['member', 'role']} />
    </div>
  )

  const renderOperations = () => (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Operations</h2>
      <SimDataTable columns={[
        { key: 'time', label: 'Time', render: (r) => r.time || r.created },
        { key: 'description', label: 'Description', render: (r) => r.description || r.message },
        { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={(r.status || '').includes('ERROR') || r.severity === 'error' ? 'error' : 'success'} label={r.status || r.severity || 'DONE'} /> },
      ]} rows={operations} searchKeys={['description', 'message']} pageSize={25} />
    </div>
  )

  const renderContent = () => {
    if (nav === 'instances') return renderInstances()
    if (nav === 'networking') return (
      <div className="space-y-5">
        {renderNetworking()}
        <div>
          <h2 className="text-lg font-semibold mb-2">Routes</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'dest', label: 'Destination' },
            { key: 'next_hop', label: 'Next hop' },
            { key: 'priority', label: 'Priority' },
          ]} rows={routes} searchKeys={['name']} />
        </div>
        <div>
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-lg font-semibold">Forwarding rules</h2>
            <button type="button" className="gcp-btn-sm" onClick={() => run(() => gcpApi.createForwardingRule(sessionId, { name: `fr-${Date.now().toString(36).slice(-4)}`, port: 443 }), 'Forwarding rule created')}>
              <Plus size={11} /> Create
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'ip', label: 'IP' },
            { key: 'port', label: 'Port' },
            { key: 'target', label: 'Target' },
          ]} rows={forwardingRules} searchKeys={['name']} />
        </div>
        <button type="button" className="gcp-btn-sm" onClick={() => {
          const net = networks[0]?.name || 'vpc-prod'
          run(() => gcpApi.createSubnet(sessionId, net, `subnet-${Date.now().toString(36).slice(-4)}`, '10.128.32.0/20'), 'Subnet created')
        }}>
          <Plus size={11} /> Add subnet to {networks[0]?.name || 'VPC'}
        </button>
      </div>
    )
    if (nav === 'disks') return renderDisks()
    if (nav === 'storage') return renderStorage()
    if (nav === 'iam') return renderIam()
    if (nav === 'operations') return renderOperations()
    return renderOverview()
  }

  return (
    <div className={simPanelRoot(embedded, 'gcp-shell sim-product')}>
      <LabChromeBar title="Google Cloud" subtitle={scenario?.title || slug} accent={ACCENT}
        className="lab-chrome-bar !bg-[#1a73e8]" {...chromeProps}>
        <button type="button" className="lab-chrome-btn flex items-center gap-1" onClick={() => setCloudShellOpen((o) => !o)}>
          <Terminal size={13} /> {cloudShellOpen ? 'Hide Cloud Shell' : 'Cloud Shell'}
        </button>
        {onToggleTerminal && (
          <button type="button" className="lab-chrome-btn flex items-center gap-1" onClick={onToggleTerminal}>
            <Terminal size={13} /> {simTerminalOpen ? 'Hide terminal' : 'Terminal'}
          </button>
        )}
      </LabChromeBar>

      {goal.objective && (
        <div className="px-4 py-2 text-sm bg-amber-50 border-b border-amber-200 flex items-center gap-2">
          <AlertTriangle size={14} className="text-amber-600 shrink-0" />
          <span><strong>{goal.title}:</strong> {goal.objective}</span>
        </div>
      )}

      <div className="px-4 py-2 bg-[#0b3d91] border-b border-black/20 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-300" />
        <span className="text-xs text-slate-300">{st?.session?.user || 'admin'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#0b1b33] gcp-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#f8f9fa]">{renderContent()}</main>
      </div>

      {cloudShellOpen && (
        <CloudShellPanel
          provider="gcp"
          accent={ACCENT}
          onClose={() => setCloudShellOpen(false)}
          onCommand={async (action, payload) => {
            const res = await gcpApi.action(sessionId, action, payload)
            await run(() => Promise.resolve(res), res?.message || 'Cloud Shell command')
            return res
          }}
        />
      )}

      <SimModal open={!!instanceDetail} onClose={() => setInstanceDetail(null)} title={`${instanceDetail?.name || ''} — Machine type`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setInstanceDetail(null)}>Cancel</button>
          <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
            run(() => gcpApi.setMachineType(sessionId, instanceDetail.name, resizeTo), 'Machine type changed')
            setInstanceDetail(null)
          }}>Save</button>
        </>}>
        <p className="text-xs text-slate-400 mb-3">Current machine type: <span className="font-mono">{instanceDetail?.machine_type}</span> · Status: {instanceDetail?.status}</p>
        {instanceDetail?.status === 'RUNNING' && (
          <div className="gcp-banner mb-3"><AlertTriangle size={13} /> Stop the instance first to change its machine type.</div>
        )}
        <label className="block text-sm">New machine type
          <select className="w-full mt-1 border rounded px-2 py-1.5 text-slate-900" value={resizeTo} onChange={(e) => setResizeTo(e.target.value)}>
            {MACHINE_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </SimModal>

      <SimModal open={ruleModalOpen} onClose={() => setRuleModalOpen(false)} title="Create firewall rule"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setRuleModalOpen(false)}>Cancel</button>
          <button type="button" className="gcp-btn-primary" disabled={busy} onClick={submitRule}>Create</button>
        </>}>
        <label className="block text-sm">Name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={ruleName} onChange={(e) => setRuleName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Port (TCP)
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={rulePort} onChange={(e) => setRulePort(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Priority
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={rulePriority} onChange={(e) => setRulePriority(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Action
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={ruleAction} onChange={(e) => setRuleAction(e.target.value)}>
            <option value="ALLOW">Allow</option>
            <option value="DENY">Deny</option>
          </select>
        </label>
      </SimModal>

      <SimModal open={!!attachTarget} onClose={() => setAttachTarget(null)} title={`Attach disk — ${attachTarget || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setAttachTarget(null)}>Cancel</button>
          <button type="button" className="gcp-btn-primary" disabled={busy || !instances.length} onClick={() => {
            run(() => gcpApi.attachDisk(sessionId, instances[0].name, attachTarget), 'Disk attached')
            setAttachTarget(null)
          }}>Attach to {instances[0]?.name || 'instance'}</button>
        </>}>
        <p className="text-sm text-slate-300">Attach this persistent disk to the instance <span className="font-mono">{instances[0]?.name}</span>.</p>
      </SimModal>

      <SimModal open={createDiskModal} onClose={() => setCreateDiskModal(false)} title="Create persistent disk"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setCreateDiskModal(false)}>Cancel</button>
          <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
            run(() => gcpApi.createDisk(sessionId, newDiskName, Number(newDiskSize)), 'Disk created')
            setCreateDiskModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Disk name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={newDiskName} onChange={(e) => setNewDiskName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Size (GB)
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={newDiskSize} onChange={(e) => setNewDiskSize(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={createBucketOpen} onClose={() => setCreateBucketOpen(false)} title="Create bucket"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setCreateBucketOpen(false)}>Cancel</button>
          <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
            run(() => gcpApi.createBucket(sessionId, bucketName), 'Bucket created')
            setCreateBucketOpen(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={bucketName} onChange={(e) => setBucketName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={iamOpen} onClose={() => setIamOpen(false)} title="Grant access"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setIamOpen(false)}>Cancel</button>
          <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
            run(() => gcpApi.addIamBinding(sessionId, iamMember, iamRole), 'Access granted')
            setIamOpen(false)
          }}>Grant</button>
        </>}>
        <label className="block text-sm">Principal
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={iamMember} onChange={(e) => setIamMember(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Role
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={iamRole} onChange={(e) => setIamRole(e.target.value)}>
            <option value="roles/owner">roles/owner</option>
            <option value="roles/editor">roles/editor</option>
            <option value="roles/viewer">roles/viewer</option>
            <option value="roles/compute.admin">roles/compute.admin</option>
            <option value="roles/storage.admin">roles/storage.admin</option>
          </select>
        </label>
      </SimModal>
    </div>
  )
}
