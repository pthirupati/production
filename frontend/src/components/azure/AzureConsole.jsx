import { useState } from 'react'
import { azureApi } from '../../api/azure'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Cloud, Server, Network, Shield, HardDrive, Plus, AlertTriangle,
  Terminal, Play, Square, RotateCw, Maximize2, Link2, Unlink,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession } from '../sim/shared'
import '../../styles/sim-products.css'
import './azure.css'

const AZ_LAB_USER = 'admin@fixitlab.onmicrosoft.com'
const AZ_LAB_PASS = 'lab123'
const ACCENT = '#0078d4'

const SIDEBAR = [
  { key: 'overview', label: 'Overview', icon: Cloud },
  { key: 'vms', label: 'Virtual machines', icon: Server },
  { key: 'networking', label: 'Networking', icon: Network },
  { key: 'disks', label: 'Disks', icon: HardDrive },
]

const VM_SIZE_OPTIONS = [
  { value: 'Standard_B1s', label: 'Standard_B1s (1 vCPU, 1 GiB) — burstable' },
  { value: 'Standard_B2s', label: 'Standard_B2s (2 vCPU, 4 GiB) — burstable' },
  { value: 'Standard_B2ms', label: 'Standard_B2ms (2 vCPU, 8 GiB) — burstable' },
  { value: 'Standard_D2s_v5', label: 'Standard_D2s_v5 (2 vCPU, 8 GiB) — general purpose' },
  { value: 'Standard_D4s_v5', label: 'Standard_D4s_v5 (4 vCPU, 16 GiB) — general purpose' },
  { value: 'Standard_D8s_v5', label: 'Standard_D8s_v5 (8 vCPU, 32 GiB) — general purpose' },
  { value: 'Standard_E2s_v5', label: 'Standard_E2s_v5 (2 vCPU, 16 GiB) — memory optimized' },
  { value: 'Standard_F2s_v2', label: 'Standard_F2s_v2 (2 vCPU, 4 GiB) — compute optimized' },
]

function powerStatus(power) {
  if (power === 'running') return 'success'
  if (power === 'stopped') return 'error'
  return 'pending'
}

