import { useEffect, useRef, useState } from 'react'
import { commvaultApi } from '../../api/commvault'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Play, RotateCcw, HardDrive, Users, Briefcase, Server, AlertTriangle,
  Database, Shield, Plus, Terminal, CheckCircle2, XCircle, Clock, Loader2,
  Boxes, Cloud, FileText, Lock,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import { renderCommvaultV2Page } from './CommvaultV2Panels'
import '../../styles/sim-products.css'
import './commvault.css'

/* SIMULATED-CREDENTIAL: lab-console flavour, not a real secret. Shown to the
   learner on screen (with an autofill button) so the fake console feels real, and
   the gate is bypassed entirely once a provisioned lab session exists. Grants no
   access to anything. Secret scanners should allowlist this marker rather than
   flagging these lines. See docs/AUDIT_2026_08_TODO.md §Y2e. */
const CV_LAB_USER = 'lab_commvault'
const CV_LAB_PASS = 'lab_commvault@123'

const SIDEBAR = [
  { key: 'clients', label: 'Client Computers', icon: Server },
  { key: 'plans', label: 'Plans', icon: FileText },
  { key: 'k8s', label: 'Kubernetes', icon: Boxes },
  { key: 'saas', label: 'SaaS apps', icon: Cloud },
  { key: 'storage-policies', label: 'Storage Policies', icon: Shield },
  { key: 'schedules', label: 'Schedules', icon: Clock },
  { key: 'job-controller', label: 'Job Controller', icon: Briefcase },
  { key: 'aux-copies', label: 'Aux Copies', icon: Database },
  { key: 'media-agents', label: 'Media Agents', icon: Database },
  { key: 'libraries', label: 'Libraries', icon: HardDrive },
  { key: 'ransomware', label: 'Ransomware', icon: Lock },
  { key: 'reports', label: 'Reports', icon: FileText },
  { key: 'activity', label: 'Activity Log', icon: Users },
]

const JOB_ICON = {
  pending: <Clock size={13} className="text-amber-500" />,
  running: <Loader2 size={13} className="text-sky-500 animate-spin" />,
  completed: <CheckCircle2 size={13} className="text-emerald-500" />,
  failed: <XCircle size={13} className="text-red-500" />,
  killed: <XCircle size={13} className="text-slate-400" />,
}

function JobProgress({ job }) {
  if (job.status === 'pending') return <span className="text-[11px] text-amber-600">Queued…</span>
  if (job.status === 'completed' || job.status === 'failed' || job.status === 'killed') {
    return <SimStatusBadge status={job.status} />
  }
  return (
    <div className="w-32">
      <div className="h-1.5 rounded bg-slate-200 overflow-hidden">
        <div className="h-full rounded bg-sky-500 transition-all duration-500" style={{ width: `${job.progress || 0}%` }} />
      </div>
      <div className="text-[10px] text-slate-500 mt-0.5">{job.progress || 0}%</div>
    </div>
  )
}

