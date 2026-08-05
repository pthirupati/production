import { useEffect, useRef, useState } from 'react'
import { awxApi } from '../../api/awx'
import toast from 'react-hot-toast'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Play, RefreshCw, Layers, FolderGit2, Key, ListChecks, Server, AlertTriangle,
  Calendar, Activity, CheckSquare, Users, Bell, Settings, Cpu, Package, Plus, Terminal,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import {
  SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, SimTerminalLog, useSimSession,
} from '../sim/shared'
import {
  AWX_SIDEBAR, AWX_DASHBOARD_STATS, AWX_JOB_LOG, AWX_HOSTS, AWX_SCHEDULES, AWX_USERS, AWX_CREDENTIAL_TYPES,
  AWX_ACTIVITY, AWX_APPROVALS, AWX_ORGANIZATIONS, AWX_TEAMS, AWX_INSTANCE_GROUPS, AWX_EXEC_ENVS,
  AWX_NOTIFICATIONS, AWX_MGMT_JOBS, AWX_APPLICATIONS, AWX_SETTINGS_SECTIONS,
} from '../../mockData/awx'
import '../../styles/sim-products.css'

// Lab sign-in credentials, consistent with the other simulators
// (lab_<product> / lab_<product>@123). The AWX default admin/admin is also accepted.
const AWX_LAB_USER = 'lab_awx'
const AWX_LAB_PASS = 'lab_awx@123'

const NAV_ICONS = {
  dashboard: Layers, jobs: Play, schedules: Calendar, activity: Activity, approvals: CheckSquare,
  credentials: Key, projects: FolderGit2, inventories: Server, hosts: Server, organizations: Users,
  users: Users, teams: Users, notifications: Bell, settings: Settings,
  'job-templates': ListChecks, 'workflow-templates': Activity,
}

const SIDEBAR = AWX_SIDEBAR.map((s) => ({
  ...s,
  icon: NAV_ICONS[s.key],
  items: s.items?.map((i) => ({ ...i, icon: NAV_ICONS[i.key] || ListChecks })),
}))

