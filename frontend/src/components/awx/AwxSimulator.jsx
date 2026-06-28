import { useState } from 'react'
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
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')

  const inv = state?.inventory || {}
  const loggedIn = inv?.session?.logged_in
  const goal = state?.goal || {}
  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? undefined : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
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
              {AWX_DASHBOARD_STATS.map((s) => (
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
          ]} rows={inv.jobs || []} searchKeys={['name', 'status']} onRowClick={(j) => setSelectedJob(j)} />
          {selectedJob && (
            <div className="awx-widget space-y-3">
              <div className="flex justify-between items-center flex-wrap gap-2">
                <h3 className="font-semibold">{selectedJob.name} <span className="text-xs text-slate-400 font-mono">#{selectedJob.id}</span></h3>
                <div className="flex items-center gap-2">
                  <SimStatusBadge status={selectedJob.status} />
                  <button type="button" className="awx-btn-launch text-[11px] py-1 px-2 flex items-center gap-1" disabled={busy}
                    onClick={() => { run(() => awxApi.relaunchJob(sessionId, selectedJob.id), 'Job relaunched'); }}>
                    <RefreshCw size={12} /> Relaunch
                  </button>
                  {['running', 'pending', 'waiting'].includes(selectedJob.status) && (
                    <button type="button" className="px-2 py-1 border border-red-300 text-red-600 rounded text-[11px]" disabled={busy}
                      onClick={() => { run(() => awxApi.cancelJob(sessionId, selectedJob.id), 'Job canceled'); }}>
                      Cancel
                    </button>
                  )}
                </div>
              </div>
              <SimTerminalLog lines={AWX_JOB_LOG} title={`Output — ${selectedJob.name} (${selectedJob.status})`} />
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
      return <SimDataTable columns={[
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
      return <SimDataTable columns={[
        { key: 'username', label: 'Username', sortable: true },
        { key: 'name', label: 'Name', sortable: true },
        { key: 'role', label: 'Role', sortable: true },
      ]} rows={AWX_USERS} searchKeys={['username', 'name']} />
    }
    if (nav === 'workflow-templates') {
      return (
        <div className="awx-widget p-6 min-h-[320px] relative bg-slate-50">
          <p className="text-sm text-slate-600 mb-4">Workflow Visualizer — drag nodes, connect success/failure paths</p>
          <div className="flex items-center gap-8">
            <div className="px-4 py-2 rounded border-2 border-green-500 bg-white font-medium text-sm">Start</div>
            <div className="px-4 py-2 rounded border bg-white shadow text-sm">Deploy Web → <SimStatusBadge status="success" label="OK" /></div>
            <div className="px-4 py-2 rounded border bg-white shadow text-sm">Run Tests → <SimStatusBadge status="pending" /></div>
          </div>
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
          ]} rows={AWX_ACTIVITY} searchKeys={['user', 'action']} />
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
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status} /> },
            { key: 'requestedBy', label: 'Requested By', sortable: true },
            { key: 'age', label: 'Age', sortable: true },
          ]} rows={AWX_APPROVALS} searchKeys={['workflow']} />
        </div>
      )
    }
    if (nav === 'organizations') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Organization', sortable: true },
        { key: 'description', label: 'Description', sortable: true },
        { key: 'inventories', label: 'Inventories', sortable: true },
        { key: 'users', label: 'Users', sortable: true },
      ]} rows={AWX_ORGANIZATIONS} searchKeys={['name']} />
    }
    if (nav === 'teams') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Team', sortable: true },
        { key: 'organization', label: 'Organization', sortable: true },
        { key: 'members', label: 'Members', sortable: true },
        { key: 'role', label: 'Role', sortable: true },
      ]} rows={AWX_TEAMS} searchKeys={['name']} />
    }
    if (nav === 'instance-groups') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Instance Group', sortable: true },
        { key: 'instances', label: 'Instances', sortable: true },
        { key: 'capacity', label: 'Capacity', sortable: true },
        { key: 'jobsRunning', label: 'Running Jobs', sortable: true },
      ]} rows={AWX_INSTANCE_GROUPS} searchKeys={['name']} />
    }
    if (nav === 'execution-envs') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Environment', sortable: true },
        { key: 'image', label: 'Image', sortable: true },
        { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status} /> },
      ]} rows={AWX_EXEC_ENVS} searchKeys={['name']} />
    }
    if (nav === 'applications') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Application', sortable: true },
        { key: 'clientType', label: 'Client Type', sortable: true },
        { key: 'redirect', label: 'Redirect URI', sortable: true },
      ]} rows={AWX_APPLICATIONS} searchKeys={['name']} />
    }
    if (nav === 'notifications') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Template', sortable: true },
        { key: 'type', label: 'Type', sortable: true },
        { key: 'destinations', label: 'Destination', sortable: true },
        { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'ok' ? 'success' : 'disabled'} label={r.status} /> },
      ]} rows={AWX_NOTIFICATIONS} searchKeys={['name']} />
    }
    if (nav === 'mgmt-jobs') {
      return <SimDataTable columns={[
        { key: 'name', label: 'Job', sortable: true },
        { key: 'schedule', label: 'Schedule', sortable: true },
        { key: 'lastRun', label: 'Last Run', render: (r) => <SimStatusBadge status="success" label={r.lastRun} /> },
      ]} rows={AWX_MGMT_JOBS} searchKeys={['name']} />
    }
    if (nav.startsWith('settings-')) {
      const rows = AWX_SETTINGS_SECTIONS[nav] || []
      return (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold capitalize">{nav.replace('settings-', '').replace(/-/g, ' ')} Settings</h2>
          <div className="awx-widget divide-y">
            {rows.map((r) => (
              <div key={r.key} className="flex justify-between py-3 text-sm">
                <span className="text-slate-600">{r.key}</span>
                <span className="font-mono text-slate-800">{r.value}</span>
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
    </div>
  )
}