export default function CommvaultSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run, refresh } = useSimSession(sessionId, slug, commvaultApi)
  const [nav, setNav] = useState('clients')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [backupModal, setBackupModal] = useState(null)
  const [restoreModal, setRestoreModal] = useState(null)
  const [subclientModal, setSubclientModal] = useState(false)
  const [scName, setScName] = useState('default')
  const [scPolicy, setScPolicy] = useState('Gold-Retention-30d')
  const [scContent, setScContent] = useState('/data')
  const [clientModal, setClientModal] = useState(false)
  const [clientName, setClientName] = useState('new-client')
  const [clientOs, setClientOs] = useState('Linux')
  const [clientIp, setClientIp] = useState('')

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}
  const jobs = st.jobs || []
  const TERMINAL = ['completed', 'failed', 'killed']
  const hasLiveJob = jobs.some((j) => !TERMINAL.includes(j.status))

  const refreshRef = useRef(refresh)
  refreshRef.current = refresh
  useEffect(() => {
    if (!loggedIn || !hasLiveJob) return undefined
    // A 1s poll is a network round-trip + full re-render each tick, so stop it
    // entirely while the tab is hidden instead of burning it in the background.
    // Backup/restore jobs here are long-running, so the resume path MUST refresh
    // immediately before restarting the timer — a job routinely reaches a
    // terminal status while hidden, and only restarting the interval would keep
    // showing a stale "Running" badge. The hasLiveJob guard above still owns the
    // real teardown: once every job is terminal the effect re-runs and returns
    // early, removing the listener along with the timer.
    let t = null
    const stop = () => { if (t) { clearInterval(t); t = null } }
    const start = () => { if (!t) t = setInterval(() => { refreshRef.current?.() }, 1000) }
    const onVis = () => {
      if (document.visibilityState === 'visible') { refreshRef.current?.(); start() } else stop()
    }
    // refreshRef (not refresh) is deliberate: the effect must not re-run — and
    // therefore must not drop the listener — every time refresh is re-created.
    if (document.visibilityState === 'visible') start()
    document.addEventListener('visibilitychange', onVis)
    return () => { stop(); document.removeEventListener('visibilitychange', onVis) }
  }, [loggedIn, hasLiveJob])

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
    vmwareHref,
  }

  const breadcrumbs = [{ label: st?.summary?.commcell || 'CommCell', onClick: () => setNav('clients') }]
  if (nav !== 'clients') breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === CV_LAB_USER && loginPass === CV_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        run(() => commvaultApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${CV_LAB_USER} / ${CV_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0c1930]')}>
        <LabChromeBar title="Commvault Command Center" subtitle={scenario?.title || slug} accent="#0b3d78" {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold bg-[#0b3d78] flex items-center gap-2">
              <Database size={18} /> CommCell Console
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Sign in to the Commvault CommCell training instance.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={CV_LAB_USER}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-[#0b3d78]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} autoComplete="current-password"
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-[#0b3d78]" />
              </div>
              {loginError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>
              )}
              <button type="submit" disabled={busy}
                className="cv-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(CV_LAB_USER); setLoginPass(CV_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{CV_LAB_USER}</span> / <span className="font-mono text-slate-700">{CV_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const renderContent = () => {
    const v2 = renderCommvaultV2Page({ nav, st, sessionId, busy, run })
    if (v2) return v2
    if (nav === 'clients') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Client Computers</h2>
            <button type="button" className="cv-btn-primary flex items-center gap-1" onClick={() => setClientModal(true)}>
              <Plus size={14} /> Add client
            </button>
          </div>
          {broken.missing_client && (
            <div className="cv-panel text-sm text-amber-800 bg-amber-50 border border-amber-200 px-3 py-2 rounded">
              Objective: register a new client with the CommCell.
            </div>
          )}
          <SimDataTable columns={[
            { key: 'name', label: 'Client', sortable: true },
            { key: 'source', label: 'Discovered via', sortable: true },
            { key: 'os', label: 'OS', sortable: true },
            { key: 'ip', label: 'IP' },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'online' ? 'success' : 'error'} label={r.status} /> },
            { key: 'backup_health', label: 'Protection', render: (r) => (
              <SimStatusBadge
                status={r.backup_health === 'protected' ? 'success' : r.backup_health === 'overdue' ? 'warning' : 'error'}
                label={r.backup_health}
              />
            ) },
            { key: 'actions', label: 'Actions', render: (r) => (
              <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                <button type="button" className="cv-btn-sm" onClick={() => setBackupModal(r.name)}><Play size={11} /> Backup</button>
                <button type="button" className="cv-btn-sm cv-btn-outline" onClick={() => setRestoreModal(r.name)}><RotateCcw size={11} /> Restore</button>
              </div>
            ) },
          ]} rows={st.clients || []} searchKeys={['name', 'ip', 'os']} />
        </div>
      )
    }
    if (nav === 'storage-policies') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Storage Policies</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Storage Policy', sortable: true },
            { key: 'retention_days', label: 'Retention', sortable: true, render: (r) => `${r.retention_days} days` },
            { key: 'library', label: 'Library', sortable: true },
            { key: 'enabled', label: 'State', render: (r) => <SimStatusBadge status={r.enabled ? 'success' : 'disabled'} label={r.enabled ? 'Enabled' : 'Disabled'} /> },
            { key: 'actions', label: 'Actions', render: (r) => (
              <div className="flex gap-1">
                {!r.enabled && (
                  <button type="button" className="cv-btn-sm" onClick={(e) => { e.stopPropagation(); run(() => commvaultApi.enablePolicy(sessionId, r.name), 'Storage policy enabled') }}>
                    Enable
                  </button>
                )}
                <button type="button" className="cv-btn-sm cv-btn-outline" onClick={(e) => {
                  e.stopPropagation()
                  run(() => commvaultApi.setRetention(sessionId, r.name, (r.retention_days || 30) + 30), 'Retention updated')
                }}>
                  +30d retention
                </button>
              </div>
            ) },
          ]} rows={st.storage_policies || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'job-controller') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Job Controller</h2>
          <SimDataTable columns={[
            { key: 'id', label: 'Job ID', sortable: true },
            { key: 'kind', label: 'Type', sortable: true, render: (r) => <span className="capitalize">{r.kind}</span> },
            { key: 'subclient', label: 'Subclient', sortable: true },
            { key: 'type', label: 'Job Type', sortable: true },
            { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GB` },
            { key: 'status', label: 'Status', render: (r) => <div className="flex items-center gap-1.5">{JOB_ICON[r.status]}<JobProgress job={r} /></div> },
            { key: 'actions', label: 'Actions', render: (r) => !['completed', 'failed', 'killed'].includes(r.status) && (
              <button type="button" className="cv-btn-sm cv-btn-outline" onClick={(e) => {
                e.stopPropagation()
                run(() => commvaultApi.killJob(sessionId, r.id), 'Job killed')
              }}>Kill</button>
            ) },
          ]} rows={jobs} searchKeys={['subclient', 'kind']} emptyMessage="No jobs run yet — start a backup or restore from Client Computers." />
        </div>
      )
    }
    if (nav === 'schedules') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Schedules</h2>
            <button type="button" className="cv-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => commvaultApi.createSchedule(sessionId, {
                name: `Schedule-${Date.now().toString(36).slice(-4)}`,
                client: (st.clients || [])[0]?.name || 'web01',
                type: 'Incremental',
                cron: '0 2 * * *',
              }), 'Schedule created')}>
              <Plus size={14} /> Create schedule
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Schedule', sortable: true },
            { key: 'client', label: 'Client', sortable: true },
            { key: 'type', label: 'Type', sortable: true },
            { key: 'cron', label: 'Cron', sortable: true },
            { key: 'enabled', label: 'State', render: (r) => <SimStatusBadge status={r.enabled ? 'success' : 'disabled'} label={r.enabled ? 'Enabled' : 'Disabled'} /> },
            { key: 'actions', label: 'Actions', render: (r) => !r.enabled && (
              <button type="button" className="cv-btn-sm" onClick={(e) => {
                e.stopPropagation()
                run(() => commvaultApi.enableSchedule(sessionId, r.name), 'Schedule enabled')
              }}>Enable</button>
            ) },
          ]} rows={st.schedules || []} searchKeys={['name', 'client']} />
        </div>
      )
    }
    if (nav === 'aux-copies') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Auxiliary Copies</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Copy', sortable: true },
            { key: 'source_policy', label: 'Source policy', sortable: true },
            { key: 'dest_library', label: 'Destination', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'running' ? 'info' : 'success'} label={r.status} /> },
            { key: 'actions', label: 'Actions', render: (r) => (
              <button type="button" className="cv-btn-sm" onClick={(e) => {
                e.stopPropagation()
                run(() => commvaultApi.runAuxCopy(sessionId, r.name), 'Aux copy started')
              }}><Play size={11} /> Run</button>
            ) },
          ]} rows={st.aux_copies || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'media-agents') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Media Agents</h2>
            <button type="button" className="cv-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => commvaultApi.addMediaAgent(sessionId, `MA-${Date.now().toString(36).slice(-4)}`), 'Media Agent added')}>
              <Plus size={14} /> Add Media Agent
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Media Agent', sortable: true },
            { key: 'os', label: 'OS', sortable: true },
            { key: 'streams', label: 'Streams', sortable: true },
            { key: 'free_space_gb', label: 'Free (GB)', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'online' ? 'success' : 'error'} label={r.status} /> },
          ]} rows={st.media_agents || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'libraries') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Disk Libraries</h2>
            <button type="button" className="cv-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => commvaultApi.createLibrary(sessionId, `Lib-${Date.now().toString(36).slice(-4)}`), 'Library created')}>
              <Plus size={14} /> Create Library
            </button>
          </div>
          {(st.libraries || []).map((l) => {
            const pct = Math.round(((l.used_gb || 0) / (l.capacity_gb || 1)) * 100)
            return (
              <div key={l.name} className="cv-panel p-4">
                <div className="flex justify-between items-center mb-2">
                  <div className="font-medium flex items-center gap-2"><HardDrive size={15} className="text-[#0b3d78]" /> {l.name}</div>
                  <span className="text-xs text-slate-500">{l.type} · {l.media_agent || '—'} · {l.used_gb} / {l.capacity_gb} GB</span>
                </div>
                <div className="h-2 rounded bg-slate-200 overflow-hidden">
                  <div className="h-full rounded" style={{ width: `${pct}%`, background: pct > 85 ? '#ef4444' : '#0b3d78' }} />
                </div>
              </div>
            )
          })}
        </div>
      )
    }
    if (nav === 'activity') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Activity Log</h2>
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
    <div className={simPanelRoot(embedded, 'cv-shell sim-product')}>
      <LabChromeBar title="CommCell Console" subtitle={scenario?.title || slug}
        accent="#0b3d78" className="lab-chrome-bar !bg-[#0b3d78]" {...chromeProps}>
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

      <div className="px-4 py-2 bg-[#081f3d] border-b border-black/20 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-300" />
        <span className="text-xs text-slate-400 flex items-center gap-1"><Users size={12} /> {st?.session?.user || 'admin'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent="#0b3d78"
          className="!w-[220px] !bg-[#0c1930] cv-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#f4f6fa]">{renderContent()}</main>
      </div>

      <SimModal open={!!backupModal} onClose={() => setBackupModal(null)} title={`Run Backup — ${backupModal || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setBackupModal(null)}>Cancel</button>
          <button type="button" className="cv-btn-primary" disabled={busy} onClick={() => {
            run(() => commvaultApi.runBackup(sessionId, backupModal), 'Backup job started')
            setBackupModal(null)
          }}>Run Full Backup</button>
        </>}>
        <p className="text-sm text-slate-600">Runs a Full backup job against the default subclient of <strong>{backupModal}</strong> using its assigned storage policy.</p>
      </SimModal>

      <SimModal open={!!restoreModal} onClose={() => setRestoreModal(null)} title={`Run Restore — ${restoreModal || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setRestoreModal(null)}>Cancel</button>
          <button type="button" className="cv-btn-primary" disabled={busy} onClick={() => {
            run(() => commvaultApi.runRestore(sessionId, restoreModal), 'Restore job started')
            setRestoreModal(null)
          }}>Restore Latest Backup</button>
        </>}>
        <p className="text-sm text-slate-600">Restores the most recent successful backup for <strong>{restoreModal}</strong> in place.</p>
      </SimModal>

      <SimModal open={clientModal} onClose={() => setClientModal(false)} title="Add Client"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setClientModal(false)}>Cancel</button>
          <button type="button" className="cv-btn-primary" disabled={busy} onClick={() => {
            run(() => commvaultApi.addClient(sessionId, clientName, clientOs, clientIp), 'Client added')
            setClientModal(false)
          }}>Add</button>
        </>}>
        <label className="block text-sm">Client name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={clientName} onChange={(e) => setClientName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Operating system
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={clientOs} onChange={(e) => setClientOs(e.target.value)}>
            <option>Linux</option><option>Windows</option>
          </select>
        </label>
        <label className="block text-sm mt-3">IP address
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={clientIp} onChange={(e) => setClientIp(e.target.value)} placeholder="10.0.0.20" />
        </label>
      </SimModal>

      <SimModal open={subclientModal} onClose={() => setSubclientModal(false)} title="Create Subclient"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setSubclientModal(false)}>Cancel</button>
          <button type="button" className="cv-btn-primary" disabled={busy} onClick={() => {
            run(() => commvaultApi.createSubclient(sessionId, broken.missing_subclient, scName, scPolicy, [scContent]), 'Subclient created')
            setSubclientModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Subclient name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={scName} onChange={(e) => setScName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Storage policy
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={scPolicy} onChange={(e) => setScPolicy(e.target.value)}>
            {(st.storage_policies || []).map((p) => <option key={p.id} value={p.name}>{p.name}</option>)}
          </select>
        </label>
        <label className="block text-sm mt-3">Content path
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={scContent} onChange={(e) => setScContent(e.target.value)} />
        </label>
      </SimModal>

      {broken.missing_subclient && nav === 'clients' && (
        <button type="button" onClick={() => setSubclientModal(true)}
          className="fixed bottom-4 right-4 cv-btn-primary shadow-lg">
          <Plus size={14} className="inline mr-1" /> Create missing subclient
        </button>
      )}
    </div>
  )
}
