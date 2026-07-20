import { useState } from 'react'
import { netappApi } from '../../api/netapp'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Plus, HardDrive, Layers, Network, Shield, Server, AlertTriangle,
  Terminal, Link2, Maximize2,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import '../../styles/sim-products.css'
import './netapp.css'

const NA_LAB_USER = 'lab_netapp'
const NA_LAB_PASS = 'lab_netapp@123'
const ACCENT = '#0f6d5c'

const SIDEBAR = [
  { key: 'clusters', label: 'Clusters', icon: Server },
  { key: 'svms', label: 'SVMs', icon: Layers },
  { key: 'aggregates', label: 'Aggregates', icon: Layers },
  { key: 'volumes', label: 'Volumes', icon: HardDrive },
  { key: 'snapshots', label: 'Snapshots', icon: Shield },
  { key: 'luns', label: 'LUNs', icon: HardDrive },
  { key: 'protection', label: 'Protection', icon: Shield },
  { key: 'network', label: 'Network', icon: Network },
  { key: 'activity', label: 'Activity', icon: Server },
]

export default function NetAppSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, netappApi)
  const [nav, setNav] = useState('volumes')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [volModal, setVolModal] = useState(false)
  const [volName, setVolName] = useState('vol_new')
  const [volSvm, setVolSvm] = useState('svm-prod')
  const [volAggr, setVolAggr] = useState('aggr1')
  const [volSize, setVolSize] = useState(50)
  const [resizeTarget, setResizeTarget] = useState(null)
  const [resizeSize, setResizeSize] = useState(200)
  const [smModal, setSmModal] = useState(false)
  const [smSource, setSmSource] = useState('svm-prod:vol_db_data')
  const [smDest, setSmDest] = useState('svm-dr:vol_dr_copy')
  const [lunTarget, setLunTarget] = useState(null)
  const [initiator, setInitiator] = useState('iqn.1994-05.com.redhat:client1')

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
    vmwareHref,
  }

  const breadcrumbs = [{ label: st?.summary?.cluster || 'Cluster', onClick: () => setNav('volumes') }]
  if (nav !== 'volumes') breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === NA_LAB_USER && loginPass === NA_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        run(() => netappApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${NA_LAB_USER} / ${NA_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0a2e28]')}>
        <LabChromeBar title="NetApp ONTAP System Manager" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: ACCENT }}>
              <HardDrive size={18} /> ONTAP System Manager
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Sign in to the NetApp ONTAP training cluster.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={NA_LAB_USER}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none" style={{ borderColor: undefined }} />
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
                className="na-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(NA_LAB_USER); setLoginPass(NA_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{NA_LAB_USER}</span> / <span className="font-mono text-slate-700">{NA_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const renderContent = () => {
    if (nav === 'clusters') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Cluster', sortable: true },
        { key: 'nodes', label: 'Nodes', sortable: true },
        { key: 'health', label: 'Health', render: (r) => <SimStatusBadge status={r.health === 'ok' ? 'success' : 'error'} label={r.health} /> },
      ]} rows={st.clusters || []} searchKeys={['name']} />
    }
    if (nav === 'svms') {
      return <SimDataTable columns={[
        { key: 'name', label: 'SVM', sortable: true },
        { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'running' ? 'success' : 'error'} label={r.state} /> },
        { key: 'protocols', label: 'Protocols', render: (r) => (r.protocols || []).join(', ').toUpperCase() },
      ]} rows={st.svms || []} searchKeys={['name']} />
    }
    if (nav === 'aggregates') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Aggregate', sortable: true },
        { key: 'raid', label: 'RAID', sortable: true },
        { key: 'used', label: 'Used', render: (r) => `${r.used_gb} / ${r.size_gb} GB` },
        { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'online' ? 'success' : 'error'} label={r.state} /> },
      ]} rows={st.aggregates || []} searchKeys={['name']} />
    }
    if (nav === 'volumes') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Volumes</h2>
            <button type="button" className="na-btn-primary flex items-center gap-1" onClick={() => setVolModal(true)}>
              <Plus size={14} /> Create volume
            </button>
          </div>
          {broken.volume_near_full && (
            <div className="na-panel text-sm text-amber-800 bg-amber-50 border border-amber-200 px-3 py-2 rounded flex items-center gap-2">
              <AlertTriangle size={14} /> <strong>{broken.volume_near_full}</strong> is nearly full — resize before it runs out of space.
            </div>
          )}
          <SimDataTable columns={[
            { key: 'name', label: 'Volume', sortable: true },
            { key: 'svm', label: 'SVM', sortable: true },
            { key: 'aggregate', label: 'Aggregate', sortable: true },
            { key: 'used', label: 'Used', render: (r) => {
              const pct = Math.round(((r.used_gb || 0) / (r.size_gb || 1)) * 100)
              return (
                <div className="w-28">
                  <div className="h-1.5 rounded bg-slate-200 overflow-hidden">
                    <div className="h-full rounded" style={{ width: `${pct}%`, background: pct > 85 ? '#dc2626' : ACCENT }} />
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{r.used_gb} / {r.size_gb} GB ({pct}%)</div>
                </div>
              )
            } },
            { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'online' ? 'success' : 'error'} label={r.state} /> },
            { key: 'actions', label: 'Actions', render: (r) => (
              <div className="flex gap-1">
                <button type="button" className="na-btn-sm" onClick={(e) => { e.stopPropagation(); setResizeTarget(r.name); setResizeSize(r.size_gb * 2) }}>
                  <Maximize2 size={11} /> Resize
                </button>
                <button type="button" className="na-btn-sm" onClick={(e) => {
                  e.stopPropagation()
                  run(() => netappApi.takeSnapshot(sessionId, r.name), 'Snapshot created')
                }}>Snap</button>
              </div>
            ) },
          ]} rows={st.volumes || []} searchKeys={['name', 'svm']} />
        </div>
      )
    }
    if (nav === 'snapshots') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Snapshots</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Snapshot', sortable: true },
            { key: 'volume', label: 'Volume', sortable: true },
            { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GB` },
            { key: 'created', label: 'Created', sortable: true },
          ]} rows={st.snapshots || []} searchKeys={['name', 'volume']} />
          {(st.qtrees || []).length > 0 && (
            <>
              <h2 className="text-lg font-semibold pt-2">Qtrees</h2>
              <SimDataTable columns={[
                { key: 'name', label: 'Qtree', sortable: true },
                { key: 'volume', label: 'Volume', sortable: true },
                { key: 'security_style', label: 'Security', sortable: true },
              ]} rows={st.qtrees || []} searchKeys={['name']} />
            </>
          )}
        </div>
      )
    }
    if (nav === 'luns') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">LUNs</h2>
          <SimDataTable columns={[
            { key: 'path', label: 'Path', sortable: true },
            { key: 'svm', label: 'SVM', sortable: true },
            { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GB` },
            { key: 'os_type', label: 'OS Type', sortable: true },
            { key: 'mapped', label: 'Mapped', render: (r) => <SimStatusBadge status={r.mapped ? 'success' : 'warning'} label={r.mapped ? 'Mapped' : 'Unmapped'} /> },
            { key: 'actions', label: 'Actions', render: (r) => !r.mapped && (
              <button type="button" className="na-btn-sm" onClick={(e) => { e.stopPropagation(); setLunTarget(r.path) }}>
                <Link2 size={11} /> Map
              </button>
            ) },
          ]} rows={st.luns || []} searchKeys={['path']} />
        </div>
      )
    }
    if (nav === 'protection') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">SnapMirror Relationships</h2>
            <button type="button" className="na-btn-primary flex items-center gap-1" onClick={() => setSmModal(true)}>
              <Plus size={14} /> New SnapMirror
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'source', label: 'Source', sortable: true },
            { key: 'destination', label: 'Destination', sortable: true },
            { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'snapmirrored' ? 'success' : 'warning'} label={r.state} /> },
            { key: 'lag', label: 'Lag', sortable: true },
            { key: 'actions', label: 'Actions', render: (r) => (
              <div className="flex gap-1">
                {r.state === 'snapmirrored' && (
                  <button type="button" className="na-btn-sm na-btn-outline" onClick={(e) => { e.stopPropagation(); run(() => netappApi.breakMirror(sessionId, r.id), 'SnapMirror broken') }}>
                    Break
                  </button>
                )}
                {r.state === 'broken-off' && (
                  <button type="button" className="na-btn-sm" onClick={(e) => { e.stopPropagation(); run(() => netappApi.resyncMirror(sessionId, r.id), 'SnapMirror resynced') }}>
                    Resync
                  </button>
                )}
              </div>
            ) },
          ]} rows={st.snapmirrors || []} searchKeys={['source', 'destination']} />
        </div>
      )
    }
    if (nav === 'network') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Network Interfaces</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'LIF', sortable: true },
            { key: 'svm', label: 'SVM', sortable: true },
            { key: 'address', label: 'Address', sortable: true },
            { key: 'home_port', label: 'Port', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'up' ? 'success' : 'error'} label={r.status} /> },
          ]} rows={st.network_interfaces || []} searchKeys={['name', 'address']} />
          <h2 className="text-lg font-semibold pt-2">NFS / CIFS Exports</h2>
          <SimDataTable columns={[
            { key: 'volume', label: 'Volume', sortable: true },
            { key: 'policy', label: 'Export Policy', sortable: true },
            { key: 'clients', label: 'Allowed Clients', render: (r) => (r.clients || []).join(', ') },
            { key: 'rules', label: 'Rules', sortable: true },
          ]} rows={st.exports || []} searchKeys={['volume']} />
        </div>
      )
    }
    if (nav === 'activity') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Activity</h2>
          <SimDataTable columns={[
            { key: 'time', label: 'Time', sortable: true },
            { key: 'severity', label: 'Severity', sortable: true },
            { key: 'message', label: 'Message', sortable: true },
          ]} rows={st.activity_log || st.events || []} searchKeys={['message']} emptyMessage="No activity yet." />
        </div>
      )
    }
    return null
  }

  return (
    <div className={simPanelRoot(embedded, 'na-shell sim-product')}>
      <LabChromeBar title={`ONTAP System Manager · ${st?.summary?.version || '9.14'}`} subtitle={scenario?.title || slug}
        accent={ACCENT} className="lab-chrome-bar !bg-[#0f6d5c]" {...chromeProps}>
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

      <div className="px-4 py-2 bg-[#083f34] border-b border-black/20 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-300" />
        <span className="text-xs text-slate-400">{st?.session?.user || 'admin'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#0a2e28] na-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#f2f7f6]">{renderContent()}</main>
      </div>

      <SimModal open={volModal} onClose={() => setVolModal(false)} title="Create Volume"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setVolModal(false)}>Cancel</button>
          <button type="button" className="na-btn-primary" disabled={busy} onClick={() => {
            run(() => netappApi.createVolume(sessionId, volName, volSvm, volAggr, volSize), 'Volume created')
            setVolModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Volume name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={volName} onChange={(e) => setVolName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">SVM
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={volSvm} onChange={(e) => setVolSvm(e.target.value)}>
            {(st.svms || []).map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
        <label className="block text-sm mt-3">Aggregate
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={volAggr} onChange={(e) => setVolAggr(e.target.value)}>
            {(st.aggregates || []).map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
          </select>
        </label>
        <label className="block text-sm mt-3">Size (GB)
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={volSize} onChange={(e) => setVolSize(Number(e.target.value))} />
        </label>
      </SimModal>

      <SimModal open={!!resizeTarget} onClose={() => setResizeTarget(null)} title={`Resize Volume — ${resizeTarget || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setResizeTarget(null)}>Cancel</button>
          <button type="button" className="na-btn-primary" disabled={busy} onClick={() => {
            run(() => netappApi.resizeVolume(sessionId, resizeTarget, resizeSize), 'Volume resized')
            setResizeTarget(null)
          }}>Resize</button>
        </>}>
        <label className="block text-sm">New size (GB)
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={resizeSize} onChange={(e) => setResizeSize(Number(e.target.value))} />
        </label>
      </SimModal>

      <SimModal open={smModal} onClose={() => setSmModal(false)} title="Create SnapMirror Relationship"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setSmModal(false)}>Cancel</button>
          <button type="button" className="na-btn-primary" disabled={busy} onClick={() => {
            run(() => netappApi.createSnapmirror(sessionId, smSource, smDest), 'SnapMirror created')
            setSmModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Source (svm:volume)
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={smSource} onChange={(e) => setSmSource(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Destination (svm:volume)
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={smDest} onChange={(e) => setSmDest(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={!!lunTarget} onClose={() => setLunTarget(null)} title={`Map LUN — ${lunTarget || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setLunTarget(null)}>Cancel</button>
          <button type="button" className="na-btn-primary" disabled={busy} onClick={() => {
            run(() => netappApi.mountLun(sessionId, lunTarget, initiator), 'LUN mapped')
            setLunTarget(null)
          }}>Map</button>
        </>}>
        <label className="block text-sm">Initiator IQN
          <input className="w-full mt-1 border rounded px-2 py-1.5 font-mono text-xs" value={initiator} onChange={(e) => setInitiator(e.target.value)} />
        </label>
      </SimModal>
    </div>
  )
}
