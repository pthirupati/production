import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { vmwareApi } from '../../api/vmware'
import toast from 'react-hot-toast'

/* ─── helpers ─────────────────────────────────────────────────────────── */
const fmtBytes = (gb) => gb >= 1024 ? `${(gb / 1024).toFixed(1)} TB` : `${gb} GB`
const fmtUptime = (s) => {
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  return d > 0 ? `${d}d ${h}h ${m}m` : `${h}h ${m}m`
}
const fmtMb = (mb) => mb >= 1024 ? `${(mb / 1024).toFixed(0)} GB` : `${mb} MB`
const fmtTime = (iso) => iso ? new Date(iso).toLocaleString('en-US', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—'

function StatusIcon({ status, size = 10 }) {
  const cls = status === 'connected' || status === 'poweredOn' ? 'bg-[#2db52d]'
    : status === 'disconnected' || status === 'poweredOff' ? 'bg-[#e0412b]'
    : status === 'suspended' ? 'bg-[#f5a623]'
    : status === 'notResponding' ? 'bg-[#e0412b]'
    : 'bg-[#f5a623]'
  return (
    <span className={`inline-flex items-center justify-center rounded-full shrink-0`} style={{ width: size, height: size }}>
      <span className={`rounded-full ${cls}`} style={{ width: size - 2, height: size - 2 }} />
    </span>
  )
}

function UsageBar({ pct, color = '#4c9be8' }) {
  return (
    <div className="h-3 bg-[#d8d8d8] rounded-sm overflow-hidden border border-[#b0b0b0]">
      <div className="h-full" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
    </div>
  )
}

/* ─── Simulated sparkline chart ─────────────────────────────────────── */
function PerfChart({ cpuPct = 30, memPct = 50 }) {
  const W = 560, H = 120
  // Stabilize points so the chart doesn't redraw on every parent re-render.
  const cpuPts = useMemo(
    () => Array.from({ length: 20 }, (_, i) => cpuPct + Math.sin(i * 0.6) * 10 + (((i * 17 + cpuPct * 3) % 17) - 8) * 0.5),
    [cpuPct],
  )
  const memPts = useMemo(
    () => Array.from({ length: 20 }, (_, i) => memPct + Math.sin(i * 0.4) * 8 + (((i * 13 + memPct * 5) % 13) - 6) * 0.5),
    [memPct],
  )
  const toSvg = (pts) => pts.map((v, i) => `${(i / 19) * W},${H - (v / 100) * H}`).join(' ')
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="block">
      <polyline points={toSvg(cpuPts)} fill="none" stroke="#4c9be8" strokeWidth="1.5" />
      <polyline points={toSvg(memPts)} fill="none" stroke="#9b59b6" strokeWidth="1.5" />
    </svg>
  )
}

