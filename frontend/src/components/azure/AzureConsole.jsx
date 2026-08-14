import { useMemo, useState } from 'react'
import { azureApi } from '../../api/azure'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Cloud, Server, Network, Shield, HardDrive, Plus, AlertTriangle,
  Terminal, Play, Square, RotateCw, Maximize2, Link2, Unlink, KeyRound,
  Database, Users, Activity, Layers, Box, Boxes, AppWindow, Zap, Container,
  Flame, Globe2, ShieldAlert, IdCard, RefreshCw,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import {
  SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, SimModal, useSimSession,
  GlobalSearch, indexAzureState, SimLoginGateCard } from '../sim/shared'
import CloudShellPanel from '../lab/CloudShellPanel'
import { renderAzureV2Page } from './AzureV2Panels'
import '../../styles/sim-products.css'
import './azure.css'

/* SIMULATED-CREDENTIAL: lab-console flavour, not a real secret. Shown to the
   learner on screen (with an autofill button) so the fake console feels real, and
   the gate is bypassed entirely once a provisioned lab session exists. Grants no
   access to anything. Secret scanners should allowlist this marker rather than
   flagging these lines. See docs/AUDIT_2026_08_TODO.md §Y2e. */
const AZ_LAB_USER = 'admin@fixitlab.onmicrosoft.com'
const AZ_LAB_PASS = 'lab123'
const ACCENT = '#0078d4'

// Stable fallbacks for absent server state. A bare `|| {}` mints a new identity
// every render, so the `indexAzureState(st)` memo below re-indexed the entire
// console state on every pass. Frozen so an accidental in-place mutation throws
// rather than silently corrupting the shared fallback.
const EMPTY_OBJ = Object.freeze({})
const EMPTY_ARR = Object.freeze([])

