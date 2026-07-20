import { useState } from 'react'
import { dockerApi } from '../../api/docker'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Container, Image, Network, HardDrive, Layers,
  Play, Square, Trash2, RotateCw, Plus, Download,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import '../../styles/sim-products.css'
import './docker.css'

const DOCKER_LAB_USER = 'admin'
const DOCKER_LAB_PASS = 'lab123'
const ACCENT = '#2496ed'

const SIDEBAR = [
  { key: 'containers', label: 'Containers', icon: Container },
  { key: 'images', label: 'Images', icon: Image },
  { key: 'networks', label: 'Networks', icon: Network },
  { key: 'volumes', label: 'Volumes', icon: HardDrive },
  { key: 'compose', label: 'Compose', icon: Layers },
]

function containerTone(state) {
  if (state === 'running') return 'success'
  if (state === 'exited' || state === 'dead') return 'error'
  return 'pending'
}

function composeTone(status) {
  if (status === 'running') return 'success'
  if (status === 'exited') return 'error'
  return 'pending'
}

export default function DockerConsole({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, dockerApi)
  const [nav, setNav] = useState('containers')
  const [loggedIn, setLoggedIn] = useState(false)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [pullOpen, setPullOpen] = useState(false)
  const [pullImage, setPullImage] = useState('nginx:latest')
  const [netOpen, setNetOpen] = useState(false)
  const [newNet, setNewNet] = useState('')
  const [volOpen, setVolOpen] = useState(false)
  const [newVol, setNewVol] = useState('')

  const daemon = state?.daemon || {}
  const summary = state?.summary || {}
  const containers = daemon.containers || []
  const images = daemon.images || []
  const networks = daemon.networks || []
  const volumes = daemon.volumes || []
  const composeGroups = daemon.compose_services || []

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const breadcrumbs = [
    { label: 'Docker Host', onClick: () => setNav('containers') },
  ]
  if (nav !== 'containers') {
    breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })
  }

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === DOCKER_LAB_USER && loginPass === DOCKER_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        setLoggedIn(true)
        run(() => dockerApi.login(sessionId, DOCKER_LAB_USER), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${DOCKER_LAB_USER} / ${DOCKER_LAB_PASS}`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0d1117]')}>
        <LabChromeBar title="Docker Host Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: ACCENT }}>
              <Container size={18} /> Sign in to Docker Host
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Authenticate to manage containers on this host.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm" placeholder={DOCKER_LAB_USER} />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm" />
              </div>
              {loginError && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>}
              <button type="submit" disabled={busy} className="docker-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(DOCKER_LAB_USER); setLoginPass(DOCKER_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const flatCompose = composeGroups.flatMap((g) =>
    (g.services || []).map((svc) => ({ ...svc, project: g.project })),
  )

  const renderContent = () => {
    if (nav === 'containers') {
      return (
        <div>
          <div className="grid sm:grid-cols-3 gap-3 mb-4">
            {[
              { label: 'Running', value: summary.containers_running ?? 0 },
              { label: 'Stopped', value: summary.containers_stopped ?? 0 },
              { label: 'Disk usage', value: `${summary.disk_usage_gb ?? 0} GB` },
            ].map((c) => (
              <div key={c.label} className="bg-white border border-slate-200 rounded p-3">
                <div className="text-xl font-semibold" style={{ color: ACCENT }}>{c.value}</div>
                <div className="text-xs text-slate-500 mt-0.5">{c.label}</div>
              </div>
            ))}
          </div>
          <SimDataTable
            searchKeys={['shortName', 'image', 'status']}
            columns={[
              { key: 'shortName', label: 'Name', sortable: true },
              { key: 'image', label: 'Image', sortable: true },
              {
                key: 'state', label: 'Status',
                render: (r) => <SimStatusBadge status={containerTone(r.state)} label={r.status || r.state} />,
              },
              {
                key: 'ports', label: 'Ports',
                render: (r) => (r.ports || []).map((p) => `${p.host || ''}:${p.container}/${p.protocol || 'tcp'}`).join(', ') || '—',
              },
              { key: 'cpu', label: 'CPU %', render: (r) => r.cpuPercent ?? 0 },
              { key: 'mem', label: 'Mem', render: (r) => `${r.memUsageMb ?? 0} / ${r.memLimitMb ?? 0} MB` },
              {
                key: 'actions', label: 'Actions',
                render: (r) => (
                  <div className="flex gap-1 flex-wrap">
                    <button type="button" title="Start" className="p-1 rounded hover:bg-slate-100" disabled={busy || r.state === 'running'}
                      onClick={(e) => { e.stopPropagation(); run(() => dockerApi.startContainer(sessionId, r.shortName), 'Started') }}>
                      <Play size={14} />
                    </button>
                    <button type="button" title="Stop" className="p-1 rounded hover:bg-slate-100" disabled={busy || r.state !== 'running'}
                      onClick={(e) => { e.stopPropagation(); run(() => dockerApi.stopContainer(sessionId, r.shortName), 'Stopped') }}>
                      <Square size={14} />
                    </button>
                    <button type="button" title="Restart" className="p-1 rounded hover:bg-slate-100" disabled={busy}
                      onClick={(e) => { e.stopPropagation(); run(() => dockerApi.restartContainer(sessionId, r.shortName), 'Restarted') }}>
                      <RotateCw size={14} />
                    </button>
                    <button type="button" title="Remove" className="p-1 rounded hover:bg-slate-100" disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation()
                        run(() => dockerApi.removeContainer(sessionId, r.shortName, r.state === 'running'), 'Removed')
                      }}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                ),
              },
            ]}
            rows={containers}
          />
        </div>
      )
    }

    if (nav === 'images') {
      return (
        <div>
          <div className="flex justify-end mb-3">
            <button type="button" className="docker-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
              onClick={() => setPullOpen(true)} disabled={busy}>
              <Download size={14} /> Pull image
            </button>
          </div>
          <SimDataTable
            searchKeys={['repoTag', 'repository', 'tag']}
            columns={[
              { key: 'repoTag', label: 'Repository:Tag', sortable: true, render: (r) => r.repoTag || `${r.repository}:${r.tag}` },
              { key: 'id', label: 'Image ID', render: (r) => (r.id || '').slice(0, 12) },
              { key: 'sizeMb', label: 'Size (MB)', sortable: true },
              { key: 'dangling', label: 'Dangling', render: (r) => (r.dangling ? 'yes' : '—') },
              {
                key: 'actions', label: 'Actions',
                render: (r) => (
                  <button type="button" className="docker-btn-ghost" disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation()
                      run(() => dockerApi.removeImage(sessionId, r.repoTag || `${r.repository}:${r.tag}`, !!r.dangling), 'Image removed')
                    }}>
                    <Trash2 size={12} className="inline mr-0.5" />Remove
                  </button>
                ),
              },
            ]}
            rows={images}
          />
        </div>
      )
    }

    if (nav === 'networks') {
      return (
        <div>
          <div className="flex justify-end mb-3">
            <button type="button" className="docker-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
              onClick={() => setNetOpen(true)} disabled={busy}>
              <Plus size={14} /> Create network
            </button>
          </div>
          <SimDataTable
            searchKeys={['name', 'driver']}
            columns={[
              { key: 'name', label: 'Name', sortable: true },
              { key: 'driver', label: 'Driver' },
              { key: 'scope', label: 'Scope' },
              { key: 'id', label: 'ID', render: (r) => (r.id || '').slice(0, 12) },
              {
                key: 'actions', label: 'Actions',
                render: (r) => (['bridge', 'host', 'none'].includes(r.name) ? null : (
                  <button type="button" className="docker-btn-ghost" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => dockerApi.removeNetwork(sessionId, r.name), 'Network removed') }}>
                    <Trash2 size={12} className="inline mr-0.5" />Remove
                  </button>
                )),
              },
            ]}
            rows={networks}
          />
        </div>
      )
    }

    if (nav === 'volumes') {
      return (
        <div>
          <div className="flex justify-end gap-2 mb-3">
            <button type="button" className="docker-btn-ghost" disabled={busy}
              onClick={() => run(() => dockerApi.pruneVolumes(sessionId), 'Pruned')}>
              Prune dangling
            </button>
            <button type="button" className="docker-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
              onClick={() => setVolOpen(true)} disabled={busy}>
              <Plus size={14} /> Create volume
            </button>
          </div>
          <SimDataTable
            searchKeys={['name', 'driver']}
            columns={[
              { key: 'name', label: 'Name', sortable: true },
              { key: 'driver', label: 'Driver' },
              { key: 'sizeMb', label: 'Size (MB)', sortable: true },
              { key: 'dangling', label: 'Dangling', render: (r) => (r.dangling ? 'yes' : '—') },
              {
                key: 'actions', label: 'Actions',
                render: (r) => (
                  <button type="button" className="docker-btn-ghost" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => dockerApi.removeVolume(sessionId, r.name), 'Volume removed') }}>
                    <Trash2 size={12} className="inline mr-0.5" />Remove
                  </button>
                ),
              },
            ]}
            rows={volumes}
          />
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {composeGroups.map((g) => (
          <div key={g.project} className="bg-white border border-slate-200 rounded p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-800">Project: {g.project}</h3>
              <div className="flex gap-2">
                <button type="button" className="docker-btn-primary inline-flex items-center gap-1 px-2.5 py-1 text-xs" disabled={busy}
                  onClick={() => run(() => dockerApi.composeUp(sessionId, g.project), 'Compose up')}>
                  <Play size={12} /> Up
                </button>
                <button type="button" className="docker-btn-ghost" disabled={busy}
                  onClick={() => run(() => dockerApi.composeDown(sessionId, g.project), 'Compose down')}>
                  <Square size={12} className="inline mr-0.5" />Down
                </button>
                <button type="button" className="docker-btn-ghost" disabled={busy}
                  onClick={() => run(() => dockerApi.composeRestart(sessionId, g.project), 'Compose restart')}>
                  <RotateCw size={12} className="inline mr-0.5" />Restart
                </button>
              </div>
            </div>
            <SimDataTable
              searchKeys={['name', 'image', 'status']}
              columns={[
                { key: 'name', label: 'Service', sortable: true },
                { key: 'image', label: 'Image' },
                {
                  key: 'status', label: 'Status',
                  render: (r) => <SimStatusBadge status={composeTone(r.status)} label={`${r.status} (${r.runningReplicas ?? 0}/${r.replicas ?? 1})`} />,
                },
                {
                  key: 'actions', label: 'Actions',
                  render: (r) => (
                    <button type="button" className="docker-btn-ghost" disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation()
                        run(() => dockerApi.composeUp(sessionId, g.project, r.name), 'Service up')
                      }}>
                      Start
                    </button>
                  ),
                },
              ]}
              rows={g.services || []}
            />
          </div>
        ))}
        {flatCompose.length === 0 && (
          <p className="text-sm text-slate-500">No Compose projects on this host.</p>
        )}
      </div>
    )
  }

  return (
    <div className={simPanelRoot(embedded, 'bg-[#f0f4f8] text-slate-900')}>
      <LabChromeBar title="Docker Host Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#1d252d] text-white" />
        <main className="flex-1 overflow-auto p-5 bg-[#f0f4f8]">
          <SimBreadcrumbs items={breadcrumbs} />
          {renderContent()}
        </main>
      </div>

      <SimModal open={pullOpen} onClose={() => setPullOpen(false)} title="Pull image"
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setPullOpen(false)}>Cancel</button>
          <button type="button" className="docker-btn-primary px-3 py-1.5 text-sm" disabled={busy || !pullImage.trim()}
            onClick={() => {
              run(() => dockerApi.pullImage(sessionId, pullImage.trim()), 'Pull complete')
              setPullOpen(false)
            }}>Pull</button>
        </>}>
        <label className="block text-sm text-slate-200">Image
          <input className="mt-1 w-full border rounded px-2 py-1.5 text-sm text-slate-900"
            value={pullImage} onChange={(e) => setPullImage(e.target.value)} placeholder="nginx:latest" />
        </label>
      </SimModal>

      <SimModal open={netOpen} onClose={() => setNetOpen(false)} title="Create network"
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setNetOpen(false)}>Cancel</button>
          <button type="button" className="docker-btn-primary px-3 py-1.5 text-sm" disabled={busy || !newNet.trim()}
            onClick={() => {
              run(() => dockerApi.createNetwork(sessionId, newNet.trim()), 'Network created')
              setNetOpen(false)
              setNewNet('')
            }}>Create</button>
        </>}>
        <label className="block text-sm text-slate-200">Name
          <input className="mt-1 w-full border rounded px-2 py-1.5 text-sm text-slate-900"
            value={newNet} onChange={(e) => setNewNet(e.target.value)} placeholder="app-net" />
        </label>
      </SimModal>

      <SimModal open={volOpen} onClose={() => setVolOpen(false)} title="Create volume"
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setVolOpen(false)}>Cancel</button>
          <button type="button" className="docker-btn-primary px-3 py-1.5 text-sm" disabled={busy || !newVol.trim()}
            onClick={() => {
              run(() => dockerApi.createVolume(sessionId, newVol.trim()), 'Volume created')
              setVolOpen(false)
              setNewVol('')
            }}>Create</button>
        </>}>
        <label className="block text-sm text-slate-200">Name
          <input className="mt-1 w-full border rounded px-2 py-1.5 text-sm text-slate-900"
            value={newVol} onChange={(e) => setNewVol(e.target.value)} placeholder="app-data" />
        </label>
      </SimModal>
    </div>
  )
}
