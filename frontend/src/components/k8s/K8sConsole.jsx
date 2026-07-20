import { useState } from 'react'
import { k8sApi } from '../../api/k8s'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Layers, Server, Box, Network, FolderTree, HardDrive, Activity,
  Plus, RotateCw, Trash2, Ban, ArrowDownToLine, Unlock,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import '../../styles/sim-products.css'
import './k8s.css'

const K8S_LAB_USER = 'admin'
const K8S_LAB_PASS = 'lab123'
const ACCENT = '#326ce5'

const SIDEBAR = [
  { key: 'overview', label: 'Overview', icon: Layers },
  { key: 'nodes', label: 'Nodes', icon: Server },
  { key: 'workloads', label: 'Workloads', icon: Box },
  { key: 'pods', label: 'Pods', icon: Box },
  { key: 'services', label: 'Services', icon: Network },
  { key: 'namespaces', label: 'Namespaces', icon: FolderTree },
  { key: 'storage', label: 'Storage', icon: HardDrive },
  { key: 'events', label: 'Events', icon: Activity },
]

function nodeTone(status) {
  if (status === 'Ready') return 'success'
  if (status === 'NotReady') return 'error'
  return 'pending'
}

function podTone(phase, containers = []) {
  if (containers.some((c) => c.reason === 'CrashLoopBackOff')) return 'error'
  if (phase === 'Running') return 'success'
  if (phase === 'Pending' || phase === 'Terminating') return 'pending'
  return 'error'
}

function depTone(d) {
  if (d.readyReplicas === d.replicas && d.replicas > 0) return 'success'
  if (d.readyReplicas === 0) return 'error'
  return 'pending'
}

function pvcTone(status) {
  if (status === 'Bound') return 'success'
  if (status === 'Pending') return 'pending'
  return 'error'
}

