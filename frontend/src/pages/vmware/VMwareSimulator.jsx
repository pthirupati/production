import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { vmwareApi } from '../../api/vmware'
import toast from 'react-hot-toast'
import VmwareLabChrome from '../../components/vmware/VmwareLabChrome'
import VmwareInventoryTree from '../../components/vmware/VmwareInventoryTree'
import VmwareConsole from '../../components/vmware/VmwareConsole'
import VmwareContextMenu from '../../components/vmware/VmwareContextMenu'
import VmModal from '../../components/vmware/VmModal'
import VmConfigurePanel from '../../components/vmware/VmConfigurePanel'
import VmwareToast from '../../components/vmware/VmwareToast'
import '../../styles/vmware-sim.css'

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

function UsageBar({ pct, color = '#2D7CFF' }) {
  return (
    <div className="vm-usage-bar">
      <div className="vm-usage-bar-fill" style={{ width: `${Math.min(pct, 100)}%`, background: color, boxShadow: `0 0 10px ${color}` }} />
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
    <div className="vm-modal-overlay">
      <div className="vm-modal w-96">
        <div className="vm-modal-header">
          <span>Take Snapshot — {vm.name}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Snapshot name</label>
            <input value={name} onChange={e => setName(e.target.value)} className="vm-input" />
          </div>
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Description (optional)</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2} className="vm-input resize-none" />
          </div>
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          <button type="button" disabled={acting || !name.trim()} onClick={create} className="vm-btn vm-btn-green">
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
    <div className="vm-modal-overlay">
      <div className="vm-modal w-96">
        <div className="vm-modal-header">
          <span>Migrate VM — {vm.name}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">
          <p className="text-xs text-[#8fa5b8]">Select destination host (VMotion):</p>
          {available.length === 0 ? (
            <p className="text-sm text-[#D9534F]">No compatible hosts available</p>
          ) : available.map(h => (
            <label key={h.id} className="flex items-center gap-2 cursor-pointer text-sm text-[#E8EDF2]">
              <input type="radio" name="host" value={h.name} checked={targetHost === h.name} onChange={() => setTargetHost(h.name)} />
              <StatusIcon status={h.status} />
              <span>{h.name}</span>
            </label>
          ))}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          <button type="button" disabled={acting || !targetHost} onClick={migrate} className="vm-btn vm-btn-blue">
            {acting ? 'Migrating…' : 'Migrate'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Create VM Modal ────────────────────────────────────────────────── */
function CreateVmModal({ hosts, datastores, networks, onClose, onAction }) {
  const [name, setName] = useState('')
  const [cpu, setCpu] = useState('2')
  const [memGb, setMemGb] = useState('4')
  const [diskGb, setDiskGb] = useState('40')
  const [guestOs, setGuestOs] = useState('Ubuntu Linux (64-bit)')
  const [hostId, setHostId] = useState(hosts[0]?.id || '')
  const [dsId, setDsId] = useState(datastores[0]?.id || '')
  const [netId, setNetId] = useState(networks[0]?.id || '')
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const create = async () => {
    if (!name.trim()) { setError('VM name is required'); return }
    setActing(true); setError('')
    try {
      await onAction('create_vm', {
        name: name.trim(), cpu: parseInt(cpu), memory_mb: parseInt(memGb) * 1024,
        disk_gb: parseInt(diskGb), guest_os: guestOs, host_id: hostId, datastore_id: dsId, network_id: netId,
      })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Create failed')
    } finally { setActing(false) }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[480px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>New Virtual Machine</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-[#8fa5b8] mb-1">VM Name *</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="my-server-01" className="vm-input !pl-3" />
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Guest OS</label>
              <select value={guestOs} onChange={e => setGuestOs(e.target.value)} className="vm-input !pl-3">
                {['Ubuntu Linux (64-bit)', 'Red Hat Enterprise Linux 8 (64-bit)', 'CentOS 7 (64-bit)', 'Windows Server 2019 (64-bit)', 'Debian GNU/Linux 11 (64-bit)', 'Other Linux (64-bit)'].map(o => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Host</label>
              <select value={hostId} onChange={e => setHostId(e.target.value)} className="vm-input !pl-3">
                {hosts.filter(h => h.status === 'connected' && !h.maintenance).map(h => (
                  <option key={h.id} value={h.id}>{h.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">CPUs</label>
              <select value={cpu} onChange={e => setCpu(e.target.value)} className="vm-input !pl-3">
                {['1','2','4','8','16'].map(v => <option key={v} value={v}>{v} vCPU{v !== '1' ? 's' : ''}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Memory (GB)</label>
              <select value={memGb} onChange={e => setMemGb(e.target.value)} className="vm-input !pl-3">
                {['1','2','4','8','16','32','64'].map(v => <option key={v} value={v}>{v} GB</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Hard disk (GB)</label>
              <input type="number" min="10" value={diskGb} onChange={e => setDiskGb(e.target.value)} className="vm-input !pl-3" />
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Datastore</label>
              <select value={dsId} onChange={e => setDsId(e.target.value)} className="vm-input !pl-3">
                {datastores.filter(d => d.accessible).map(d => (
                  <option key={d.id} value={d.id}>{d.name} ({fmtBytes(d.free_gb)} free)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Network</label>
              <select value={netId} onChange={e => setNetId(e.target.value)} className="vm-input !pl-3">
                {networks.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
              </select>
            </div>
          </div>
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          <button type="button" disabled={acting || !name.trim()} onClick={create} className="vm-btn vm-btn-blue">
            {acting ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Edit VM Modal ──────────────────────────────────────────────────── */
function EditVmModal({ vm, networks, onClose, onAction }) {
  const [cpu, setCpu] = useState(String(vm.cpu))
  const [memGb, setMemGb] = useState(String(Math.round(vm.memory_mb / 1024)))
  const [annotation, setAnnotation] = useState(vm.annotation || '')
  const [netId, setNetId] = useState(vm.network_id || '')
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')
  const isPoweredOn = vm.power === 'poweredOn'

  const save = async () => {
    setActing(true); setError('')
    try {
      const payload = { vm_id: vm.id, annotation }
      if (!isPoweredOn) { payload.cpu = parseInt(cpu); payload.memory_mb = parseInt(memGb) * 1024 }
      if (netId !== vm.network_id) {
        await onAction('change_network', { vm_id: vm.id, network_id: netId })
      }
      await onAction('edit_vm', payload)
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Save failed')
    } finally { setActing(false) }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[420px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>Edit Settings — {vm.name}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">
          {isPoweredOn && (
            <div className="text-[11px] text-[#F5A623] bg-[rgba(245,166,35,.12)] border border-[rgba(245,166,35,.25)] rounded p-2">
              CPU and Memory cannot be changed while the VM is powered on.
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">CPUs</label>
              <select value={cpu} onChange={e => setCpu(e.target.value)} disabled={isPoweredOn} className="vm-input !pl-3 disabled:opacity-50">
                {['1','2','4','8','16'].map(v => <option key={v} value={v}>{v} vCPU{v !== '1' ? 's' : ''}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Memory (GB)</label>
              <select value={memGb} onChange={e => setMemGb(e.target.value)} disabled={isPoweredOn} className="vm-input !pl-3 disabled:opacity-50">
                {['1','2','4','8','16','32','64'].map(v => <option key={v} value={v}>{v} GB</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-[#8fa5b8] mb-1">Network</label>
              <select value={netId} onChange={e => setNetId(e.target.value)} className="vm-input !pl-3">
                {networks.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-[#8fa5b8] mb-1">Annotation / Notes</label>
              <textarea value={annotation} onChange={e => setAnnotation(e.target.value)} rows={2} className="vm-input !pl-3 resize-none" />
            </div>
          </div>
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          <button type="button" disabled={acting} onClick={save} className="vm-btn vm-btn-blue">
            {acting ? 'Saving…' : 'OK'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Clone VM Modal ─────────────────────────────────────────────────── */
function CloneVmModal({ vm, onClose, onAction }) {
  const [cloneName, setCloneName] = useState(`${vm.name}-clone`)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const clone = async () => {
    if (!cloneName.trim()) { setError('Clone name is required'); return }
    setActing(true); setError('')
    try {
      await onAction('clone_vm', { vm_id: vm.id, clone_name: cloneName.trim() })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Clone failed')
    } finally { setActing(false) }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-80">
        <div className="vm-modal-header">
          <span>Clone Virtual Machine — {vm.name}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Clone name</label>
            <input value={cloneName} onChange={e => setCloneName(e.target.value)} className="vm-input !pl-3" />
          </div>
          <p className="text-[10px] text-[#8fa5b8]">Creates a full copy of the VM in a powered-off state.</p>
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          <button type="button" disabled={acting || !cloneName.trim()} onClick={clone} className="vm-btn vm-btn-blue">
            {acting ? 'Cloning…' : 'Clone'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Main component ─────────────────────────────────────────────────── */
export default function VMwareSimulator() {
  const { sessionId: paramSessionId } = useParams()
  const [searchParams] = useSearchParams()
  // Prefer session ID from query param (redirected from LabRunner) over URL segment
  const sessionId = searchParams.get('session') || paramSessionId
  const scenarioSlug = searchParams.get('scenario') || ''
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [selectedNode, setSelectedNode] = useState({ type: 'host', id: null })
  const [activeTab, setActiveTab] = useState('summary')
  const [expandedSections, setExpandedSections] = useState({ hosts: true, vms: true, storage: true, networks: false })
  const [showSnapshotModal, setShowSnapshotModal] = useState(false)
  const [showMigrateModal, setShowMigrateModal] = useState(false)
  const [showCreateVmModal, setShowCreateVmModal] = useState(false)
  const [showEditVmModal, setShowEditVmModal] = useState(false)
  const [showCloneVmModal, setShowCloneVmModal] = useState(false)
  const [pendingDeleteVm, setPendingDeleteVm] = useState(null)
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false)
  const [inventorySearch, setInventorySearch] = useState('')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [tasksOpen, setTasksOpen] = useState(true)
  const [monSub, setMonSub] = useState('performance')
  const [monRange, setMonRange] = useState('1H')
  const [consoleVm, setConsoleVm] = useState(null)
  const [ctxMenu, setCtxMenu] = useState(null)
  const [vmToast, setVmToast] = useState(null)
  const rootRef = useRef(null)
  const actionsRef = useRef(null)

  const initialSelectionDone = useRef(false)
  const load = useCallback(async () => {
    try {
      const data = await vmwareApi.getState(sessionId, scenarioSlug)
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
    const onFs = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      rootRef.current?.requestFullscreen?.().catch(() => {})
    } else {
      document.exitFullscreen?.().catch(() => {})
    }
  }

  useEffect(() => {
    const onEsc = (e) => {
      if (e.key === 'Escape') {
        setConsoleVm(null)
        setCtxMenu(null)
        setActionsMenuOpen(false)
        setShowSnapshotModal(false)
        setShowMigrateModal(false)
        setShowCreateVmModal(false)
        setShowEditVmModal(false)
        setShowCloneVmModal(false)
        setPendingDeleteVm(null)
      }
    }
    document.addEventListener('keydown', onEsc)
    return () => document.removeEventListener('keydown', onEsc)
  }, [])

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
      const msg = res.message || 'Action completed'
      setVmToast({ message: msg, kind: 'success' })
      toast.success(msg, { style: { background: '#1b2a3b', color: '#e8edf2', border: '1px solid #2d3a4a', fontSize: '12px' } })
    } catch (err) {
      const errMsg = err.response?.data?.error || 'Action failed'
      setVmToast({ message: errMsg, kind: 'error' })
      toast.error(errMsg, { style: { background: '#1b2a3b', color: '#f08080', border: '1px solid #2d3a4a', fontSize: '12px' } })
    } finally {
      setActing(false)
    }
  }

  const handleCtxAction = (action, payload) => {
    if (action === '__snapshot__') {
      setSelectedNode({ type: 'vm', id: payload.id })
      setShowSnapshotModal(true)
    } else if (action === '__clone__') {
      setSelectedNode({ type: 'vm', id: payload.id })
      setShowCloneVmModal(true)
    } else if (action === '__migrate__') {
      setSelectedNode({ type: 'vm', id: payload.id })
      setShowMigrateModal(true)
    } else if (action === '__edit__') {
      setSelectedNode({ type: 'vm', id: payload.id })
      setShowEditVmModal(true)
    } else if (action === '__delete__') {
      setPendingDeleteVm(payload)
    } else if (action === '__suspend__') {
      toast('Suspend simulated')
    } else if (action === '__rename__') {
      toast('Rename simulated — use Edit Settings')
    } else {
      runAction(action, payload)
    }
  }

  const openVmContext = (e, vm) => {
    e.preventDefault()
    setCtxMenu({ x: e.clientX, y: e.clientY, vm })
  }

  if (loading) {
    return (
      <div className="vmware-sim vm-loading">
        <div className="text-center">
          <div className="vm-loading-spinner mx-auto mb-3" />
          <p className="text-[#8fa5b8] text-sm">Loading VMware Simulator…</p>
        </div>
      </div>
    )
  }

  const invSearch = inventorySearch.trim().toLowerCase()
  const filterLabel = (label) => !invSearch || label.toLowerCase().includes(invSearch)

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
      <div className="vm-toolbar-row">
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
        <ToolbarBtn onClick={() => setShowCloneVmModal(true)} disabled={acting} label="Clone…" />
        <ToolbarSep />
        <ToolbarBtn onClick={() => setShowEditVmModal(true)} disabled={acting} label="Edit Settings…" />
        <ToolbarBtn onClick={() => setPendingDeleteVm(vm)} disabled={isOn || acting} label="Delete" red />
        <div className="flex-1" />
        <RefreshBtn onClick={load} />
      </div>
    )
  }

  /* ── Host toolbar ── */
  const renderHostToolbar = (host) => (
    <div className="vm-toolbar-row">
      <ToolbarBtn onClick={() => { }} disabled label="Get vCenter Server" blue />
      <ToolbarSep />
      <ToolbarBtn onClick={() => setShowCreateVmModal(true)} disabled={acting} label="Create/Register VM" />
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
          <div className="absolute top-full left-0 mt-0.5 bg-[#243447] border border-[#2D3A4A] shadow-lg z-20 min-w-40 text-xs rounded-md overflow-hidden">
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
    <div ref={rootRef} className="vmware-sim flex flex-col h-screen select-none overflow-hidden">

      <VmwareLabChrome
        sessionId={sessionId}
        inventorySearch={inventorySearch}
        onSearchChange={setInventorySearch}
        onFullscreenToggle={toggleFullscreen}
        isFullscreen={isFullscreen}
      />

      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Left inventory tree ── */}
        <aside className="vm-nav">
          <VmwareInventoryTree
            inv={inv}
            hosts={hosts}
            vms={vms}
            datastores={datastores}
            networks={networks}
            filterLabel={filterLabel}
            selectedNode={selectedNode}
            setSelectedNode={setSelectedNode}
            setActiveTab={setActiveTab}
            onVmContextMenu={openVmContext}
            onCreateVm={() => setShowCreateVmModal(true)}
          />
        </aside>

        {/* ── Main content ──────────────────────────────────────────── */}
        <main className="vm-main">

          {/* Datastore full incident banner */}
          {datastores.some(d => d.free_gb / d.capacity_gb < 0.05) && (() => {
            const criticalDs = datastores.find(d => d.free_gb / d.capacity_gb < 0.05)
            const pct = criticalDs ? Math.round((1 - criticalDs.free_gb / criticalDs.capacity_gb) * 100) : 0
            return (
            <div className="vm-banner-warning">
              <span className="shrink-0">⚠</span>
              <span>{criticalDs?.name || 'Datastore-01'} is full ({pct}%). VMs on it are not responding and snapshots are blocked. Reboot a VM to recover it, or free space.</span>
              <div className="flex-1" />
              <button type="button" className="shrink-0 px-3 py-1 rounded-md border-none bg-[#F5A623] text-[#1B1B2F] text-[11.5px] font-bold cursor-pointer"
                onClick={() => runAction('expand_datastore', { datastore: criticalDs?.name, gb: 500 })}>
                Free space
              </button>
            </div>
            )
          })()}

          <div className="vm-breadcrumb">
            <span className="text-[#8fa5b8]">Home</span>
            <span className="text-[#4a5a6d] text-[9px]">›</span>
            <span className="text-[#8fa5b8]">{inv.datacenter || 'DC-Prod'}</span>
            <span className="text-[#4a5a6d] text-[9px]">›</span>
            <span className="text-white">{selectedVm?.name || selectedHost?.name || selectedDs?.name || selectedNet?.name || 'Inventory'}</span>
          </div>

          <div className="vm-object-bar">
            {selectedVm && <StatusIcon status={selectedVm.power} size={12} />}
            {selectedHost && <StatusIcon status={selectedHost.status} size={12} />}
            {selectedDs && <StatusIcon status={selectedDs.accessible ? 'connected' : 'disconnected'} size={12} />}
            <span className="text-[15px] font-bold text-white">
              {selectedVm?.name || selectedHost?.name || selectedDs?.name || selectedNet?.name || 'Select an object'}
            </span>
            {selectedVm && (
              <span className="vm-state-badge bg-[rgba(93,184,93,.12)] text-[#5DB85D]">
                <StatusIcon status={selectedVm.power} size={8} />
                {selectedVm.power}
              </span>
            )}
            {selectedHost && (
              <span className="text-[11px] text-[#8fa5b8]">{selectedHost.version} · Uptime {fmtUptime(selectedHost.uptime_seconds)}</span>
            )}
            {selectedVm && (
              <span className="text-[11px] text-[#8fa5b8]">{selectedVm.guest_os_version} · {selectedVm.ip}</span>
            )}
            <div className="flex-1 min-w-[8px]" />
            {(selectedVm || selectedHost) && (
              <div className="relative" ref={actionsRef}>
                <button type="button" onClick={() => setActionsMenuOpen(v => !v)} className="vm-actions-btn">
                  Actions <span className="text-[9px]">▼</span>
                </button>
                {actionsMenuOpen && selectedHost && (
                  <div className="vm-actions-menu">
                    <ActionsMenuItem label="Create VM…" onClick={() => { setShowCreateVmModal(true); setActionsMenuOpen(false) }} />
                    <ActionsMenuItem label={`${selectedHost.ssh_enabled ? 'Disable' : 'Enable'} SSH`} onClick={() => toast('SSH toggle simulated')} />
                    <ActionsMenuItem label="Reboot Host" onClick={() => toast('Host reboot simulated')} />
                    <ActionsMenuItem label="Enter Maintenance Mode" onClick={() => runAction('enter_maintenance', { host_name: selectedHost.name })} />
                    <div className="h-px bg-[#2D3A4A] my-1" />
                    <ActionsMenuItem label="Add Permission…" onClick={() => toast('Add permission simulated')} />
                  </div>
                )}
                {actionsMenuOpen && selectedVm && (
                  <div className="vm-actions-menu">
                    <ActionsMenuItem label="Power On" onClick={() => runAction('power_on', { vm_id: selectedVm.id })} disabled={selectedVm.power === 'poweredOn' || acting} />
                    <ActionsMenuItem label="Power Off" onClick={() => runAction('power_off', { vm_id: selectedVm.id })} disabled={selectedVm.power === 'poweredOff' || acting} />
                    <ActionsMenuItem label="Suspend" onClick={() => toast('Suspend simulated')} disabled={selectedVm.power !== 'poweredOn'} />
                    <ActionsMenuItem label="Reset" onClick={() => runAction('reboot', { vm_id: selectedVm.id })} disabled={selectedVm.power !== 'poweredOn' || acting} />
                    <div className="h-px bg-[#2D3A4A] my-1" />
                    <ActionsMenuItem label="Take Snapshot…" onClick={() => { setShowSnapshotModal(true); setActionsMenuOpen(false) }} />
                    <ActionsMenuItem label="Clone…" onClick={() => { setShowCloneVmModal(true); setActionsMenuOpen(false) }} />
                    <ActionsMenuItem label="Migrate…" onClick={() => { setShowMigrateModal(true); setActionsMenuOpen(false) }} />
                    <ActionsMenuItem label="Edit Settings…" onClick={() => { setShowEditVmModal(true); setActionsMenuOpen(false) }} />
                    <ActionsMenuItem label="Rename…" onClick={() => toast('Rename simulated — use Edit Settings')} />
                    <div className="h-px bg-[#2D3A4A] my-1" />
                    <ActionsMenuItem label="Open Console" onClick={() => { setConsoleVm(selectedVm); setActionsMenuOpen(false) }} />
                    <ActionsMenuItem label="Delete from Disk" color="#D9534F" onClick={() => { setPendingDeleteVm(selectedVm); setActionsMenuOpen(false) }} disabled={selectedVm.power === 'poweredOn'} />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* SSH / alarm banner */}
          {selectedHost?.ssh_enabled && (
            <div className="shrink-0 px-4 py-2 flex items-center gap-2 border-b border-[#2D3A4A] bg-[rgba(45,124,255,.08)]">
              <span className="text-[#5b9bf5] text-[11px]">ℹ SSH is enabled on this host. Disable SSH unless required for administration.</span>
              <button type="button" className="ml-auto vm-btn text-[10px] py-0.5 px-2">Actions</button>
            </div>
          )}
          {activeAlarms.length > 0 && selectedVm && activeAlarms.some(a => a.entity === selectedVm.name) && (
            <div className="shrink-0 px-4 py-2 flex items-center gap-2 border-b border-[rgba(217,83,79,.35)] bg-[rgba(217,83,79,.1)]">
              <span className="text-[#D9534F] text-[11px]">⚠ {activeAlarms.find(a => a.entity === selectedVm.name)?.name}</span>
              <button type="button" onClick={() => runAction('acknowledge_alarm', { alarm_id: activeAlarms.find(a => a.entity === selectedVm?.name)?.id })}
                className="ml-auto vm-btn vm-btn-red text-[10px] py-0.5 px-2">
                Acknowledge
              </button>
            </div>
          )}

          {/* Toolbar */}
          {selectedVm && renderVmToolbar(selectedVm)}
          {selectedHost && renderHostToolbar(selectedHost)}
          {selectedDs && (
            <div className="vm-toolbar-row">
              <ToolbarBtn onClick={() => { }} disabled label="Register VM" />
              <ToolbarBtn onClick={() => runAction('expand_datastore', { datastore: selectedDs.name, gb: 500 })} disabled={acting} label="Increase Capacity" />
              <div className="flex-1" />
              <RefreshBtn onClick={load} />
            </div>
          )}

          <div className="vm-tabs">
            {getTabs(selectedNode.type).map(t => (
              <button
                key={t}
                type="button"
                onClick={() => setActiveTab(t)}
                className={`vm-tab ${activeTab === t ? 'vm-tab-active' : ''}`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          <div className="flex flex-1 min-h-0 overflow-hidden">
            <div className="vm-content">

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
                        <span className="text-[#8FA5B8] text-[10px]">Storage</span>
                        <table className="vm-table mt-1">
                          <thead>
                            <tr>
                              {['Name', 'Type', 'Capacity', 'Free'].map(h => <th key={h} className={h === 'Capacity' || h === 'Free' ? 'text-right' : ''}>{h}</th>)}
                            </tr>
                          </thead>
                          <tbody>
                            {datastores.map(ds => (
                              <tr key={ds.id}>
                                <td className="text-[#5b9bf5]">{ds.name}</td>
                                <td>{ds.type}</td>
                                <td className="text-right">{fmtBytes(ds.capacity_gb)}</td>
                                <td className="text-right">{fmtBytes(ds.free_gb)}</td>
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

              {/* ── HOST PERMISSIONS ─────────────────────────────── */}
              {selectedHost && activeTab === 'permissions' && (
                <PermissionsPanel entityName={selectedHost.name} definedIn={selectedHost.name} />
              )}

              {/* ── HOST DATASTORES ──────────────────────────────── */}
              {selectedHost && activeTab === 'datastores' && (
                <ContentPanel title={`Datastores on ${selectedHost.name}`}>
                  <table className="vm-table">
                    <thead>
                      <tr>
                        {['Name', 'Type', 'Capacity', 'Free', 'Used %', 'Accessible'].map(h => (
                          <th key={h}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {datastores.filter(d => d.hosts?.includes(selectedHost.id)).map((ds) => {
                        const usedPct = (((ds.capacity_gb - ds.free_gb) / ds.capacity_gb) * 100).toFixed(0)
                        return (
                          <tr key={ds.id} className="cursor-pointer"
                            onClick={() => { setSelectedNode({ type: 'datastore', id: ds.id }); setActiveTab('summary') }}>
                            <td className="text-[#5b9bf5]">{ds.name}</td>
                            <td>{ds.type}</td>
                            <td>{fmtBytes(ds.capacity_gb)}</td>
                            <td className="font-medium" style={{ color: ds.free_gb < 50 ? '#D9534F' : '#5DB85D' }}>{fmtBytes(ds.free_gb)}</td>
                            <td>
                              <div className="flex items-center gap-1">
                                <div className="w-16"><UsageBar pct={Number(usedPct)} color={Number(usedPct) > 85 ? '#e0412b' : '#4c9be8'} /></div>
                                <span>{usedPct}%</span>
                              </div>
                            </td>
                            <td>
                              <span className={ds.accessible ? 'text-[#5DB85D] font-semibold' : 'text-[#D9534F]'}>{ds.accessible ? 'Yes' : 'No'}</span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </ContentPanel>
              )}

              {/* ── HOST NETWORKS ────────────────────────────────── */}
              {selectedHost && activeTab === 'networks' && (
                <ContentPanel title={`Networks on ${selectedHost.name}`}>
                  <table className="vm-table">
                    <thead>
                      <tr>
                        {['Name', 'Type', 'VLAN', 'vSwitch', 'VMs'].map(h => (
                          <th key={h}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {networks.filter(n => n.hosts?.includes(selectedHost.id)).map((net) => (
                        <tr key={net.id} className="cursor-pointer"
                          onClick={() => { setSelectedNode({ type: 'network', id: net.id }); setActiveTab('summary') }}>
                          <td className="text-[#5b9bf5]">{net.name}</td>
                          <td>{net.type}</td>
                          <td>{net.vlan === 0 ? 'All (0)' : net.vlan}</td>
                          <td className="text-[#8FA5B8]">{net.switch}</td>
                          <td>{vms.filter(v => v.network_id === net.id && v.host_id === selectedHost.id).length}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button type="button" onClick={() => toast('Add port group simulated')} className="mt-3 vm-btn vm-btn-blue text-[11px]">Add port group…</button>
                </ContentPanel>
              )}

              {/* ── VM SUMMARY ───────────────────────────────────── */}
              {selectedVm && activeTab === 'summary' && (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: 'Power On', action: 'power_on', show: selectedVm.power === 'poweredOff', green: true },
                      { label: 'Power Off', action: 'power_off', show: selectedVm.power === 'poweredOn', red: true },
                      { label: 'Reset', action: 'reboot', show: selectedVm.power === 'poweredOn' },
                      { label: 'Suspend', action: 'suspend', show: selectedVm.power === 'poweredOn' },
                      { label: 'Take Snapshot', action: '__snapshot__', show: true },
                      { label: 'Launch Console', action: '__console__', show: true, blue: true },
                    ].filter(a => a.show).map(a => (
                      <button
                        key={a.label}
                        type="button"
                        disabled={acting}
                        onClick={() => {
                          if (a.action === '__snapshot__') setShowSnapshotModal(true)
                          else if (a.action === '__console__') setConsoleVm(selectedVm)
                          else runAction(a.action, { vm_id: selectedVm.id })
                        }}
                        className={`vm-btn text-[11.5px] py-1.5 px-3 ${a.green ? 'vm-btn-green' : a.red ? 'vm-btn-red' : a.blue ? 'vm-btn-blue' : ''}`}
                      >
                        {a.label}
                      </button>
                    ))}
                  </div>
                  <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1fr] gap-4">
                    <ContentPanel title="Virtual machine details">
                      <InfoRow label="Guest OS" value={selectedVm.guest_os_version} />
                      <InfoRow label="Hostname" value={selectedVm.hostname} />
                      <InfoRow label="IP address" value={selectedVm.ip} />
                      <InfoRow label="VMware Tools" value={selectedVm.tools === 'ok' ? 'Running' : 'Not Running'} valueColor={selectedVm.tools === 'ok' ? '#5DB85D' : '#D9534F'} />
                      <InfoRow label="VM hardware" value={selectedVm.hardware_version} />
                      <InfoRow label="Annotation" value={selectedVm.annotation || '—'} />
                    </ContentPanel>
                    <div className="space-y-4">
                      <ContentPanel title="Resource usage">
                        {selectedVm.power === 'poweredOn' ? (
                          <div className="space-y-4">
                            {[
                              { label: 'CPU', pct: selectedVm.cpu_pct, text: `${selectedVm.cpu_pct}%`, color: '#2D7CFF' },
                              { label: 'Memory', pct: selectedVm.mem_pct, text: `${selectedVm.mem_pct}%`, color: '#9b59b6' },
                              { label: 'Disk I/O', pct: Math.min(selectedVm.disk_io_mbps * 2, 100), text: `${selectedVm.disk_io_mbps} MB/s`, color: '#F5A623' },
                            ].map(({ label, pct, text, color }) => (
                              <div key={label}>
                                <div className="flex justify-between text-xs mb-1.5"><span className="font-semibold text-[#E8EDF2]">{label}</span><span className="text-[#8FA5B8]">{text}</span></div>
                                <UsageBar pct={pct} color={color} />
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[#8FA5B8] text-xs">VM is powered off — no usage data.</p>
                        )}
                      </ContentPanel>
                      <div className="vm-panel p-3.5 text-center bg-gradient-to-br from-[#1B2A3B] to-[#243447]">
                        <p className="text-[10px] text-[#8FA5B8] uppercase tracking-widest mb-2.5">Console preview</p>
                        <div className="vm-console mb-3">
                          {selectedVm.power === 'poweredOn' ? (
                            <pre className="text-[8px] leading-snug text-[#5DB85D] p-2">{`root@${selectedVm.hostname || selectedVm.name}:~# uptime\n 14:22:01 up 14 days,  3:22,  1 user\nroot@${selectedVm.hostname || selectedVm.name}:~# _`}</pre>
                          ) : (
                            <span className="text-[#5a6a7d] text-xs">● Powered off</span>
                          )}
                        </div>
                        <button type="button" onClick={() => setConsoleVm(selectedVm)} className="vm-btn vm-btn-blue inline-flex">
                          Launch web console
                        </button>
                      </div>
                    </div>
                  </div>

                  <ContentPanel title="Recent tasks">
                    {recentTasks.filter(t => t.target === selectedVm.name).length === 0 ? (
                      <p className="text-[#8FA5B8] text-[11px]">No recent tasks for this VM</p>
                    ) : (
                      <table className="vm-table">
                        <thead>
                          <tr>
                            {['Task', 'Target', 'Status', 'Start', 'Duration'].map(h => <th key={h}>{h}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {recentTasks.filter(t => t.target === selectedVm.name).slice(0, 8).map((t, i) => (
                            <tr key={t.id || i}>
                              <td>{t.name}</td>
                              <td className="text-[#5b9bf5]">{t.target}</td>
                              <td><span className={t.status === 'success' ? 'text-[#5DB85D]' : 'text-[#D9534F]'}>{t.result}</span></td>
                              <td className="font-mono text-[#8fa5b8]">{fmtTime(t.started)}</td>
                              <td className="text-[#8fa5b8]">{t.completed && t.started ? `${Math.max(1, Math.round((new Date(t.completed) - new Date(t.started)) / 1000))}s` : '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </ContentPanel>
                </div>
              )}

              {/* ── VM MONITOR ───────────────────────────────────── */}
              {selectedVm && activeTab === 'monitor' && (
                <div className="space-y-3">
                  <div className="flex gap-1 border-b border-[#2D3A4A] mb-2">
                    {['performance', 'tasks', 'events', 'logs', 'notifications'].map(sub => (
                      <button key={sub} type="button" onClick={() => setMonSub(sub)}
                        className={`px-4 py-2 text-xs font-semibold border-b-2 capitalize ${monSub === sub ? 'border-[#2D7CFF] text-white' : 'border-transparent text-[#8FA5B8]'}`}>
                        {sub}
                      </button>
                    ))}
                  </div>
                  {(monSub === 'performance' || monSub === 'tasks' || monSub === 'events') && (
                  <div className="flex items-center gap-2 mb-2">
                    <button type="button" onClick={load} className="vm-btn text-[11px] py-1 px-3 text-[#00C8FF]">
                      ↻ Refresh
                    </button>
                  </div>
                  )}
                  {monSub === 'performance' && (
                  <>
                  <div className="flex gap-1.5 flex-wrap mb-2">
                    {['Real-time', '1H', '1D', '1W', '1M'].map(r => (
                      <button key={r} type="button" onClick={() => setMonRange(r)}
                        className={`px-3.5 py-1.5 rounded-md text-[11.5px] font-semibold border ${monRange === r ? 'border-[#2D7CFF] bg-[rgba(45,124,255,.12)] text-[#5b9bf5]' : 'border-[#2D3A4A] bg-[#243447] text-[#8FA5B8]'}`}>
                        {r}
                      </button>
                    ))}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <ContentPanel title="CPU usage">
                    {selectedVm.power !== 'poweredOn' ? (
                      <p className="text-[#8FA5B8] text-[11px]">VM is not powered on</p>
                    ) : (
                      <>
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm font-bold text-[#4c9be8]">{selectedVm.cpu_pct}%</span>
                        </div>
                        <PerfChart cpuPct={selectedVm.cpu_pct} memPct={0} />
                      </>
                    )}
                  </ContentPanel>
                  <ContentPanel title="Memory usage">
                    {selectedVm.power !== 'poweredOn' ? (
                      <p className="text-[#8FA5B8] text-[11px]">VM is not powered on</p>
                    ) : (
                      <>
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm font-bold text-[#9b59b6]">{selectedVm.mem_pct}%</span>
                        </div>
                        <PerfChart cpuPct={0} memPct={selectedVm.mem_pct} />
                      </>
                    )}
                  </ContentPanel>
                  </div>
                  <ContentPanel title="Summary metrics">
                    {selectedVm.power !== 'poweredOn' ? (
                      <p className="text-[#8FA5B8] text-[11px]">VM is not powered on — no performance data available</p>
                    ) : (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <MetricCard label="CPU" value={`${selectedVm.cpu_pct}%`} color="#4c9be8" />
                        <MetricCard label="Memory" value={`${selectedVm.mem_pct}%`} color="#9b59b6" />
                        <MetricCard label="Disk" value={`${selectedVm.disk_io_mbps} MB/s`} color="#e67e22" />
                        <MetricCard label="Network" value={`${selectedVm.net_mbps} Mbps`} color="#27ae60" />
                      </div>
                    )}
                  </ContentPanel>
                  </>
                  )}
                  {monSub === 'tasks' && (
                    <ContentPanel title="Tasks for this VM">
                      {recentTasks.filter(t => t.target === selectedVm.name).length === 0 ? (
                        <p className="text-[#8FA5B8] text-[11px]">No recent tasks for this VM</p>
                      ) : (
                        <table className="vm-table">
                          <thead>
                            <tr>
                              {['Task', 'Status', 'Started', 'Completed'].map(h => <th key={h}>{h}</th>)}
                            </tr>
                          </thead>
                          <tbody>
                            {recentTasks.filter(t => t.target === selectedVm.name).slice(0, 10).map((t, i) => (
                              <tr key={t.id || i}>
                                <td>{t.name}</td>
                                <td><span className={t.status === 'success' ? 'text-[#5DB85D]' : 'text-[#D9534F]'}>{t.result}</span></td>
                                <td className="font-mono text-[#8fa5b8]">{fmtTime(t.started)}</td>
                                <td className="font-mono text-[#8fa5b8]">{fmtTime(t.completed)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </ContentPanel>
                  )}
                  {monSub === 'events' && (
                    <ContentPanel title="Events for this VM">
                      {events.filter(ev => ev.entity === selectedVm.name).length === 0 ? (
                        <p className="text-[#8FA5B8] text-[11px]">No events for this VM</p>
                      ) : (
                        <table className="vm-table">
                          <thead>
                            <tr>
                              {['Time', 'Severity', 'Message'].map(h => <th key={h}>{h}</th>)}
                            </tr>
                          </thead>
                          <tbody>
                            {[...events].filter(ev => ev.entity === selectedVm.name).reverse().slice(0, 20).map((ev, i) => (
                              <tr key={i}>
                                <td className="font-mono whitespace-nowrap">{ev.time?.slice(11, 19)}</td>
                                <td>
                                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${ev.severity === 'critical' ? 'bg-[rgba(217,83,79,.2)] text-[#D9534F]' : ev.severity === 'warning' ? 'bg-[rgba(245,166,35,.2)] text-[#F5A623]' : 'bg-[rgba(93,184,93,.2)] text-[#5DB85D]'}`}>
                                    {ev.severity}
                                  </span>
                                </td>
                                <td>{ev.message}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </ContentPanel>
                  )}
                  {monSub === 'logs' && (
                    <div className="rounded-lg border border-[#2D3A4A] bg-[#05090f] p-4 font-mono text-[11.5px] leading-relaxed space-y-0.5">
                      {[
                        { t: `[${new Date().toISOString().slice(11, 19)}] vpxa: Connected to vCenter`, c: '#8FA5B8' },
                        { t: `[${new Date().toISOString().slice(11, 19)}] vmx: ${selectedVm.name}: Tools heartbeat OK`, c: '#5DB85D' },
                        { t: `[${new Date().toISOString().slice(11, 19)}] hostd: Guest OS reported IP ${selectedVm.ip || '10.20.30.41'}`, c: '#8FA5B8' },
                        { t: `[${new Date().toISOString().slice(11, 19)}] vmkernel: CPU scheduler: ${selectedVm.cpu_pct}% used`, c: '#8FA5B8' },
                        { t: `[${new Date().toISOString().slice(11, 19)}] vmsvc: Snapshot manager idle`, c: '#8FA5B8' },
                      ].map((l, i) => (
                        <div key={i} style={{ color: l.c }}>{l.t}</div>
                      ))}
                    </div>
                  )}
                  {monSub === 'notifications' && (
                    <ContentPanel title="Notifications">
                      {activeAlarms.filter(a => a.entity === selectedVm.name).length === 0 ? (
                        <p className="text-[#8FA5B8] text-[11px]">No active notifications</p>
                      ) : activeAlarms.filter(a => a.entity === selectedVm.name).map(a => (
                        <div key={a.id} className="flex items-center gap-3 py-2.5 border-b border-[#22303f] last:border-0">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${a.severity === 'critical' ? 'bg-[rgba(217,83,79,.2)] text-[#D9534F]' : 'bg-[rgba(245,166,35,.2)] text-[#F5A623]'}`}>{a.severity}</span>
                          <div className="flex-1">
                            <p className="text-xs font-semibold text-[#E8EDF2] m-0">{a.name}</p>
                            <p className="text-[11px] text-[#8FA5B8] m-0 mt-0.5">{a.entity}</p>
                          </div>
                          <button type="button" onClick={() => runAction('acknowledge_alarm', { alarm_id: a.id })} className="vm-btn text-[10px] py-0.5 px-2">Ack</button>
                        </div>
                      ))}
                    </ContentPanel>
                  )}
                </div>
              )}

              {/* ── VM CONFIGURE ─────────────────────────────────── */}
              {selectedVm && activeTab === 'configure' && (
                <VmConfigurePanel
                  vm={selectedVm}
                  networks={networks}
                  acting={acting}
                  onSave={(payload) => runAction('edit_vm', payload)}
                  onAddDisk={() => runAction('add_disk', { vm_id: selectedVm.id, size_gb: 100 })}
                  onEditNetwork={() => setShowEditVmModal(true)}
                />
              )}

              {/* ── VM SNAPSHOTS ─────────────────────────────────── */}
              {selectedVm && activeTab === 'snapshots' && (
                <div className="vm-panel">
                  <div className="vm-panel-header flex items-center justify-between">
                    <span>Snapshot manager</span>
                    <button type="button" onClick={() => setShowSnapshotModal(true)} disabled={acting} className="vm-btn vm-btn-blue text-[11px] py-1 px-3">
                      Take snapshot
                    </button>
                  </div>
                  <div className="vm-panel-body px-3.5">
                    {(selectedVm.snapshots?.length === 0 || !selectedVm.snapshots) ? (
                      <p className="text-[#8FA5B8] text-xs text-center py-5">No snapshots yet.</p>
                    ) : selectedVm.snapshots.map(snap => (
                      <div key={snap.id} className="flex items-center gap-3 py-3 border-b border-[#22303f] last:border-0">
                        <span className="w-8 h-8 rounded-md flex items-center justify-center bg-[rgba(45,124,255,.12)] text-[#2D7CFF] text-sm">📷</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-[12.5px] font-semibold text-[#E8EDF2] m-0">{snap.name}</p>
                          <p className="text-[11px] text-[#8FA5B8] m-0 mt-0.5">{snap.description || 'No description'} · {fmtTime(snap.created)}</p>
                        </div>
                        <button type="button" onClick={() => runAction('revert_snapshot', { vm_id: selectedVm.id, snapshot_id: snap.id })} disabled={acting}
                          className="vm-btn text-[11px] py-1 px-2.5">Revert</button>
                        <button type="button" onClick={() => runAction('delete_snapshot', { vm_id: selectedVm.id, snapshot_id: snap.id })} disabled={acting}
                          className="vm-btn vm-btn-red text-[11px] py-1 px-2.5">Delete</button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ── VM PERMISSIONS / NETWORKS / UPDATES ──────────── */}
              {selectedVm && activeTab === 'permissions' && (
                <PermissionsPanel entityName={selectedVm.name} definedIn={selectedVm.name} />
              )}
              {selectedVm && activeTab === 'networks' && (
                <ContentPanel title={`Network adapters — ${selectedVm.name}`}>
                  <table className="vm-table">
                    <thead>
                      <tr>
                        {['Adapter', 'Network', 'MAC', 'Status', 'Type'].map(h => <th key={h}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Network adapter 1</td>
                        <td className="text-[#5b9bf5]">{networks.find(n => n.id === selectedVm.network_id)?.name || 'VM Network'}</td>
                        <td className="font-mono text-[#8FA5B8]">{selectedVm.mac || '00:50:56:aa:bb:cc'}</td>
                        <td className="text-[#5DB85D] font-semibold">Connected</td>
                        <td className="text-[#8FA5B8]">VMXNET3</td>
                      </tr>
                    </tbody>
                  </table>
                  <button type="button" onClick={() => setShowEditVmModal(true)} className="mt-3 vm-btn vm-btn-blue text-[11px]">Add network adapter…</button>
                </ContentPanel>
              )}
              {selectedVm && activeTab === 'updates' && (
                <div className="space-y-3">
                  <div className="vm-panel p-4 flex items-center gap-3.5">
                    <span className="w-11 h-11 rounded-[11px] flex items-center justify-center bg-[rgba(93,184,93,.12)] text-[#5DB85D] text-lg">✓</span>
                    <div className="flex-1">
                      <p className="text-sm font-bold text-white m-0">VMware Tools is up to date</p>
                      <p className="text-xs text-[#8FA5B8] m-0 mt-1">{selectedVm.name} · Guest OS: {selectedVm.guest_os_version || selectedVm.guest_os}</p>
                    </div>
                    <button type="button" onClick={() => setVmToast({ message: 'VMware Tools current', kind: 'success' })} className="vm-btn vm-btn-blue text-xs py-2 px-4">
                      Check for updates
                    </button>
                  </div>
                  <ContentPanel title="Installed components">
                    <table className="vm-table">
                      <thead><tr>{['Component', 'Version', 'Status'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                      <tbody>
                        <tr><td>VMware Tools</td><td className="font-mono text-[#8FA5B8]">12.3.5</td><td className="text-[#5DB85D] font-semibold">Current</td></tr>
                        <tr><td>Guest OS patches</td><td className="font-mono text-[#8FA5B8]">Latest</td><td className="text-[#5DB85D] font-semibold">Current</td></tr>
                      </tbody>
                    </table>
                  </ContentPanel>
                </div>
              )}

              {/* ── HOST VMs / USERS ─────────────────────────────── */}
              {selectedHost && activeTab === 'vms' && (
                <ContentPanel title={`Virtual machines on ${selectedHost.name}`}>
                  <VmTable vms={vms.filter(v => v.host_id === selectedHost.id)}
                    onSelect={vm => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary') }}
                    onAction={runAction} acting={acting} />
                </ContentPanel>
              )}
              {selectedHost && activeTab === 'users' && (
                <ContentPanel title={`Local users — ${selectedHost.name}`}>
                  <div className="flex justify-end mb-2">
                    <button type="button" onClick={() => toast('Add user simulated')} className="vm-btn vm-btn-blue text-[11px]">Add user…</button>
                  </div>
                  <table className="vm-table">
                    <thead><tr>{['Username', 'Role', 'Status', 'Last login'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                    <tbody>
                      {[
                        { user: 'root', role: 'Administrator', status: 'Enabled', login: 'Today 09:14' },
                        { user: 'dcui', role: 'Administrator', status: 'Enabled', login: 'Yesterday' },
                        { user: 'vpxuser', role: 'System', status: 'Enabled', login: 'Today 08:02' },
                      ].map(r => (
                        <tr key={r.user}>
                          <td className="text-[#5b9bf5]">{r.user}</td>
                          <td>{r.role}</td>
                          <td className="text-[#5DB85D] font-semibold">{r.status}</td>
                          <td className="text-[#8FA5B8]">{r.login}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </ContentPanel>
              )}

              {/* ── HOST UPDATES ─────────────────────────────────── */}
              {selectedHost && activeTab === 'updates' && (
                <div className="space-y-3">
                  <div className="vm-panel p-4 flex items-center gap-3.5">
                    <span className="w-11 h-11 rounded-[11px] flex items-center justify-center bg-[rgba(93,184,93,.12)] text-[#5DB85D]">✓</span>
                    <div className="flex-1">
                      <p className="text-sm font-bold text-white m-0">{selectedHost.name} is up to date</p>
                      <p className="text-xs text-[#8FA5B8] m-0 mt-1">ESXi {selectedHost.version} · Last checked just now</p>
                    </div>
                    <button type="button" onClick={() => setVmToast({ message: 'No updates available', kind: 'success' })} className="vm-btn vm-btn-blue text-xs py-2 px-4">
                      Check for updates
                    </button>
                  </div>
                  <ContentPanel title="Installed components">
                    <table className="vm-table">
                      <thead>
                        <tr>
                          {['Component', 'Version', 'Vendor', 'Status'].map(h => <th key={h}>{h}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          { comp: 'VMware ESXi', ver: selectedHost.version, vendor: 'VMware', status: 'Current', color: '#5DB85D' },
                          { comp: 'VMware Tools', ver: '12.3.5', vendor: 'VMware', status: 'Current', color: '#5DB85D' },
                          { comp: 'vCenter Agent', ver: '8.0.2', vendor: 'VMware', status: 'Current', color: '#5DB85D' },
                          { comp: 'NIC Driver', ver: '1.9.4', vendor: 'Intel', status: 'Current', color: '#5DB85D' },
                        ].map(row => (
                          <tr key={row.comp}>
                            <td>{row.comp}</td>
                            <td className="font-mono text-[#8FA5B8]">{row.ver}</td>
                            <td className="text-[#8FA5B8]">{row.vendor}</td>
                            <td style={{ color: row.color, fontWeight: 600 }}>{row.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ContentPanel>
                </div>
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

              {/* ── DATASTORE MONITOR ────────────────────────────── */}
              {selectedDs && activeTab === 'permissions' && (
                <PermissionsPanel entityName={selectedDs.name} definedIn={selectedDs.name} />
              )}

              {selectedDs && activeTab === 'monitor' && (
                <div className="space-y-3">
                  <ContentPanel title="Space utilization">
                    <div className="mb-2">
                      <div className="flex justify-between text-[11px] mb-1">
                        <span>Used: {fmtBytes(selectedDs.capacity_gb - selectedDs.free_gb)}</span>
                        <span>Free: {fmtBytes(selectedDs.free_gb)}</span>
                        <span>Capacity: {fmtBytes(selectedDs.capacity_gb)}</span>
                      </div>
                      <UsageBar pct={((selectedDs.capacity_gb - selectedDs.free_gb) / selectedDs.capacity_gb) * 100}
                        color={selectedDs.free_gb < 50 ? '#e0412b' : '#4c9be8'} />
                    </div>
                  </ContentPanel>
                  <ContentPanel title="I/O Performance (last hour)">
                    <div className="grid grid-cols-3 gap-4">
                      <MetricCard label="Read Throughput" value="48 MB/s" color="#4c9be8" />
                      <MetricCard label="Write Throughput" value="32 MB/s" color="#e67e22" />
                      <MetricCard label="I/O Latency" value="4.2 ms" color="#9b59b6" />
                    </div>
                  </ContentPanel>
                </div>
              )}

              {/* ── DATASTORE HOSTS ───────────────────────────────── */}
              {selectedDs && activeTab === 'hosts' && (
                <ContentPanel title={`Hosts connected to ${selectedDs.name}`}>
                  <table className="vm-table">
                    <thead>
                      <tr>
                        {['', 'Host', 'Status', 'Version'].map(h => <th key={h}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {hosts.filter(h => selectedDs.hosts?.includes(h.id)).map((h) => (
                        <tr key={h.id} className="cursor-pointer"
                          onClick={() => { setSelectedNode({ type: 'host', id: h.id }); setActiveTab('summary') }}>
                          <td><StatusIcon status={h.status} /></td>
                          <td className="text-[#5b9bf5]">{h.name}</td>
                          <td>{h.status}</td>
                          <td className="text-[#8FA5B8]">{h.version}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </ContentPanel>
              )}

              {/* ── DATASTORE VMS ─────────────────────────────────── */}
              {selectedDs && activeTab === 'vms' && (
                <ContentPanel title={`VMs on ${selectedDs.name}`}>
                  <VmTable vms={vms.filter(v => v.datastore_id === selectedDs.id)}
                    onSelect={vm => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary') }}
                    onAction={runAction} acting={acting} />
                </ContentPanel>
              )}

              {/* ── NETWORK ──────────────────────────────────────── */}
              {selectedNet && activeTab === 'permissions' && (
                <PermissionsPanel entityName={selectedNet.name} definedIn={selectedNet.name} />
              )}

              {selectedNet && activeTab === 'summary' && (
                <ContentPanel title="Network details">
                  <InfoRow label="Type" value={selectedNet.type} />
                  <InfoRow label="VLAN ID" value={selectedNet.vlan === 0 ? 'All (0)' : String(selectedNet.vlan)} />
                  <InfoRow label="vSwitch" value={selectedNet.switch} />
                  <InfoRow label="Connected hosts" value={selectedNet.hosts?.length || 0} />
                </ContentPanel>
              )}

              {/* ── NETWORK HOSTS ─────────────────────────────────── */}
              {selectedNet && activeTab === 'hosts' && (
                <ContentPanel title={`Hosts using ${selectedNet.name}`}>
                  <table className="vm-table">
                    <thead>
                      <tr>
                        {['', 'Host', 'Status'].map(h => <th key={h}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {hosts.filter(h => selectedNet.hosts?.includes(h.id)).map((h) => (
                        <tr key={h.id} className="cursor-pointer"
                          onClick={() => { setSelectedNode({ type: 'host', id: h.id }); setActiveTab('summary') }}>
                          <td><StatusIcon status={h.status} /></td>
                          <td className="text-[#5b9bf5]">{h.name}</td>
                          <td>{h.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </ContentPanel>
              )}

              {/* ── NETWORK VMS ───────────────────────────────────── */}
              {selectedNet && activeTab === 'vms' && (
                <ContentPanel title={`VMs on ${selectedNet.name}`}>
                  <VmTable vms={vms.filter(v => v.network_id === selectedNet.id)}
                    onSelect={vm => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary') }}
                    onAction={runAction} acting={acting} />
                </ContentPanel>
              )}

              {/* ── EVENTS TAB ───────────────────────────────────── */}
              {activeTab === 'events' && (
                <ContentPanel title="Events">
                  {events.length === 0 ? <p className="text-[#8FA5B8] text-xs">No events</p> : (
                    <table className="vm-table">
                      <thead>
                        <tr>
                          {['Time', 'Severity', 'Entity', 'Message'].map(h => <th key={h}>{h}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {[...events].reverse().map((ev, i) => (
                          <tr key={i} className="cursor-pointer">
                            <td className="font-mono whitespace-nowrap text-[#8FA5B8]">{ev.time?.slice(11, 19)}</td>
                            <td>
                              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${ev.severity === 'critical' ? 'bg-[rgba(217,83,79,.2)] text-[#D9534F]' : ev.severity === 'warning' ? 'bg-[rgba(245,166,35,.2)] text-[#F5A623]' : 'bg-[rgba(93,184,93,.2)] text-[#5DB85D]'}`}>
                                {ev.severity.toUpperCase()}
                              </span>
                            </td>
                            <td className="text-[#5b9bf5]">{ev.entity}</td>
                            <td>{ev.message}</td>
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
              <aside className="vm-resource-aside">
                <p className="text-[10px] font-bold text-[#8fa5b8] uppercase tracking-wider mb-2">Resources</p>
                {[
                  { label: 'CPU', free: selectedHost ? `${100 - selectedHost.cpu_pct}%` : `${100 - (selectedVm?.cpu_pct || 0)}%`, used: `${selectedHost?.cpu_pct || selectedVm?.cpu_pct || 0}%`, color: '#4c9be8', pct: selectedHost?.cpu_pct || selectedVm?.cpu_pct || 0 },
                  { label: 'Memory', free: selectedHost ? `${(selectedHost.memory_gb * (1 - selectedHost.mem_pct / 100)).toFixed(1)} GB free` : `${(selectedVm?.memory_mb * (1 - (selectedVm?.mem_pct || 0) / 100) / 1024).toFixed(1)} GB`, used: selectedHost ? `${(selectedHost.memory_gb * selectedHost.mem_pct / 100).toFixed(1)} GB` : `${(selectedVm?.memory_mb / 1024).toFixed(1)} GB`, color: '#9b59b6', pct: selectedHost?.mem_pct || selectedVm?.mem_pct || 0 },
                  { label: 'Storage', free: selectedHost ? `${fmtBytes(datastores.filter(d => d.hosts?.includes(selectedHost.id)).reduce((s, d) => s + d.free_gb, 0))} free` : fmtBytes(datastores.find(d => d.id === selectedVm?.datastore_id)?.free_gb || 0), used: `${selectedHost?.storage_pct || 0}%`, color: '#e67e22', pct: selectedHost?.storage_pct || 0 },
                  { label: 'Network', free: `${100 - Math.min(selectedHost?.network_mbps || 0, 100)}%`, used: `${selectedHost?.network_mbps || selectedVm?.net_mbps || 0} Mbps`, color: '#27ae60', pct: Math.min(selectedHost?.network_mbps || 0, 100) },
                ].map(({ label, free, used, color, pct }) => (
                  <div key={label} className="vm-resource-card">
                    <p className="text-[10px] font-semibold text-[#e8edf2] mb-1">{label}</p>
                    <div className="flex justify-between text-[9px] text-[#8fa5b8] mb-0.5">
                      <span>FREE: {free}</span>
                    </div>
                    <div className="flex justify-between text-[9px] text-[#8fa5b8] mb-1">
                      <span>USED: {used}</span>
                    </div>
                    <UsageBar pct={pct} color={color} />
                  </div>
                ))}
              </aside>
            )}
          </div>

          {/* ── Recent tasks bottom panel ─────────────────────────── */}
          <div className={`vm-tasks-panel ${tasksOpen ? '' : 'vm-tasks-collapsed'}`}>
            <button type="button" className="vm-tasks-header w-full text-left flex items-center" onClick={() => setTasksOpen(o => !o)}>
              <span>{tasksOpen ? '▼' : '▲'}</span>
              <span className="ml-2">Recent Tasks</span>
              <span className="text-[#8fa5b8] ml-2">({recentTasks.length})</span>
            </button>
            {tasksOpen && (
            <div className="overflow-x-auto vm-tasks-body">
              <table className="vm-table">
                <thead>
                  <tr>
                    {['Task Name', 'Target', 'Initiator', 'Queued', 'Started', 'Result', 'Completed'].map(h => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recentTasks.slice(0, 15).map((t, i) => (
                    <tr key={t.id || i}>
                      <td className="whitespace-nowrap">{t.name}</td>
                      <td className="text-[#5b9bf5]">{t.target}</td>
                      <td>{t.initiator}</td>
                      <td className="font-mono text-[#8fa5b8]">{fmtTime(t.queued)}</td>
                      <td className="font-mono text-[#8fa5b8]">{fmtTime(t.started)}</td>
                      <td>
                        <span className={t.status === 'success' ? 'text-[#5DB85D]' : 'text-[#D9534F]'}>
                          {t.status === 'success' ? '✓' : '✗'} {t.result}
                        </span>
                      </td>
                      <td className="font-mono text-[#8fa5b8]">{fmtTime(t.completed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
          </div>
        </main>
      </div>

      {/* Console + context menu */}
      {consoleVm && (
        <VmwareConsole vm={consoleVm} onClose={() => setConsoleVm(null)} />
      )}
      {ctxMenu && (
        <VmwareContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          vm={ctxMenu.vm}
          onClose={() => setCtxMenu(null)}
          onAction={handleCtxAction}
          onConsole={setConsoleVm}
          acting={acting}
        />
      )}

      {vmToast && (
        <VmwareToast
          message={vmToast.message}
          kind={vmToast.kind}
          onDone={() => setVmToast(null)}
        />
      )}

      {/* Modals */}
      {showSnapshotModal && selectedVm && (
        <SnapshotModal vm={selectedVm} onClose={() => setShowSnapshotModal(false)} onAction={runAction} />
      )}
      {showMigrateModal && selectedVm && (
        <MigrateModal vm={selectedVm} hosts={hosts} onClose={() => setShowMigrateModal(false)} onAction={runAction} />
      )}
      {showCreateVmModal && (
        <CreateVmModal hosts={hosts} datastores={datastores} networks={networks}
          onClose={() => setShowCreateVmModal(false)} onAction={runAction} />
      )}
      {showEditVmModal && selectedVm && (
        <EditVmModal vm={selectedVm} networks={networks}
          onClose={() => setShowEditVmModal(false)} onAction={runAction} />
      )}
      {showCloneVmModal && selectedVm && (
        <CloneVmModal vm={selectedVm} onClose={() => setShowCloneVmModal(false)} onAction={runAction} />
      )}
      {pendingDeleteVm && (
        <div className="vm-modal-overlay">
          <div className="vm-modal w-80">
            <div className="vm-modal-header bg-[rgba(217,83,79,.2)]">
              Confirm Delete
            </div>
            <div className="vm-modal-body">
              <p className="text-sm text-[#e8edf2] mb-1">Delete VM <strong>{pendingDeleteVm.name}</strong>?</p>
              <p className="text-xs text-[#8fa5b8]">This removes the VM from inventory. Disk files will be released.</p>
            </div>
            <div className="vm-modal-footer">
              <button type="button" onClick={() => setPendingDeleteVm(null)} className="vm-btn">Cancel</button>
              <button type="button" onClick={async () => {
                await runAction('delete_vm', { vm_id: pendingDeleteVm.id })
                setPendingDeleteVm(null)
                setSelectedNode({ type: 'host', id: hosts[0]?.id || null })
                setActiveTab('summary')
              }} className="vm-btn vm-btn-red">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ─── Sub-components ─────────────────────────────────────────────────── */
function getTabs(type) {
  if (type === 'vm') return ['summary', 'monitor', 'snapshots', 'configure', 'permissions', 'networks', 'updates', 'events']
  if (type === 'host') return ['summary', 'monitor', 'configure', 'permissions', 'datastores', 'networks', 'vms', 'users', 'updates', 'events']
  if (type === 'datastore') return ['summary', 'monitor', 'permissions', 'hosts', 'vms']
  if (type === 'network') return ['summary', 'permissions', 'hosts', 'vms']
  return ['summary']
}

function NavSection({ label, expanded, onToggle, children }) {
  return (
    <div>
      <button type="button" onClick={onToggle} className="w-full flex items-center gap-1 px-3 py-1.5 text-[10px] font-bold text-[#8fa5b8] uppercase tracking-wider hover:bg-white/[0.05]">
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
        role="button"
        tabIndex={0}
        onClick={() => { onClick(); if (children) setOpen(v => !v) }}
        onKeyDown={e => { if (e.key === 'Enter') { onClick(); if (children) setOpen(v => !v) } }}
        className={`vm-nav-item ${active ? 'vm-nav-item-active' : ''}`}
        style={{ paddingLeft: 10 }}
      >
        <span className="shrink-0">{icon}</span>
        <StatusIcon status={status} size={8} />
        <span className="truncate flex-1">{label}</span>
        {badge && <span className="text-[8px] bg-[#F5A623] text-[#1B2A3B] rounded px-1 font-bold">{badge}</span>}
        {children && <span className="text-[8px] text-[#6880a0]">{open ? '▾' : '▸'}</span>}
      </div>
      {open && children && <div className="pl-4">{children}</div>}
    </div>
  )
}

function NavSubItem({ label, onClick }) {
  return (
    <div role="button" tabIndex={0} onClick={onClick} onKeyDown={e => e.key === 'Enter' && onClick()}
      className="px-3 py-1 text-[10px] text-[#8fa5b8] cursor-pointer hover:bg-white/[0.05] hover:text-white">
      {label}
    </div>
  )
}

function ContentPanel({ title, children }) {
  return (
    <div className="vm-panel mb-4">
      <div className="vm-panel-header">{title}</div>
      <div className="vm-panel-body">{children}</div>
    </div>
  )
}

function InfoRow({ label, value, valueColor }) {
  return (
    <div className="vm-info-row">
      <span className="vm-info-label">{label}</span>
      <span className="vm-info-value" style={valueColor ? { color: valueColor } : undefined}>{value}</span>
    </div>
  )
}

function MetricCard({ label, value, color }) {
  return (
    <div className="border border-[#2D3A4A] rounded-lg p-2.5 text-center bg-[#1B2A3B]">
      <p className="text-[10px] text-[#8FA5B8] uppercase tracking-wide">{label}</p>
      <p className="text-base font-bold mt-0.5" style={{ color }}>{value}</p>
    </div>
  )
}

function VmTable({ vms, onSelect, onAction, acting }) {
  return (
    <table className="vm-table">
      <thead>
        <tr>
          {['', 'Name', 'Power', 'Guest OS', 'IP', 'CPU', 'Memory', ''].map((h, i) => (
            <th key={i}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {vms.map((vm) => (
          <tr key={vm.id} onClick={() => onSelect(vm)}>
            <td><StatusIcon status={vm.power} /></td>
            <td className="text-[#5b9bf5]">{vm.name}</td>
            <td>{vm.power}</td>
            <td className="text-[#8fa5b8]">{vm.guest_os_version || vm.guest_os}</td>
            <td className="text-[#8fa5b8]">{vm.ip}</td>
            <td>{vm.cpu_pct}%</td>
            <td>{vm.mem_pct}%</td>
            <td className="whitespace-nowrap">
              {vm.power === 'poweredOff' ? (
                <button type="button" onClick={e => { e.stopPropagation(); onAction('power_on', { vm_id: vm.id }) }} disabled={acting}
                  className="vm-btn vm-btn-green text-[10px] py-0.5 px-2">Power On</button>
              ) : (
                <button type="button" onClick={e => { e.stopPropagation(); onAction('power_off', { vm_id: vm.id }) }} disabled={acting}
                  className="vm-btn text-[10px] py-0.5 px-2">Power Off</button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ToolbarBtn({ onClick, disabled, label, blue, red }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={`vm-btn ${blue ? 'vm-btn-blue' : red ? 'vm-btn-red' : ''}`}>
      {label}
    </button>
  )
}

function ToolbarSep() {
  return <span className="w-px h-4 bg-[#2d3a4a] mx-1" />
}

function RefreshBtn({ onClick }) {
  return (
    <button type="button" onClick={onClick} title="Refresh" className="vm-btn">↻</button>
  )
}

function PermissionsPanel({ entityName, definedIn }) {
  const rows = [
    { user: 'VSPHERE.LOCAL\\Administrator', role: 'Administrator', prop: 'Yes', defined: 'Root' },
    { user: 'VSPHERE.LOCAL\\SSOAdminServer', role: 'Administrator', prop: 'Yes', defined: 'Root' },
    { user: 'root', role: 'Administrator', prop: 'No', defined: definedIn || entityName },
  ]
  return (
    <ContentPanel title={`Roles & Permissions — ${entityName}`}>
      <div className="flex justify-end mb-2">
        <button type="button" onClick={() => toast('Add permission simulated')} className="vm-btn vm-btn-blue text-[11px]">Add permission…</button>
      </div>
      <table className="vm-table">
        <thead>
          <tr>
            {['User / Group', 'Role', 'Propagate', 'Defined In'].map(h => <th key={h}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.user}>
              <td className="text-[#5b9bf5]">{r.user}</td>
              <td>{r.role}</td>
              <td>{r.prop}</td>
              <td className="text-[#8FA5B8]">{r.defined}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ContentPanel>
  )
}

function ActionsMenuItem({ label, onClick, disabled, color }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="w-full text-left px-3 py-2 hover:bg-[#2d4057] disabled:opacity-40 disabled:cursor-not-allowed text-[12px] rounded"
      style={{ color: color || '#e8edf2' }}
    >
      {label}
    </button>
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
