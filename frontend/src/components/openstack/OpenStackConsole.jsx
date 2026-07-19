import { useState } from 'react'
import { openstackApi } from '../../api/openstack'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Cloud, Server, Network, HardDrive, Plus, Play, Square, RotateCw,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import '../../styles/sim-products.css'
import './openstack.css'

const OS_LAB_USER = 'admin'
const OS_LAB_PASS = 'lab123'
const ACCENT = '#cf2a27'

const SIDEBAR = [
  { key: 'overview', label: 'Overview', icon: Cloud },
  { key: 'instances', label: 'Instances', icon: Server },
  { key: 'networks', label: 'Networks', icon: Network },
  { key: 'volumes', label: 'Volumes', icon: HardDrive },
]

const FLAVOR_OPTIONS = [
  { value: 'm1.tiny', label: 'm1.tiny (1 vCPU, 1 GiB)' },
  { value: 'm1.small', label: 'm1.small (1 vCPU, 2 GiB)' },
  { value: 'm1.medium', label: 'm1.medium (2 vCPU, 4 GiB)' },
  { value: 'm1.large', label: 'm1.large (4 vCPU, 8 GiB)' },
  { value: 'm1.xlarge', label: 'm1.xlarge (8 vCPU, 16 GiB)' },
]

function statusTone(status) {
  if (status === 'ACTIVE') return 'success'
  if (status === 'SHUTOFF' || status === 'ERROR') return 'error'
  return 'pending'
}