export default function AwxSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run, refresh } = useSimSession(sessionId, slug, awxApi)
  const [nav, setNav] = useState('dashboard')
  const [selectedJob, setSelectedJob] = useState(null)
  const [launchModal, setLaunchModal] = useState(null)
  const [credModal, setCredModal] = useState(false)
  const [credType, setCredType] = useState('machine')
  const [credName, setCredName] = useState('Machine SSH')
  const [projectModal, setProjectModal] = useState(false)
  const [projectName, setProjectName] = useState('ansible-playbooks')
  const [inventoryModal, setInventoryModal] = useState(false)
  const [inventoryName, setInventoryName] = useState('Production')
  const [templateModal, setTemplateModal] = useState(false)
  const [templateName, setTemplateName] = useState('Site Deploy')
  const [scheduleModal, setScheduleModal] = useState(false)
  const [scheduleName, setScheduleName] = useState('Nightly patch')
  const [scheduleTemplate, setScheduleTemplate] = useState('Patch Linux')
  const [hostModal, setHostModal] = useState(false)
  const [hostName, setHostName] = useState('app01.fixitlab.local')
  const [hostInventory, setHostInventory] = useState('Production')
  const [orgModal, setOrgModal] = useState(false)
  const [orgName, setOrgName] = useState('New Organization')
  const [orgDesc, setOrgDesc] = useState('')
  const [teamModal, setTeamModal] = useState(false)
  const [teamName, setTeamName] = useState('New Team')
  const [teamOrg, setTeamOrg] = useState('Default')
  const [userModal, setUserModal] = useState(false)
  const [userName, setUserName] = useState('new-user')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')

  const inv = state?.inventory || {}
  const loggedIn = inv?.session?.logged_in
  const goal = state?.goal || {}
  const jobs = inv.jobs || []
  // A job is "live" until it reaches a terminal status. While any job is live,
  // poll get_state so the wall-clock status/stdout advance shows up in the UI.
  const TERMINAL = ['successful', 'failed', 'canceled', 'error']
  const hasLiveJob = jobs.some((j) => !TERMINAL.includes(j.status))
  // Always re-derive the selected job from live state (by id) so its status
  // badge and streamed stdout re-render as polling advances the job.
  const liveSelectedJob = selectedJob
    ? (jobs.find((j) => j.id === selectedJob.id) || selectedJob)
    : null

  const refreshRef = useRef(refresh)
  refreshRef.current = refresh
  useEffect(() => {
    if (!loggedIn || !hasLiveJob) return undefined
    const t = setInterval(() => { refreshRef.current?.() }, 1200)
    return () => clearInterval(t)
  }, [loggedIn, hasLiveJob])
  // Companions pass onExit; primary embeds pass onToggleTerminal. Never drop
  // Back just because embedded=true — that was hiding Close on Open AWX overlays.
  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: onExit || onToggleTerminal,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : (onExit ? 'Close' : 'Terminal'),
    vmwareHref,
  }

  const breadcrumbs = [{ label: inv?.summary?.organization || 'Default', onClick: () => setNav('dashboard') }]
  if (nav !== 'dashboard') breadcrumbs.push({ label: AWX_SIDEBAR.find((s) => s.key === nav || s.items?.some((i) => i.key === nav))?.label || nav.replace(/-/g, ' ') })

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === AWX_LAB_USER && loginPass === AWX_LAB_PASS)
        || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        run(() => awxApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${AWX_LAB_USER} / ${AWX_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#1a1a2e]')}>
        <LabChromeBar title="Ansible AWX" subtitle={scenario?.title || slug} accent="#EE0000" {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold bg-[#EE0000] flex items-center gap-2">
              <Layers size={18} /> Ansible AWX
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Sign in to the Ansible AWX / Tower training instance.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={AWX_LAB_USER}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-[#EE0000]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} autoComplete="current-password"
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-[#EE0000]" />
              </div>
              {loginError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>
              )}
              <button type="submit" disabled={busy}
                className="awx-btn-launch w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(AWX_LAB_USER); setLoginPass(AWX_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{AWX_LAB_USER}</span> / <span className="font-mono text-slate-700">{AWX_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const renderContent = () => {
    if (nav === 'dashboard' || nav === 'jobs') {
      return (
        <div className="space-y-4">
          {nav === 'dashboard' && (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
              {[
                { label: 'Hosts', value: (inv.hosts || []).length, color: '#EE0000' },
                { label: 'Failed Hosts', value: (inv.hosts || []).filter((h) => h.status === 'failed').length, color: '#c0392b' },
                { label: 'Inventories', value: (inv.inventories || []).length, color: '#2980b9' },
                { label: 'Projects', value: (inv.projects || []).length, color: '#27ae60' },
                { label: 'Job Templates', value: (inv.job_templates || []).length, color: '#8e44ad' },
                { label: 'Jobs Running', value: (inv.jobs || []).filter((j) => ['running', 'pending', 'waiting'].includes(j.status)).length, color: '#f39c12' },
                { label: 'Jobs Failed', value: (inv.jobs || []).filter((j) => j.status === 'failed').length, color: '#e74c3c' },
              ].map((s) => (
                <div key={s.label} className="awx-widget text-center">
                  <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
                  <div className="text-[10px] text-slate-500 uppercase mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          )}
          {(inv.broken?.awx_not_installed) && (
            <div className="awx-widget flex items-center justify-between">
              <div><div className="font-medium">AWX Operator</div><div className="text-sm text-slate-500">Not installed</div></div>
              <button onClick={() => run(() => awxApi.installAwx(sessionId), 'AWX installed')} className="awx-btn-launch">Install AWX</button>
            </div>
          )}
          <h2 className="text-lg font-semibold">{nav === 'jobs' ? 'Jobs' : 'Recent Jobs'}</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Job', sortable: true },
            { key: 'status', label: 'Status', sortable: true, render: (r) => <SimStatusBadge status={r.status} /> },
            { key: 'id', label: 'ID', sortable: true },
          ]} rows={jobs} searchKeys={['name', 'status']} onRowClick={(j) => setSelectedJob(j)} />
          {liveSelectedJob && (
            <div className="awx-widget space-y-3">
              <div className="flex justify-between items-center flex-wrap gap-2">
                <h3 className="font-semibold">{liveSelectedJob.name} <span className="text-xs text-slate-400 font-mono">#{liveSelectedJob.id}</span></h3>
                <div className="flex items-center gap-2">
                  <SimStatusBadge status={liveSelectedJob.status} />
                  <button type="button" className="awx-btn-launch text-[11px] py-1 px-2 flex items-center gap-1" disabled={busy}
                    onClick={() => { run(() => awxApi.relaunchJob(sessionId, liveSelectedJob.id), 'Job relaunched').then((r) => { if (r?.job_id) setSelectedJob({ id: r.job_id }) }) }}>
                    <RefreshCw size={12} /> Relaunch
                  </button>
                  {['running', 'pending', 'waiting'].includes(liveSelectedJob.status) && (
                    <button type="button" className="px-2 py-1 border border-red-300 text-red-600 rounded text-[11px]" disabled={busy}
                      onClick={() => { run(() => awxApi.cancelJob(sessionId, liveSelectedJob.id), 'Job canceled'); }}>
                      Cancel
                    </button>
                  )}
                </div>
              </div>
              <SimTerminalLog lines={liveSelectedJob.stdout || AWX_JOB_LOG} title={`Output — ${liveSelectedJob.name} (${liveSelectedJob.status})`} />
            </div>
          )}
        </div>
      )
    }
    if (nav === 'job-templates' || nav === 'templates') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Job Templates</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setTemplateModal(true)}>
              <Plus size={14} /> Create template
            </button>
          </div>
          {inv.broken?.missing_template && (
            <div className="awx-widget text-sm text-amber-800 bg-amber-50 border border-amber-200 px-3 py-2 rounded">
              Scenario requires a job template — click Create template.
            </div>
          )}
          <SimDataTable columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'playbook', label: 'Playbook', sortable: true },
            { key: 'inventory', label: 'Inventory', sortable: true },
            { key: 'actions', label: 'Actions', render: (jt) => (
              <div className="flex gap-1">
                <button type="button" className="awx-btn-launch text-[10px] py-1 px-2" onClick={(e) => { e.stopPropagation(); setLaunchModal(jt) }}><Play size={12} /></button>
              </div>
            )},
          ]} rows={inv.job_templates || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'projects') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Projects</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setProjectModal(true)}>
              <Plus size={14} /> Add project
            </button>
          </div>
          {(inv.projects || []).map((p) => (
            <div key={p.id} className="awx-widget flex justify-between items-center">
              <div><div className="font-medium">{p.name}</div><div className="text-xs text-slate-500">{p.scm_type} · <SimStatusBadge status={p.status} label={p.status} /></div></div>
              <button onClick={() => run(() => awxApi.syncProject(sessionId, p.id), 'Synced')} className="px-3 py-1.5 border rounded text-sm flex items-center gap-1"><RefreshCw size={14} /> Sync</button>
            </div>
          ))}
        </div>
      )
    }
    if (nav === 'inventories') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Inventories</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setInventoryModal(true)}>
              <Plus size={14} /> Add inventory
            </button>
          </div>
          <SimDataTable columns={[
          { key: 'name', label: 'Inventory', sortable: true },
          { key: 'hosts', label: 'Hosts', sortable: true },
          { key: 'id', label: 'ID' },
          ]} rows={inv.inventories || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'hosts') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Hosts</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setHostModal(true)}>
              <Plus size={14} /> Add host
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Host', sortable: true },
            { key: 'inventory', label: 'Inventory', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status} /> },
            { key: 'source', label: 'Source', sortable: true },
            { key: 'ip', label: 'IP' },
            { key: 'enabled', label: 'Enabled', render: (r) => (
              <button type="button" className="px-2 py-1 border rounded text-[10px]" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => awxApi.toggleHost(sessionId, r.id), (r.enabled !== false) ? 'Host disabled' : 'Host enabled') }}>
                {(r.enabled !== false) ? 'Enabled' : 'Disabled'}
              </button>
            ) },
          ]} rows={inv.hosts || AWX_HOSTS} searchKeys={['name', 'inventory', 'source', 'ip']} />
        </div>
      )
    }
    if (nav === 'credentials') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between">
            <h2 className="text-lg font-semibold">Credentials</h2>
            <button type="button" className="awx-btn-launch" onClick={() => setCredModal(true)}>+ Create</button>
          </div>
          {inv.broken?.credential_missing && (
            <button onClick={() => run(() => awxApi.attachCredential(sessionId), 'Credential attached')} className="awx-btn-launch">Attach Machine credential</button>
          )}
          <SimDataTable columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'kind', label: 'Type', sortable: true },
          ]} rows={inv.credentials || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'schedules') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Schedules</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setScheduleModal(true)}>
              <Plus size={14} /> Add schedule
            </button>
          </div>
          <SimDataTable columns={[
        { key: 'name', label: 'Schedule', sortable: true },
        { key: 'template', label: 'Template', sortable: true },
        { key: 'next_run', label: 'Next Run', sortable: true, render: (r) => new Date(r.next_run || r.nextRun || Date.now()).toLocaleString() },
        { key: 'enabled', label: 'State', render: (r) => <SimStatusBadge status={r.enabled ? 'success' : 'disabled'} label={r.enabled ? 'Enabled' : 'Disabled'} /> },
        { key: 'actions', label: 'Actions', render: (r) => (
          <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="px-2 py-1 border rounded text-[10px]" disabled={busy}
              onClick={() => run(() => awxApi.toggleSchedule(sessionId, r.id), r.enabled ? 'Schedule disabled' : 'Schedule enabled')}>
              {r.enabled ? 'Disable' : 'Enable'}
            </button>
            <button type="button" className="px-2 py-1 border border-red-300 text-red-600 rounded text-[10px]" disabled={busy}
              onClick={() => run(() => awxApi.deleteSchedule(sessionId, r.id), 'Schedule deleted')}>
              Delete
            </button>
          </div>
        ) },
          ]} rows={inv.schedules || AWX_SCHEDULES} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'users') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Users</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setUserModal(true)}>
              <Plus size={14} /> Add user
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'username', label: 'Username', sortable: true },
            { key: 'name', label: 'Name', sortable: true },
            { key: 'role', label: 'Role', sortable: true },
          ]} rows={inv.users || AWX_USERS} searchKeys={['username', 'name']} />
        </div>
      )
    }
    if (nav === 'workflow-templates') {
      const workflows = inv.workflow_templates || []
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Workflow Templates</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" disabled={busy}
              onClick={() => run(() => awxApi.createWorkflowTemplate(sessionId, `WF-${Date.now().toString(36).slice(-4)}`), 'Workflow created')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'organization', label: 'Organization' },
            { key: 'inventory', label: 'Inventory' },
            { key: 'nodes', label: 'Nodes', render: (r) => (r.nodes || []).length },
            {
              key: 'actions', label: '',
              render: (r) => (
                <button type="button" className="awx-btn-launch text-xs" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => awxApi.launchWorkflow(sessionId, r.id), 'Workflow launched') }}>
                  Launch
                </button>
              ),
            },
          ]} rows={workflows} searchKeys={['name']}
            expandRow={(r) => (
              <div className="p-3 text-sm flex flex-wrap items-center gap-3">
                {(r.nodes || []).map((n, i) => (
                  <span key={n.id || i} className="px-3 py-1.5 rounded border bg-white shadow-sm">
                    {n.name} <span className="text-slate-400">({n.type})</span>
                    {i < (r.nodes || []).length - 1 ? ' →' : ''}
                  </span>
                ))}
              </div>
            )}
          />
        </div>
      )
    }
    if (nav === 'activity') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Activity Stream</h2>
          <SimDataTable columns={[
            { key: 'time', label: 'Time', sortable: true, render: (r) => new Date(r.time).toLocaleString() },
            { key: 'user', label: 'User', sortable: true },
            { key: 'action', label: 'Action', sortable: true },
            { key: 'object', label: 'Object', sortable: true },
          ]} rows={inv.activity || AWX_ACTIVITY} searchKeys={['user', 'action']} />
        </div>
      )
    }
    if (nav === 'approvals') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Workflow Approvals</h2>
          <SimDataTable columns={[
            { key: 'workflow', label: 'Workflow', sortable: true },
            { key: 'step', label: 'Step', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'approved' ? 'success' : r.status === 'denied' ? 'error' : 'pending'} label={r.status} /> },
            { key: 'requestedBy', label: 'Requested By', sortable: true },
            { key: 'age', label: 'Age', sortable: true },
            {
              key: 'actions', label: '',
              render: (r) => r.status === 'pending' ? (
                <div className="flex gap-1">
                  <button type="button" className="awx-btn-launch text-xs" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => awxApi.approveWorkflow(sessionId, r.id, true), 'Approved') }}>Approve</button>
                  <button type="button" className="text-xs px-2 py-1 border rounded" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => awxApi.approveWorkflow(sessionId, r.id, false), 'Denied') }}>Deny</button>
                </div>
              ) : null,
            },
          ]} rows={inv.approvals || AWX_APPROVALS} searchKeys={['workflow']} />
        </div>
      )
    }
    if (nav === 'organizations') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Organizations</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setOrgModal(true)}>
              <Plus size={14} /> Add organization
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Organization', sortable: true },
            { key: 'description', label: 'Description', sortable: true },
            { key: 'inventories', label: 'Inventories', sortable: true },
            { key: 'users', label: 'Users', sortable: true },
          ]} rows={inv.organizations || AWX_ORGANIZATIONS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'teams') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Teams</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" onClick={() => setTeamModal(true)}>
              <Plus size={14} /> Add team
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Team', sortable: true },
            { key: 'organization', label: 'Organization', sortable: true },
            { key: 'members', label: 'Members', sortable: true },
            { key: 'role', label: 'Role', sortable: true },
          ]} rows={inv.teams || AWX_TEAMS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'instance-groups') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Instance Groups</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" disabled={busy}
              onClick={() => run(() => awxApi.createInstanceGroup(sessionId, {
                name: `ig-${Date.now().toString(36).slice(-4)}`,
                instances: 1,
                capacity: 100,
              }), 'Instance group created')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Instance Group', sortable: true },
            { key: 'instances', label: 'Instances', sortable: true },
            { key: 'capacity', label: 'Capacity', sortable: true },
            { key: 'jobsRunning', label: 'Running Jobs', sortable: true },
            {
              key: 'actions', label: '',
              render: (r) => (
                <button type="button" className="awx-btn-ghost text-xs" disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation()
                    run(() => awxApi.scaleInstanceGroup(sessionId, r.name, { instances: (r.instances || 1) + 1 }), 'Scaled')
                  }}>
                  + Instance
                </button>
              ),
            },
          ]} rows={(inv.instance_groups || AWX_INSTANCE_GROUPS).map((g) => ({
            ...g,
            jobsRunning: g.jobsRunning ?? g.jobs_running,
          }))} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'execution-envs') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Execution Environments</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" disabled={busy}
              onClick={() => run(() => awxApi.createExecutionEnvironment(sessionId, {
                name: `EE-${Date.now().toString(36).slice(-4)}`,
                image: 'quay.io/ansible/awx-ee:latest',
              }), 'Execution environment created')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Environment', sortable: true },
            { key: 'image', label: 'Image', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status} /> },
          ]} rows={inv.execution_environments || AWX_EXEC_ENVS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'applications') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Applications</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" disabled={busy}
              onClick={() => run(() => awxApi.createApplication(sessionId, {
                name: `App-${Date.now().toString(36).slice(-4)}`,
                clientType: 'Confidential',
                redirect: 'https://awx.fixitlab.local/api/o/authorize/',
              }), 'Application created')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Application', sortable: true },
            { key: 'clientType', label: 'Client Type', sortable: true },
            { key: 'redirect', label: 'Redirect URI', sortable: true },
          ]} rows={inv.applications || AWX_APPLICATIONS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'notifications') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Notification Templates</h2>
            <button type="button" className="awx-btn-launch flex items-center gap-1" disabled={busy}
              onClick={() => run(() => awxApi.createNotification(sessionId, {
                name: `Notify-${Date.now().toString(36).slice(-4)}`, type: 'Slack', destinations: '#ops',
              }), 'Notification created')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Template', sortable: true },
            { key: 'type', label: 'Type', sortable: true },
            { key: 'destinations', label: 'Destination', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'ok' ? 'success' : 'disabled'} label={r.status} /> },
          ]} rows={inv.notifications || AWX_NOTIFICATIONS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'mgmt-jobs') {
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Management Jobs</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Job', sortable: true },
            { key: 'schedule', label: 'Schedule', sortable: true },
            { key: 'enabled', label: 'Enabled', render: (r) => (r.enabled === false ? 'No' : 'Yes') },
            { key: 'lastRun', label: 'Last Run', render: (r) => <SimStatusBadge status="success" label={r.lastRun || '—'} /> },
            {
              key: 'actions', label: '',
              render: (r) => (
                <div className="flex gap-1">
                  <button type="button" className="awx-btn-launch !text-[11px] !py-0.5 !px-2" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => awxApi.launchMgmtJob(sessionId, r.id), 'Launched') }}>Launch</button>
                  <button type="button" className="text-xs text-slate-500 underline" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => awxApi.toggleMgmtJob(sessionId, r.id), 'Updated') }}>
                    {r.enabled === false ? 'Enable' : 'Disable'}
                  </button>
                </div>
              ),
            },
          ]} rows={inv.management_jobs || AWX_MGMT_JOBS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav.startsWith('settings-')) {
      const rows = (inv.settings && inv.settings[nav]) || AWX_SETTINGS_SECTIONS[nav] || []
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold capitalize">{nav.replace('settings-', '').replace(/-/g, ' ')} Settings</h2>
          <div className="awx-widget divide-y">
            {rows.map((r) => (
              <div key={r.key} className="flex justify-between items-center gap-3 py-3 text-sm">
                <span className="text-slate-600 shrink-0">{r.key}</span>
                <input
                  className="font-mono text-slate-800 text-right bg-transparent border-b border-transparent hover:border-slate-300 focus:border-red-400 outline-none min-w-0 flex-1 max-w-md"
                  defaultValue={r.value}
                  disabled={busy}
                  onBlur={(e) => {
                    if (e.target.value !== r.value) {
                      run(() => awxApi.updateSetting(sessionId, nav, r.key, e.target.value), 'Setting saved')
                    }
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      )
    }
    return (
      <div className="awx-widget p-8 text-center text-slate-500 capitalize">
        <Package size={28} className="mx-auto mb-2 opacity-40" />
        {nav.replace(/-/g, ' ')} — AWX administration view
      </div>
    )
  }

  return (
    <div className={simPanelRoot(embedded, 'awx-shell sim-product')}>
      <LabChromeBar title={`Ansible AWX · ${inv?.summary?.version || '24'}`} subtitle={scenario?.title || slug}
        accent="#EE0000" className="lab-chrome-bar !bg-[#2c2c54]" {...chromeProps}>
        {onToggleTerminal && (
          <button
            type="button"
            className="lab-chrome-btn flex items-center gap-1"
            onClick={onToggleTerminal}
          >
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

      <div className="px-4 py-2 bg-[#1c1c1c] border-b border-black/20 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-400" />
        <span className="text-xs text-slate-400">{inv?.summary?.user || 'admin'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent="#EE0000"
          className="!w-[220px] !bg-[#1c1c1c] awx-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#f4f4f4]">{renderContent()}</main>
      </div>

      <SimModal open={!!launchModal} onClose={() => setLaunchModal(null)} title={`Launch — ${launchModal?.name || ''}`}
        footer={<><button type="button" className="text-sm px-3" onClick={() => setLaunchModal(null)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.launchTemplate(sessionId, launchModal.id), 'Job launched')
            setLaunchModal(null)
          }}>Launch</button></>}>
        <p className="text-sm text-slate-600">Optional survey variables and credentials are pre-filled for training.</p>
      </SimModal>

      <SimModal open={credModal} onClose={() => setCredModal(false)} title="Create Credential"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setCredModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.createCredential(sessionId, credName, credType), 'Credential created')
            setCredModal(false)
            refresh?.()
          }}>Save</button>
        </>}>
        <label className="block text-sm mb-2">Name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={credName} onChange={(e) => setCredName(e.target.value)} />
        </label>
        <label className="block text-sm mb-2">Credential Type
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={credType} onChange={(e) => setCredType(e.target.value)}>
            {AWX_CREDENTIAL_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </label>
        {AWX_CREDENTIAL_TYPES.find((t) => t.id === credType)?.fields.map((f) => (
          <input key={f} placeholder={f.replace('_', ' ')} className="w-full mt-2 border rounded px-2 py-1.5 text-sm" />
        ))}
      </SimModal>

      <SimModal open={templateModal} onClose={() => setTemplateModal(false)} title="Create Job Template"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setTemplateModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.createTemplate(sessionId, templateName), 'Template created')
            setTemplateModal(false)
            refresh?.()
          }}>Create</button>
        </>}>
        <label className="block text-sm">Template name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={projectModal} onClose={() => setProjectModal(false)} title="Add Project"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setProjectModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.createProject(sessionId, projectName), 'Project created')
            setProjectModal(false)
            refresh?.()
          }}>Add</button>
        </>}>
        <label className="block text-sm">Project name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={projectName} onChange={(e) => setProjectName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={inventoryModal} onClose={() => setInventoryModal(false)} title="Add Inventory"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setInventoryModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.createInventory(sessionId, inventoryName), 'Inventory created')
            setInventoryModal(false)
            refresh?.()
          }}>Add</button>
        </>}>
        <label className="block text-sm">Inventory name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={inventoryName} onChange={(e) => setInventoryName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={scheduleModal} onClose={() => setScheduleModal(false)} title="Add Schedule"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setScheduleModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.createSchedule(sessionId, scheduleName, scheduleTemplate), 'Schedule created')
            setScheduleModal(false)
          }}>Save</button>
        </>}>
        <label className="block text-sm">Schedule name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={scheduleName} onChange={(e) => setScheduleName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Job template
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={scheduleTemplate} onChange={(e) => setScheduleTemplate(e.target.value)}>
            {(inv.job_templates || []).map((jt) => <option key={jt.id} value={jt.name}>{jt.name}</option>)}
            {!(inv.job_templates || []).length && <option value="Patch Linux">Patch Linux</option>}
          </select>
        </label>
      </SimModal>

      <SimModal open={hostModal} onClose={() => setHostModal(false)} title="Add Host"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setHostModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.action(sessionId, 'create_host', { name: hostName, inventory: hostInventory }), 'Host created')
            setHostModal(false)
          }}>Add</button>
        </>}>
        <label className="block text-sm">Host name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={hostName} onChange={(e) => setHostName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Inventory
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={hostInventory} onChange={(e) => setHostInventory(e.target.value)}>
            {(inv.inventories || []).map((i) => <option key={i.id} value={i.name}>{i.name}</option>)}
            {!(inv.inventories || []).length && <option value="Production">Production</option>}
          </select>
        </label>
      </SimModal>

      <SimModal open={orgModal} onClose={() => setOrgModal(false)} title="Add Organization"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setOrgModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.action(sessionId, 'create_organization', { name: orgName, description: orgDesc }), 'Organization created')
            setOrgModal(false)
          }}>Add</button>
        </>}>
        <label className="block text-sm">Organization name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={orgName} onChange={(e) => setOrgName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Description
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={orgDesc} onChange={(e) => setOrgDesc(e.target.value)} />
        </label>
      </SimModal>

      <SimModal open={teamModal} onClose={() => setTeamModal(false)} title="Add Team"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setTeamModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.action(sessionId, 'create_team', { name: teamName, organization: teamOrg }), 'Team created')
            setTeamModal(false)
          }}>Add</button>
        </>}>
        <label className="block text-sm">Team name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={teamName} onChange={(e) => setTeamName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Organization
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={teamOrg} onChange={(e) => setTeamOrg(e.target.value)}>
            {(inv.organizations || []).map((o) => <option key={o.id} value={o.name}>{o.name}</option>)}
            {!(inv.organizations || []).length && <option value="Default">Default</option>}
          </select>
        </label>
      </SimModal>

      <SimModal open={userModal} onClose={() => setUserModal(false)} title="Add User"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setUserModal(false)}>Cancel</button>
          <button type="button" className="awx-btn-launch" disabled={busy} onClick={() => {
            run(() => awxApi.action(sessionId, 'create_user', { username: userName }), 'User created')
            setUserModal(false)
          }}>Add</button>
        </>}>
        <label className="block text-sm">Username
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={userName} onChange={(e) => setUserName(e.target.value)} />
        </label>
      </SimModal>
    </div>
  )
}
