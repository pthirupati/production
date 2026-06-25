import { useMemo, useState } from 'react'
import {
  Cloud, Plus, Settings, GitBranch, FileText, Server, Users, Terminal, Code2,
} from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { simPanelRoot } from '../../utils/simLayout'
import {
  SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, SimTerminalLog,
} from '../sim/shared'
import {
  TFC_ORG, TFC_WORKSPACES, TFC_RUNS, TFC_VARIABLES, TFC_MODULES, TFC_TEAMS,
  TFC_AGENT_POOLS, TFC_RUN_LOG, TFC_SIDEBAR,
  TFC_STATES, TFC_LOCKS, TFC_WS_NOTIFICATIONS, TFC_TEAM_ACCESS, TFC_HEALTH,
  TFC_SETTINGS_GENERAL, TFC_SETTINGS_SSO, TFC_SETTINGS_VCS, TFC_SETTINGS_TOKENS,
  TFC_AUDIT_LOG, TFC_USAGE,
} from '../../mockData/terraformCloud'
import TerraformWorkspaceIde from './TerraformWorkspaceIde'
import { getIacProfile } from '../../utils/iacFlavor'
import '../../styles/sim-products.css'

const ICONS = {
  workspaces: GitBranch, explorer: Cloud, 'registry-modules': FileText, 'registry-providers': Server,
  'settings-teams': Users, 'settings-agents': Server, 'settings-general': Settings,
}

const SIDEBAR = TFC_SIDEBAR.map((s) => ({
  ...s,
  icon: Cloud,
  items: s.items?.map((i) => ({ ...i, icon: ICONS[i.key] || FileText })),
}))