export default function K8sConsole({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, k8sApi)
  const [nav, setNav] = useState('overview')
  const [loggedIn, setLoggedIn] = useState(false)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [scaleTarget, setScaleTarget] = useState(null)
  const [scaleReplicas, setScaleReplicas] = useState(1)
  const [nsOpen, setNsOpen] = useState(false)
  const [newNs, setNewNs] = useState('')

  const cluster = state?.cluster || {}
  const summary = state?.summary || {}
  const nodes = cluster.nodes || []
  const deployments = cluster.deployments || []
  const pods = cluster.pods || []
  const services = cluster.services || []
  const namespaces = cluster.namespaces || []
  const pvcs = cluster.pvcs || []
  const pvs = cluster.pvs || []
  const events = cluster.events || []

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const breadcrumbs = [
    { label: 'Cluster', onClick: () => setNav('overview') },
  ]
  if (nav !== 'overview') {
    breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })
  }

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === K8S_LAB_USER && loginPass === K8S_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        setLoggedIn(true)
        run(() => k8sApi.login(sessionId, K8S_LAB_USER), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${K8S_LAB_USER} / ${K8S_LAB_PASS}`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#1a1a2e]')}>
        <LabChromeBar title="Kubernetes Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: ACCENT }}>
              <Layers size={18} /> Sign in to Kubernetes
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Authenticate to the lab cluster to manage workloads.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm" placeholder={K8S_LAB_USER} />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm" />
              </div>
              {loginError && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>}
              <button type="submit" disabled={busy} className="k8s-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(K8S_LAB_USER); setLoginPass(K8S_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const renderContent = () => {
    if (nav === 'overview') {
      return (
        <div className="space-y-4">
          <div className="grid sm:grid-cols-4 gap-3">
            {[
              { label: 'Nodes Ready', value: `${summary.nodes_ready ?? 0}/${summary.nodes_total ?? 0}`, go: 'nodes' },
              { label: 'Pods Running', value: summary.pods_running ?? 0, go: 'pods' },
              { label: 'Deployments', value: `${summary.deployments_healthy ?? 0}/${summary.deployments_total ?? 0}`, go: 'workloads' },
              { label: 'Namespaces', value: summary.namespaces ?? 0, go: 'namespaces' },
            ].map((c) => (
              <button key={c.label} type="button" onClick={() => setNav(c.go)}
                className="text-left bg-white border border-slate-200 rounded p-4 hover:border-blue-300">
                <div className="text-2xl font-semibold" style={{ color: ACCENT }}>{c.value}</div>
                <div className="text-xs text-slate-500 mt-1">{c.label}</div>
              </button>
            ))}
          </div>
          {(summary.pods_crashloop > 0 || summary.pods_pending > 0 || summary.nodes_draining > 0) && (
            <div className="text-sm bg-amber-50 border border-amber-200 text-amber-900 rounded px-3 py-2">
              {[
                summary.pods_crashloop > 0 && `${summary.pods_crashloop} CrashLoopBackOff`,
                summary.pods_pending > 0 && `${summary.pods_pending} Pending`,
                summary.nodes_draining > 0 && `${summary.nodes_draining} draining`,
              ].filter(Boolean).join(' · ')}
            </div>
          )}
        </div>
      )
    }

    if (nav === 'nodes') {
      return (
        <SimDataTable
          searchKeys={['name', 'status']}
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            {
              key: 'status', label: 'Status',
              render: (r) => <SimStatusBadge status={nodeTone(r.status)} label={r.unschedulable ? `${r.status} (cordoned)` : r.status} />,
            },
            { key: 'roles', label: 'Roles', render: (r) => (r.roles || []).join(', ') },
            { key: 'version', label: 'Version' },
            { key: 'cpu', label: 'CPU', render: (r) => `${r.requested?.cpu || '—'} / ${r.capacity?.cpu || '—'}` },
            { key: 'memory', label: 'Memory', render: (r) => `${r.requested?.memory || '—'} / ${r.capacity?.memory || '—'}` },
            {
              key: 'actions', label: 'Actions',
              render: (r) => (
                <div className="flex gap-1 flex-wrap">
                  <button type="button" className="k8s-btn-ghost" disabled={busy || r.unschedulable}
                    onClick={(e) => { e.stopPropagation(); run(() => k8sApi.cordonNode(sessionId, r.name), 'Cordoned') }}>
                    <Ban size={12} className="inline mr-0.5" />Cordon
                  </button>
                  <button type="button" className="k8s-btn-ghost" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => k8sApi.drainNode(sessionId, r.name), 'Draining') }}>
                    <ArrowDownToLine size={12} className="inline mr-0.5" />Drain
                  </button>
                  <button type="button" className="k8s-btn-ghost" disabled={busy || !r.unschedulable}
                    onClick={(e) => { e.stopPropagation(); run(() => k8sApi.uncordonNode(sessionId, r.name), 'Uncordoned') }}>
                    <Unlock size={12} className="inline mr-0.5" />Uncordon
                  </button>
                </div>
              ),
            },
          ]}
          rows={nodes}
        />
      )
    }

    if (nav === 'workloads') {
      return (
        <SimDataTable
          searchKeys={['name', 'namespace']}
          columns={[
            { key: 'name', label: 'Deployment', sortable: true },
            { key: 'namespace', label: 'Namespace', sortable: true },
            {
              key: 'ready', label: 'Ready',
              render: (r) => <SimStatusBadge status={depTone(r)} label={`${r.readyReplicas ?? 0}/${r.replicas ?? 0}`} />,
            },
            { key: 'image', label: 'Image', render: (r) => r.image || '—' },
            {
              key: 'actions', label: 'Actions',
              render: (r) => (
                <div className="flex gap-1 flex-wrap">
                  <button type="button" className="k8s-btn-ghost" disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation()
                      setScaleTarget(r)
                      setScaleReplicas(r.replicas ?? 1)
                    }}>Scale</button>
                  <button type="button" className="k8s-btn-ghost" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => k8sApi.restartDeployment(sessionId, r.name, r.namespace), 'Restarted') }}>
                    <RotateCw size={12} className="inline mr-0.5" />Restart
                  </button>
                  <button type="button" className="k8s-btn-ghost" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => k8sApi.deleteDeployment(sessionId, r.name, r.namespace), 'Deleted') }}>
                    <Trash2 size={12} className="inline mr-0.5" />Delete
                  </button>
                </div>
              ),
            },
          ]}
          rows={deployments}
        />
      )
    }

    if (nav === 'pods') {
      return (
        <SimDataTable
          searchKeys={['name', 'namespace', 'node']}
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'namespace', label: 'Namespace', sortable: true },
            {
              key: 'phase', label: 'Status',
              render: (r) => {
                const reason = (r.containers || []).find((c) => c.reason)?.reason
                return <SimStatusBadge status={podTone(r.phase, r.containers)} label={reason || r.phase} />
              },
            },
            { key: 'node', label: 'Node', render: (r) => r.node || '—' },
            { key: 'restarts', label: 'Restarts', render: (r) => (r.containers || []).reduce((n, c) => n + (c.restartCount || 0), 0) },
            {
              key: 'actions', label: 'Actions',
              render: (r) => (
                <button type="button" className="k8s-btn-ghost" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => k8sApi.deletePod(sessionId, r.name, r.namespace), 'Pod deleted') }}>
                  <Trash2 size={12} className="inline mr-0.5" />Delete
                </button>
              ),
            },
          ]}
          rows={pods}
        />
      )
    }

    if (nav === 'services') {
      return (
        <SimDataTable
          searchKeys={['name', 'namespace', 'type']}
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'namespace', label: 'Namespace', sortable: true },
            { key: 'type', label: 'Type', sortable: true },
            { key: 'clusterIP', label: 'Cluster IP' },
            { key: 'externalIP', label: 'External IP', render: (r) => r.externalIP || '—' },
            {
              key: 'ports', label: 'Ports',
              render: (r) => (r.ports || []).map((p) => `${p.port}${p.nodePort ? `:${p.nodePort}` : ''}/${p.protocol}`).join(', '),
            },
          ]}
          rows={services}
        />
      )
    }

    if (nav === 'namespaces') {
      return (
        <div>
          <div className="flex justify-end mb-3">
            <button type="button" className="k8s-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
              onClick={() => setNsOpen(true)} disabled={busy}>
              <Plus size={14} /> Create Namespace
            </button>
          </div>
          <SimDataTable
            searchKeys={['name', 'status']}
            columns={[
              { key: 'name', label: 'Name', sortable: true },
              { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'Active' ? 'success' : 'pending'} label={r.status} /> },
              {
                key: 'actions', label: 'Actions',
                render: (r) => (r.name === 'default' || r.name === 'kube-system') ? null : (
                  <button type="button" className="k8s-btn-ghost" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => k8sApi.deleteNamespace(sessionId, r.name), 'Namespace deleted') }}>
                    <Trash2 size={12} className="inline mr-0.5" />Delete
                  </button>
                ),
              },
            ]}
            rows={namespaces}
          />
        </div>
      )
    }

    if (nav === 'storage') {
      return (
        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Persistent Volume Claims</h3>
            <SimDataTable
              searchKeys={['name', 'namespace', 'status']}
              columns={[
                { key: 'name', label: 'Name', sortable: true },
                { key: 'namespace', label: 'Namespace', sortable: true },
                { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={pvcTone(r.status)} label={r.status} /> },
                { key: 'capacity', label: 'Capacity', render: (r) => r.capacity || '—' },
                { key: 'storageClass', label: 'Storage Class', render: (r) => r.storageClass || '—' },
                {
                  key: 'actions', label: 'Actions',
                  render: (r) => r.status === 'Pending' ? (
                    <button type="button" className="k8s-btn-ghost" disabled={busy}
                      onClick={(e) => { e.stopPropagation(); run(() => k8sApi.bindPvc(sessionId, r.name, r.namespace), 'PVC bound') }}>
                      Bind
                    </button>
                  ) : null,
                },
              ]}
              rows={pvcs}
            />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Persistent Volumes</h3>
            <SimDataTable
              searchKeys={['name', 'status']}
              columns={[
                { key: 'name', label: 'Name', sortable: true },
                { key: 'status', label: 'Status' },
                { key: 'capacity', label: 'Capacity' },
                { key: 'claim', label: 'Claim', render: (r) => r.claim || '—' },
                { key: 'storageClass', label: 'Storage Class', render: (r) => r.storageClass || '—' },
              ]}
              rows={pvs}
            />
          </div>
        </div>
      )
    }

    return (
      <SimDataTable
        searchKeys={['message', 'reason', 'involvedObject', 'namespace']}
        columns={[
          { key: 'time', label: 'Time', render: (r) => r.time || '—' },
          { key: 'type', label: 'Type', render: (r) => r.type || '—' },
          { key: 'reason', label: 'Reason' },
          { key: 'involvedObject', label: 'Object', render: (r) => r.involvedObject || '—' },
          { key: 'namespace', label: 'Namespace', render: (r) => r.namespace || '—' },
          { key: 'message', label: 'Message' },
        ]}
        rows={[...events].reverse()}
      />
    )
  }

  return (
    <div className={simPanelRoot(embedded, 'bg-[#f5f7fb] text-slate-900')}>
      <LabChromeBar title="Kubernetes Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#1e2430] text-white" />
        <main className="flex-1 overflow-auto p-5 bg-[#f5f7fb]">
          <SimBreadcrumbs items={breadcrumbs} />
          {renderContent()}
        </main>
      </div>

      <SimModal open={!!scaleTarget} onClose={() => setScaleTarget(null)} title={`Scale ${scaleTarget?.name || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setScaleTarget(null)}>Cancel</button>
          <button type="button" className="k8s-btn-primary px-3 py-1.5 text-sm" disabled={busy}
            onClick={() => {
              run(() => k8sApi.scaleDeployment(sessionId, scaleTarget.name, Number(scaleReplicas), scaleTarget.namespace), 'Scaled')
              setScaleTarget(null)
            }}>Scale</button>
        </>}>
        <label className="block text-sm text-slate-200">Replicas
          <input type="number" min={0} max={20} className="mt-1 w-full border rounded px-2 py-1.5 text-sm text-slate-900"
            value={scaleReplicas} onChange={(e) => setScaleReplicas(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={nsOpen} onClose={() => setNsOpen(false)} title="Create Namespace"
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setNsOpen(false)}>Cancel</button>
          <button type="button" className="k8s-btn-primary px-3 py-1.5 text-sm" disabled={busy || !newNs.trim()}
            onClick={() => {
              run(() => k8sApi.createNamespace(sessionId, newNs.trim()), 'Namespace created')
              setNsOpen(false)
              setNewNs('')
            }}>Create</button>
        </>}>
        <label className="block text-sm text-slate-200">Name
          <input className="mt-1 w-full border rounded px-2 py-1.5 text-sm text-slate-900"
            value={newNs} onChange={(e) => setNewNs(e.target.value)} placeholder="staging-2" />
        </label>
      </SimModal>
    </div>
  )
}
