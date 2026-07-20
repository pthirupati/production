import { useState } from 'react'
import { dellemcApi } from '../../api/dellemc'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Plus, HardDrive, Layers, Network, Users, Server, AlertTriangle,
  Terminal, Eye, Link2,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import '../../styles/sim-products.css'
import './dellemc.css'

const DE_LAB_USER = 'lab_dellemc'
const DE_LAB_PASS = 'lab_dellemc@123'
const ACCENT = '#0072c6'

const SIDEBAR = [
  { key: 'arrays', label: 'Arrays', icon: Server },
  { key: 'storage-groups', label: 'Storage Groups', icon: Layers },
  { key: 'volumes', label: 'Volumes', icon: HardDrive },
  { key: 'snapshots', label: 'Snapshots', icon: HardDrive },
  { key: 'hosts', label: 'Hosts', icon: Users },
  { key: 'masking-views', label: 'Masking Views', icon: Eye },
  { key: 'srdf', label: 'SRDF', icon: Network },
  { key: 'ports', label: 'Ports', icon: Network },
  { key: 'activity', label: 'Activity', icon: Server },
]

export default function DellEmcSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, dellemcApi)
  const [nav, setNav] = useState('volumes')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [sgModal, setSgModal] = useState(false)
  const [sgName, setSgName] = useState('SG_new')
  const [volModal, setVolModal] = useState(false)
  const [volSize, setVolSize] = useState(100)
  const [volSg, setVolSg] = useState('')
  const [mapTarget, setMapTarget] = useState(null)
  const [mapSg, setMapSg] = useState('')
  const [hostModal, setHostModal] = useState(false)
  const [hostName, setHostName] = useState('new-host')
  const [mvModal, setMvModal] = useState(false)
  const [mvName, setMvName] = useState('MV_new')
  const [mvSg, setMvSg] = useState('')
  const [mvHost, setMvHost] = useState('')
  const [mvPg, setMvPg] = useState('')

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

  const breadcrumbs = [{ label: st?.summary?.array || 'Array', onClick: () => setNav('volumes') }]
  if (nav !== 'volumes') breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === DE_LAB_USER && loginPass === DE_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        run(() => dellemcApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${DE_LAB_USER} / ${DE_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#04213f]')}>
        <LabChromeBar title="Dell EMC Unisphere" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: ACCENT }}>
              <HardDrive size={18} /> Unisphere for PowerMax
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Sign in to the Dell EMC Unisphere training array.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={DE_LAB_USER}
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
                className="de-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(DE_LAB_USER); setLoginPass(DE_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{DE_LAB_USER}</span> / <span className="font-mono text-slate-700">{DE_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const renderContent = () => {
    if (nav === 'arrays') {
      return <SimDataTable columns={[
        { key: 'id', label: 'Array ID', sortable: true },
        { key: 'model', label: 'Model', sortable: true },
        { key: 'capacity_tb', label: 'Capacity', render: (r) => `${r.used_tb} / ${r.capacity_tb} TB` },
        { key: 'health', label: 'Health', render: (r) => <SimStatusBadge status={r.health === 'normal' ? 'success' : 'error'} label={r.health} /> },
      ]} rows={st.arrays || []} searchKeys={['id', 'model']} />
    }
    if (nav === 'storage-groups') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Storage Groups</h2>
            <button type="button" className="de-btn-primary flex items-center gap-1" onClick={() => setSgModal(true)}>
              <Plus size={14} /> Create storage group
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Storage Group', sortable: true },
            { key: 'volumes', label: 'Volumes', render: (r) => (r.volumes || []).length },
            { key: 'slo', label: 'SLO', sortable: true, render: (r) => r.slo || '—' },
            { key: 'host_io_limit', label: 'IOPS limit', render: (r) => r.host_io_limit || 'Unlimited' },
            { key: 'array', label: 'Array', sortable: true },
            { key: 'actions', label: 'Actions', render: (r) => (
              <button type="button" className="de-btn-sm" onClick={(e) => {
                e.stopPropagation()
                run(() => dellemcApi.setHostIoLimit(sessionId, r.name, 10000), 'Host I/O limit set')
              }}>Set 10k IOPS</button>
            ) },
          ]} rows={st.storage_groups || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'volumes') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Volumes</h2>
            <button type="button" className="de-btn-primary flex items-center gap-1" onClick={() => setVolModal(true)}>
              <Plus size={14} /> Create volume
            </button>
          </div>
          {broken.unmapped_volume && (
            <div className="de-panel text-sm text-amber-800 bg-amber-50 border border-amber-200 px-3 py-2 rounded flex items-center gap-2">
              <AlertTriangle size={14} /> Volume <strong>{broken.unmapped_volume}</strong> is unmapped — provision it into a storage group.
            </div>
          )}
          <SimDataTable columns={[
            { key: 'id', label: 'Volume', sortable: true },
            { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GB` },
            { key: 'storage_group', label: 'Storage Group', sortable: true, render: (r) => r.storage_group || '—' },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'Ready' ? 'success' : 'warning'} label={r.status} /> },
            { key: 'actions', label: 'Actions', render: (r) => (
              <div className="flex gap-1">
                {r.status !== 'Ready' && (
                  <button type="button" className="de-btn-sm" onClick={(e) => { e.stopPropagation(); setMapTarget(r.id); setMapSg((st.storage_groups || [])[0]?.name || '') }}>
                    <Link2 size={11} /> Map
                  </button>
                )}
                <button type="button" className="de-btn-sm" onClick={(e) => {
                  e.stopPropagation()
                  run(() => dellemcApi.createSnapshot(sessionId, r.id), 'Snapshot created')
                }}>Snap</button>
                <button type="button" className="de-btn-sm" onClick={(e) => {
                  e.stopPropagation()
                  run(() => dellemcApi.expandVolume(sessionId, r.id, (r.size_gb || 100) + 100), 'Volume expanded')
                }}>Expand</button>
              </div>
            ) },
          ]} rows={st.volumes || []} searchKeys={['id']} />
        </div>
      )
    }
    if (nav === 'snapshots') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Snapshots</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Snapshot', sortable: true },
            { key: 'volume_id', label: 'Volume', sortable: true },
            { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GB` },
            { key: 'created', label: 'Created', sortable: true },
          ]} rows={st.snapshots || []} searchKeys={['name', 'volume_id']} />
        </div>
      )
    }
    if (nav === 'hosts') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Hosts</h2>
            <button type="button" className="de-btn-primary flex items-center gap-1" onClick={() => setHostModal(true)}>
              <Plus size={14} /> Register host
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Host', sortable: true },
            { key: 'host_type', label: 'Type', sortable: true },
            { key: 'initiators', label: 'Initiators', render: (r) => <span className="font-mono text-xs">{(r.initiators || []).join(', ')}</span> },
          ]} rows={st.hosts || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'masking-views') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Masking Views</h2>
            <button type="button" className="de-btn-primary flex items-center gap-1" onClick={() => setMvModal(true)}>
              <Plus size={14} /> Create masking view
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Masking View', sortable: true },
            { key: 'storage_group', label: 'Storage Group', sortable: true },
            { key: 'host', label: 'Host', sortable: true },
            { key: 'port_group', label: 'Port Group', sortable: true },
            { key: 'actions', label: 'Actions', render: (r) => (
              <button type="button" className="de-btn-sm de-btn-outline" onClick={(e) => {
                e.stopPropagation()
                run(() => dellemcApi.deleteMaskingView(sessionId, r.name), 'Masking view deleted')
              }}>Delete</button>
            ) },
          ]} rows={st.masking_views || []} searchKeys={['name', 'host']} />
        </div>
      )
    }
    if (nav === 'srdf') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">SRDF Groups</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'RDF Group', sortable: true },
            { key: 'local_volume', label: 'Local', sortable: true },
            { key: 'remote_volume', label: 'Remote', sortable: true },
            { key: 'mode', label: 'Mode', sortable: true },
            { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'Consistent' ? 'success' : 'warning'} label={r.state} /> },
            { key: 'actions', label: 'Actions', render: (r) => r.state !== 'FailedOver' && (
              <button type="button" className="de-btn-sm" onClick={(e) => {
                e.stopPropagation()
                run(() => dellemcApi.failoverSrdf(sessionId, r.name), 'SRDF failover complete')
              }}>Failover</button>
            ) },
          ]} rows={st.srdf || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'ports') {
      return <SimDataTable columns={[
        { key: 'id', label: 'Port', sortable: true },
        { key: 'director', label: 'Director', sortable: true },
        { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'online' ? 'success' : 'error'} label={r.status} /> },
        { key: 'speed', label: 'Speed', sortable: true },
      ]} rows={st.ports || []} searchKeys={['id', 'director']} />
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
    <div className={simPanelRoot(embedded, 'de-shell sim-product')}>
      <LabChromeBar title={`Unisphere · ${st?.summary?.version || 'PowerMax 10.2'}`} subtitle={scenario?.title || slug}
        accent={ACCENT} className="lab-chrome-bar !bg-[#0072c6]" {...chromeProps}>
        {onToggleTerminal && (
          <button type="button" className="lab-chrome-btn flex items-center gap-1" onClick={onToggleTerminal}>
            <Terminal size={13} /> {simTerminalOpen ? 'Hide terminal' : 'Terminal'}
          </button>
        )}
      </LabChromeBar>

      {goal.objective && (
        <div className="sim-goal-banner">
          <AlertTriangle size={14} className="shrink-0" />
          <span><strong>{goal.title}:</strong> {goal.objective}</span>
        </div>
      )}

      <div className="px-4 py-2 bg-[#023a68] border-b border-black/20 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-300" />
        <span className="text-xs text-slate-400">{st?.session?.user || 'admin'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#04213f] de-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#f2f5f9]">{renderContent()}</main>
      </div>

      <SimModal open={sgModal} onClose={() => setSgModal(false)} title="Create Storage Group"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setSgModal(false)}>Cancel</button>
          <button type="button" className="de-btn-primary" disabled={busy} onClick={() => {
            run(() => dellemcApi.createStorageGroup(sessionId, sgName), 'Storage group created')
            setSgModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Storage group name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={sgName} onChange={(e) => setSgName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={volModal} onClose={() => setVolModal(false)} title="Create Volume"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setVolModal(false)}>Cancel</button>
          <button type="button" className="de-btn-primary" disabled={busy} onClick={() => {
            run(() => dellemcApi.createVolume(sessionId, volSize, volSg || undefined), 'Volume created')
            setVolModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Size (GB)
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={volSize} onChange={(e) => setVolSize(Number(e.target.value))} />
        </label>
        <label className="block text-sm mt-3">Storage group (optional)
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={volSg} onChange={(e) => setVolSg(e.target.value)}>
            <option value="">— Unmapped —</option>
            {(st.storage_groups || []).map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
      </SimModal>

      <SimModal open={!!mapTarget} onClose={() => setMapTarget(null)} title={`Map Volume ${mapTarget || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setMapTarget(null)}>Cancel</button>
          <button type="button" className="de-btn-primary" disabled={busy} onClick={() => {
            run(() => dellemcApi.mapVolume(sessionId, mapTarget, mapSg), 'Volume mapped')
            setMapTarget(null)
          }}>Map</button>
        </>}>
        <label className="block text-sm">Storage group
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={mapSg} onChange={(e) => setMapSg(e.target.value)}>
            {(st.storage_groups || []).map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
      </SimModal>

      <SimModal open={hostModal} onClose={() => setHostModal(false)} title="Register Host"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setHostModal(false)}>Cancel</button>
          <button type="button" className="de-btn-primary" disabled={busy} onClick={() => {
            run(() => dellemcApi.addHost(sessionId, hostName, ['10:00:00:00:c9:aa:bb:99']), 'Host registered')
            setHostModal(false)
          }}>Register</button>
        </>}>
        <label className="block text-sm">Host name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={hostName} onChange={(e) => setHostName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={mvModal} onClose={() => setMvModal(false)} title="Create Masking View"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setMvModal(false)}>Cancel</button>
          <button type="button" className="de-btn-primary" disabled={busy} onClick={() => {
            run(() => dellemcApi.createMaskingView(sessionId, mvName, mvSg, mvHost, mvPg), 'Masking view created')
            setMvModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={mvName} onChange={(e) => setMvName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Storage group
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={mvSg} onChange={(e) => setMvSg(e.target.value)}>
            <option value="">Select…</option>
            {(st.storage_groups || []).map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
        <label className="block text-sm mt-3">Host
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={mvHost} onChange={(e) => setMvHost(e.target.value)}>
            <option value="">Select…</option>
            {(st.hosts || []).map((h) => <option key={h.name} value={h.name}>{h.name}</option>)}
          </select>
        </label>
        <label className="block text-sm mt-3">Port group
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={mvPg} onChange={(e) => setMvPg(e.target.value)}>
            <option value="">Select…</option>
            {(st.port_groups || []).map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
          </select>
        </label>
      </SimModal>
    </div>
  )
}