export default function TerraformCloudShell({
  sessionId, scenario, embedded, chromeProps,
  terminalSession, terminalHost, blockedCommands, isMobile,
  state, setState, refresh, busy, run,
  onToggleTerminal, simTerminalOpen = false,
}) {
  const [nav, setNav] = useState('workspaces')
  const [shellMode, setShellMode] = useState('ide')
  const [selectedWs, setSelectedWs] = useState(TFC_WORKSPACES.find((w) => w.name === 'lab-workspace') || TFC_WORKSPACES[0])
  const [wsTab, setWsTab] = useState('runs')
  const [selectedRun, setSelectedRun] = useState(null)
  const [showNewWs, setShowNewWs] = useState(false)
  const [newWsName, setNewWsName] = useState('lab-workspace')
  const [extraWorkspaces, setExtraWorkspaces] = useState([])
  const allWorkspaces = useMemo(() => [...TFC_WORKSPACES, ...extraWorkspaces], [extraWorkspaces])
  const [showApply, setShowApply] = useState(false)
  const [showVarModal, setShowVarModal] = useState(false)
  const slug = scenario?.slug || ''
  const iac = getIacProfile()

  const breadcrumbs = useMemo(() => {
    const items = [{ label: TFC_ORG.name, onClick: () => { setNav('workspaces'); setSelectedWs(null) } }]
    if (nav === 'workspaces' && !selectedWs) items.push({ label: 'Workspaces' })
    if (selectedWs) {
      items.push({ label: 'Workspaces', onClick: () => setSelectedWs(null) })
      items.push({ label: selectedWs.name })
    } else if (nav.startsWith('registry')) items.push({ label: 'Registry' }, { label: nav.replace('registry-', '') })
    else if (nav.startsWith('settings')) items.push({ label: 'Settings' }, { label: nav.replace('settings-', '') })
    return items
  }, [nav, selectedWs])

  const workspaceColumns = [
    { key: 'name', label: 'Name', sortable: true, render: (r) => <span className="text-violet-300 font-medium">{r.name}</span> },
    { key: 'project', label: 'Project', sortable: true },
    { key: 'status', label: 'Status', sortable: true, render: (r) => <SimStatusBadge status={r.status} /> },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'lastRun', label: 'Last Run', sortable: true },
    { key: 'updatedAt', label: 'Updated', sortable: true, render: (r) => new Date(r.updatedAt).toLocaleString() },
  ]

  const renderWorkspaceDetail = () => {
    const ws = selectedWs || TFC_WORKSPACES.find((w) => w.name === 'lab-workspace')
    const tabs = ['Runs', 'States', 'Variables', 'Settings', 'Locks', 'Notifications', 'Team Access', 'Health', 'IDE']
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <div className="px-5 py-3 border-b border-[#2d2d44] flex items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-white">{ws.name}</h1>
            <p className="text-xs text-slate-500">Project: {ws.project} · ID {ws.id}</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="tfc-btn-primary" onClick={() => run('terraform_plan', {}, 'Plan queued')}>Queue plan</button>
            <button type="button" className="tfc-btn-primary" onClick={() => setShowApply(true)}>Apply run</button>
          </div>
        </div>
        <div className="flex border-b border-[#2d2d44] px-5 gap-1 shrink-0">
          {tabs.map((t) => (
            <button key={t} type="button" onClick={() => setWsTab(t.toLowerCase())}
              className={`tfc-tab ${wsTab === t.toLowerCase() ? 'tfc-tab-active' : ''}`}>{t}</button>
          ))}
        </div>
        <div className="flex-1 min-h-0 overflow-auto">
          {wsTab === 'runs' && (
            <div className="p-5 space-y-4">
              <SimDataTable columns={[
                { key: 'id', label: 'Run', sortable: true },
                { key: 'status', label: 'Status', sortable: true, render: (r) => <SimStatusBadge status={r.status} /> },
                { key: 'triggeredBy', label: 'Triggered By', sortable: true },
                { key: 'planCost', label: 'Plan Cost', sortable: true },
                { key: 'time', label: 'Duration', sortable: true },
              ]} rows={TFC_RUNS} searchKeys={['id', 'status']} onRowClick={(r) => setSelectedRun(r)} />
              {selectedRun && (
                <div className="tfc-card p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">Run {selectedRun.id}</h3>
                    <SimStatusBadge status={selectedRun.status} />
                  </div>
                  <div className="tfc-run-timeline">
                    {['Pending', 'Planning', 'Cost Estimation', 'Policy Check', 'Apply', selectedRun.status === 'Errored' ? 'Errored' : 'Applied'].map((step, i) => (
                      <span key={step} className={`tfc-run-step ${i < 5 ? 'tfc-run-step-done' : 'tfc-run-step-active'}`}>{step}</span>
                    ))}
                  </div>
                  <SimTerminalLog lines={TFC_RUN_LOG} title="Plan + Apply output" />
                </div>
              )}
            </div>
          )}
          {wsTab === 'variables' && (
            <div className="p-5">
              <div className="flex justify-between mb-3">
                <h3 className="font-semibold">Variables</h3>
                <button type="button" className="tfc-btn-primary" onClick={() => setShowVarModal(true)}>+ Add variable</button>
              </div>
              <SimDataTable columns={[
                { key: 'key', label: 'Key', sortable: true },
                { key: 'value', label: 'Value', sortable: true },
                { key: 'category', label: 'Category', sortable: true },
                { key: 'sensitive', label: 'Sensitive', render: (r) => r.sensitive ? 'Yes' : 'No' },
                { key: 'hcl', label: 'HCL', render: (r) => r.hcl ? 'Yes' : 'No' },
              ]} rows={TFC_VARIABLES} searchKeys={['key']} />
            </div>
          )}
          {wsTab === 'settings' && (
            <div className="p-5 grid gap-4 md:grid-cols-2">
              {[
                ['Workspace name', ws.name], ['Execution mode', 'Remote'], ['Auto apply', 'Disabled'],
                ['Terraform version', '1.7.5'], ['Working directory', '/'], ['VCS repository', 'github.com/fixitlab/infra'],
              ].map(([k, v]) => (
                <div key={k} className="tfc-card p-3">
                  <div className="text-[10px] uppercase text-slate-500 mb-1">{k}</div>
                  <div className="text-sm">{v}</div>
                </div>
              ))}
            </div>
          )}
          {wsTab === 'states' && (
            <div className="p-5">
              <h3 className="font-semibold mb-3">State versions</h3>
              <SimDataTable columns={[
                { key: 'serial', label: 'Serial', sortable: true },
                { key: 'createdAt', label: 'Created', sortable: true, render: (r) => new Date(r.createdAt).toLocaleString() },
                { key: 'createdBy', label: 'Created By', sortable: true },
                { key: 'resources', label: 'Resources', sortable: true },
              ]} rows={TFC_STATES} searchKeys={['createdBy']} />
            </div>
          )}
          {wsTab === 'locks' && (
            <div className="p-5">
              <h3 className="font-semibold mb-3">State locks</h3>
              {TFC_LOCKS.length === 0 ? (
                <p className="text-sm text-slate-500">No active locks.</p>
              ) : (
                <SimDataTable columns={[
                  { key: 'operation', label: 'Operation', sortable: true },
                  { key: 'lockedBy', label: 'Locked By', sortable: true },
                  { key: 'lockedAt', label: 'Locked At', sortable: true, render: (r) => new Date(r.lockedAt).toLocaleString() },
                  { key: 'age', label: 'Age', sortable: true },
                ]} rows={TFC_LOCKS} searchKeys={['lockedBy']} />
              )}
            </div>
          )}
          {wsTab === 'notifications' && (
            <div className="p-5">
              <SimDataTable columns={[
                { key: 'name', label: 'Destination', sortable: true },
                { key: 'triggers', label: 'Triggers', sortable: true },
                { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'enabled' ? 'success' : 'disabled'} label={r.status} /> },
              ]} rows={TFC_WS_NOTIFICATIONS} searchKeys={['name']} />
            </div>
          )}
          {wsTab === 'team access' && (
            <div className="p-5">
              <SimDataTable columns={[
                { key: 'team', label: 'Team', sortable: true },
                { key: 'permission', label: 'Permission', sortable: true },
                { key: 'inherited', label: 'Inherited', render: (r) => r.inherited ? 'Yes' : 'No' },
              ]} rows={TFC_TEAM_ACCESS} searchKeys={['team']} />
            </div>
          )}
          {wsTab === 'health' && (
            <div className="p-5 grid gap-3 md:grid-cols-2">
              {TFC_HEALTH.map((h) => (
                <div key={h.check} className="tfc-card p-4 flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{h.check}</div>
                    <div className="text-xs text-slate-500 mt-1">{h.detail}</div>
                  </div>
                  <SimStatusBadge status={h.status === 'passing' ? 'success' : h.status === 'warning' ? 'pending' : 'error'} label={h.status} />
                </div>
              ))}
            </div>
          )}
          {wsTab === 'ide' && (
            <TerraformWorkspaceIde sessionId={sessionId} scenario={scenario} terminalSession={terminalSession}
              terminalHost={terminalHost} blockedCommands={blockedCommands} isMobile={isMobile}
              state={state} setState={setState} onRefresh={refresh} />
          )}
          {!['runs', 'variables', 'settings', 'ide', 'states', 'locks', 'notifications', 'team access', 'health'].includes(wsTab) && (
            <div className="p-8 text-center text-slate-500 text-sm capitalize">{wsTab} — workspace configuration view</div>
          )}
        </div>
      </div>
    )
  }

  const renderMain = () => {
    if (selectedWs || nav === 'workspace-detail') return renderWorkspaceDetail()
    if (nav === 'workspaces') {
      return (
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold text-white">Workspaces</h1>
            <button type="button" className="tfc-btn-primary flex items-center gap-1" onClick={() => setShowNewWs(true)}>
              <Plus size={14} /> New Workspace
            </button>
          </div>
          <SimDataTable columns={workspaceColumns} rows={allWorkspaces} searchKeys={['name', 'project', 'status']}
            onRowClick={(ws) => { setSelectedWs(ws); setWsTab('runs') }} />
        </div>
      )
    }
    if (nav === 'registry-modules') {
      return (
        <div className="p-5">
          <h1 className="text-xl font-semibold text-white mb-4">Private Registry — Modules</h1>
          <SimDataTable columns={[
            { key: 'name', label: 'Module', sortable: true },
            { key: 'provider', label: 'Provider', sortable: true },
            { key: 'version', label: 'Latest Version', sortable: true },
            { key: 'published', label: 'Published', sortable: true },
          ]} rows={TFC_MODULES} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'settings-teams') {
      return (
        <div className="p-5">
          <h1 className="text-xl font-semibold text-white mb-4">Teams</h1>
          <SimDataTable columns={[
            { key: 'name', label: 'Team', sortable: true },
            { key: 'access', label: 'Organization Access', sortable: true },
            { key: 'members', label: 'Members', sortable: true },
          ]} rows={TFC_TEAMS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'settings-agents') {
      return (
        <div className="p-5">
          <h1 className="text-xl font-semibold text-white mb-4">Agent Pools</h1>
          <SimDataTable columns={[
            { key: 'name', label: 'Pool', sortable: true },
            { key: 'agents', label: 'Agents', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status} /> },
          ]} rows={TFC_AGENT_POOLS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'registry-providers') {
      return (
        <div className="p-5">
          <h1 className="text-xl font-semibold text-white mb-4">Private Registry — Providers</h1>
          <SimDataTable columns={[
            { key: 'name', label: 'Provider', sortable: true, render: (_, i) => ['hashicorp/aws', 'hashicorp/random'][i] || 'hashicorp/aws' },
            { key: 'version', label: 'Version', sortable: true, render: () => '5.47.0' },
            { key: 'published', label: 'Published', sortable: true, render: () => '2026-06-01' },
          ]} rows={[{ id: 'p1' }, { id: 'p2' }]} searchKeys={[]} />
        </div>
      )
    }
    if (nav === 'settings-general') {
      return (
        <div className="p-5 grid gap-4 md:grid-cols-2">
          {TFC_SETTINGS_GENERAL.map(([k, v]) => (
            <div key={k} className="tfc-card p-3"><div className="text-[10px] uppercase text-slate-500 mb-1">{k}</div><div className="text-sm">{v}</div></div>
          ))}
        </div>
      )
    }
    if (nav === 'settings-sso') {
      return (
        <div className="p-5 grid gap-4 md:grid-cols-2">
          {TFC_SETTINGS_SSO.map(([k, v]) => (
            <div key={k} className="tfc-card p-3"><div className="text-[10px] uppercase text-slate-500 mb-1">{k}</div><div className="text-sm">{v}</div></div>
          ))}
        </div>
      )
    }
    if (nav === 'settings-vcs') {
      return (
        <div className="p-5">
          <SimDataTable columns={[
            { key: 'provider', label: 'Provider', sortable: true },
            { key: 'org', label: 'Organization', sortable: true },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'connected' ? 'success' : 'disabled'} label={r.status} /> },
            { key: 'repos', label: 'Repos', sortable: true },
          ]} rows={TFC_SETTINGS_VCS} searchKeys={['provider']} />
        </div>
      )
    }
    if (nav === 'settings-tokens') {
      return (
        <div className="p-5">
          <SimDataTable columns={[
            { key: 'name', label: 'Token', sortable: true },
            { key: 'created', label: 'Created', sortable: true },
            { key: 'lastUsed', label: 'Last Used', sortable: true },
            { key: 'scopes', label: 'Scopes', sortable: true },
          ]} rows={TFC_SETTINGS_TOKENS} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'settings-audit') {
      return (
        <div className="p-5">
          <SimDataTable columns={[
            { key: 'time', label: 'Time', sortable: true, render: (r) => new Date(r.time).toLocaleString() },
            { key: 'user', label: 'User', sortable: true },
            { key: 'action', label: 'Action', sortable: true },
            { key: 'target', label: 'Target', sortable: true },
          ]} rows={TFC_AUDIT_LOG} searchKeys={['user', 'action']} />
        </div>
      )
    }
    if (nav === 'settings-usage') {
      return (
        <div className="p-5 grid gap-4 md:grid-cols-3">
          {TFC_USAGE.map((u) => (
            <div key={u.metric} className="tfc-card p-4">
              <div className="text-[10px] uppercase text-slate-500">{u.metric}</div>
              <div className="text-2xl font-bold text-violet-300 mt-1">{u.value}</div>
              <div className="text-xs text-slate-500 mt-1">Limit: {u.limit}</div>
            </div>
          ))}
        </div>
      )
    }
    if (nav === 'settings-cost' || nav === 'settings-notifications') {
      return (
        <div className="p-5">
          <h1 className="text-xl font-semibold text-white mb-4 capitalize">{nav.replace('settings-', '').replace(/-/g, ' ')}</h1>
          <div className="tfc-card p-4 text-sm text-slate-400">
            {nav === 'settings-cost' ? 'Cost estimation is enabled for all workspaces. Plans show estimated monthly cost before apply.' : 'Organization notifications route to Slack #infra and email platform@fixitlab.local on errored runs.'}
          </div>
        </div>
      )
    }
    if (nav === 'explorer' || nav === 'registry-public' || nav === 'registry-private') {
      return (
        <div className="p-5">
          <h1 className="text-xl font-semibold text-white mb-2 capitalize">{nav.replace(/-/g, ' ')}</h1>
          <p className="text-sm text-slate-500 mb-4">Browse {nav.includes('registry') ? 'registry modules and providers' : 'projects and workspace hierarchy'}.</p>
          <SimDataTable columns={workspaceColumns} rows={allWorkspaces.slice(0, 6)} searchKeys={['name']} onRowClick={(ws) => { setSelectedWs(ws); setWsTab('runs') }} />
        </div>
      )
    }
    return (
      <div className="p-8 text-center text-slate-500">
        <Settings size={32} className="mx-auto mb-2 opacity-40" />
        <p className="text-sm capitalize">{nav.replace(/-/g, ' ')} — Terraform Cloud settings</p>
      </div>
    )
  }

  const chromeWithLabel = {
    ...chromeProps,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const modeTabs = (
    <>
      <button
        type="button"
        className={`tfc-tab ${shellMode === 'ide' ? 'tfc-tab-active' : ''}`}
        onClick={() => setShellMode('ide')}
      >
        <Code2 size={13} className="inline mr-1" /> VS Code IDE
      </button>
      <button
        type="button"
        className={`tfc-tab ${shellMode === 'cloud' ? 'tfc-tab-active' : ''}`}
        onClick={() => setShellMode('cloud')}
      >
        <Cloud size={13} className="inline mr-1" /> Terraform Cloud
      </button>
      {onToggleTerminal && (
        <button
          type="button"
          className={`tfc-tab ${simTerminalOpen ? 'tfc-tab-active' : ''}`}
          onClick={onToggleTerminal}
        >
          <Terminal size={13} className="inline mr-1" /> Terminal
        </button>
      )}
    </>
  )

  if (shellMode === 'ide') {
    return (
      <div className={simPanelRoot(embedded, 'tfc-shell sim-product')}>
        <LabChromeBar icon={Cloud} title={`${iac.label} · VS Code IDE`} subtitle={scenario?.title || slug}
          accent={iac.accent} className="lab-chrome-bar !bg-[#1a1a2e]" {...chromeWithLabel}>
          {modeTabs}
        </LabChromeBar>
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <TerraformWorkspaceIde
            sessionId={sessionId}
            scenario={scenario}
            terminalSession={terminalSession}
            terminalHost={terminalHost}
            blockedCommands={blockedCommands}
            isMobile={isMobile}
            state={state}
            setState={setState}
            onRefresh={refresh}
            standalone
          />
        </div>
      </div>
    )
  }

  return (
    <div className={simPanelRoot(embedded, 'tfc-shell sim-product')}>
      <LabChromeBar icon={Cloud} title={iac.cloudTitle} subtitle={scenario?.title || slug}
        accent={iac.accent} className="lab-chrome-bar !bg-[#1a1a2e]" {...chromeWithLabel}>
        {modeTabs}
      </LabChromeBar>

      <div className="tfc-topbar flex items-center justify-between px-4 py-2 shrink-0">
        <SimBreadcrumbs items={breadcrumbs} />
        <span className="tfc-org-switcher">{TFC_ORG.name}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={selectedWs ? 'workspaces' : nav}
          onSelect={(key) => { setNav(key); setSelectedWs(null); if (key === 'workspaces') setWsTab('runs') }}
          accent={iac.accent} className="tfc-sidebar" />
        <main className="tfc-content flex-1 min-h-0 flex flex-col overflow-hidden">{renderMain()}</main>
      </div>

      <SimModal open={showNewWs} onClose={() => setShowNewWs(false)} title="Create Workspace"
        footer={<><button type="button" className="text-sm text-slate-400 px-3 py-1.5" onClick={() => setShowNewWs(false)}>Cancel</button><button type="button" className="tfc-btn-primary" onClick={() => {
          const name = (newWsName || 'lab-workspace').trim()
          const ws = { id: `ws-${Date.now()}`, name, project: 'Training', status: 'ready', terraform: '1.7.5', updated: 'Just now' }
          setExtraWorkspaces((prev) => [...prev, ws])
          setShowNewWs(false)
          setSelectedWs(ws)
          setWsTab('ide')
        }}>Create</button></>}>
        <div className="space-y-3 text-sm">
          <label className="block"><span className="text-slate-400 text-xs">Name</span><input className="w-full mt-1 px-3 py-2 rounded bg-slate-900 border border-slate-600" value={newWsName} onChange={(e) => setNewWsName(e.target.value)} /></label>
          <label className="block"><span className="text-slate-400 text-xs">Project</span><select className="w-full mt-1 px-3 py-2 rounded bg-slate-900 border border-slate-600"><option>Training</option></select></label>
        </div>
      </SimModal>

      <SimModal open={showApply} onClose={() => setShowApply(false)} title="Confirm Apply"
        footer={<><button type="button" className="text-sm px-3 py-1.5" onClick={() => setShowApply(false)}>Cancel</button><button type="button" className="tfc-btn-primary" disabled={busy} onClick={() => { run('terraform_apply', {}, 'Apply complete'); setShowApply(false) }}>Confirm & Apply</button></>}>
        <p className="text-sm text-slate-300">Apply the latest successful plan to infrastructure?</p>
      </SimModal>

      <SimModal open={showVarModal} onClose={() => setShowVarModal(false)} title="Add Variable"
        footer={<button type="button" className="tfc-btn-primary" onClick={() => setShowVarModal(false)}>Save variable</button>}>
        <div className="space-y-3 text-sm">
          <input placeholder="Key" className="w-full px-3 py-2 rounded bg-slate-900 border border-slate-600" />
          <input placeholder="Value" className="w-full px-3 py-2 rounded bg-slate-900 border border-slate-600" />
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" /> Sensitive</label>
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" /> HCL</label>
        </div>
      </SimModal>
    </div>
  )
}