/* ─── Snapshot modal ─────────────────────────────────────────────────── */
function SnapshotModal({ vm, onClose, onAction }) {
  const [name, setName] = useState(`snapshot-${new Date().toISOString().slice(0, 10)}`)
  const [desc, setDesc] = useState('')
  const [acting, setActing] = useState(false)

  const [error, setError] = useState('')
  const create = async () => {
    setActing(true)
    setError('')
    try {
      await onAction('take_snapshot', { vm_name: vm.name, snapshot_name: name, description: desc })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Snapshot failed')
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[#f5f5f5] border border-[#c0c0c0] shadow-xl rounded w-96">
        <div className="bg-[#5b9bd5] text-white text-sm font-semibold px-3 py-2 flex items-center justify-between">
          <span>Take Snapshot — {vm.name}</span>
          <button onClick={onClose} className="hover:bg-white/20 rounded px-1">✕</button>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="block text-xs text-[#444] mb-1">Snapshot name</label>
            <input value={name} onChange={e => setName(e.target.value)}
              className="w-full border border-[#aaa] rounded px-2 py-1 text-sm focus:outline-none focus:border-[#5b9bd5]" />
          </div>
          <div>
            <label className="block text-xs text-[#444] mb-1">Description (optional)</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2}
              className="w-full border border-[#aaa] rounded px-2 py-1 text-sm focus:outline-none focus:border-[#5b9bd5]" />
          </div>
        </div>
        {error && (
          <div className="px-4 pb-2 text-xs text-red-600">{error}</div>
        )}
        <div className="px-4 pb-4 flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-1.5 text-sm border border-[#aaa] rounded bg-[#e8e8e8] hover:bg-[#ddd]">Cancel</button>
          <button disabled={acting || !name.trim()} onClick={create}
            className="px-4 py-1.5 text-sm rounded bg-[#5b9bd5] text-white hover:bg-[#4a8ac4] disabled:opacity-50">
            {acting ? 'Creating…' : 'OK'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Migrate modal ──────────────────────────────────────────────────── */
function MigrateModal({ vm, hosts, onClose, onAction }) {
  const [targetHost, setTargetHost] = useState('')
  const [acting, setActing] = useState(false)
  const available = hosts.filter(h => h.id !== vm.host_id && h.status === 'connected')

  const migrate = async () => {
    if (!targetHost) return
    setActing(true)
    await onAction('migrate_vm', { vm_name: vm.name, target_host: targetHost })
    setActing(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[#f5f5f5] border border-[#c0c0c0] shadow-xl rounded w-96">
        <div className="bg-[#5b9bd5] text-white text-sm font-semibold px-3 py-2 flex items-center justify-between">
          <span>Migrate VM — {vm.name}</span>
          <button onClick={onClose} className="hover:bg-white/20 rounded px-1">✕</button>
        </div>
        <div className="p-4 space-y-3">
          <p className="text-xs text-[#555]">Select destination host (VMotion):</p>
          {available.length === 0 ? (
            <p className="text-sm text-[#e04]">No compatible hosts available</p>
          ) : available.map(h => (
            <label key={h.id} className="flex items-center gap-2 cursor-pointer">
              <input type="radio" name="host" value={h.name} checked={targetHost === h.name} onChange={() => setTargetHost(h.name)} />
              <StatusIcon status={h.status} />
              <span className="text-sm">{h.name}</span>
            </label>
          ))}
        </div>
        <div className="px-4 pb-4 flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-1.5 text-sm border border-[#aaa] rounded bg-[#e8e8e8] hover:bg-[#ddd]">Cancel</button>
          <button disabled={acting || !targetHost} onClick={migrate}
            className="px-4 py-1.5 text-sm rounded bg-[#5b9bd5] text-white hover:bg-[#4a8ac4] disabled:opacity-50">
            {acting ? 'Migrating…' : 'Migrate'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Main component ─────────────────────────────────────────────────── */
export default function VMwareSimulator() {
  const { sessionId } = useParams()
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [selectedNode, setSelectedNode] = useState({ type: 'host', id: null })
  const [activeTab, setActiveTab] = useState('summary')
  const [expandedSections, setExpandedSections] = useState({ hosts: true, vms: true, storage: true, networks: false })
  const [showSnapshotModal, setShowSnapshotModal] = useState(false)
  const [showMigrateModal, setShowMigrateModal] = useState(false)
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false)
  const actionsRef = useRef(null)

  const initialSelectionDone = useRef(false)
  const load = useCallback(async () => {
    try {
      const data = await vmwareApi.getState(sessionId)
      setState(data)
      if (!initialSelectionDone.current && data.inventory?.hosts?.length) {
        setSelectedNode({ type: 'host', id: data.inventory.hosts[0].id })
        initialSelectionDone.current = true
      }
    } catch {
      toast.error('Could not load VMware simulator')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const handler = (e) => { if (actionsRef.current && !actionsRef.current.contains(e.target)) setActionsMenuOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const runAction = async (action, payload = {}) => {
    setActing(true)
    setActionsMenuOpen(false)
    try {
      const res = await vmwareApi.action(sessionId, action, payload)
      if (res.state) setState(res.state)
      else await load()
      toast.success(res.message || 'Action completed', { style: { background: '#fff', color: '#222', border: '1px solid #ccc', fontSize: '12px' } })
    } catch (err) {
      toast.error(err.response?.data?.error || 'Action failed', { style: { background: '#fff', color: '#c00', border: '1px solid #ccc', fontSize: '12px' } })
    } finally {
      setActing(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#1e3a5f' }}>
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-[#5b9bd5] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-white text-sm">Loading VMware Simulator…</p>
        </div>
      </div>
    )
  }

  const inv = state?.inventory || {}
  const summary = state?.summary || {}
  const hosts = inv.hosts || []
  const vms = inv.vms || []
  const datastores = inv.datastores || []
  const networks = inv.networks || []
  const alarms = inv.alarms || []
  const events = inv.events || []
  const recentTasks = inv.recent_tasks || []

  const selectedHost = selectedNode.type === 'host' ? (hosts.find(h => h.id === selectedNode.id) ?? null) : null
  const selectedVm = selectedNode.type === 'vm' ? vms.find(v => v.id === selectedNode.id) : null
  const selectedDs = selectedNode.type === 'datastore' ? datastores.find(d => d.id === selectedNode.id) : null
  const selectedNet = selectedNode.type === 'network' ? networks.find(n => n.id === selectedNode.id) : null

  const activeAlarms = alarms.filter(a => a.status === 'active')

  const toggleSection = (k) => setExpandedSections(p => ({ ...p, [k]: !p[k] }))

  /* ── VM toolbar actions ── */
  const renderVmToolbar = (vm) => {
    const isOn = vm.power === 'poweredOn'
    const isOff = vm.power === 'poweredOff'
    const isSuspended = vm.power === 'suspended'
    return (
      <div className="flex items-center gap-1 px-2 py-1.5 bg-[#eef2f7] border-b border-[#c8d0dc] flex-wrap">
        <ToolbarBtn onClick={() => runAction('power_on', { vm_id: vm.id })} disabled={isOn || acting} label="Power On" />
        <ToolbarSep />
        <ToolbarBtn onClick={() => runAction('power_off_guest', { vm_id: vm.id })} disabled={!isOn || acting} label="Shut Down Guest" />
        <ToolbarBtn onClick={() => runAction('reboot_guest', { vm_id: vm.id })} disabled={!isOn || acting} label="Restart Guest" />
        <ToolbarSep />
        <ToolbarBtn onClick={() => runAction('power_off', { vm_id: vm.id })} disabled={isOff || acting} label="Power Off" />
        <ToolbarBtn onClick={() => runAction('reboot', { vm_id: vm.id })} disabled={!isOn || acting} label="Reset" />
        <ToolbarBtn onClick={() => runAction('suspend', { vm_id: vm.id })} disabled={!isOn || acting} label="Suspend" />
        {isSuspended && <ToolbarBtn onClick={() => runAction('resume', { vm_id: vm.id })} disabled={acting} label="Resume" />}
        <ToolbarSep />
        <ToolbarBtn onClick={() => setShowSnapshotModal(true)} disabled={acting} label="Take Snapshot" />
        <ToolbarBtn onClick={() => setShowMigrateModal(true)} disabled={acting} label="Migrate…" />
        <div className="flex-1" />
        <RefreshBtn onClick={load} />
      </div>
    )
  }

  /* ── Host toolbar ── */
  const renderHostToolbar = (host) => (
    <div className="flex items-center gap-1 px-2 py-1.5 bg-[#eef2f7] border-b border-[#c8d0dc] flex-wrap">
      <ToolbarBtn onClick={() => { }} disabled label="Get vCenter Server" blue />
      <ToolbarSep />
      <ToolbarBtn onClick={() => { }} disabled={acting} label="Create/Register VM" />
      <ToolbarSep />
      {host.maintenance
        ? <ToolbarBtn onClick={() => runAction('exit_maintenance', { host_name: host.name })} disabled={acting} label="Exit Maintenance Mode" />
        : <ToolbarBtn onClick={() => runAction('enter_maintenance', { host_name: host.name })} disabled={acting} label="Enter Maintenance Mode" />
      }
      {host.status === 'disconnected' && (
        <ToolbarBtn onClick={() => runAction('reconnect_host', { host_name: host.name })} disabled={acting} label="Reconnect Host" blue />
      )}
      <ToolbarSep />
      <div className="relative" ref={actionsRef}>
        <button
          onClick={() => setActionsMenuOpen(v => !v)}
          className="px-2.5 py-1 text-[11px] border border-[#aab] rounded bg-[#e4e9f0] hover:bg-[#d8dfe8] flex items-center gap-1"
        >
          Actions <span className="text-[9px]">▼</span>
        </button>
        {actionsMenuOpen && (
          <div className="absolute top-full left-0 mt-0.5 bg-white border border-[#ccc] shadow-lg z-20 min-w-40 text-xs">
            <ActionsMenuItem label={`${host.ssh_enabled ? 'Disable' : 'Enable'} SSH`} onClick={() => toast('SSH toggle simulated')} />
            <ActionsMenuItem label="Reboot Host" onClick={() => toast('Host reboot simulated')} />
            <ActionsMenuItem label="Shut Down Host" onClick={() => toast('Shutdown simulated')} />
          </div>
        )}
      </div>
      <div className="flex-1" />
      <RefreshBtn onClick={load} />
    </div>
  )

  return (
    <div className="flex flex-col h-screen select-none" style={{ background: '#f0f0f0', fontFamily: 'Arial, sans-serif', fontSize: '12px' }}>

      {/* ── Top header bar ─────────────────────────────────────────── */}
      <header className="shrink-0 flex items-center h-9 px-3 gap-3" style={{ background: '#1e3a5f' }}>
        <Link to={`/lab/${sessionId}`} className="text-[#8ab4d4] hover:text-white text-[11px] flex items-center gap-1 mr-2">
          ← Back to lab
        </Link>
        {/* VMware logo */}
        <div className="flex items-center gap-1.5">
          <span className="text-white font-bold text-sm tracking-tight" style={{ fontFamily: 'Arial, sans-serif' }}>
            <span style={{ color: '#5b9bd5' }}>vm</span>ware
          </span>
          <span className="text-[#aac] text-[11px] font-semibold">ESXi</span>
        </div>
        <div className="h-4 w-px bg-[#3a5a7f] mx-1" />
        <div className="flex items-center gap-1 text-[11px] text-[#8ab4d4]">
          <StatusIcon status={summary.hosts_connected === summary.hosts_total ? 'connected' : 'disconnected'} />
          <span className="text-white">{hosts[0]?.name || 'esxi.local'}</span>
        </div>
        <div className="flex-1" />
        {activeAlarms.length > 0 && (
          <div className="flex items-center gap-1 bg-[#c0392b]/20 border border-[#c0392b]/40 rounded px-2 py-0.5 text-[11px] text-[#ff8080]">
            ⚠ {activeAlarms.length} active alarm{activeAlarms.length > 1 ? 's' : ''}
          </div>
        )}
        <div className="text-[#8ab4d4] text-[11px] flex items-center gap-2 ml-2">
          <span>root</span>
          <span className="border border-[#3a5a7f] rounded px-1 hover:border-[#5b9bd5] cursor-pointer">H</span>
          <span className="border border-[#3a5a7f] rounded px-1 hover:border-[#5b9bd5] cursor-pointer">?</span>
        </div>
      </header>

      {/* ── Secondary nav ─────────────────────────────────────────── */}
      <div className="shrink-0 flex items-center h-7 px-3 gap-4 border-b border-[#3a5a7f]" style={{ background: '#2a4a6f' }}>
        {['Home', 'Navigator', 'VMs', 'Storage', 'Networking', 'Monitor'].map(tab => (
          <button key={tab} className="text-[11px] text-[#8ab4d4] hover:text-white px-1 py-0.5 hover:bg-[#3a5a7f]/50 rounded transition-colors">
            {tab}
          </button>
        ))}
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Left navigator ─────────────────────────────────────────── */}
        <aside className="shrink-0 overflow-y-auto border-r border-[#c0c8d4]" style={{ width: 220, background: '#1e3a5f' }}>
          <div className="px-2 pt-2 pb-1 text-[10px] font-bold text-[#8ab4d4] uppercase tracking-wider">Navigator</div>

          {/* Hosts */}
          <NavSection label="Host" expanded={expandedSections.hosts} onToggle={() => toggleSection('hosts')}>
            {hosts.map(host => (
              <NavItem
                key={host.id}
                icon={<HostIcon />}
                label={host.name}
                status={host.status}
                active={selectedNode.type === 'host' && selectedNode.id === host.id}
                onClick={() => { setSelectedNode({ type: 'host', id: host.id }); setActiveTab('summary') }}
                badge={host.maintenance ? 'M' : null}
              >
                <NavSubItem label="Manage" onClick={() => { setSelectedNode({ type: 'host', id: host.id }); setActiveTab('configure') }} />
                <NavSubItem label="Monitor" onClick={() => { setSelectedNode({ type: 'host', id: host.id }); setActiveTab('monitor') }} />
              </NavItem>
            ))}
          </NavSection>

          {/* VMs */}
          <NavSection label="Virtual Machines" expanded={expandedSections.vms} onToggle={() => toggleSection('vms')}>
            {vms.map(vm => (
              <NavItem
                key={vm.id}
                icon={<VmIcon power={vm.power} />}
                label={vm.name}
                status={vm.power}
                active={selectedNode.type === 'vm' && selectedNode.id === vm.id}
                onClick={() => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary') }}
              >
                <NavSubItem label="Monitor" onClick={() => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('monitor') }} />
                <NavSubItem label="Snapshots" onClick={() => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('snapshots') }} />
              </NavItem>
            ))}
          </NavSection>

          {/* Storage */}
          <NavSection label="Storage" expanded={expandedSections.storage} onToggle={() => toggleSection('storage')}>
            {datastores.map(ds => (
              <NavItem
                key={ds.id}
                icon={<DsIcon />}
                label={ds.name}
                status={ds.accessible ? 'connected' : 'disconnected'}
                active={selectedNode.type === 'datastore' && selectedNode.id === ds.id}
                onClick={() => { setSelectedNode({ type: 'datastore', id: ds.id }); setActiveTab('summary') }}
              />
            ))}
          </NavSection>

          {/* Networking */}
          <NavSection label="Networking" expanded={expandedSections.networks} onToggle={() => toggleSection('networks')}>
            {networks.map(net => (
              <NavItem
                key={net.id}
                icon={<NetIcon />}
                label={net.name}
                status="connected"
                active={selectedNode.type === 'network' && selectedNode.id === net.id}
                onClick={() => { setSelectedNode({ type: 'network', id: net.id }); setActiveTab('summary') }}
              />
            ))}
          </NavSection>
        </aside>

        {/* ── Main content ──────────────────────────────────────────── */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">

          {/* Object header */}
          <div className="shrink-0 px-3 py-1.5 border-b border-[#c0c8d4] flex items-center gap-3" style={{ background: '#f8f9fb' }}>
            <div className="flex items-center gap-2">
              {selectedVm && <StatusIcon status={selectedVm.power} size={12} />}
              {selectedHost && <StatusIcon status={selectedHost.status} size={12} />}
              {selectedDs && <StatusIcon status={selectedDs.accessible ? 'connected' : 'disconnected'} size={12} />}
              <span className="font-semibold text-[#1e3a5f] text-sm">
                {selectedVm?.name || selectedHost?.name || selectedDs?.name || selectedNet?.name || 'Select an object'}
              </span>
            </div>
            {selectedHost && (
              <div className="text-[10px] text-[#666] flex items-center gap-3">
                <span>{selectedHost.version} (Build {selectedHost.build})</span>
                <span>Uptime: {fmtUptime(selectedHost.uptime_seconds)}</span>
              </div>
            )}
            {selectedVm && (
              <div className="text-[10px] text-[#666] flex items-center gap-3">
                <span>{selectedVm.guest_os_version}</span>
                <span>{selectedVm.ip}</span>
                <span className={selectedVm.power === 'poweredOn' ? 'text-[#2db52d]' : 'text-[#e0412b]'}>
                  {selectedVm.power}
                </span>
              </div>
            )}
          </div>

          {/* SSH / alarm banner */}
          {selectedHost?.ssh_enabled && (
            <div className="shrink-0 px-3 py-1.5 flex items-center gap-2 border-b border-[#b0c0d4]" style={{ background: '#e8f0fc' }}>
              <span className="text-[#1a4fa0] text-[11px]">ℹ SSH is enabled on this host. You should disable SSH unless it is necessary for administrative purposes.</span>
              <button className="ml-auto text-[11px] text-[#1a4fa0] border border-[#1a4fa0] px-2 py-0.5 rounded hover:bg-[#1a4fa0]/10">Actions</button>
            </div>
          )}
          {activeAlarms.length > 0 && selectedVm && activeAlarms.some(a => a.entity === selectedVm.name) && (
            <div className="shrink-0 px-3 py-1.5 flex items-center gap-2 border-b border-[#f5c0b0]" style={{ background: '#fff0ee' }}>
              <span className="text-[#c03] text-[11px]">⚠ {activeAlarms.find(a => a.entity === selectedVm.name)?.name}</span>
              <button onClick={() => runAction('acknowledge_alarm', { alarm_id: activeAlarms.find(a => a.entity === selectedVm?.name)?.id })}
                className="ml-auto text-[11px] text-[#c03] border border-[#c03] px-2 py-0.5 rounded hover:bg-[#c03]/10">
                Acknowledge
              </button>
            </div>
          )}

          {/* Toolbar */}
          {selectedVm && renderVmToolbar(selectedVm)}
          {selectedHost && renderHostToolbar(selectedHost)}
          {selectedDs && (
            <div className="flex items-center gap-1 px-2 py-1.5 bg-[#eef2f7] border-b border-[#c8d0dc]">
              <ToolbarBtn onClick={() => { }} disabled label="Register VM" />
              <ToolbarBtn onClick={() => runAction('expand_datastore', { datastore: selectedDs.name, gb: 500 })} disabled={acting} label="Increase Capacity" />
              <div className="flex-1" />
              <RefreshBtn onClick={load} />
            </div>
          )}

          {/* Content tabs */}
          <div className="shrink-0 flex border-b border-[#c0c8d4]" style={{ background: '#f8f9fb' }}>
            {getTabs(selectedNode.type).map(t => (
              <button
                key={t}
                onClick={() => setActiveTab(t)}
                className="px-4 py-2 text-[11px] font-medium border-b-2 transition-colors"
                style={{
                  borderBottomColor: activeTab === t ? '#5b9bd5' : 'transparent',
                  color: activeTab === t ? '#1e3a5f' : '#666',
                  background: activeTab === t ? '#fff' : 'transparent',
                }}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          {/* Scrollable content + right resource panel */}
          <div className="flex flex-1 min-h-0 overflow-hidden">
            <div className="flex-1 overflow-y-auto p-3">

              {/* ── HOST SUMMARY ─────────────────────────────────── */}
              {selectedHost && activeTab === 'summary' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    {/* Hardware panel */}
                    <ContentPanel title="Hardware">
                      <InfoRow label="Manufacturer" value={selectedHost.vendor} />
                      <InfoRow label="Model" value={selectedHost.model} />
                      <InfoRow label="CPU" value={`${selectedHost.cpu_sockets} CPUs x ${selectedHost.cpu_model}`} />
                      <InfoRow label="Memory" value={`${selectedHost.memory_gb} GB`} />
                      <InfoRow label="Virtual flash" value="0 B used, 0 B capacity" />
                      <InfoRow label="Networking" value={`${selectedHost.network_adapters} adapters`} />
                      <div className="mt-1">
                        <span className="text-[#555] text-[10px]">Storage</span>
                        <table className="w-full mt-1 text-[10px] border-collapse">
                          <thead>
                            <tr className="bg-[#e8edf4]">
                              <th className="border border-[#ccc] px-1 py-0.5 text-left font-semibold">Name</th>
                              <th className="border border-[#ccc] px-1 py-0.5 text-left font-semibold">Type</th>
                              <th className="border border-[#ccc] px-1 py-0.5 text-right font-semibold">Capacity</th>
                              <th className="border border-[#ccc] px-1 py-0.5 text-right font-semibold">Free</th>
                            </tr>
                          </thead>
                          <tbody>
                            {datastores.map(ds => (
                              <tr key={ds.id} className="hover:bg-[#f0f4f8]">
                                <td className="border border-[#ccc] px-1 py-0.5 text-[#1a4fa0]">{ds.name}</td>
                                <td className="border border-[#ccc] px-1 py-0.5">{ds.type}</td>
                                <td className="border border-[#ccc] px-1 py-0.5 text-right">{fmtBytes(ds.capacity_gb)}</td>
                                <td className="border border-[#ccc] px-1 py-0.5 text-right">{fmtBytes(ds.free_gb)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </ContentPanel>

                    {/* Config + perf panel */}
                    <div className="space-y-3">
                      <ContentPanel title="Configuration">
                        <InfoRow label="Power policy" value={selectedHost.power_policy} />
                        <InfoRow label="NTP server" value={selectedHost.ntp_server} />
                        <InfoRow label="DNS" value={selectedHost.dns_servers.join(', ')} />
                        <InfoRow label="IP address" value={selectedHost.ip} />
                        <InfoRow label="SSH" value={selectedHost.ssh_enabled ? 'Enabled' : 'Disabled'} />
                        <InfoRow label="HA" value={<span className={summary.cluster_ha ? 'text-[#2db52d]' : 'text-[#e0412b]'}>{summary.cluster_ha ? 'Enabled' : 'Disabled'}</span>} />
                        <InfoRow label="DRS" value={<span className={summary.cluster_drs ? 'text-[#2db52d]' : 'text-[#888]'}>{summary.cluster_drs ? 'Enabled' : 'Disabled'}</span>} />
                        {!summary.cluster_ha && (
                          <button onClick={() => runAction('enable_ha')} disabled={acting}
                            className="mt-1 w-full py-1 text-[11px] bg-[#5b9bd5] text-white rounded hover:bg-[#4a8ac4] disabled:opacity-50">
                            Enable HA
                          </button>
                        )}
                      </ContentPanel>
                      <ContentPanel title="Performance summary last hour">
                        <div className="flex items-center gap-3 mb-1 text-[10px]">
                          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#4c9be8]" /> Consumed host CPU</span>
                          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#9b59b6]" /> Consumed host memory</span>
                        </div>
                        <PerfChart cpuPct={selectedHost.cpu_pct} memPct={selectedHost.mem_pct} />
                        <div className="flex justify-between text-[10px] text-[#888] mt-1">
                          <span>60 min ago</span><span>Now</span>
                        </div>
                      </ContentPanel>
                    </div>
                  </div>

                  {/* VMs on this host */}
                  <ContentPanel title={`Virtual Machines on ${selectedHost.name}`}>
                    <VmTable vms={vms.filter(v => v.host_id === selectedHost.id)}
                      onSelect={vm => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary') }}
                      onAction={runAction} acting={acting} />
                  </ContentPanel>
                </div>
              )}

              {/* ── HOST MONITOR ─────────────────────────────────── */}
              {selectedHost && activeTab === 'monitor' && (
                <div className="space-y-3">
                  <ContentPanel title="Resource utilisation">
                    <div className="grid grid-cols-3 gap-4">
                      {[
                        { label: 'CPU', pct: selectedHost.cpu_pct, color: '#4c9be8', detail: `${selectedHost.cpu_sockets * selectedHost.cpu_cores_per_socket * selectedHost.cpu_mhz / 1000} GHz total` },
                        { label: 'Memory', pct: selectedHost.mem_pct, color: '#9b59b6', detail: `${selectedHost.memory_gb} GB total` },
                        { label: 'Storage', pct: selectedHost.storage_pct, color: '#e67e22', detail: `${fmtBytes(datastores.reduce((s, d) => s + d.capacity_gb, 0))} total` },
                      ].map(({ label, pct, color, detail }) => (
                        <div key={label}>
                          <div className="flex justify-between text-[11px] mb-1"><span className="font-semibold">{label}</span><span className="text-[#666]">{pct}%</span></div>
                          <UsageBar pct={pct} color={color} />
                          <p className="text-[10px] text-[#888] mt-0.5">{detail}</p>
                        </div>
                      ))}
                    </div>
                  </ContentPanel>
                  <ContentPanel title="Performance charts">
                    <PerfChart cpuPct={selectedHost.cpu_pct} memPct={selectedHost.mem_pct} />
                  </ContentPanel>
                  <ContentPanel title="Alarms">
                    {activeAlarms.length === 0 ? (
                      <p className="text-[#888] text-[11px]">No active alarms</p>
                    ) : activeAlarms.map(a => (
                      <div key={a.id} className="flex items-center gap-2 py-1.5 border-b border-[#eee] last:border-0">
                        <span className={`text-[10px] font-bold px-1 rounded ${a.severity === 'critical' ? 'bg-[#fde8e4] text-[#c03]' : 'bg-[#fef9e4] text-[#a07]'}`}>{a.severity.toUpperCase()}</span>
                        <span className="text-[11px] flex-1">{a.name}</span>
                        <span className="text-[10px] text-[#888]">{a.entity}</span>
                        <button onClick={() => runAction('acknowledge_alarm', { alarm_id: a.id })} disabled={acting}
                          className="text-[10px] text-[#5b9bd5] hover:underline disabled:opacity-50">Ack</button>
                      </div>
                    ))}
                  </ContentPanel>
                </div>
              )}

              {/* ── HOST CONFIGURE ───────────────────────────────── */}
              {selectedHost && activeTab === 'configure' && (
                <div className="space-y-3">
                  <ContentPanel title="Cluster settings">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-[11px] font-semibold mb-1">vSphere HA</p>
                        <div className="flex items-center gap-2">
                          <StatusIcon status={summary.cluster_ha ? 'connected' : 'disconnected'} />
                          <span className="text-[11px]">{summary.cluster_ha ? 'Enabled' : 'Disabled'}</span>
                          {summary.cluster_ha
                            ? <button onClick={() => runAction('disable_ha')} disabled={acting} className="ml-auto text-[11px] border border-[#ccc] px-2 py-0.5 rounded hover:bg-[#f0f0f0] disabled:opacity-50">Disable</button>
                            : <button onClick={() => runAction('enable_ha')} disabled={acting} className="ml-auto text-[11px] bg-[#5b9bd5] text-white px-2 py-0.5 rounded hover:bg-[#4a8ac4] disabled:opacity-50">Enable</button>
                          }
                        </div>
                      </div>
                      <div>
                        <p className="text-[11px] font-semibold mb-1">vSphere DRS</p>
                        <div className="flex items-center gap-2">
                          <StatusIcon status={summary.cluster_drs ? 'connected' : 'disconnected'} />
                          <span className="text-[11px]">{summary.cluster_drs ? 'Enabled' : 'Disabled'}</span>
                          {!summary.cluster_drs && (
                            <button onClick={() => runAction('enable_drs')} disabled={acting} className="ml-auto text-[11px] bg-[#5b9bd5] text-white px-2 py-0.5 rounded hover:bg-[#4a8ac4] disabled:opacity-50">Enable</button>
                          )}
                        </div>
                      </div>
                    </div>
                  </ContentPanel>
                  <ContentPanel title="Host network adapters">
                    {(inv.vswitches || []).map(vsw => (
                      <div key={vsw.id} className="border border-[#ddd] rounded p-2 mb-2">
                        <p className="text-[11px] font-semibold">{vsw.name} <span className="text-[10px] text-[#888] font-normal">({vsw.type})</span></p>
                        <div className="grid grid-cols-3 gap-1 mt-1 text-[10px]">
                          <span className="text-[#666]">Ports: {vsw.ports}</span>
                          <span className="text-[#666]">MTU: {vsw.mtu}</span>
                          <span className="text-[#666]">Uplinks: {vsw.uplinks?.join(', ')}</span>
                        </div>
                        <p className="text-[10px] text-[#888] mt-0.5">Port groups: {vsw.portgroups?.join(', ')}</p>
                      </div>
                    ))}
                  </ContentPanel>
                </div>
              )}

              {/* ── VM SUMMARY ───────────────────────────────────── */}
              {selectedVm && activeTab === 'summary' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <ContentPanel title="Virtual machine details">
                      <InfoRow label="Guest OS" value={selectedVm.guest_os_version} />
                      <InfoRow label="Hostname" value={selectedVm.hostname} />
                      <InfoRow label="IP address" value={selectedVm.ip} />
                      <InfoRow label="VMware Tools" value={<span className={selectedVm.tools === 'ok' ? 'text-[#2db52d]' : 'text-[#e0412b]'}>{selectedVm.tools === 'ok' ? 'Running' : 'Not Running'} (v{selectedVm.tools_version})</span>} />
                      <InfoRow label="VM hardware" value={selectedVm.hardware_version} />
                      <InfoRow label="Annotation" value={selectedVm.annotation || '—'} />
                    </ContentPanel>
                    <ContentPanel title="Hardware configuration">
                      <InfoRow label="CPUs" value={`${selectedVm.cpu} vCPU`} />
                      <InfoRow label="Memory" value={fmtMb(selectedVm.memory_mb)} />
                      <InfoRow label="Hard disk" value={fmtBytes(selectedVm.disk_gb)} />
                      <InfoRow label="Network" value={networks.find(n => n.id === selectedVm.network_id)?.name || 'VM Network'} />
                      <InfoRow label="Datastore" value={datastores.find(d => d.id === selectedVm.datastore_id)?.name || '—'} />
                      <InfoRow label="Host" value={hosts.find(h => h.id === selectedVm.host_id)?.name || '—'} />
                    </ContentPanel>
                  </div>

                  {/* Resource consumption */}
                  {selectedVm.power === 'poweredOn' && (
                    <ContentPanel title="Resource consumption">
                      <div className="grid grid-cols-4 gap-3">
                        {[
                          { label: 'CPU', pct: selectedVm.cpu_pct, color: '#4c9be8' },
                          { label: 'Memory', pct: selectedVm.mem_pct, color: '#9b59b6' },
                          { label: 'Disk I/O', pct: Math.min(selectedVm.disk_io_mbps * 2, 100), color: '#e67e22', detail: `${selectedVm.disk_io_mbps} MB/s` },
                          { label: 'Network', pct: Math.min(selectedVm.net_mbps * 5, 100), color: '#27ae60', detail: `${selectedVm.net_mbps} Mbps` },
                        ].map(({ label, pct, color, detail }) => (
                          <div key={label}>
                            <div className="flex justify-between text-[10px] mb-1"><span>{label}</span><span>{detail || `${pct}%`}</span></div>
                            <UsageBar pct={pct} color={color} />
                          </div>
                        ))}
                      </div>
                    </ContentPanel>
                  )}

                  {/* Snapshots */}
                  {(selectedVm.snapshots?.length > 0) && (
                    <ContentPanel title="Snapshots">
                      {selectedVm.snapshots.map(snap => (
                        <div key={snap.id} className="flex items-center gap-3 py-1.5 border-b border-[#eee] last:border-0">
                          <span className="text-[11px] flex-1">{snap.name}</span>
                          <span className="text-[10px] text-[#888]">{fmtTime(snap.created)}</span>
                          <button onClick={() => runAction('revert_snapshot', { vm_id: selectedVm.id, snapshot_id: snap.id })} disabled={acting}
                            className="text-[10px] text-[#5b9bd5] hover:underline disabled:opacity-50">Revert</button>
                          <button onClick={() => runAction('delete_snapshot', { vm_id: selectedVm.id, snapshot_id: snap.id })} disabled={acting}
                            className="text-[10px] text-[#c03] hover:underline disabled:opacity-50">Delete</button>
                        </div>
                      ))}
                    </ContentPanel>
                  )}
                </div>
              )}

              {/* ── VM MONITOR ───────────────────────────────────── */}
              {selectedVm && activeTab === 'monitor' && (
                <div className="space-y-3">
                  <ContentPanel title="Performance">
                    {selectedVm.power !== 'poweredOn' ? (
                      <p className="text-[#888] text-[11px]">VM is not powered on — no performance data available</p>
                    ) : (
                      <>
                        <PerfChart cpuPct={selectedVm.cpu_pct} memPct={selectedVm.mem_pct} />
                        <div className="grid grid-cols-4 gap-2 mt-2">
                          <MetricCard label="CPU" value={`${selectedVm.cpu_pct}%`} color="#4c9be8" />
                          <MetricCard label="Memory" value={`${selectedVm.mem_pct}%`} color="#9b59b6" />
                          <MetricCard label="Disk" value={`${selectedVm.disk_io_mbps} MB/s`} color="#e67e22" />
                          <MetricCard label="Network" value={`${selectedVm.net_mbps} Mbps`} color="#27ae60" />
                        </div>
                      </>
                    )}
                  </ContentPanel>
                </div>
              )}

              {/* ── VM SNAPSHOTS ─────────────────────────────────── */}
              {selectedVm && activeTab === 'snapshots' && (
                <ContentPanel title="Snapshot Manager">
                  <div className="flex items-center gap-2 mb-3">
                    <button onClick={() => setShowSnapshotModal(true)} disabled={acting}
                      className="px-3 py-1.5 text-[11px] bg-[#5b9bd5] text-white rounded hover:bg-[#4a8ac4] disabled:opacity-50">
                      Take Snapshot
                    </button>
                  </div>
                  {(selectedVm.snapshots?.length === 0 || !selectedVm.snapshots) ? (
                    <p className="text-[#888] text-[11px]">No snapshots</p>
                  ) : selectedVm.snapshots.map(snap => (
                    <div key={snap.id} className="flex items-center gap-3 py-2 border-b border-[#eee] last:border-0">
                      <span className="text-[10px] text-[#666]">📷</span>
                      <div className="flex-1">
                        <p className="text-[11px] font-semibold">{snap.name}</p>
                        <p className="text-[10px] text-[#888]">{snap.description || 'No description'} · {fmtTime(snap.created)}</p>
                      </div>
                      <button onClick={() => runAction('revert_snapshot', { vm_id: selectedVm.id, snapshot_id: snap.id })} disabled={acting}
                        className="px-2 py-0.5 text-[10px] border border-[#aaa] rounded bg-[#f0f0f0] hover:bg-[#e0e0e0] disabled:opacity-50">Revert</button>
                      <button onClick={() => runAction('delete_snapshot', { vm_id: selectedVm.id, snapshot_id: snap.id })} disabled={acting}
                        className="px-2 py-0.5 text-[10px] border border-[#faa] rounded bg-[#fff0ee] text-[#c03] hover:bg-[#ffe0dc] disabled:opacity-50">Delete</button>
                    </div>
                  ))}
                </ContentPanel>
              )}

              {/* ── DATASTORE ────────────────────────────────────── */}
              {selectedDs && activeTab === 'summary' && (
                <div className="space-y-3">
                  <ContentPanel title="Datastore details">
                    <InfoRow label="Type" value={selectedDs.type} />
                    <InfoRow label="Version" value={selectedDs.version} />
                    <InfoRow label="Capacity" value={fmtBytes(selectedDs.capacity_gb)} />
                    <InfoRow label="Free" value={<span className={selectedDs.free_gb < 50 ? 'text-[#e04]' : 'text-[#2db52d]'}>{fmtBytes(selectedDs.free_gb)}</span>} />
                    <InfoRow label="Used" value={fmtBytes(selectedDs.capacity_gb - selectedDs.free_gb)} />
                    <InfoRow label="Accessible" value={<span className={selectedDs.accessible ? 'text-[#2db52d]' : 'text-[#e04]'}>{selectedDs.accessible ? 'Yes' : 'No'}</span>} />
                    <InfoRow label="Hosts" value={selectedDs.hosts?.length || 0} />
                    <InfoRow label="VMs" value={selectedDs.vms?.length || 0} />
                  </ContentPanel>
                  <ContentPanel title="Capacity">
                    <div className="flex items-center gap-2 mb-1">
                      <UsageBar pct={((selectedDs.capacity_gb - selectedDs.free_gb) / selectedDs.capacity_gb) * 100} color={selectedDs.free_gb < 50 ? '#e0412b' : '#4c9be8'} />
                      <span className="text-[11px] shrink-0">{(((selectedDs.capacity_gb - selectedDs.free_gb) / selectedDs.capacity_gb) * 100).toFixed(0)}%</span>
                    </div>
                    <button onClick={() => runAction('expand_datastore', { datastore: selectedDs.name, gb: 500 })} disabled={acting}
                      className="mt-2 px-3 py-1.5 text-[11px] border border-[#aaa] rounded bg-[#e8e8e8] hover:bg-[#ddd] disabled:opacity-50">
                      Increase capacity (+500 GB)
                    </button>
                  </ContentPanel>
                </div>
              )}

              {/* ── NETWORK ──────────────────────────────────────── */}
              {selectedNet && activeTab === 'summary' && (
                <ContentPanel title="Network details">
                  <InfoRow label="Type" value={selectedNet.type} />
                  <InfoRow label="VLAN ID" value={selectedNet.vlan === 0 ? 'All (0)' : String(selectedNet.vlan)} />
                  <InfoRow label="vSwitch" value={selectedNet.switch} />
                  <InfoRow label="Connected hosts" value={selectedNet.hosts?.length || 0} />
                </ContentPanel>
              )}

              {/* ── EVENTS TAB ───────────────────────────────────── */}
              {activeTab === 'events' && (
                <ContentPanel title="Events">
                  {events.length === 0 ? <p className="text-[#888] text-[11px]">No events</p> : (
                    <table className="w-full text-[10px] border-collapse">
                      <thead>
                        <tr className="bg-[#e8edf4]">
                          <th className="border border-[#ccc] px-1 py-1 text-left">Time</th>
                          <th className="border border-[#ccc] px-1 py-1 text-left">Severity</th>
                          <th className="border border-[#ccc] px-1 py-1 text-left">Entity</th>
                          <th className="border border-[#ccc] px-1 py-1 text-left">Message</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...events].reverse().map((ev, i) => (
                          <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-[#f8f9fb]'}>
                            <td className="border border-[#e0e0e0] px-1 py-0.5 font-mono whitespace-nowrap">{ev.time?.slice(11, 19)}</td>
                            <td className="border border-[#e0e0e0] px-1 py-0.5">
                              <span className={`px-1 rounded text-[9px] font-bold ${ev.severity === 'critical' ? 'bg-[#fde8e4] text-[#c03]' : ev.severity === 'warning' ? 'bg-[#fef9e4] text-[#a07]' : 'bg-[#e8f5e4] text-[#270]'}`}>
                                {ev.severity.toUpperCase()}
                              </span>
                            </td>
                            <td className="border border-[#e0e0e0] px-1 py-0.5 text-[#1a4fa0]">{ev.entity}</td>
                            <td className="border border-[#e0e0e0] px-1 py-0.5">{ev.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </ContentPanel>
              )}
            </div>

            {/* ── Right resource summary ─────────────────────────── */}
            {(selectedHost || selectedVm) && (
              <aside className="shrink-0 border-l border-[#c0c8d4] overflow-y-auto p-2 space-y-2" style={{ width: 160, background: '#f8f9fb' }}>
                <p className="text-[10px] font-bold text-[#1e3a5f] uppercase tracking-wider">Resources</p>
                {[
                  { label: 'CPU', free: selectedHost ? `${100 - selectedHost.cpu_pct}%` : `${100 - (selectedVm?.cpu_pct || 0)}%`, used: `${selectedHost?.cpu_pct || selectedVm?.cpu_pct || 0}%`, color: '#4c9be8', pct: selectedHost?.cpu_pct || selectedVm?.cpu_pct || 0 },
                  { label: 'Memory', free: selectedHost ? `${(selectedHost.memory_gb * (1 - selectedHost.mem_pct / 100)).toFixed(1)} GB free` : `${(selectedVm?.memory_mb * (1 - (selectedVm?.mem_pct || 0) / 100) / 1024).toFixed(1)} GB`, used: selectedHost ? `${(selectedHost.memory_gb * selectedHost.mem_pct / 100).toFixed(1)} GB` : `${(selectedVm?.memory_mb / 1024).toFixed(1)} GB`, color: '#9b59b6', pct: selectedHost?.mem_pct || selectedVm?.mem_pct || 0 },
                  { label: 'Storage', free: selectedHost ? `${fmtBytes(datastores.filter(d => d.hosts?.includes(selectedHost.id)).reduce((s, d) => s + d.free_gb, 0))} free` : fmtBytes(datastores.find(d => d.id === selectedVm?.datastore_id)?.free_gb || 0), used: `${selectedHost?.storage_pct || 0}%`, color: '#e67e22', pct: selectedHost?.storage_pct || 0 },
                  { label: 'Network', free: `${100 - Math.min(selectedHost?.network_mbps || 0, 100)}%`, used: `${selectedHost?.network_mbps || selectedVm?.net_mbps || 0} Mbps`, color: '#27ae60', pct: Math.min(selectedHost?.network_mbps || 0, 100) },
                ].map(({ label, free, used, color, pct }) => (
                  <div key={label} className="border border-[#ddd] rounded p-1.5 bg-white">
                    <p className="text-[10px] font-semibold text-[#333] mb-1">{label}</p>
                    <div className="flex justify-between text-[9px] text-[#666] mb-0.5">
                      <span>FREE: {free}</span>
                    </div>
                    <div className="flex justify-between text-[9px] text-[#666] mb-1">
                      <span>USED: {used}</span>
                    </div>
                    <UsageBar pct={pct} color={color} />
                    <p className="text-[9px] text-right text-[#888] mt-0.5">CAPACITY</p>
                  </div>
                ))}
              </aside>
            )}
          </div>

          {/* ── Recent tasks bottom panel ─────────────────────────── */}
          <div className="shrink-0 border-t border-[#c0c8d4]" style={{ background: '#f8f9fb' }}>
            <div className="flex items-center px-3 py-1 border-b border-[#e0e4ec] cursor-pointer hover:bg-[#eef2f7]">
              <span className="text-[11px] font-semibold text-[#1e3a5f]">Recent Tasks</span>
              <span className="text-[10px] text-[#888] ml-2">({recentTasks.length})</span>
            </div>
            <div className="overflow-x-auto" style={{ maxHeight: 120 }}>
              <table className="w-full text-[10px] border-collapse min-w-max">
                <thead className="sticky top-0">
                  <tr style={{ background: '#e8edf4' }}>
                    {['Task Name', 'Target', 'Initiator', 'Queued', 'Started', 'Result', 'Completed'].map(h => (
                      <th key={h} className="border border-[#ccc] px-2 py-0.5 text-left font-semibold whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recentTasks.slice(0, 15).map((t, i) => (
                    <tr key={t.id || i} className={i % 2 === 0 ? 'bg-white' : 'bg-[#f8f9fb]'}>
                      <td className="border border-[#e8e8e8] px-2 py-0.5 whitespace-nowrap">{t.name}</td>
                      <td className="border border-[#e8e8e8] px-2 py-0.5 text-[#1a4fa0]">{t.target}</td>
                      <td className="border border-[#e8e8e8] px-2 py-0.5">{t.initiator}</td>
                      <td className="border border-[#e8e8e8] px-2 py-0.5 font-mono">{fmtTime(t.queued)}</td>
                      <td className="border border-[#e8e8e8] px-2 py-0.5 font-mono">{fmtTime(t.started)}</td>
                      <td className="border border-[#e8e8e8] px-2 py-0.5">
                        <span className={`flex items-center gap-1 ${t.status === 'success' ? 'text-[#2db52d]' : 'text-[#e0412b]'}`}>
                          {t.status === 'success' ? '✓' : '✗'} {t.result}
                        </span>
                      </td>
                      <td className="border border-[#e8e8e8] px-2 py-0.5 font-mono">{fmtTime(t.completed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>

      {/* Modals */}
      {showSnapshotModal && selectedVm && (
        <SnapshotModal vm={selectedVm} onClose={() => setShowSnapshotModal(false)} onAction={runAction} />
      )}
      {showMigrateModal && selectedVm && (
        <MigrateModal vm={selectedVm} hosts={hosts} onClose={() => setShowMigrateModal(false)} onAction={runAction} />
      )}
    </div>
  )
}

/* ─── Sub-components ─────────────────────────────────────────────────── */
function getTabs(type) {
  if (type === 'vm') return ['summary', 'monitor', 'snapshots', 'configure', 'events']
  if (type === 'host') return ['summary', 'monitor', 'configure', 'permissions', 'datastores', 'networks', 'events']
  if (type === 'datastore') return ['summary', 'monitor', 'hosts', 'vms']
  if (type === 'network') return ['summary', 'hosts', 'vms']
  return ['summary']
}

function NavSection({ label, expanded, onToggle, children }) {
  return (
    <div>
      <button onClick={onToggle} className="w-full flex items-center gap-1 px-2 py-1.5 text-[10px] font-bold text-[#8ab4d4] uppercase tracking-wider hover:bg-[#2a4a6f]">
        <span className="text-[8px]">{expanded ? '▼' : '▶'}</span>
        {label}
      </button>
      {expanded && <div>{children}</div>}
    </div>
  )
}

function NavItem({ icon, label, status, active, onClick, badge, children }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <div
        onClick={() => { onClick(); setOpen(v => !v) }}
        className="flex items-center gap-1.5 px-3 py-1.5 cursor-pointer text-[11px] transition-colors"
        style={{ background: active ? '#2a4a6f' : 'transparent', color: active ? '#fff' : '#c8d8e8' }}
        onMouseEnter={e => { if (!active) e.currentTarget.style.background = '#243a5e' }}
        onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
      >
        <span className="shrink-0">{icon}</span>
        <span className="truncate flex-1">{label}</span>
        {badge && <span className="text-[9px] bg-amber-500 text-white rounded px-0.5">{badge}</span>}
        <StatusIcon status={status} size={8} />
        {children && <span className="text-[8px] text-[#6880a0]">{open ? '▾' : '▸'}</span>}
      </div>
      {open && children && <div className="pl-4">{children}</div>}
    </div>
  )
}

function NavSubItem({ label, onClick }) {
  return (
    <div onClick={onClick} className="px-3 py-1 text-[10px] text-[#8ab4d4] cursor-pointer hover:bg-[#2a4a6f] hover:text-white">
      {label}
    </div>
  )
}

function ContentPanel({ title, children }) {
  return (
    <div className="border border-[#c0c8d4] rounded bg-white overflow-hidden">
      <div className="px-3 py-1.5 border-b border-[#c0c8d4] text-[11px] font-semibold text-[#1e3a5f]" style={{ background: '#eef2f7' }}>
        {title}
      </div>
      <div className="p-3">{children}</div>
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start py-0.5 border-b border-[#f0f0f0] last:border-0">
      <span className="text-[10px] text-[#555] w-28 shrink-0">{label}</span>
      <span className="text-[11px] text-[#222] flex-1">{value}</span>
    </div>
  )
}

function MetricCard({ label, value, color }) {
  return (
    <div className="border border-[#ddd] rounded p-2 text-center bg-[#fafafa]">
      <p className="text-[10px] text-[#888]">{label}</p>
      <p className="text-base font-bold mt-0.5" style={{ color }}>{value}</p>
    </div>
  )
}

function VmTable({ vms, onSelect, onAction, acting }) {
  return (
    <table className="w-full text-[10px] border-collapse">
      <thead>
        <tr style={{ background: '#e8edf4' }}>
          {['', 'Name', 'Power', 'Guest OS', 'IP', 'CPU', 'Memory', ''].map((h, i) => (
            <th key={i} className="border border-[#ccc] px-1 py-1 text-left font-semibold">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {vms.map((vm, i) => (
          <tr key={vm.id} className={`${i % 2 === 0 ? 'bg-white' : 'bg-[#f8f9fb]'} hover:bg-[#e8f0fc] cursor-pointer`}
            onClick={() => onSelect(vm)}>
            <td className="border border-[#e0e0e0] px-1 py-0.5"><StatusIcon status={vm.power} /></td>
            <td className="border border-[#e0e0e0] px-1 py-0.5 text-[#1a4fa0]">{vm.name}</td>
            <td className="border border-[#e0e0e0] px-1 py-0.5">{vm.power}</td>
            <td className="border border-[#e0e0e0] px-1 py-0.5">{vm.guest_os_version || vm.guest_os}</td>
            <td className="border border-[#e0e0e0] px-1 py-0.5">{vm.ip}</td>
            <td className="border border-[#e0e0e0] px-1 py-0.5">{vm.cpu_pct}%</td>
            <td className="border border-[#e0e0e0] px-1 py-0.5">{vm.mem_pct}%</td>
            <td className="border border-[#e0e0e0] px-1 py-0.5 whitespace-nowrap">
              {vm.power === 'poweredOff' ? (
                <button onClick={e => { e.stopPropagation(); onAction('power_on', { vm_id: vm.id }) }} disabled={acting}
                  className="px-1.5 py-0.5 text-[9px] bg-[#5b9bd5] text-white rounded hover:bg-[#4a8ac4] disabled:opacity-50">Power On</button>
              ) : (
                <button onClick={e => { e.stopPropagation(); onAction('power_off', { vm_id: vm.id }) }} disabled={acting}
                  className="px-1.5 py-0.5 text-[9px] border border-[#ccc] rounded bg-[#f0f0f0] hover:bg-[#e0e0e0] disabled:opacity-50">Power Off</button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ToolbarBtn({ onClick, disabled, label, blue }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`px-2.5 py-1 text-[11px] border rounded disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${blue
        ? 'bg-[#5b9bd5] text-white border-[#4a8ac4] hover:bg-[#4a8ac4]'
        : 'border-[#aab] bg-[#e4e9f0] hover:bg-[#d8dfe8] text-[#222]'}`}
    >
      {label}
    </button>
  )
}

function ToolbarSep() {
  return <span className="w-px h-4 bg-[#c0c8d4] mx-1" />
}

function RefreshBtn({ onClick }) {
  return (
    <button onClick={onClick} title="Refresh" className="px-2 py-1 border border-[#aab] rounded bg-[#e4e9f0] hover:bg-[#d8dfe8] text-[11px]">
      ↻
    </button>
  )
}

function ActionsMenuItem({ label, onClick }) {
  return (
    <button onClick={onClick} className="w-full text-left px-3 py-1.5 hover:bg-[#e8f0fc] text-[11px]">{label}</button>
  )
}

function HostIcon() {
  return <span className="text-[#5b9bd5] text-[10px]">⊞</span>
}

function VmIcon({ power }) {
  return <span className={`text-[10px] ${power === 'poweredOn' ? 'text-[#2db52d]' : power === 'suspended' ? 'text-[#f5a623]' : 'text-[#888]'}`}>◼</span>
}

function DsIcon() {
  return <span className="text-[#e67e22] text-[10px]">⬡</span>
}

function NetIcon() {
  return <span className="text-[#27ae60] text-[10px]">⬡</span>
}