export default function AzureConsole({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, azureApi)
  const [nav, setNav] = useState('overview')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [vmDetail, setVmDetail] = useState(null)
  const [resizeTo, setResizeTo] = useState('')
  const [ruleModalNsg, setRuleModalNsg] = useState(null)
  const [ruleName, setRuleName] = useState('AllowRule')
  const [rulePort, setRulePort] = useState('22')
  const [rulePriority, setRulePriority] = useState(200)
  const [ruleAccess, setRuleAccess] = useState('Allow')
  const [attachTarget, setAttachTarget] = useState(null)
  const [createDiskModal, setCreateDiskModal] = useState(false)
  const [newDiskName, setNewDiskName] = useState('disk-new')
  const [newDiskSize, setNewDiskSize] = useState(128)

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}
  const vms = st.vms || []
  const nsgs = st.nsgs || []
  const disks = st.disks || []
  const vnets = st.vnets || []
  const resourceGroups = st.resource_groups || []

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const breadcrumbs = [{ label: st?.subscription?.name || 'Subscription', onClick: () => setNav('overview') }]
  if (nav !== 'overview') breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === AZ_LAB_USER && loginPass === AZ_LAB_PASS) || (u === 'admin' && loginPass === 'admin')
      if (ok) {
        setLoginError('')
        run(() => azureApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${AZ_LAB_USER} / ${AZ_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0a1929]')}>
        <LabChromeBar title="Microsoft Azure" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: ACCENT }}>
              <Cloud size={18} /> Sign in to Azure
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Sign in to the FixItLab Enterprise Subscription.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Email, phone, or Skype</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={AZ_LAB_USER}
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
                className="az-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign in
              </button>
              <button type="button"
                onClick={() => { setLoginUser(AZ_LAB_USER); setLoginPass(AZ_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{AZ_LAB_USER}</span> / <span className="font-mono text-slate-700">{AZ_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const vmPower = (vm, op) => {
    const fn = op === 'start' ? azureApi.startVm : op === 'stop' ? azureApi.stopVm : azureApi.restartVm
    run(() => fn(sessionId, vm.name), `${op[0].toUpperCase()}${op.slice(1)} requested`)
  }

  const submitRule = () => {
    run(() => azureApi.addNsgRule(sessionId, ruleModalNsg, {
      name: ruleName, priority: Number(rulePriority), protocol: 'TCP',
      destination_port: rulePort, access: ruleAccess, direction: 'Inbound',
    }), 'Rule added')
    setRuleModalNsg(null)
  }

  const renderOverview = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Resource groups</h2>
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'location', label: 'Region', sortable: true },
        { key: 'resources', label: 'Resources', render: () => vms.length + vnets.length + nsgs.length + disks.length },
      ]} rows={resourceGroups} searchKeys={['name']} />
      <h2 className="text-lg font-semibold pt-2">Quick glance</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="az-tile"><Server size={16} /> <div><div className="az-tile-num">{vms.length}</div><div className="az-tile-label">Virtual machines</div></div></div>
        <div className="az-tile"><Network size={16} /> <div><div className="az-tile-num">{vnets.length}</div><div className="az-tile-label">Virtual networks</div></div></div>
        <div className="az-tile"><Shield size={16} /> <div><div className="az-tile-num">{nsgs.length}</div><div className="az-tile-label">Network security groups</div></div></div>
        <div className="az-tile"><HardDrive size={16} /> <div><div className="az-tile-num">{disks.length}</div><div className="az-tile-label">Disks</div></div></div>
      </div>
    </div>
  )

  const renderVms = () => (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Virtual machines</h2>
      {broken.vm_undersized && (
        <div className="az-banner">
          <AlertTriangle size={14} /> <strong>{broken.vm_undersized}</strong> looks undersized for its current workload — consider resizing it.
        </div>
      )}
      {broken.vm_stopped && (
        <div className="az-banner">
          <AlertTriangle size={14} /> <strong>{broken.vm_stopped}</strong> is stopped.
        </div>
      )}
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'power_state', label: 'Status', render: (r) => <SimStatusBadge status={powerStatus(r.power_state)} label={r.power_state} /> },
        { key: 'size', label: 'Size', sortable: true },
        { key: 'private_ip', label: 'Private IP', sortable: true },
        { key: 'resource_group', label: 'Resource group', sortable: true },
        { key: 'actions', label: 'Actions', render: (r) => (
          <div className="flex items-center gap-1">
            {r.power_state !== 'running' && (
              <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); vmPower(r, 'start') }}>
                <Play size={11} /> Start
              </button>
            )}
            {r.power_state === 'running' && (
              <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); vmPower(r, 'stop') }}>
                <Square size={11} /> Stop
              </button>
            )}
            <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); vmPower(r, 'restart') }}>
              <RotateCw size={11} /> Restart
            </button>
            <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); setVmDetail(r); setResizeTo(r.size) }}>
              <Maximize2 size={11} /> Size
            </button>
          </div>
        ) },
      ]} rows={vms} searchKeys={['name']} onRowClick={(r) => { setVmDetail(r); setResizeTo(r.size) }} />
    </div>
  )

  const renderNetworking = () => (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-2">Virtual networks</h2>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'address_space', label: 'Address space', sortable: true },
          { key: 'subnets', label: 'Subnets', render: (r) => (r.subnets || []).map((s) => s.name).join(', ') },
        ]} rows={vnets} searchKeys={['name']} />
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-2">Network security groups</h2>
        {nsgs.map((nsg) => (
          <div key={nsg.name} className="az-panel mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-sm flex items-center gap-1.5"><Shield size={14} /> {nsg.name}</span>
              <button type="button" className="az-btn-sm" onClick={() => { setRuleModalNsg(nsg.name); setRuleName('AllowRule'); setRulePort('22'); setRulePriority(200); setRuleAccess('Allow') }}>
                <Plus size={11} /> Add inbound rule
              </button>
            </div>
            <SimDataTable columns={[
              { key: 'priority', label: 'Priority', sortable: true },
              { key: 'name', label: 'Name', sortable: true },
              { key: 'direction', label: 'Direction', sortable: true },
              { key: 'protocol', label: 'Protocol', sortable: true },
              { key: 'destination_port', label: 'Port', sortable: true },
              { key: 'access', label: 'Action', render: (r) => <SimStatusBadge status={r.access === 'Allow' ? 'success' : 'error'} label={r.access} /> },
              { key: 'actions', label: '', render: (r) => !r.system && (
                <button type="button" className="az-btn-sm az-btn-outline"
                  onClick={() => run(() => azureApi.removeNsgRule(sessionId, nsg.name, r.name), 'Rule removed')}>
                  Remove
                </button>
              ) },
            ]} rows={nsg.rules || []} pageSize={20} />
          </div>
        ))}
      </div>
    </div>
  )

  const renderDisks = () => (
    <div className="space-y-3">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Disks</h2>
        <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateDiskModal(true)}>
          <Plus size={14} /> Create disk
        </button>
      </div>
      {broken.disk_unattached && (
        <div className="az-banner">
          <AlertTriangle size={14} /> <strong>{broken.disk_unattached}</strong> is unattached.
        </div>
      )}
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GiB` },
        { key: 'sku', label: 'SKU', sortable: true },
        { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'Attached' ? 'success' : 'warning'} label={r.state} /> },
        { key: 'attached_to', label: 'Attached to', render: (r) => r.attached_to || '—' },
        { key: 'actions', label: 'Actions', render: (r) => (
          r.state === 'Attached' && !r.os_disk ? (
            <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); run(() => azureApi.detachDisk(sessionId, r.name), 'Disk detached') }}>
              <Unlink size={11} /> Detach
            </button>
          ) : r.state === 'Unattached' ? (
            <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); setAttachTarget(r.name) }}>
              <Link2 size={11} /> Attach
            </button>
          ) : null
        ) },
      ]} rows={disks} searchKeys={['name']} />
    </div>
  )

  const renderContent = () => {
    if (nav === 'vms') return renderVms()
    if (nav === 'networking') return renderNetworking()
    if (nav === 'disks') return renderDisks()
    return renderOverview()
  }

  return (
    <div className={simPanelRoot(embedded, 'az-shell sim-product')}>
      <LabChromeBar title="Microsoft Azure" subtitle={scenario?.title || slug} accent={ACCENT}
        className="lab-chrome-bar !bg-[#0078d4]" {...chromeProps}>
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

      <div className="px-4 py-2 bg-[#053e6e] border-b border-black/20 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-300" />
        <span className="text-xs text-slate-300">{st?.session?.user || 'admin'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#04223f] az-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#f5f7fa]">{renderContent()}</main>
      </div>

      <SimModal open={!!vmDetail} onClose={() => setVmDetail(null)} title={`${vmDetail?.name || ''} — Size`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setVmDetail(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.resizeVm(sessionId, vmDetail.name, resizeTo), 'Resize completed')
            setVmDetail(null)
          }}>Resize</button>
        </>}>
        <p className="text-xs text-slate-400 mb-3">Current size: <span className="font-mono">{vmDetail?.size}</span> · Status: {vmDetail?.power_state}</p>
        <label className="block text-sm">New size
          <select className="w-full mt-1 border rounded px-2 py-1.5 text-slate-900" value={resizeTo} onChange={(e) => setResizeTo(e.target.value)}>
            {VM_SIZE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </SimModal>

      <SimModal open={!!ruleModalNsg} onClose={() => setRuleModalNsg(null)} title={`Add inbound security rule — ${ruleModalNsg || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setRuleModalNsg(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={submitRule}>Add</button>
        </>}>
        <label className="block text-sm">Name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={ruleName} onChange={(e) => setRuleName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Destination port
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={rulePort} onChange={(e) => setRulePort(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Priority
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={rulePriority} onChange={(e) => setRulePriority(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Action
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={ruleAccess} onChange={(e) => setRuleAccess(e.target.value)}>
            <option value="Allow">Allow</option>
            <option value="Deny">Deny</option>
          </select>
        </label>
      </SimModal>

      <SimModal open={!!attachTarget} onClose={() => setAttachTarget(null)} title={`Attach disk — ${attachTarget || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setAttachTarget(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy || !vms.length} onClick={() => {
            run(() => azureApi.attachDisk(sessionId, vms[0].name, attachTarget), 'Disk attached')
            setAttachTarget(null)
          }}>Attach to {vms[0]?.name || 'VM'}</button>
        </>}>
        <p className="text-sm text-slate-300">Attach this managed disk to the virtual machine <span className="font-mono">{vms[0]?.name}</span>.</p>
      </SimModal>

      <SimModal open={createDiskModal} onClose={() => setCreateDiskModal(false)} title="Create managed disk"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setCreateDiskModal(false)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.createDisk(sessionId, newDiskName, Number(newDiskSize)), 'Disk created')
            setCreateDiskModal(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Disk name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={newDiskName} onChange={(e) => setNewDiskName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Size (GiB)
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={newDiskSize} onChange={(e) => setNewDiskSize(e.target.value)} />
        </label>
      </SimModal>
    </div>
  )
}