const SIDEBAR = [
  { key: 'overview', label: 'Overview', icon: Cloud },
  { key: 'vms', label: 'Virtual machines', icon: Server },
  { key: 'vmss', label: 'Scale sets', icon: Boxes },
  { key: 'appservice', label: 'App Services', icon: AppWindow },
  { key: 'functions', label: 'Function apps', icon: Zap },
  { key: 'containerapps', label: 'Container apps', icon: Container },
  { key: 'aks', label: 'Kubernetes services', icon: Boxes },
  { key: 'networking', label: 'Networking', icon: Network },
  { key: 'loadbalancers', label: 'Load balancers', icon: Layers },
  { key: 'firewall', label: 'Firewalls & VPN', icon: Flame },
  { key: 'disks', label: 'Disks', icon: HardDrive },
  { key: 'storage', label: 'Storage accounts', icon: Database },
  { key: 'cosmos', label: 'Cosmos DB', icon: Globe2 },
  { key: 'keyvault', label: 'Key vaults', icon: KeyRound },
  { key: 'entra', label: 'Microsoft Entra ID', icon: IdCard },
  { key: 'iam', label: 'Access control (IAM)', icon: Users },
  { key: 'sentinel', label: 'Microsoft Sentinel', icon: ShieldAlert },
  { key: 'activity', label: 'Activity log', icon: Activity },
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

const AZ_IMAGE_OPTIONS = [
  { value: 'Ubuntu 22.04 LTS', label: 'Ubuntu Server 22.04 LTS — gen2' },
  { value: 'Ubuntu 24.04 LTS', label: 'Ubuntu Server 24.04 LTS — gen2' },
  { value: 'Debian 12', label: 'Debian 12 "bookworm" — gen2' },
  { value: 'Red Hat Enterprise Linux 9', label: 'Red Hat Enterprise Linux 9 — gen2' },
  { value: 'Windows Server 2022 Datacenter', label: 'Windows Server 2022 Datacenter — gen2' },
]

const AZ_LOCATION_OPTIONS = [
  { value: 'eastus', label: 'East US' },
  { value: 'eastus2', label: 'East US 2' },
  { value: 'westus2', label: 'West US 2' },
  { value: 'centralus', label: 'Central US' },
  { value: 'westeurope', label: 'West Europe' },
  { value: 'northeurope', label: 'North Europe' },
  { value: 'southeastasia', label: 'Southeast Asia' },
]

const AZ_OS_DISK_SKU_OPTIONS = [
  { value: 'Premium_SSD_LRS', label: 'Premium SSD (locally redundant)' },
  { value: 'StandardSSD_LRS', label: 'Standard SSD (locally redundant)' },
  { value: 'Standard_SSD_LRS', label: 'Standard SSD LRS' },
  { value: 'Standard_LRS', label: 'Standard HDD (locally redundant)' },
  { value: 'Premium_SSD_ZRS', label: 'Premium SSD (zone redundant)' },
]

const NET_CREATE_DEFAULTS = '__create_defaults__'

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
  const { state, loading, busy, error, run, refresh } = useSimSession(sessionId, slug, azureApi)
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
  const [ruleProtocol, setRuleProtocol] = useState('TCP')
  const [ruleSource, setRuleSource] = useState('*')
  const [attachTarget, setAttachTarget] = useState(null)
  const [createDiskModal, setCreateDiskModal] = useState(false)
  const [newDiskName, setNewDiskName] = useState('disk-new')
  const [newDiskSize, setNewDiskSize] = useState(128)
  const [createRgOpen, setCreateRgOpen] = useState(false)
  const [rgName, setRgName] = useState('rg-workloads')
  const [createSaOpen, setCreateSaOpen] = useState(false)
  const [saName, setSaName] = useState('stworkloads')
  const [createVmOpen, setCreateVmOpen] = useState(false)
  const [newVmName, setNewVmName] = useState('vm-app01')
  const [newVmSize, setNewVmSize] = useState('Standard_B2s')
  const [newVmImage, setNewVmImage] = useState('Ubuntu 22.04 LTS')
  const [newVmLocation, setNewVmLocation] = useState('eastus')
  const [newVmRg, setNewVmRg] = useState('')
  const [newVmNet, setNewVmNet] = useState('')
  const [newVmPublicIp, setNewVmPublicIp] = useState(true)
  const [newVmAdmin, setNewVmAdmin] = useState('azureuser')
  const [newVmAuth, setNewVmAuth] = useState('sshPublicKey')
  const [newVmSshKey, setNewVmSshKey] = useState('')
  const [newVmPassword, setNewVmPassword] = useState('')
  const [newVmOsDiskSku, setNewVmOsDiskSku] = useState('Premium_SSD_LRS')
  const [newVmOsDiskGb, setNewVmOsDiskGb] = useState(30)
  const [subnetModal, setSubnetModal] = useState(null)
  const [subnetName, setSubnetName] = useState('snet-app')
  const [subnetCidr, setSubnetCidr] = useState('10.10.2.0/24')
  const [secretModal, setSecretModal] = useState(null)
  const [secretName, setSecretName] = useState('')
  const [roleModal, setRoleModal] = useState(false)
  const [rolePrincipal, setRolePrincipal] = useState('')
  const [roleName, setRoleName] = useState('Reader')
  const [lbRuleModal, setLbRuleModal] = useState(null)
  const [lbRuleName, setLbRuleName] = useState('https')
  const [lbFront, setLbFront] = useState(443)
  const [lbBack, setLbBack] = useState(443)
  const [containerModal, setContainerModal] = useState(null)
  const [containerName, setContainerName] = useState('logs')
  const [cloudShellOpen, setCloudShellOpen] = useState(false)
  const [createVmssOpen, setCreateVmssOpen] = useState(false)
  const [vmssName, setVmssName] = useState('vmss-api')
  const [vmssCap, setVmssCap] = useState(2)
  const [createAppOpen, setCreateAppOpen] = useState(false)
  const [appName, setAppName] = useState('app-workloads')
  const [createFuncOpen, setCreateFuncOpen] = useState(false)
  const [funcName, setFuncName] = useState('func-events')
  const [createCaOpen, setCreateCaOpen] = useState(false)
  const [caName, setCaName] = useState('ca-worker')
  const [createAksOpen, setCreateAksOpen] = useState(false)
  const [aksName, setAksName] = useState('aks-workloads')
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteUpn, setInviteUpn] = useState('partner@fabrikam.com')

  const st = state?.state || EMPTY_OBJ
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || EMPTY_OBJ
  const broken = st?.broken || EMPTY_OBJ
  const vms = st.vms || EMPTY_ARR
  const nsgs = st.nsgs || EMPTY_ARR
  const disks = st.disks || EMPTY_ARR
  const vnets = st.vnets || EMPTY_ARR
  const resourceGroups = st.resource_groups || EMPTY_ARR
  const storageAccounts = st.storage_accounts || EMPTY_ARR
  const keyVaults = st.key_vaults || EMPTY_ARR
  const roleAssignments = st.role_assignments || EMPTY_ARR
  const loadBalancers = st.load_balancers || EMPTY_ARR
  const searchServices = useMemo(
    () => SIDEBAR.map((s) => ({ key: s.key, label: s.label, keywords: s.key })),
    [],
  )
  const searchResources = useMemo(() => indexAzureState(st), [st])
  const publicIps = st.public_ips || EMPTY_ARR
  const activityLog = st.activity_log || st.events || EMPTY_ARR
  const snapshots = st.snapshots || EMPTY_ARR

  const defaultRg = resourceGroups[0]?.name || 'rg-fixitlab-prod'
  const netOptions = useMemo(() => {
    const opts = []
    for (const vn of vnets) {
      for (const sn of (vn.subnets || [])) {
        opts.push({
          value: `${vn.name}/${sn.name}`,
          label: `${vn.name} / ${sn.name}${sn.address_prefix ? ` (${sn.address_prefix})` : ''}`,
          vnet: vn.name,
          subnet: sn.name,
        })
      }
    }
    return opts
  }, [vnets])
  const defaultNet = netOptions[0]?.value || NET_CREATE_DEFAULTS

  const openCreateVm = () => {
    setNewVmName(`vm-app${Date.now().toString(36).slice(-3)}`)
    setNewVmSize('Standard_B2s')
    setNewVmImage('Ubuntu 22.04 LTS')
    setNewVmLocation(resourceGroups[0]?.location || 'eastus')
    setNewVmRg(defaultRg)
    setNewVmNet(defaultNet)
    setNewVmPublicIp(true)
    setNewVmAdmin('azureuser')
    setNewVmAuth('sshPublicKey')
    setNewVmSshKey('')
    setNewVmPassword('')
    setNewVmOsDiskSku('Premium_SSD_LRS')
    setNewVmOsDiskGb(30)
    setCreateVmOpen(true)
  }

  const submitCreateVm = () => {
    const payload = {
      name: newVmName.trim(),
      size: newVmSize,
      image: newVmImage,
      os: newVmImage,
      location: newVmLocation,
      resource_group: newVmRg || defaultRg,
      assign_public_ip: !!newVmPublicIp,
      admin_username: newVmAdmin.trim() || 'azureuser',
      authentication_type: newVmAuth,
      os_disk_sku: newVmOsDiskSku,
      os_disk_gb: Number(newVmOsDiskGb) || 30,
    }
    if (newVmNet === NET_CREATE_DEFAULTS) {
      payload.create_networking = true
      payload.vnet = `vnet-${payload.name}`
      payload.subnet = 'default'
    } else {
      const [vnet, subnet] = (newVmNet || defaultNet).split('/')
      payload.vnet = vnet
      payload.subnet = subnet
    }
    if (newVmAuth === 'sshPublicKey' && newVmSshKey.trim()) {
      payload.ssh_public_key = newVmSshKey.trim()
    }
    // Password is never sent to the API as a real secret — engine only records auth type.
    run(() => azureApi.createVm(sessionId, payload), 'VM created')
    setCreateVmOpen(false)
  }

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: onExit || onToggleTerminal,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : (onExit ? 'Close' : 'Terminal'),
  }

  const breadcrumbs = [{ label: st?.subscription?.name || 'Subscription', onClick: () => setNav('overview') }]
  if (nav !== 'overview') breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })

  if (loading) {
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0a1929]')}>
        <LabChromeBar title="Microsoft Azure" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-6 text-sm text-slate-400">
          Loading Azure portal…
        </div>
      </div>
    )
  }

  if (error || !state) {
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0a1929]')}>
        <LabChromeBar title="Microsoft Azure" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
          <AlertTriangle className="text-amber-400" size={32} aria-hidden />
          <p className="text-sm text-slate-300 max-w-md">
            {error || 'Could not load Azure portal state. Check that the lab session is running, then retry.'}
          </p>
          <button
            type="button"
            onClick={() => refresh()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-sky-500/40 text-sky-300 text-sm hover:bg-sky-500/10"
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      </div>
    )
  }

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
          <SimLoginGateCard title="Sign in to Azure" onClose={onExit} className="bg-white rounded-lg shadow-2xl w-full max-w-[400px] overflow-hidden">
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
            </form>
          </SimLoginGateCard>
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
      name: ruleName, priority: Number(rulePriority), protocol: ruleProtocol,
      destination_port: rulePort, access: ruleAccess, direction: 'Inbound',
      source: ruleSource || '*',
    }), 'Rule added')
    setRuleModalNsg(null)
  }

  const renderOverview = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Resource groups</h2>
        <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateRgOpen(true)}>
          <Plus size={14} /> Create resource group
        </button>
      </div>
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'location', label: 'Region', sortable: true },
        { key: 'resources', label: 'Resources', render: () => vms.length + vnets.length + nsgs.length + disks.length + storageAccounts.length },
      ]} searchKeys={['name', 'location', 'resources']} rows={resourceGroups} />
      <h2 className="text-lg font-semibold pt-2">Subscription glance</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <div className="az-tile"><Server size={16} /> <div><div className="az-tile-num">{vms.length}</div><div className="az-tile-label">VMs</div></div></div>
        <div className="az-tile"><Boxes size={16} /> <div><div className="az-tile-num">{(st.vmss || []).length}</div><div className="az-tile-label">Scale sets</div></div></div>
        <div className="az-tile"><AppWindow size={16} /> <div><div className="az-tile-num">{(st.web_apps || []).length}</div><div className="az-tile-label">Web apps</div></div></div>
        <div className="az-tile"><Network size={16} /> <div><div className="az-tile-num">{vnets.length}</div><div className="az-tile-label">VNets</div></div></div>
        <div className="az-tile"><Database size={16} /> <div><div className="az-tile-num">{storageAccounts.length}</div><div className="az-tile-label">Storage</div></div></div>
        <div className="az-tile"><Globe2 size={16} /> <div><div className="az-tile-num">{(st.cosmos_accounts || []).length}</div><div className="az-tile-label">Cosmos</div></div></div>
      </div>
      <div className="flex justify-between items-center flex-wrap gap-2 pt-2">
        <h2 className="text-lg font-semibold">Public IP addresses</h2>
        <button type="button" className="az-btn-sm flex items-center gap-1" onClick={() => run(() => azureApi.createPublicIp(sessionId, {
          name: `pip-${Date.now().toString(36).slice(-4)}`,
        }), 'Public IP created')}>
          <Plus size={11} /> Create public IP
        </button>
      </div>
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'ip', label: 'IP address', sortable: true },
        { key: 'sku', label: 'SKU' },
        { key: 'allocation', label: 'Allocation' },
        { key: 'attached_to', label: 'Associated to', render: (r) => r.attached_to || '—' },
        { key: 'actions', label: 'Actions', render: (r) => (
          <div className="flex items-center gap-1 flex-wrap">
            {r.attached_to ? (
              <button type="button" className="az-btn-sm" onClick={(e) => {
                e.stopPropagation()
                run(() => azureApi.disassociatePublicIp(sessionId, r.name), 'Public IP disassociated')
              }}>
                Disassociate
              </button>
            ) : (
              <button type="button" className="az-btn-sm" disabled={!vms.length} onClick={(e) => {
                e.stopPropagation()
                const vmName = vms[0]?.name
                if (!vmName) return
                run(() => azureApi.associatePublicIp(sessionId, r.name, vmName), `Associated to ${vmName}`)
              }}>
                Associate
              </button>
            )}
          </div>
        ) },
      ]} searchKeys={['name', 'ip', 'sku', 'allocation', 'attached_to']} rows={publicIps} />
    </div>
  )

  const renderVms = () => (
    <div className="space-y-3">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Virtual machines</h2>
        <button type="button" className="az-btn-primary flex items-center gap-1" onClick={openCreateVm}>
          <Plus size={14} /> Create VM
        </button>
      </div>
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
        { key: 'public_ip', label: 'Public IP', sortable: true },
        { key: 'resource_group', label: 'Resource group', sortable: true },
        { key: 'actions', label: 'Actions', render: (r) => (
          <div className="flex items-center gap-1 flex-wrap">
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
      ]} searchKeys={['name', 'power_state', 'size', 'private_ip', 'public_ip', 'resource_group']} rows={vms} onRowClick={(r) => { setVmDetail(r); setResizeTo(r.size) }} />
    </div>
  )

  const renderNetworking = () => (
    <div className="space-y-5">
      <div>
        <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Virtual networks</h2>
          <div className="flex gap-2 flex-wrap">
            <button type="button" className="az-btn-sm" onClick={() => run(() => azureApi.createVnet(sessionId, {
              name: `vnet-${Date.now().toString(36).slice(-4)}`,
              address_space: '10.20.0.0/16',
            }), 'VNet created')}>
              <Plus size={11} /> Create VNet
            </button>
            <button type="button" className="az-btn-sm" onClick={() => run(() => azureApi.createNsg(sessionId, `nsg-${Date.now().toString(36).slice(-4)}`), 'NSG created')}>
              <Plus size={11} /> Create NSG
            </button>
          </div>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'address_space', label: 'Address space', sortable: true },
          { key: 'subnets', label: 'Subnets', render: (r) => (r.subnets || []).map((s) => s.name).join(', ') },
          { key: 'actions', label: '', render: (r) => (
            <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); setSubnetModal(r.name); setSubnetName('snet-app'); setSubnetCidr('10.10.2.0/24') }}>
              <Plus size={11} /> Add subnet
            </button>
          ) },
        ]} searchKeys={['name', 'address_space', 'subnets']} rows={vnets} />
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-2">Network security groups</h2>
        {nsgs.map((nsg) => (
          <div key={nsg.name} className="az-panel mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-sm flex items-center gap-1.5"><Shield size={14} /> {nsg.name}</span>
              <button type="button" className="az-btn-sm" onClick={() => {
                setRuleModalNsg(nsg.name); setRuleName('AllowRule'); setRulePort('22')
                setRulePriority(200); setRuleAccess('Allow'); setRuleProtocol('TCP'); setRuleSource('*')
              }}>
                <Plus size={11} /> Add inbound rule
              </button>
            </div>
            <SimDataTable columns={[
              { key: 'priority', label: 'Priority', sortable: true },
              { key: 'name', label: 'Name', sortable: true },
              { key: 'direction', label: 'Direction', sortable: true },
              { key: 'protocol', label: 'Protocol', sortable: true },
              { key: 'source', label: 'Source', sortable: true, render: (r) => r.source || '*' },
              { key: 'destination_port', label: 'Port', sortable: true },
              { key: 'access', label: 'Action', render: (r) => <SimStatusBadge status={r.access === 'Allow' ? 'success' : 'error'} label={r.access} /> },
              { key: 'actions', label: '', render: (r) => !r.system && (
                <button type="button" className="az-btn-sm az-btn-outline"
                  onClick={() => run(() => azureApi.removeNsgRule(sessionId, nsg.name, r.name), 'Rule removed')}>
                  Remove
                </button>
              ) },
            ]} searchKeys={['priority', 'name', 'direction', 'protocol', 'source', 'destination_port', 'access']} rows={nsg.rules || []} pageSize={20} />
          </div>
        ))}
      </div>
    </div>
  )

  const renderLoadBalancers = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Load balancers</h2>
        <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => run(() => azureApi.createLoadBalancer(sessionId, {
          name: `lb-${Date.now().toString(36).slice(-4)}`,
        }), 'Load balancer created')}>
          <Plus size={14} /> Create load balancer
        </button>
      </div>
      {loadBalancers.map((lb) => (
        <div key={lb.name} className="az-panel">
          <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
            <div>
              <div className="font-semibold text-sm flex items-center gap-1.5"><Layers size={14} /> {lb.name}</div>
              <div className="text-xs text-slate-500">Frontend {lb.frontend_ip} · SKU {lb.sku} · Backend {(lb.backend_pool || []).join(', ')}</div>
            </div>
            <button type="button" className="az-btn-sm" onClick={() => { setLbRuleModal(lb.name); setLbRuleName('https'); setLbFront(443); setLbBack(443) }}>
              <Plus size={11} /> Add rule
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Rule' },
            { key: 'frontend_port', label: 'Frontend port' },
            { key: 'backend_port', label: 'Backend port' },
            { key: 'protocol', label: 'Protocol' },
          ]} searchKeys={['name', 'frontend_port', 'backend_port', 'protocol']} rows={lb.rules || []} pageSize={10} />
          <h3 className="text-sm font-semibold mt-3 mb-1">Health probes</h3>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'protocol', label: 'Protocol' },
            { key: 'port', label: 'Port' },
            { key: 'path', label: 'Path', render: (r) => r.path || '—' },
          ]} searchKeys={['name', 'protocol', 'port', 'path']} rows={lb.probes || []} pageSize={10} />
        </div>
      ))}
      {!loadBalancers.length && <p className="text-sm text-slate-500">No load balancers in this subscription lab.</p>}
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
          <div className="flex gap-1">
            {r.state === 'Attached' && !r.os_disk ? (
              <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); run(() => azureApi.detachDisk(sessionId, r.name), 'Disk detached') }}>
                <Unlink size={11} /> Detach
              </button>
            ) : null}
            {r.state === 'Unattached' ? (
              <button type="button" className="az-btn-sm" onClick={(e) => { e.stopPropagation(); setAttachTarget(r.name) }}>
                <Link2 size={11} /> Attach
              </button>
            ) : null}
            <button type="button" className="az-btn-sm" onClick={(e) => {
              e.stopPropagation()
              run(() => azureApi.snapshotDisk(sessionId, r.name, `${r.name}-snap`), 'Snapshot created')
            }}>
              <Box size={11} /> Snapshot
            </button>
          </div>
        ) },
      ]} searchKeys={['name', 'size_gb', 'sku', 'state', 'attached_to']} rows={disks} />
      {snapshots.length > 0 && (
        <>
          <h2 className="text-lg font-semibold pt-2">Snapshots</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'source_disk', label: 'Source disk' },
            { key: 'size_gb', label: 'Size', render: (r) => `${r.size_gb} GiB` },
            { key: 'created', label: 'Created' },
          ]} searchKeys={['name', 'source_disk', 'size_gb', 'created']} rows={snapshots} />
        </>
      )}
    </div>
  )

  const renderStorage = () => (
    <div className="space-y-3">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Storage accounts</h2>
        <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateSaOpen(true)}>
          <Plus size={14} /> Create storage account
        </button>
      </div>
      {storageAccounts.map((sa) => (
        <div key={sa.name} className="az-panel mb-3">
          <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
            <div>
              <div className="font-semibold text-sm flex items-center gap-1.5"><Database size={14} /> {sa.name}</div>
              <div className="text-xs text-slate-500">{sa.sku} · {sa.kind} · {sa.access_tier} · HTTPS only: {sa.https_only ? 'Yes' : 'No'}</div>
            </div>
            <button type="button" className="az-btn-sm" onClick={() => { setContainerModal(sa.name); setContainerName('logs') }}>
              <Plus size={11} /> Container
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Container' },
            { key: 'public_access', label: 'Public access' },
            { key: 'blobs', label: 'Blobs' },
          ]} searchKeys={['name', 'public_access', 'blobs']} rows={sa.blob_containers || []} pageSize={10} />
        </div>
      ))}
    </div>
  )

  const renderKeyVault = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Key vaults</h2>
      {keyVaults.map((kv) => (
        <div key={kv.name} className="az-panel">
          <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
            <div className="font-semibold text-sm flex items-center gap-1.5"><KeyRound size={14} /> {kv.name}</div>
            <div className="flex gap-2 flex-wrap">
              <button type="button" className="az-btn-sm" onClick={() => { setSecretModal(kv.name); setSecretName('new-secret') }}>
                <Plus size={11} /> Set secret
              </button>
              <button type="button" className="az-btn-sm" onClick={() => run(() => azureApi.importCertificate(sessionId, kv.name, `cert-${Date.now().toString(36).slice(-4)}`), 'Certificate imported')}>
                <Plus size={11} /> Import certificate
              </button>
            </div>
          </div>
          <h3 className="text-xs font-semibold uppercase text-slate-500 mb-1">Secrets</h3>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'enabled', label: 'Enabled', render: (r) => <SimStatusBadge status={r.enabled ? 'success' : 'error'} label={r.enabled ? 'Yes' : 'No'} /> },
            { key: 'content_type', label: 'Content type' },
          ]} searchKeys={['name', 'enabled', 'content_type']} rows={kv.secrets || []} pageSize={10} />
          <h3 className="text-xs font-semibold uppercase text-slate-500 mt-3 mb-1">Certificates</h3>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'enabled', label: 'Enabled', render: (r) => r.enabled ? 'Yes' : 'No' },
            { key: 'expires', label: 'Expires' },
          ]} searchKeys={['name', 'enabled', 'expires']} rows={kv.certificates || []} pageSize={10} />
        </div>
      ))}
    </div>
  )

  const renderIam = () => (
    <div className="space-y-3">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-lg font-semibold">Role assignments</h2>
        <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setRoleModal(true)}>
          <Plus size={14} /> Add role assignment
        </button>
      </div>
      <SimDataTable columns={[
        { key: 'principal', label: 'Principal', sortable: true },
        { key: 'role', label: 'Role', sortable: true },
        { key: 'scope', label: 'Scope', render: (r) => <span className="font-mono text-[11px]">{r.scope}</span> },
        { key: 'actions', label: '', render: (r) => (
          <button type="button" className="az-btn-sm az-btn-outline"
            onClick={() => run(() => azureApi.removeRoleAssignment(sessionId, r.id), 'Role assignment removed')}>
            Remove
          </button>
        ) },
      ]} searchKeys={['principal', 'role', 'scope']} rows={roleAssignments} />
    </div>
  )

  const renderActivity = () => (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Activity log</h2>
      <SimDataTable columns={[
        { key: 'time', label: 'Time', sortable: true },
        { key: 'operation', label: 'Operation', render: (r) => r.operation || r.message },
        { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={(r.status || '').includes('Fail') || r.severity === 'error' ? 'error' : 'success'} label={r.status || r.severity || 'Succeeded'} /> },
        { key: 'caller', label: 'Caller', render: (r) => r.caller || '—' },
      ]} searchKeys={['time', 'operation', 'status', 'caller']} rows={activityLog} pageSize={25} />
    </div>
  )

  const renderContent = () => {
    const v2 = renderAzureV2Page({
      nav, st, sessionId, busy, run,
      createVmssOpen, setCreateVmssOpen, vmssName, setVmssName, vmssCap, setVmssCap,
      createAppOpen, setCreateAppOpen, appName, setAppName,
      createFuncOpen, setCreateFuncOpen, funcName, setFuncName,
      createCaOpen, setCreateCaOpen, caName, setCaName,
      createAksOpen, setCreateAksOpen, aksName, setAksName,
      inviteOpen, setInviteOpen, inviteUpn, setInviteUpn,
    })
    if (v2) return v2
    if (nav === 'vms') return renderVms()
    if (nav === 'networking') return renderNetworking()
    if (nav === 'loadbalancers') return renderLoadBalancers()
    if (nav === 'disks') return renderDisks()
    if (nav === 'storage') return renderStorage()
    if (nav === 'keyvault') return renderKeyVault()
    if (nav === 'iam') return renderIam()
    if (nav === 'activity') return renderActivity()
    return renderOverview()
  }

  return (
    <div className={simPanelRoot(embedded, 'az-shell sim-product')}>
      <LabChromeBar title="Microsoft Azure" subtitle={scenario?.title || slug} accent={ACCENT}
        className="lab-chrome-bar !bg-[#0078d4]" {...chromeProps}>
        <GlobalSearch
          services={searchServices}
          resources={searchResources}
          placeholder="Search resources, services… (/)"
          onSelect={(hit) => { if (hit.navKey) setNav(hit.navKey) }}
        />
        <button type="button" className="lab-chrome-btn flex items-center gap-1" onClick={() => setCloudShellOpen((o) => !o)}>
          <Terminal size={13} /> {cloudShellOpen ? 'Hide Cloud Shell' : 'Cloud Shell'}
        </button>
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

      <div className="px-4 py-2 bg-[#053e6e] border-b border-black/20 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-300" />
        <span className="text-xs text-slate-300">{st?.session?.user || 'admin'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={setNav} accent={ACCENT}
          className="!w-[220px] !bg-[#04223f] az-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#f5f7fa]" style={{ paddingBottom: cloudShellOpen ? 12 : undefined }}>{renderContent()}</main>
      </div>

      {cloudShellOpen && (
        <CloudShellPanel
          provider="azure"
          accent={ACCENT}
          onClose={() => setCloudShellOpen(false)}
          onCommand={async (action, payload) => {
            const res = await azureApi.action(sessionId, action, payload)
            await run(() => Promise.resolve(res), res?.message || 'Cloud Shell command')
            return res
          }}
        />
      )}

      <SimModal shellClass="az-shell" open={!!vmDetail} onClose={() => setVmDetail(null)} title={`${vmDetail?.name || ''} — Size`}
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

      <SimModal shellClass="az-shell" open={!!ruleModalNsg} onClose={() => setRuleModalNsg(null)} title={`Add inbound security rule — ${ruleModalNsg || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setRuleModalNsg(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={submitRule}>Add</button>
        </>}>
        <label className="block text-sm">Name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={ruleName} onChange={(e) => setRuleName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Protocol
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={ruleProtocol} onChange={(e) => setRuleProtocol(e.target.value)}>
            <option value="TCP">TCP</option>
            <option value="UDP">UDP</option>
            <option value="*">Any</option>
          </select>
        </label>
        <label className="block text-sm mt-3">Source <span className="text-slate-500">(* or CIDR)</span>
          <input className="w-full mt-1 border rounded px-2 py-1.5 font-mono text-xs" value={ruleSource}
            onChange={(e) => setRuleSource(e.target.value)} placeholder="*" />
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

      <SimModal shellClass="az-shell" open={!!attachTarget} onClose={() => setAttachTarget(null)} title={`Attach disk — ${attachTarget || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setAttachTarget(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy || !vms.length} onClick={() => {
            run(() => azureApi.attachDisk(sessionId, vms[0].name, attachTarget), 'Disk attached')
            setAttachTarget(null)
          }}>Attach to {vms[0]?.name || 'VM'}</button>
        </>}>
        <p className="text-sm text-slate-300">Attach this managed disk to <span className="font-mono">{vms[0]?.name}</span>.</p>
      </SimModal>

      <SimModal shellClass="az-shell" open={createDiskModal} onClose={() => setCreateDiskModal(false)} title="Create managed disk"
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

      <SimModal shellClass="az-shell" open={createRgOpen} onClose={() => setCreateRgOpen(false)} title="Create resource group"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setCreateRgOpen(false)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.createResourceGroup(sessionId, rgName), 'Resource group created')
            setCreateRgOpen(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={rgName} onChange={(e) => setRgName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal shellClass="az-shell" open={createSaOpen} onClose={() => setCreateSaOpen(false)} title="Create storage account"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setCreateSaOpen(false)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.createStorageAccount(sessionId, saName), 'Storage account created')
            setCreateSaOpen(false)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Name (lowercase)
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={saName} onChange={(e) => setSaName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal shellClass="az-shell" open={createVmOpen} onClose={() => setCreateVmOpen(false)} title="Create a virtual machine" width="max-w-2xl"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setCreateVmOpen(false)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy || !newVmName.trim()} onClick={submitCreateVm}>
            Create
          </button>
        </>}>
        <div className="space-y-3">
          <p className="text-xs text-slate-500">Basics · Disks · Networking · Management (lab simulation)</p>
          <label className="block text-sm">Virtual machine name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={newVmName} onChange={(e) => setNewVmName(e.target.value)} />
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block text-sm">Region
              <select className="w-full mt-1 border rounded px-2 py-1.5" value={newVmLocation} onChange={(e) => setNewVmLocation(e.target.value)}>
                {AZ_LOCATION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="block text-sm">Resource group
              <select className="w-full mt-1 border rounded px-2 py-1.5" value={newVmRg || defaultRg} onChange={(e) => setNewVmRg(e.target.value)}>
                {resourceGroups.map((rg) => (
                  <option key={rg.name} value={rg.name}>{rg.name} ({rg.location || '—'})</option>
                ))}
                {!resourceGroups.length && <option value={defaultRg}>{defaultRg}</option>}
              </select>
            </label>
          </div>
          <label className="block text-sm">Image
            <select className="w-full mt-1 border rounded px-2 py-1.5" value={newVmImage} onChange={(e) => setNewVmImage(e.target.value)}>
              {AZ_IMAGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <label className="block text-sm">Size
            <select className="w-full mt-1 border rounded px-2 py-1.5" value={newVmSize} onChange={(e) => setNewVmSize(e.target.value)}>
              {VM_SIZE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block text-sm">Administrator username
              <input className="w-full mt-1 border rounded px-2 py-1.5" value={newVmAdmin} onChange={(e) => setNewVmAdmin(e.target.value)} />
            </label>
            <label className="block text-sm">Authentication type
              <select className="w-full mt-1 border rounded px-2 py-1.5" value={newVmAuth} onChange={(e) => setNewVmAuth(e.target.value)}>
                <option value="sshPublicKey">SSH public key</option>
                <option value="password">Password</option>
              </select>
            </label>
          </div>
          {newVmAuth === 'sshPublicKey' ? (
            <label className="block text-sm">SSH public key
              <textarea
                className="w-full mt-1 border rounded px-2 py-1.5 font-mono text-xs min-h-[72px]"
                placeholder="ssh-rsa AAAA… (optional — lab uses a simulated fingerprint if empty)"
                value={newVmSshKey}
                onChange={(e) => setNewVmSshKey(e.target.value)}
              />
            </label>
          ) : (
            <label className="block text-sm">Password
              <input
                type="password"
                className="w-full mt-1 border rounded px-2 py-1.5"
                placeholder="Not stored — simulation only"
                value={newVmPassword}
                onChange={(e) => setNewVmPassword(e.target.value)}
                autoComplete="new-password"
              />
            </label>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block text-sm">OS disk type
              <select className="w-full mt-1 border rounded px-2 py-1.5" value={newVmOsDiskSku} onChange={(e) => setNewVmOsDiskSku(e.target.value)}>
                {AZ_OS_DISK_SKU_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="block text-sm">OS disk size (GiB)
              <input type="number" min={30} className="w-full mt-1 border rounded px-2 py-1.5" value={newVmOsDiskGb} onChange={(e) => setNewVmOsDiskGb(e.target.value)} />
            </label>
          </div>
          <label className="block text-sm">Virtual network / subnet
            <select className="w-full mt-1 border rounded px-2 py-1.5" value={newVmNet || defaultNet} onChange={(e) => setNewVmNet(e.target.value)}>
              {netOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              <option value={NET_CREATE_DEFAULTS}>Create new VNet + subnet (defaults)</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm mt-1">
            <input type="checkbox" checked={newVmPublicIp} onChange={(e) => setNewVmPublicIp(e.target.checked)} />
            Create and associate a public IP address
          </label>
        </div>
      </SimModal>

      <SimModal shellClass="az-shell" open={!!subnetModal} onClose={() => setSubnetModal(null)} title={`Add subnet — ${subnetModal || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setSubnetModal(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.createSubnet(sessionId, subnetModal, subnetName, subnetCidr), 'Subnet created')
            setSubnetModal(null)
          }}>Add</button>
        </>}>
        <label className="block text-sm">Subnet name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={subnetName} onChange={(e) => setSubnetName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Address prefix
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={subnetCidr} onChange={(e) => setSubnetCidr(e.target.value)} />
        </label>
      </SimModal>

      <SimModal shellClass="az-shell" open={!!secretModal} onClose={() => setSecretModal(null)} title={`Set secret — ${secretModal || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setSecretModal(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.setSecret(sessionId, secretModal, secretName), 'Secret set')
            setSecretModal(null)
          }}>Set</button>
        </>}>
        <label className="block text-sm">Secret name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={secretName} onChange={(e) => setSecretName(e.target.value)} />
        </label>
      </SimModal>

      <SimModal shellClass="az-shell" open={roleModal} onClose={() => setRoleModal(false)} title="Add role assignment"
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setRoleModal(false)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.assignRole(sessionId, rolePrincipal, roleName), 'Role assigned')
            setRoleModal(false)
          }}>Assign</button>
        </>}>
        <label className="block text-sm">Principal
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={rolePrincipal} onChange={(e) => setRolePrincipal(e.target.value)} placeholder="user@fixitlab.onmicrosoft.com" />
        </label>
        <label className="block text-sm mt-3">Role
          <select className="w-full mt-1 border rounded px-2 py-1.5" value={roleName} onChange={(e) => setRoleName(e.target.value)}>
            <option>Owner</option>
            <option>Contributor</option>
            <option>Reader</option>
            <option>Virtual Machine Contributor</option>
            <option>Storage Blob Data Contributor</option>
          </select>
        </label>
      </SimModal>

      <SimModal shellClass="az-shell" open={!!lbRuleModal} onClose={() => setLbRuleModal(null)} title={`Add LB rule — ${lbRuleModal || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setLbRuleModal(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.createLbRule(sessionId, lbRuleModal, {
              rule_name: lbRuleName, frontend_port: Number(lbFront), backend_port: Number(lbBack),
            }), 'LB rule added')
            setLbRuleModal(null)
          }}>Add</button>
        </>}>
        <label className="block text-sm">Rule name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={lbRuleName} onChange={(e) => setLbRuleName(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Frontend port
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={lbFront} onChange={(e) => setLbFront(e.target.value)} />
        </label>
        <label className="block text-sm mt-3">Backend port
          <input type="number" className="w-full mt-1 border rounded px-2 py-1.5" value={lbBack} onChange={(e) => setLbBack(e.target.value)} />
        </label>
      </SimModal>

      <SimModal shellClass="az-shell" open={!!containerModal} onClose={() => setContainerModal(null)} title={`New container — ${containerModal || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3" onClick={() => setContainerModal(null)}>Cancel</button>
          <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
            run(() => azureApi.createBlobContainer(sessionId, containerModal, containerName), 'Container created')
            setContainerModal(null)
          }}>Create</button>
        </>}>
        <label className="block text-sm">Container name
          <input className="w-full mt-1 border rounded px-2 py-1.5" value={containerName} onChange={(e) => setContainerName(e.target.value)} />
        </label>
      </SimModal>
    </div>
  )
}