export default function OpenStackConsole({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, openstackApi)
  const [nav, setNav] = useState('overview')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [launchOpen, setLaunchOpen] = useState(false)
  const [newName, setNewName] = useState('app-02')
  const [newFlavor, setNewFlavor] = useState('m1.small')
  const [attachTarget, setAttachTarget] = useState(null)

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const instances = st.instances || []
  const networks = st.networks || []
  const volumes = st.volumes || []
  const project = st.project || {}

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const breadcrumbs = [
    { label: project.name || 'Project', onClick: () => setNav('overview') },
  ]
  if (nav !== 'overview') {
    breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })
  }

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === OS_LAB_USER && loginPass === OS_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        run(() => openstackApi.login(sessionId, OS_LAB_USER), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${OS_LAB_USER} / ${OS_LAB_PASS}`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#1a1a1a]')}>
        <LabChromeBar title="OpenStack Horizon" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: ACCENT }}>
              <Cloud size={18} /> Sign in to Horizon
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Authenticate to the {project.name || 'fixitlab-prod'} project.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">User Name</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm" placeholder={OS_LAB_USER} />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm" />
              </div>
              {loginError && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>}
              <button type="submit" disabled={busy} className="os-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(OS_LAB_USER); setLoginPass(OS_LAB_PASS); setLoginError('') }}
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
          {goal.summary && (
            <div className="text-sm bg-amber-50 border border-amber-200 text-amber-900 rounded px-3 py-2">{goal.summary}</div>
          )}
          <div className="grid sm:grid-cols-3 gap-3">
            {[
              { label: 'Instances', value: instances.length, go: 'instances' },
              { label: 'Networks', value: networks.length, go: 'networks' },
              { label: 'Volumes', value: volumes.length, go: 'volumes' },
            ].map((c) => (
              <button key={c.label} type="button" onClick={() => setNav(c.go)}
                className="text-left bg-white border border-slate-200 rounded p-4 hover:border-red-300">
                <div className="text-2xl font-semibold" style={{ color: ACCENT }}>{c.value}</div>
                <div className="text-xs text-slate-500 mt-1">{c.label}</div>
              </button>
            ))}
          </div>
        </div>
      )
    }
    if (nav === 'instances') {
      return (
        <div>
          <div className="flex justify-end mb-3">
            <button type="button" className="os-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
              onClick={() => setLaunchOpen(true)} disabled={busy}>
              <Plus size={14} /> Launch Instance
            </button>
          </div>
          <SimDataTable
            searchKeys={['name', 'private_ip']}
            columns={[
              { key: 'name', label: 'Instance Name', sortable: true },
              { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={statusTone(r.status)} label={r.status} /> },
              { key: 'flavor', label: 'Flavor', sortable: true },
              { key: 'private_ip', label: 'IP Address', sortable: true },
              { key: 'image', label: 'Image' },
              {
                key: 'actions', label: 'Actions',
                render: (r) => (
                  <div className="flex gap-1">
                    <button type="button" title="Start" className="p-1 rounded hover:bg-slate-100"
                      onClick={(e) => { e.stopPropagation(); run(() => openstackApi.startInstance(sessionId, r.name), 'Started') }} disabled={busy}>
                      <Play size={14} />
                    </button>
                    <button type="button" title="Stop" className="p-1 rounded hover:bg-slate-100"
                      onClick={(e) => { e.stopPropagation(); run(() => openstackApi.stopInstance(sessionId, r.name), 'Stopped') }} disabled={busy}>
                      <Square size={14} />
                    </button>
                    <button type="button" title="Resize to m1.large" className="p-1 rounded hover:bg-slate-100"
                      onClick={(e) => { e.stopPropagation(); run(() => openstackApi.resizeInstance(sessionId, r.name, 'm1.large'), 'Resized') }} disabled={busy}>
                      <RotateCw size={14} />
                    </button>
                  </div>
                ),
              },
            ]}
            rows={instances}
          />
        </div>
      )
    }
    if (nav === 'networks') {
      return (
        <SimDataTable
          searchKeys={['name']}
          columns={[
            { key: 'name', label: 'Network Name', sortable: true },
            { key: 'status', label: 'Status' },
            { key: 'subnets', label: 'Subnets', render: (r) => (r.subnets || []).map((s) => s.cidr).join(', ') },
          ]}
          rows={networks}
        />
      )
    }
    return (
      <SimDataTable
        searchKeys={['name']}
        columns={[
          { key: 'name', label: 'Volume Name', sortable: true },
          { key: 'size_gb', label: 'Size (GiB)', sortable: true },
          { key: 'status', label: 'Status' },
          { key: 'device', label: 'Device', render: (r) => r.device || '—' },
          {
            key: 'actions', label: 'Actions',
            render: (r) => r.status === 'available' ? (
              <button type="button" className="text-xs text-red-700 underline"
                onClick={(e) => { e.stopPropagation(); setAttachTarget(r) }} disabled={busy}>Attach</button>
            ) : null,
          },
        ]}
        rows={volumes}
      />
    )
  }

  return (
    <div className={simPanelRoot(embedded, 'bg-[#f5f5f5] text-slate-900')}>
      <LabChromeBar title="OpenStack Horizon" subtitle={scenario?.title || goal.title || slug} accent={ACCENT} {...chromeProps} />
      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#2c2c2c] text-white" />
        <main className="flex-1 overflow-auto p-5 bg-[#f5f5f5]">
          <SimBreadcrumbs items={breadcrumbs} />
          {renderContent()}
        </main>
      </div>

      <SimModal open={launchOpen} onClose={() => setLaunchOpen(false)} title="Launch Instance"
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setLaunchOpen(false)}>Cancel</button>
          <button type="button" className="os-btn-primary px-3 py-1.5 text-sm" disabled={busy}
            onClick={() => {
              run(() => openstackApi.createInstance(sessionId, { name: newName, flavor: newFlavor, image: 'ubuntu-22.04', network: 'private' }), 'Launching')
              setLaunchOpen(false)
            }}>Launch</button>
        </>}>
        <label className="block text-sm text-slate-200">Instance Name
          <input className="mt-1 w-full border rounded px-2 py-1.5 text-sm text-slate-900" value={newName} onChange={(e) => setNewName(e.target.value)} />
        </label>
        <label className="block text-sm text-slate-200 mt-3">Flavor
          <select className="mt-1 w-full border rounded px-2 py-1.5 text-sm text-slate-900" value={newFlavor} onChange={(e) => setNewFlavor(e.target.value)}>
            {FLAVOR_OPTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>
      </SimModal>

      <SimModal open={!!attachTarget} onClose={() => setAttachTarget(null)} title={`Attach ${attachTarget?.name || ''}`}>
        <p className="text-sm text-slate-300 mb-3">Select the instance to attach this volume to.</p>
        <div className="space-y-2">
          {instances.map((inst) => (
            <button key={inst.id} type="button" className="w-full text-left border border-slate-600 rounded px-3 py-2 text-sm text-slate-100 hover:bg-slate-800"
              disabled={busy}
              onClick={() => {
                run(() => openstackApi.attachVolume(sessionId, attachTarget.name, inst.name), 'Volume attached')
                setAttachTarget(null)
              }}>
              {inst.name} · {inst.private_ip} · {inst.status}
            </button>
          ))}
        </div>
      </SimModal>
    </div>
  )
}
