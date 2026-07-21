import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { vmwareApi } from '../../api/vmware'
import { labApi } from '../../api/labs'
import { registerLabChildTab, subscribeLabSync, broadcastLabActivity } from '../../utils/labSync'
import toast from 'react-hot-toast'
import VmwareLoginGate, { isVcenterAuthenticated } from '../../components/vmware/VmwareLoginGate'
import VmwareScenarioActions from '../../components/vmware/VmwareScenarioActions'
import VmwareLabChrome from '../../components/vmware/VmwareLabChrome'
import VmotionWizard from '../../components/vmware/wizards/VmotionWizard'
import StorageVmotionWizard from '../../components/vmware/wizards/StorageVmotionWizard'
import VmwareOvfDeployModal from '../../components/vmware/VmwareOvfDeployModal'
import VmwareDvsEditor from '../../components/vmware/VmwareDvsEditor'
import VmwareVsanDashboard from '../../components/vmware/VmwareVsanDashboard'
import VmwarePermissionsPanel from '../../components/vmware/VmwarePermissionsPanel'
import VmwareLifecyclePanel from '../../components/vmware/VmwareLifecyclePanel'
import NsxMicroSegmentationPanel from '../../components/vmware/NsxMicroSegmentationPanel'
import SrmDisasterRecoveryPanel from '../../components/vmware/SrmDisasterRecoveryPanel'
import VamiAppliancePanel from '../../components/vmware/VamiAppliancePanel'
import VmwareAlarmDefinitionsPanel from '../../components/vmware/VmwareAlarmDefinitionsPanel'
import VmwareUsersRolesPanel from '../../components/vmware/VmwareUsersRolesPanel'
import VmCreateWizard from '../../components/vmware/wizards/VmCreateWizard'
import VmwareInventoryTree from '../../components/vmware/VmwareInventoryTree'
import VmwareConsole from '../../components/vmware/VmwareConsole'
import VmwareContextMenu from '../../components/vmware/VmwareContextMenu'
import VmwareActionsMenu from '../../components/vmware/VmwareActionsMenu'
import VmwareHostConfigurePanel from '../../components/vmware/VmwareHostConfigurePanel'
import VmwareAdministration from '../../components/vmware/VmwareAdministration'
import VmwareDatacenterDatastores from '../../components/vmware/VmwareDatacenterDatastores'
import {
  AddDiskModal,
  AddNicModal,
  CreateVswitchModal,
  CreatePortGroupModal,
  CreateDatastoreModal,
  CreateClusterModal,
  AddHostModal,
  CreateResourcePoolModal,
  CreateVappModal,
  CreateDatastoreClusterModal,
  CreateFolderModal,
} from '../../components/vmware/VmwareResourceModals'
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
function PerfChart({ cpuPct = 30, memPct = 50, perfHistory = null }) {
  const W = 560, H = 120
  const cpuPts = useMemo(() => {
    if (perfHistory?.cpu?.length >= 2) return perfHistory.cpu
    return Array.from({ length: 20 }, (_, i) => cpuPct + Math.sin(i * 0.6) * 10 + (((i * 17 + cpuPct * 3) % 17) - 8) * 0.5)
  }, [cpuPct, perfHistory?.cpu])
  const memPts = useMemo(() => {
    if (perfHistory?.mem?.length >= 2) return perfHistory.mem
    return Array.from({ length: 20 }, (_, i) => memPct + Math.sin(i * 0.4) * 8 + (((i * 13 + memPct * 5) % 13) - 6) * 0.5)
  }, [memPct, perfHistory?.mem])
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

function SnapshotManagerModal({ vm, onClose, onAction, acting }) {
  const snapshots = vm?.snapshots || []
  const [selectedId, setSelectedId] = useState(snapshots[snapshots.length - 1]?.id || '')
  const [busy, setBusy] = useState(false)
  // vSphere-style sequential default name; the learner can rename before saving.
  const [snapName, setSnapName] = useState(`Snapshot ${snapshots.length + 1}`)
  const selected = snapshots.find((s) => s.id === selectedId) || snapshots[snapshots.length - 1] || null

  useEffect(() => {
    if (!selectedId && snapshots.length) setSelectedId(snapshots[snapshots.length - 1].id)
    if (selectedId && !snapshots.some((s) => s.id === selectedId)) setSelectedId(snapshots[snapshots.length - 1]?.id || '')
  }, [selectedId, snapshots])

  // Keep the suggested snapshot name in step with the tree size so back-to-back
  // snapshots default to "Snapshot 1", "Snapshot 2", … instead of colliding.
  useEffect(() => {
    setSnapName(`Snapshot ${snapshots.length + 1}`)
  }, [snapshots.length])

  const fire = async (action, payload = {}) => {
    setBusy(true)
    try {
      await onAction(action, { vm_id: vm.id, ...payload })
    } finally {
      setBusy(false)
    }
  }

  const disabled = acting || busy

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[760px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>Snapshot Manager — {vm.name}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_260px] gap-4">
            <div className="rounded-lg border border-[#2D3A4A] bg-[#101820] p-4 min-h-[300px] overflow-auto">
              <div className="text-[11px] text-[#8FA5B8] uppercase tracking-wider mb-4">Snapshot tree</div>
              <div className="relative pl-5">
                <div className="absolute left-[29px] top-4 bottom-4 w-px bg-[#2D3A4A]" />
                <button
                  type="button"
                  className="relative flex items-center gap-3 w-full text-left rounded-md px-2 py-2 mb-1 bg-[#1B2A3B] border border-[#2D3A4A]"
                  onClick={() => setSelectedId('')}
                >
                  <span className="relative z-10 w-8 h-8 rounded-full bg-[#2D7CFF] text-white flex items-center justify-center text-xs">VM</span>
                  <div>
                    <div className="text-sm font-semibold text-[#E8EDF2]">Current state</div>
                    <div className="text-[11px] text-[#8FA5B8]">{vm.power} · {vm.guest_os_version || 'Guest OS unknown'}</div>
                  </div>
                </button>
                {snapshots.length === 0 ? (
                  <div className="ml-12 mt-8 text-xs text-[#8FA5B8]">No snapshots exist for this virtual machine.</div>
                ) : snapshots.map((snap, index) => (
                  <button
                    key={snap.id}
                    type="button"
                    className={`relative flex items-center gap-3 w-full text-left rounded-md px-2 py-2 ml-8 mb-1 border ${
                      selected?.id === snap.id ? 'bg-[rgba(45,124,255,.18)] border-[#2D7CFF]' : 'bg-[#131f2b] border-[#22303f] hover:border-[#2D3A4A]'
                    }`}
                    onClick={() => setSelectedId(snap.id)}
                  >
                    <span className="absolute -left-8 top-1/2 w-8 h-px bg-[#2D3A4A]" />
                    <span className="relative z-10 w-8 h-8 rounded-full bg-[#243447] text-[#5b9bf5] flex items-center justify-center text-xs">S{index + 1}</span>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-[#E8EDF2] truncate">{snap.name}</div>
                      <div className="text-[11px] text-[#8FA5B8] truncate">{snap.description || 'No description'} · {fmtTime(snap.created)}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <div className="rounded-lg border border-[#2D3A4A] bg-[#101820] p-3">
                <div className="text-[11px] text-[#8FA5B8] uppercase tracking-wider mb-2">Selected snapshot</div>
                {selected ? (
                  <div className="space-y-1">
                    <div className="text-sm font-semibold text-[#E8EDF2]">{selected.name}</div>
                    <div className="text-[11px] text-[#8FA5B8]">{fmtTime(selected.created)}</div>
                    <div className="text-xs text-[#B8C7D8] pt-1">{selected.description || 'No description provided.'}</div>
                  </div>
                ) : (
                  <div className="text-xs text-[#8FA5B8]">Current state selected.</div>
                )}
              </div>
              <div className="grid gap-2">
                <label className="block text-[11px] text-[#8FA5B8] uppercase tracking-wider">
                  Snapshot name
                  <input
                    type="text"
                    value={snapName}
                    onChange={(e) => setSnapName(e.target.value)}
                    disabled={disabled}
                    placeholder={`Snapshot ${snapshots.length + 1}`}
                    className="vm-input mt-1 w-full normal-case"
                  />
                </label>
                <button type="button" className="vm-btn vm-btn-blue justify-center" disabled={disabled} onClick={() => {
                  const nm = snapName.trim() || `Snapshot ${snapshots.length + 1}`
                  fire('take_snapshot', {
                    snapshot_name: nm,
                    description: 'Created from Snapshot Manager',
                  })
                }}>Take Snapshot</button>
                <button type="button" className="vm-btn justify-center" disabled={disabled || !selected} onClick={() => fire('revert_snapshot', { snapshot_id: selected.id })}>Revert to</button>
                <button type="button" className="vm-btn vm-btn-red justify-center" disabled={disabled || !selected} onClick={() => fire('delete_snapshot', { snapshot_id: selected.id })}>Delete</button>
                <button type="button" className="vm-btn vm-btn-red justify-center" disabled={disabled || snapshots.length === 0} onClick={() => fire('consolidate_snapshots')}>Delete All / Consolidate</button>
              </div>
              <div className="text-[11px] text-[#8FA5B8] leading-relaxed">
                Consolidation commits snapshot delta disks back into the base virtual disk and clears snapshot validation warnings for this lab.
              </div>
            </div>
          </div>
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Close</button>
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
        <div className="vm-modal-footer flex-wrap gap-2">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          {vm?.vmotion_failed && (
            <button type="button" disabled={acting} onClick={async () => {
              setActing(true)
              try { await onAction('resolve_vmotion', { vm_id: vm.id }); onClose() }
              finally { setActing(false) }
            }} className="vm-btn vm-btn-green">
              Resolve failed vMotion
            </button>
          )}
          <button type="button" disabled={acting || !targetHost} onClick={migrate} className="vm-btn vm-btn-blue">
            {acting ? 'Migrating…' : 'Migrate (vMotion)'}
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

/* ─── Edit VM Modal (Virtual Hardware + VM Options tabs) ──────────────── */
function EditVmModal({ vm, networks, datastores = [], onClose, onAction, onAddDisk, onAddNic }) {
  const [tab, setTab] = useState('hardware')
  const [cpu, setCpu] = useState(String(vm.cpu))
  const [memGb, setMemGb] = useState(String(Math.round(vm.memory_mb / 1024)))
  const [annotation, setAnnotation] = useState(vm.annotation || '')
  // VM Options
  const [bootDelay, setBootDelay] = useState(String(vm.boot_delay_ms ?? 0))
  const [firmware, setFirmware] = useState(vm.boot_firmware || vm.firmware || 'BIOS')
  const [enterBios, setEnterBios] = useState(!!vm.enter_bios_on_boot)
  const [firewall, setFirewall] = useState(vm.firewall_enabled !== false)
  const [rebootAction, setRebootAction] = useState(vm.reboot_power_action || 'restart')
  const [bootOrder, setBootOrder] = useState(vm.boot_order || ['disk', 'network', 'cdrom'])
  const [addMenuOpen, setAddMenuOpen] = useState(false)
  const [deviceBusy, setDeviceBusy] = useState('')
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')
  const isPoweredOn = vm.power === 'poweredOn'

  const disks = vm.disks?.length ? vm.disks : []
  const nics = vm.nics?.length ? vm.nics : []
  const cdroms = vm.cdroms?.length ? vm.cdroms : []
  const dsName = (id) => datastores.find(d => d.id === id)?.name || id || '—'

  const moveBoot = (idx, dir) => {
    setBootOrder(prev => {
      const next = [...prev]
      const j = idx + dir
      if (j < 0 || j >= next.length) return prev
      ;[next[idx], next[j]] = [next[j], next[idx]]
      return next
    })
  }

  // Per-device actions (remove / connect toggle) apply immediately and then let
  // the parent refresh the inventory; they are independent of the OK button.
  const deviceAction = async (action, payload, busyKey) => {
    setDeviceBusy(busyKey); setError('')
    try {
      await onAction(action, payload)
    } catch (e) {
      setError(e?.response?.data?.error || 'Action failed')
    } finally { setDeviceBusy('') }
  }

  const save = async () => {
    setActing(true); setError('')
    try {
      // Hardware / general
      const payload = { vm_id: vm.id, annotation }
      if (!isPoweredOn) { payload.cpu = parseInt(cpu); payload.memory_mb = parseInt(memGb) * 1024 }
      await onAction('edit_vm', payload)
      // VM Options (separate action so it works even while powered on)
      await onAction('edit_vm_options', {
        vm_id: vm.id,
        boot_delay_ms: parseInt(bootDelay) || 0,
        boot_firmware: firmware,
        enter_bios_on_boot: enterBios,
        firewall_enabled: firewall,
        reboot_power_action: rebootAction,
        boot_order: bootOrder,
      })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Save failed')
    } finally { setActing(false) }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[560px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>Edit Settings — {vm.name}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="flex border-b border-[#2d3a4a] bg-[#16222f]">
          {[['hardware', 'Virtual Hardware'], ['options', 'VM Options']].map(([id, label]) => (
            <button key={id} type="button" onClick={() => setTab(id)}
              className={`px-4 py-2 text-xs font-semibold border-b-2 ${tab === id ? 'border-[#00C8FF] text-white bg-[rgba(0,200,255,.08)]' : 'border-transparent text-[#8fa5b8] hover:text-white'}`}>
              {label}
            </button>
          ))}
        </div>
        <div className="vm-modal-body space-y-3 max-h-[65vh] overflow-y-auto">
          {tab === 'hardware' && (
            <>
              {/* ── ADD NEW DEVICE menu ── */}
              <div className="relative flex justify-end">
                <button type="button" onClick={() => setAddMenuOpen(o => !o)}
                  className="vm-btn text-[11px] py-1 px-3">ADD NEW DEVICE ▾</button>
                {addMenuOpen && (
                  <div className="absolute right-0 top-8 z-10 w-48 bg-[#1B2A3B] border border-[#2d3a4a] rounded shadow-lg py-1">
                    {[
                      ['Hard Disk', () => onAddDisk?.()],
                      ['Network Adapter', () => onAddNic?.()],
                      ['CD/DVD Drive', () => deviceAction('add_cdrom', { vm_id: vm.id }, 'add_cdrom')],
                    ].map(([label, fn]) => (
                      <button key={label} type="button"
                        onClick={() => { setAddMenuOpen(false); fn() }}
                        className="block w-full text-left px-3 py-1.5 text-xs text-[#E8EDF2] hover:bg-[rgba(0,200,255,.1)]">
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

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
                  <label className="block text-xs text-[#8fa5b8] mb-1">Annotation / Notes</label>
                  <textarea value={annotation} onChange={e => setAnnotation(e.target.value)} rows={2} className="vm-input !pl-3 resize-none" />
                </div>
              </div>

              {/* ── Full device list ── */}
              <div className="space-y-1.5 pt-1">
                <div className="text-[11px] font-bold text-[#8fa5b8] uppercase tracking-wide">Hard disks</div>
                {disks.length === 0 && <p className="text-[10px] text-[#8fa5b8]">No virtual disks.</p>}
                {disks.map((d, i) => {
                  const isBoot = (d.scsi_unit ?? i) === 0 && (d.scsi_controller ?? 0) === 0
                  return (
                    <div key={d.id || i} className="flex items-center gap-2 bg-[#16222f] border border-[#2d3a4a] rounded px-2.5 py-1.5">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-[#E8EDF2] m-0 truncate">{d.label || `Hard disk ${i + 1}`} · {d.capacity_gb} GB</p>
                        <p className="text-[10px] text-[#8fa5b8] font-mono m-0">SCSI {d.scsi_id || `${d.scsi_controller || 0}:${d.scsi_unit ?? i}`} · {d.thin_provisioned ? 'Thin' : 'Thick'} · {dsName(d.datastore_id)}</p>
                      </div>
                      <button type="button" disabled={isBoot || !!deviceBusy}
                        title={isBoot ? 'Cannot remove the boot disk' : 'Remove disk'}
                        onClick={() => deviceAction('remove_disk', { vm_id: vm.id, disk_id: d.id }, `disk-${d.id}`)}
                        className="vm-btn text-[10px] py-0.5 px-2 disabled:opacity-30">Remove</button>
                    </div>
                  )
                })}

                <div className="text-[11px] font-bold text-[#8fa5b8] uppercase tracking-wide pt-1">Network adapters</div>
                {nics.length === 0 && <p className="text-[10px] text-[#8fa5b8]">No network adapters.</p>}
                {nics.map((nic, i) => (
                  <div key={nic.id || i} className="flex items-center gap-2 bg-[#16222f] border border-[#2d3a4a] rounded px-2.5 py-1.5">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-[#E8EDF2] m-0 truncate">{nic.label || `Network adapter ${i + 1}`} · {nic.network_name || networks.find(n => n.id === nic.network_id)?.name || 'VM Network'}</p>
                      <p className="text-[10px] text-[#8fa5b8] font-mono m-0">MAC {nic.mac_address || nic.mac} · {nic.adapter_type || 'Vmxnet3'} · VLAN {nic.vlan_id ?? '—'}</p>
                    </div>
                    <label className="flex items-center gap-1 text-[10px] text-[#E8EDF2] cursor-pointer whitespace-nowrap">
                      <input type="checkbox" checked={nic.connected !== false}
                        disabled={deviceBusy === `nic-${nic.id}`}
                        onChange={e => deviceAction('set_nic_connected', { vm_id: vm.id, nic_id: nic.id, connected: e.target.checked }, `nic-${nic.id}`)} />
                      Connected
                    </label>
                    <button type="button" disabled={nics.length <= 1 || !!deviceBusy}
                      title={nics.length <= 1 ? 'Cannot remove the last adapter' : 'Remove adapter'}
                      onClick={() => deviceAction('remove_nic', { vm_id: vm.id, nic_id: nic.id }, `nic-rm-${nic.id}`)}
                      className="vm-btn text-[10px] py-0.5 px-2 disabled:opacity-30">Remove</button>
                  </div>
                ))}

                <div className="text-[11px] font-bold text-[#8fa5b8] uppercase tracking-wide pt-1">CD/DVD drives</div>
                {cdroms.length === 0 && <p className="text-[10px] text-[#8fa5b8]">No CD/DVD drives.</p>}
                {cdroms.map((cd, i) => (
                  <div key={cd.id || i} className="flex items-center gap-2 bg-[#16222f] border border-[#2d3a4a] rounded px-2.5 py-1.5">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-[#E8EDF2] m-0 truncate">{cd.label || `CD/DVD drive ${i + 1}`}</p>
                      <p className="text-[10px] text-[#8fa5b8] font-mono m-0 truncate">{cd.iso_path ? `${cd.iso_path} · ${cd.connected ? 'Connected' : 'Disconnected'}` : 'Client Device (no media)'}</p>
                    </div>
                    <button type="button" disabled={!!deviceBusy}
                      onClick={() => deviceAction('remove_cdrom', { vm_id: vm.id, cdrom_id: cd.id }, `cd-${cd.id}`)}
                      className="vm-btn text-[10px] py-0.5 px-2 disabled:opacity-30">Remove</button>
                  </div>
                ))}
              </div>
            </>
          )}
          {tab === 'options' && (
            <div className="space-y-3.5">
              <div className="text-[11px] font-bold text-[#8fa5b8] uppercase tracking-wide">Boot Options</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-[#8fa5b8] mb-1">Boot delay (ms)</label>
                  <input type="number" min="0" step="500" value={bootDelay} onChange={e => setBootDelay(e.target.value)} className="vm-input !pl-3" />
                </div>
                <div>
                  <label className="block text-xs text-[#8fa5b8] mb-1">Firmware</label>
                  <select value={firmware} onChange={e => setFirmware(e.target.value)} className="vm-input !pl-3">
                    <option value="BIOS">BIOS</option>
                    <option value="EFI">EFI</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-[#8fa5b8] mb-1">Boot order</label>
                <div className="space-y-1.5">
                  {bootOrder.map((dev, i) => (
                    <div key={dev} className="flex items-center gap-2 bg-[#16222f] border border-[#2d3a4a] rounded px-2.5 py-1.5">
                      <span className="text-[10px] text-[#8fa5b8] w-4">{i + 1}.</span>
                      <span className="text-xs text-[#E8EDF2] capitalize flex-1">{dev}</span>
                      <button type="button" onClick={() => moveBoot(i, -1)} disabled={i === 0} className="vm-btn text-[10px] py-0.5 px-2 disabled:opacity-30">↑</button>
                      <button type="button" onClick={() => moveBoot(i, 1)} disabled={i === bootOrder.length - 1} className="vm-btn text-[10px] py-0.5 px-2 disabled:opacity-30">↓</button>
                    </div>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-[#E8EDF2] cursor-pointer">
                <input type="checkbox" checked={enterBios} onChange={e => setEnterBios(e.target.checked)} />
                Force entry into BIOS/EFI setup screen on next boot
              </label>

              <div className="text-[11px] font-bold text-[#8fa5b8] uppercase tracking-wide pt-1 border-t border-[#22303f] mt-1">VMware Tools / Power</div>
              <div>
                <label className="block text-xs text-[#8fa5b8] mb-1">Reboot / Restart Guest behaviour</label>
                <select value={rebootAction} onChange={e => setRebootAction(e.target.value)} className="vm-input !pl-3">
                  <option value="restart">Restart guest OS (graceful)</option>
                  <option value="shutdown">Shut down then power on</option>
                  <option value="poweroff">Hard power cycle</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-xs text-[#E8EDF2] cursor-pointer">
                <input type="checkbox" checked={firewall} onChange={e => setFirewall(e.target.checked)} />
                Guest OS firewall enabled
              </label>
            </div>
          )}
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

/* ─── Deploy from Template Modal ─────────────────────────────────────── */
function DeployFromTemplateModal({ templates, hosts, onClose, onAction }) {
  const [templateName, setTemplateName] = useState(templates[0]?.name || '')
  const [vmName, setVmName] = useState('')
  const [hostId, setHostId] = useState(hosts.find(h => h.status === 'connected' && !h.maintenance)?.id || '')
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const deploy = async () => {
    if (!templateName) { setError('Select a template'); return }
    setActing(true); setError('')
    try {
      await onAction('deploy_from_template', {
        template_name: templateName,
        vm_name: vmName.trim() || undefined,
        host_id: hostId || undefined,
      })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Deploy failed')
    } finally { setActing(false) }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[420px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>Deploy VM from Template</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Template</label>
            <select value={templateName} onChange={e => setTemplateName(e.target.value)} className="vm-input !pl-3">
              {templates.map(t => <option key={t.id} value={t.name}>{t.name} ({t.guest_os_version || t.guest_os})</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">New VM name (optional)</label>
            <input value={vmName} onChange={e => setVmName(e.target.value)} placeholder="auto-generated if blank" className="vm-input !pl-3" />
          </div>
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Target host</label>
            <select value={hostId} onChange={e => setHostId(e.target.value)} className="vm-input !pl-3">
              {hosts.filter(h => h.status === 'connected' && !h.maintenance).map(h => (
                <option key={h.id} value={h.id}>{h.name}</option>
              ))}
            </select>
          </div>
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          <button type="button" disabled={acting || !templateName} onClick={deploy} className="vm-btn vm-btn-blue">
            {acting ? 'Deploying…' : 'Deploy'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Task / Event detail popover ────────────────────────────────────── */
function TaskEventDetailModal({ item, onClose }) {
  if (!item) return null
  const isTask = item.kind === 'task'
  const d = item.data || {}
  const severity = (d.severity || '').toLowerCase()
  const sevColor = severity === 'critical' ? '#D9534F' : severity === 'warning' ? '#F5A623' : '#5DB85D'
  const rows = isTask
    ? [
        ['Task', d.name],
        ['Status', <span key="status" className={d.status === 'success' ? 'text-[#5DB85D]' : 'text-[#D9534F]'}>{d.status === 'success' ? '✓ ' : '✗ '}{d.result || d.status}</span>],
        ['Target', d.target],
        ['Initiator', d.initiator || 'root'],
        ['Queued', fmtTime(d.queued)],
        ['Started', fmtTime(d.started)],
        ['Completed', fmtTime(d.completed)],
        ['Duration', d.completed && d.started ? `${Math.max(1, Math.round((new Date(d.completed) - new Date(d.started)) / 1000))}s` : '—'],
        ['Task ID', <span key="task-id" className="font-mono text-[10px]">{d.id || '—'}</span>],
      ]
    : [
        ['Severity', <span key="severity" style={{ color: sevColor }} className="font-semibold uppercase">{d.severity || 'info'}</span>],
        ['Entity', d.entity || '—'],
        ['User', d.user || 'root'],
        ['Time', fmtTime(d.time)],
        ['Message', d.message],
      ]
  return (
    <div className="vm-modal-overlay" onClick={onClose}>
      <div className="vm-modal w-[440px] max-w-[95vw]" onClick={e => e.stopPropagation()}>
        <div className="vm-modal-header">
          <span>{isTask ? 'Task details' : 'Event details'}{d.target || d.entity ? ` — ${d.target || d.entity}` : ''}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body">
          {rows.map(([label, value]) => (
            <div key={label} className="vm-info-row">
              <span className="vm-info-label">{label}</span>
              <span className="vm-info-value break-words">{value ?? '—'}</span>
            </div>
          ))}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn vm-btn-blue">Close</button>
        </div>
      </div>
    </div>
  )
}

/* ─── Main component ─────────────────────────────────────────────────── */
export default function VMwareSimulator() {
  const navigate = useNavigate()
  const { sessionId: paramSessionId } = useParams()
  const [searchParams] = useSearchParams()
  // Prefer session ID from query param (redirected from LabRunner) over URL segment
  const sessionId = searchParams.get('session') || paramSessionId
  const scenarioSlug = searchParams.get('scenario') || ''
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [acting, setActing] = useState(false)
  const [selectedNode, setSelectedNode] = useState({ type: 'host', id: null })
  const [activeTab, setActiveTab] = useState('summary')
  const [expandedSections, setExpandedSections] = useState({ hosts: true, vms: true, storage: true, networks: false })
  const [showSnapshotModal, setShowSnapshotModal] = useState(false)
  const [showSnapshotManager, setShowSnapshotManager] = useState(false)
  const [showMigrateModal, setShowMigrateModal] = useState(false)
  const [showCreateVmModal, setShowCreateVmModal] = useState(false)
  const [showCreateVmWizard, setShowCreateVmWizard] = useState(false)
  const [showEditVmModal, setShowEditVmModal] = useState(false)
  const [showCloneVmModal, setShowCloneVmModal] = useState(false)
  const [showDeployTemplateModal, setShowDeployTemplateModal] = useState(false)
  const [showVmotionWizard, setShowVmotionWizard] = useState(false)
  const [showStorageVmotionWizard, setShowStorageVmotionWizard] = useState(false)
  const [showOvfModal, setShowOvfModal] = useState(false)
  // Resource-management modals (add disk/NIC, create switch/portgroup/datastore/cluster).
  const [showAddDiskModal, setShowAddDiskModal] = useState(false)
  const [showAddNicModal, setShowAddNicModal] = useState(false)
  const [showCreateVswitchModal, setShowCreateVswitchModal] = useState(false)
  const [showCreatePortGroupModal, setShowCreatePortGroupModal] = useState(false)
  const [showCreateDatastoreModal, setShowCreateDatastoreModal] = useState(false)
  const [showCreateClusterModal, setShowCreateClusterModal] = useState(false)
  // New-fidelity resource modals.
  const [showAddHostModal, setShowAddHostModal] = useState(false)
  const [showResourcePoolModal, setShowResourcePoolModal] = useState(false)
  const [showVappModal, setShowVappModal] = useState(false)
  const [showDatastoreClusterModal, setShowDatastoreClusterModal] = useState(false)
  const [folderModalType, setFolderModalType] = useState(null) // 'host'|'vm'|'storage'|'network' or null
  const [forceDvs, setForceDvs] = useState(false) // open vSwitch modal preset to distributed
  const [topMenuOpen, setTopMenuOpen] = useState(false)
  const topMenuRef = useRef(null)
  const [pendingDeleteVm, setPendingDeleteVm] = useState(null)
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false)
  const [inventorySearch, setInventorySearch] = useState('')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [tasksOpen, setTasksOpen] = useState(true)
  const [monSub, setMonSub] = useState('performance')
  const [monRange, setMonRange] = useState('1H')
  const [consoleVm, setConsoleVm] = useState(null)
  const [vcAuth, setVcAuth] = useState(() => isVcenterAuthenticated())
  // Credentials hint near the simulator — dismissible, remembered per session.
  const [credsHintDismissed, setCredsHintDismissed] = useState(() => {
    try { return sessionStorage.getItem('fixitlab_vmware_creds_hint') === '1' } catch { return false }
  })
  const [ctxMenu, setCtxMenu] = useState(null)
  const [vmToast, setVmToast] = useState(null)
  // Task/Event detail popover (gap: tasks & events should be clickable).
  const [detailItem, setDetailItem] = useState(null)
  const rootRef = useRef(null)
  const actionsRef = useRef(null)

  const initialSelectionDone = useRef(false)
  const load = useCallback(async () => {
    try {
      const data = await vmwareApi.getState(sessionId, scenarioSlug)
      setState(data)
      setLoadFailed(false)
      if (!initialSelectionDone.current && data.inventory?.hosts?.length) {
        setSelectedNode({ type: 'host', id: data.inventory.hosts[0].id })
        initialSelectionDone.current = true
      }
    } catch {
      // getState already falls back to the demo sandbox on 4xx; reaching here
      // means a genuine network/auth failure. Offer a retry instead of a dead end.
      setLoadFailed(true)
    } finally {
      setLoading(false)
    }
  }, [sessionId, scenarioSlug])

  const retryLoad = useCallback(() => {
    setLoading(true)
    setLoadFailed(false)
    load()
  }, [load])

  useEffect(() => { load() }, [load])

  // Ping parent LabRunner so idle timeout resets while user works in this child tab.
  useEffect(() => {
    if (!sessionId) return undefined
    const ping = () => broadcastLabActivity(sessionId)
    const events = ['keydown', 'mousedown', 'mousemove', 'touchstart', 'scroll', 'click']
    events.forEach((e) => window.addEventListener(e, ping, { passive: true }))
    const iv = setInterval(ping, 60_000)
    ping()
    return () => {
      clearInterval(iv)
      events.forEach((e) => window.removeEventListener(e, ping))
    }
  }, [sessionId])

  // Keep guest console VM in sync with vCenter state (disk/NIC hot-add flags).
  useEffect(() => {
    if (!consoleVm?.id || !state?.inventory?.vms) return
    const fresh = state.inventory.vms.find((v) => v.id === consoleVm.id)
    if (!fresh) return
    const hwChanged = fresh.guest_disk_hidden !== consoleVm.guest_disk_hidden
      || fresh.guest_disk_visible !== consoleVm.guest_disk_visible
      || fresh.guest_nic_pending !== consoleVm.guest_nic_pending
      || (fresh.guest_pending_disks?.length || 0) !== (consoleVm.guest_pending_disks?.length || 0)
      || (fresh.guest_pending_nics?.length || 0) !== (consoleVm.guest_pending_nics?.length || 0)
      || (fresh.disks?.length || 0) !== (consoleVm.disks?.length || 0)
      || (fresh.nics?.length || 0) !== (consoleVm.nics?.length || 0)
    if (hwChanged || fresh.power !== consoleVm.power || fresh.boot_pending !== consoleVm.boot_pending) {
      setConsoleVm(fresh)
    }
  }, [state?.inventory?.vms, consoleVm?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Close this tab when the parent lab stops or the timer expires.
  useEffect(() => {
    if (!sessionId) return undefined
    registerLabChildTab(sessionId, 'vmware-sim')
    const exitLab = (reason) => {
      toast(reason === 'expired' ? 'Lab time expired — closing VMware' : 'Lab session ended', { icon: '⏰', duration: 4000 })
      navigate('/scenarios')
      setTimeout(() => { try { window.close() } catch { /* popup blocked */ } }, 600)
    }
    const unsub = subscribeLabSync(sessionId, (data) => {
      if (data.type === 'lab_stopped' || data.type === 'lab_force_close') {
        exitLab(data.reason || 'stopped')
      }
    })
    return unsub
  }, [sessionId, navigate])

  // Poll server-side lab status — catches expiry when BroadcastChannel is unavailable.
  useEffect(() => {
    if (!sessionId) return undefined
    let cancelled = false
    const poll = async () => {
      if (cancelled) return
      try {
        const lab = await labApi.getSessionStatus(sessionId)
        if (cancelled) return
        if (['TERMINATED', 'EXPIRED', 'FAILED', 'COMPLETED'].includes(lab.status)) {
          toast(lab.status === 'EXPIRED' ? 'Lab time expired' : 'Lab session ended', { icon: '⏰', duration: 4000 })
          navigate('/scenarios')
          setTimeout(() => { try { window.close() } catch { /* */ } }, 600)
        }
      } catch { /* ignore */ }
    }
    poll()
    const iv = setInterval(poll, 15000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [sessionId, navigate])

  useEffect(() => {
    if (activeTab !== 'monitor') return undefined
    const t = setInterval(() => { load() }, 5000)
    return () => clearInterval(t)
  }, [activeTab, load])

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
        setDetailItem(null)
        setActionsMenuOpen(false)
        setShowSnapshotModal(false)
        setShowSnapshotManager(false)
        setShowMigrateModal(false)
        setShowCreateVmModal(false)
        setShowEditVmModal(false)
        setShowCloneVmModal(false)
        setShowDeployTemplateModal(false)
        setShowAddDiskModal(false)
        setShowAddNicModal(false)
        setShowCreateVswitchModal(false)
        setShowCreatePortGroupModal(false)
        setShowCreateDatastoreModal(false)
        setShowCreateClusterModal(false)
        setShowAddHostModal(false)
        setShowResourcePoolModal(false)
        setShowVappModal(false)
        setShowDatastoreClusterModal(false)
        setFolderModalType(null)
        setTopMenuOpen(false)
        setPendingDeleteVm(null)
      }
    }
    document.addEventListener('keydown', onEsc)
    return () => document.removeEventListener('keydown', onEsc)
  }, [])

  useEffect(() => {
    const handler = (e) => { if (topMenuRef.current && !topMenuRef.current.contains(e.target)) setTopMenuOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    const handler = (e) => { if (actionsRef.current && !actionsRef.current.contains(e.target)) setActionsMenuOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const runAction = async (action, payload = {}, options = {}) => {
    const { silent = false } = options
    setActing(true)
    if (!silent) setActionsMenuOpen(false)
    try {
      const res = await vmwareApi.action(sessionId, action, payload)
      if (res.state) setState(res.state)
      else await load()
      const msg = res.message || 'Action completed'
      if (!silent) {
        setVmToast({ message: msg, kind: 'success' })
        toast.success(msg, { style: { background: '#1b2a3b', color: '#e8edf2', border: '1px solid #2d3a4a', fontSize: '12px' } })
      }
      return res
    } catch (err) {
      const errMsg = err.response?.data?.error || 'Action failed'
      if (!silent) {
        setVmToast({ message: errMsg, kind: 'error' })
        toast.error(errMsg, { style: { background: '#1b2a3b', color: '#f08080', border: '1px solid #2d3a4a', fontSize: '12px' } })
      }
      throw err
    } finally {
      setActing(false)
    }
  }

  const handleGuestAction = (sideEffect) => {
    if (sideEffect?.action) runAction(sideEffect.action, sideEffect, { silent: !!sideEffect.silent })
  }

  const handleCtxAction = (action, payload) => {
    const selVm = (p) => setSelectedNode({ type: 'vm', id: p.id })
    switch (action) {
      // ── VM sentinels ──
      case '__snapshot__': selVm(payload); setShowSnapshotModal(true); break
      case '__manage_snapshots__': selVm(payload); setActiveTab('snapshots'); setShowSnapshotManager(true); break
      case '__revert_latest__': {
        const snaps = payload.snapshots || []
        if (snaps.length) runAction('revert_snapshot', { vm_id: payload.id, snapshot_id: snaps[snaps.length - 1].id })
        break
      }
      case '__consolidate__': runAction('consolidate_snapshots', { vm_id: payload.id }); break
      case '__clone__': selVm(payload); setShowCloneVmModal(true); break
      case '__migrate__': selVm(payload); setShowMigrateModal(true); break
      case '__edit__': selVm(payload); setShowEditVmModal(true); break
      case '__add_disk__': selVm(payload); setShowAddDiskModal(true); break
      case '__add_nic__': selVm(payload); setShowAddNicModal(true); break
      case '__console__': setConsoleVm(payload); break
      case '__delete__': setPendingDeleteVm(payload); break
      case '__suspend__': runAction('suspend', { vm_id: payload.id }); break
      case '__rename__': selVm(payload); setShowEditVmModal(true); break
      case '__move_vm__': setVmToast({ message: `Use Migrate… to move ${payload.name} to another host or datastore`, kind: 'info' }); break
      case '__ft_on__': setVmToast({ message: 'Fault Tolerance requires a second host with a dedicated FT logging NIC', kind: 'info' }); break
      case '__assign_tag__': setVmToast({ message: 'Tag assigned (Category: Environment)', kind: 'success' }); break
      case '__remove_tag__': setVmToast({ message: 'Tag removed', kind: 'success' }); break
      case '__add_permission__':
        setSelectedNode({ type: 'admin', id: 'admin' }); setActiveTab('summary')
        break
      // ── shared creation sentinels ──
      case '__create_vm__': setShowCreateVmModal(true); break
      case '__deploy_ovf__': setShowOvfModal(true); break
      case '__create_vswitch__': setForceDvs(false); setShowCreateVswitchModal(true); break
      case '__create_vswitch_dvs__': setForceDvs(true); setShowCreateVswitchModal(true); break
      case '__create_portgroup__': setShowCreatePortGroupModal(true); break
      case '__create_datastore__': setShowCreateDatastoreModal(true); break
      case '__create_datastore_cluster__': setShowDatastoreClusterModal(true); break
      case '__browse_ds__': setSelectedNode({ type: 'datastore', id: payload.id }); setActiveTab('vms'); break
      case '__net_edit__': setSelectedNode({ type: 'network', id: payload.id }); setActiveTab('summary'); break
      case '__rename_ds__': runAction('rename_object', { kind: 'datastore', id: payload.id, name: `${payload.name}-renamed` }); break
      case '__rename_net__': runAction('rename_object', { kind: 'network', id: payload.id, name: `${payload.name}-renamed` }); break
      case '__migrate_network__': {
        const src = networks.find(n => n.id === payload.id) || networks[0]
        const dst = networks.find(n => n.id !== src?.id)
        if (src && dst) runAction('migrate_vms_network', { source_network_id: src.id, target_network_id: dst.id })
        else setVmToast({ message: 'Need at least two networks to migrate between', kind: 'error' })
        break
      }
      // ── host sentinels ──
      case '__new_resource_pool__': setShowResourcePoolModal(true); break
      case '__new_vapp__': setShowVappModal(true); break
      case '__disconnect_host__': runAction('reconnect_host', { host_id: payload.id }); break // toggles connection (sim only reconnects)
      case '__host_power_on__': setVmToast({ message: `${payload.name} is already powered on`, kind: 'info' }); break
      case '__host_shutdown__': runAction('enter_maintenance', { host_id: payload.id }); break
      case '__host_reboot__': setVmToast({ message: `Reboot of ${payload.name} — host will reconnect`, kind: 'success' }); break
      case '__attach_host_profile__': runAction('extract_host_profile', { host_id: payload.id }); break
      case '__host_settings__': setSelectedNode({ type: 'host', id: payload.id }); setActiveTab('configure'); break
      // ── datacenter sentinels ──
      case '__add_host__': setShowAddHostModal(true); break
      case '__new_cluster__': setShowCreateClusterModal(true); break
      case '__new_folder_host__': setFolderModalType('host'); break
      case '__new_folder_vm__': setFolderModalType('vm'); break
      case '__new_folder_storage__': setFolderModalType('storage'); break
      case '__new_folder_network__': setFolderModalType('network'); break
      case '__edit_default_compat__': runAction('edit_default_vm_compat', { compatibility: 'vmx-19' }); break
      case '__new_alarm_def__': setSelectedNode({ type: 'vcenter', id: 'vcenter' }); setActiveTab('alarms'); break
      case '__move_dc__': setVmToast({ message: 'Move To is unavailable for the root datacenter', kind: 'info' }); break
      case '__rename_dc__': runAction('rename_object', { kind: 'datacenter', id: payload.id, name: `${payload.name}-renamed` }); break
      case '__delete_dc__': setVmToast({ message: 'The root datacenter cannot be deleted in this lab', kind: 'info' }); break
      default:
        runAction(action, payload)
    }
  }

  const openVmContext = (e, vm) => {
    e.preventDefault()
    e.stopPropagation()
    setCtxMenu({ x: e.clientX, y: e.clientY, kind: 'vm', vm })
  }

  // Right-click handler shared by host / datastore / network tree rows and rows.
  const openNodeContext = (e, kind, node) => {
    e.preventDefault()
    e.stopPropagation()
    setCtxMenu({ x: e.clientX, y: e.clientY, kind, node })
  }

  if (loading) {
    return (
      <div className="vmware-sim vm-loading">
        <div className="text-center">
          <div className="vm-loading-spinner mx-auto mb-3" />
          <p className="text-[#8fa5b8] text-sm">Loading vCenter…</p>
        </div>
      </div>
    )
  }

  if (loadFailed) {
    return (
      <div className="vmware-sim vm-loading">
        <div className="text-center max-w-sm px-6">
          <p className="text-[#e6edf3] text-base font-semibold mb-2">Could not reach vCenter</p>
          <p className="text-[#8fa5b8] text-sm mb-4">
            The lab service didn’t respond. Check your connection and try again — your progress is preserved.
          </p>
          <button
            onClick={retryLoad}
            className="px-4 py-2 rounded text-sm font-semibold"
            style={{ background: '#2D7CFF', color: '#fff' }}
          >
            Retry
          </button>
          <Link to={`/lab/${sessionId || ''}`} className="block mt-3 text-[#5aa3ff] text-xs hover:underline">
            ← Back to lab
          </Link>
        </div>
      </div>
    )
  }

  if (!vcAuth) {
    return <VmwareLoginGate onAuthenticated={() => setVcAuth(true)} />
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
  const templates = inv.templates || []
  const contentLibrary = inv.content_library || []
  const permissions = inv.permissions || []
  const rolesCatalog = inv.roles_catalog || []
  const vcenterUsers = inv.vcenter_users || []
  const alarmDefinitions = inv.alarm_definitions || []
  const vsan = inv.vsan || {}
  const vswitches = inv.vswitches || []
  const datacenters = inv.datacenters || []
  const nsx = inv.nsx || {}
  const srm = inv.srm || {}
  const vami = inv.vami || {}
  const resourcePools = inv.resource_pools || []
  const vapps = inv.vapps || []
  const datastoreClusters = inv.datastore_clusters || []
  const folders = inv.folders || []
  const licensing = inv.licensing || {}
  const linkedMode = summary.linked_mode || inv.linked_mode
  const invSearch = inventorySearch.trim().toLowerCase()
  const filterLabel = (label) => !invSearch || label.toLowerCase().includes(invSearch)

  const selectedHost = selectedNode.type === 'host' ? (hosts.find(h => h.id === selectedNode.id) ?? null) : null
  const selectedVm = selectedNode.type === 'vm' ? vms.find(v => v.id === selectedNode.id) : null
  const selectedDs = selectedNode.type === 'datastore' ? datastores.find(d => d.id === selectedNode.id) : null
  const selectedNet = selectedNode.type === 'network' ? networks.find(n => n.id === selectedNode.id) : null
  const selectedTemplate = selectedNode.type === 'template' ? templates.find(t => t.id === selectedNode.id) : null
  const selectedDc = selectedNode.type === 'datacenter' ? (datacenters.find(d => d.id === selectedNode.id) || { id: selectedNode.id, name: inv.datacenter || 'DC-Prod' }) : null

  const activeAlarms = alarms.filter(a => a.status === 'active')

  const toggleSection = (k) => setExpandedSections(p => ({ ...p, [k]: !p[k] }))

  /* ── Resolve a task target / event entity name to an inventory node and
        select it, then open a detail popover with the full record. ── */
  const selectByTargetName = (name) => {
    if (!name) return
    const vm = vms.find(v => v.name === name)
    if (vm) { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary'); return }
    const host = hosts.find(h => h.name === name)
    if (host) { setSelectedNode({ type: 'host', id: host.id }); setActiveTab('summary'); return }
    const ds = datastores.find(d => d.name === name)
    if (ds) { setSelectedNode({ type: 'datastore', id: ds.id }); setActiveTab('summary'); return }
    const net = networks.find(n => n.name === name)
    if (net) { setSelectedNode({ type: 'network', id: net.id }); setActiveTab('summary') }
  }
  const openTaskDetail = (task) => {
    selectByTargetName(task?.target)
    setDetailItem({ kind: 'task', data: task })
  }
  const openEventDetail = (ev) => {
    selectByTargetName(ev?.entity)
    setDetailItem({ kind: 'event', data: ev })
  }

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
        <ToolbarBtn onClick={() => { setActiveTab('snapshots'); setShowSnapshotManager(true) }} disabled={acting} label="Manage Snapshots…" />
        <ToolbarBtn onClick={() => setShowMigrateModal(true)} disabled={acting} label="Migrate…" />
        <ToolbarBtn onClick={() => setShowVmotionWizard(true)} disabled={acting} label="vMotion Wizard…" />
        <ToolbarBtn onClick={() => setShowStorageVmotionWizard(true)} disabled={acting} label="Storage vMotion…" />
        <ToolbarBtn onClick={() => setShowCloneVmModal(true)} disabled={acting} label="Clone…" />
        <ToolbarSep />
        <ToolbarBtn onClick={() => setShowAddDiskModal(true)} disabled={acting} label="Add Disk…" />
        <ToolbarBtn onClick={() => setShowAddNicModal(true)} disabled={acting} label="Add Network Adapter…" />
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
      <ToolbarBtn onClick={() => setShowCreateVswitchModal(true)} disabled={acting} label="Add vSwitch…" />
      <ToolbarBtn onClick={() => setShowCreatePortGroupModal(true)} disabled={acting} label="Add Port Group…" />
      <ToolbarBtn onClick={() => setShowCreateDatastoreModal(true)} disabled={acting} label="New Datastore…" />
      <ToolbarBtn onClick={() => setShowCreateClusterModal(true)} disabled={acting} label="New Cluster…" />
      <ToolbarSep />
      {host.maintenance
        ? <ToolbarBtn onClick={() => runAction('exit_maintenance', { host_name: host.name })} disabled={acting} label="Exit Maintenance Mode" />
        : <ToolbarBtn onClick={() => runAction('enter_maintenance', { host_name: host.name })} disabled={acting} label="Enter Maintenance Mode" />
      }
      {host.status === 'disconnected' && (
        <ToolbarBtn onClick={() => runAction('reconnect_host', { host_name: host.name })} disabled={acting} label="Reconnect Host" blue />
      )}
      <ToolbarSep />
      <ToolbarBtn onClick={() => runAction('toggle_ssh', { host_name: host.name })} disabled={acting} label={`${host.ssh_enabled ? 'Disable' : 'Enable'} SSH`} />
      <div className="flex-1" />
      <span className="text-[10px] text-[#8FA5B8] mr-1">Use Actions ▾ above for the full host menu</span>
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
        vms={vms}
        summary={summary}
      />

      {/* vCenter credentials hint — shown wherever the simulator is involved. */}
      {!credsHintDismissed && (
        <div className="shrink-0 flex items-center gap-2 px-4 py-1.5 border-b border-[#2D3A4A] bg-[rgba(45,124,255,.08)] text-[11.5px]">
          <span className="text-[#5b9bf5] font-semibold">vCenter sign-in</span>
          <span className="text-[#8fa5b8]">Use</span>
          <code className="font-mono text-[#E8EDF2] bg-[#16222f] border border-[#2D3A4A] rounded px-1.5 py-0.5">lab_vmware</code>
          <span className="text-[#8fa5b8]">/</span>
          <code className="font-mono text-[#E8EDF2] bg-[#16222f] border border-[#2D3A4A] rounded px-1.5 py-0.5">lab_vmware@123</code>
          <button type="button"
            onClick={() => { navigator.clipboard?.writeText('lab_vmware@123').catch(() => {}); setVmToast({ message: 'Password copied to clipboard', kind: 'success' }) }}
            className="vm-btn text-[10px] py-0.5 px-2 ml-1">Copy password</button>
          <div className="flex-1" />
          <button type="button"
            onClick={() => { try { sessionStorage.setItem('fixitlab_vmware_creds_hint', '1') } catch { /* ignore */ } setCredsHintDismissed(true) }}
            className="text-[#8fa5b8] hover:text-white px-1" title="Dismiss">✕</button>
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Left inventory tree ── */}
        <aside className="vm-nav">
          <VmwareInventoryTree
            inv={inv}
            hosts={hosts}
            vms={vms}
            templates={templates}
            datastores={datastores}
            networks={networks}
            datacenters={datacenters}
            linkedMode={linkedMode}
            filterLabel={filterLabel}
            selectedNode={selectedNode}
            setSelectedNode={setSelectedNode}
            setActiveTab={setActiveTab}
            onVmContextMenu={openVmContext}
            onHostContextMenu={(e, host) => openNodeContext(e, 'host', host)}
            onDcContextMenu={(e, dc) => openNodeContext(e, 'datacenter', dc)}
            onDsContextMenu={(e, ds) => openNodeContext(e, 'datastore', ds)}
            onNetContextMenu={(e, net) => openNodeContext(e, 'network', net)}
            onCreateVm={() => setShowCreateVmModal(true)}
            onCreateVmWizard={() => setShowCreateVmWizard(true)}
            onDeployTemplate={() => setShowDeployTemplateModal(true)}
            onDeployOvf={() => setShowOvfModal(true)}
          />
        </aside>

        {/* ── Main content ──────────────────────────────────────────── */}
        <main className="vm-main">

          {/* Datastore capacity incident banner — critical (<5% free) takes
              precedence over a low-space warning (<15% free). */}
          {(() => {
            const criticalDs = datastores.find(d => d.capacity_gb && d.free_gb / d.capacity_gb < 0.05)
            const warnDs = !criticalDs && datastores.find(d => d.capacity_gb && d.free_gb / d.capacity_gb < 0.15)
            const ds = criticalDs || warnDs
            if (!ds) return null
            const usedPct = Math.round((1 - ds.free_gb / ds.capacity_gb) * 100)
            const isCritical = !!criticalDs
            return (
              <div className="vm-banner-warning" style={isCritical ? { background: 'rgba(217,83,79,.15)', borderBottomColor: 'var(--vm-red)', color: '#f5a0a0' } : undefined}>
                <span className="shrink-0">⚠</span>
                {isCritical ? (
                  <span>{ds.name} is full ({usedPct}% used). VMs on it are not responding and snapshots are blocked. Reboot a VM to recover it, or free space.</span>
                ) : (
                  <span>{ds.name} is low on space — only {fmtBytes(ds.free_gb)} ({(ds.free_pct ?? Math.round((ds.free_gb / ds.capacity_gb) * 100))}%) free. Free up space or increase capacity to avoid VM impact.</span>
                )}
                <div className="flex-1" />
                <button type="button"
                  className={`shrink-0 vm-btn ${isCritical ? 'vm-btn-red' : 'vm-btn-amber'} text-[11.5px] py-1 px-3`}
                  onClick={() => { setSelectedNode({ type: 'datastore', id: ds.id }); setActiveTab('summary') }}>
                  View datastore
                </button>
                <button type="button"
                  className="shrink-0 vm-btn vm-btn-blue text-[11.5px] py-1 px-3"
                  disabled={acting}
                  onClick={() => runAction('expand_datastore', { datastore: ds.name, gb: 500 })}>
                  Increase capacity
                </button>
              </div>
            )
          })()}

          <div className="vm-breadcrumb">
            {/* Top "Menu ▾" — vSphere shortcut menu incl. Administration. */}
            <div className="relative mr-1" ref={topMenuRef}>
              <button type="button" onClick={() => setTopMenuOpen(v => !v)}
                className="flex items-center gap-1 text-[11px] font-semibold text-[#c3d3e3] hover:text-white px-2 py-0.5 rounded hover:bg-white/[0.06]">
                Menu <span className="text-[8px]">▼</span>
              </button>
              {topMenuOpen && (
                <div className="absolute top-full left-0 mt-1 z-[78] min-w-[200px] bg-[#243447] border border-[#2D3A4A] rounded-[7px] shadow-2xl py-1 animate-[vmScale_0.12s_both]">
                  {[
                    ['Home', () => { setSelectedNode({ type: 'vcenter', id: 'vcenter' }); setActiveTab('summary') }],
                    ['Hosts and Clusters', () => { setSelectedNode({ type: 'datacenter', id: datacenters[0]?.id || 'dc-prod' }); setActiveTab('hosts') }],
                    ['VMs and Templates', () => { setSelectedNode({ type: 'datacenter', id: datacenters[0]?.id || 'dc-prod' }); setActiveTab('vms') }],
                    ['Storage', () => { setSelectedNode({ type: 'datacenter', id: datacenters[0]?.id || 'dc-prod' }); setActiveTab('datastores') }],
                    ['Networking', () => { setSelectedNode({ type: 'datacenter', id: datacenters[0]?.id || 'dc-prod' }); setActiveTab('networks') }],
                    ['__divider__'],
                    ['Administration', () => { setSelectedNode({ type: 'admin', id: 'admin' }); setActiveTab('summary') }],
                  ].map((item, i) => item[0] === '__divider__'
                    ? <div key={`d-${i}`} className="h-px bg-[#2D3A4A] my-1" />
                    : (
                      <button key={item[0]} type="button"
                        onClick={() => { item[1](); setTopMenuOpen(false) }}
                        className="w-full text-left px-3 py-1.5 text-[12px] text-[#e8edf2] hover:bg-[#2d4057]">
                        {item[0]}
                      </button>
                    ))}
                </div>
              )}
            </div>
            <span className="text-[#4a5a6d] text-[9px]">›</span>
            <span className="text-[#8fa5b8]">Home</span>
            <span className="text-[#4a5a6d] text-[9px]">›</span>
            <span className="text-[#8fa5b8]">{inv.datacenter || 'DC-Prod'}</span>
            <span className="text-[#4a5a6d] text-[9px]">›</span>
            <span className="text-white">{selectedVm?.name || selectedHost?.name || selectedDs?.name || selectedNet?.name || selectedTemplate?.name || selectedDc?.name || (selectedNode.type === 'admin' ? 'Administration' : 'Inventory')}</span>
          </div>

          <div className="vm-object-bar"
            onContextMenu={(e) => {
              if (selectedVm) openVmContext(e, selectedVm)
              else if (selectedHost) openNodeContext(e, 'host', selectedHost)
              else if (selectedDs) openNodeContext(e, 'datastore', selectedDs)
              else if (selectedNet) openNodeContext(e, 'network', selectedNet)
              else if (selectedDc) openNodeContext(e, 'datacenter', selectedDc)
            }}
            title="Right-click for actions">
            {selectedVm && <StatusIcon status={selectedVm.power} size={12} />}
            {selectedHost && <StatusIcon status={selectedHost.status} size={12} />}
            {selectedDs && <StatusIcon status={selectedDs.accessible ? 'connected' : 'disconnected'} size={12} />}
            <span className="text-[15px] font-bold text-white">
              {selectedVm?.name || selectedHost?.name || selectedDs?.name || selectedNet?.name || selectedTemplate?.name || 'Select an object'}
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
            {(selectedVm || selectedHost || selectedDc) && (
              <div className="relative" ref={actionsRef}>
                <button type="button" onClick={() => setActionsMenuOpen(v => !v)} className="vm-actions-btn">
                  Actions <span className="text-[9px]">▼</span>
                </button>
                {actionsMenuOpen && (
                  <VmwareActionsMenu
                    kind={selectedVm ? 'vm' : selectedHost ? 'host' : 'datacenter'}
                    target={selectedVm || selectedHost || selectedDc}
                    onAction={handleCtxAction}
                    onConsole={setConsoleVm}
                    onClose={() => setActionsMenuOpen(false)}
                    acting={acting}
                  />
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
              <ToolbarBtn onClick={() => setShowCreateDatastoreModal(true)} disabled={acting} label="New Datastore…" />
              <ToolbarBtn onClick={() => runAction('expand_datastore', { datastore: selectedDs.name, gb: 500 })} disabled={acting} label="Increase Capacity" />
              <ToolbarBtn onClick={() => runAction('remove_datastore', { datastore_id: selectedDs.id })} disabled={acting || (selectedDs.vms?.length > 0)} label="Remove Datastore" red />
              <div className="flex-1" />
              <RefreshBtn onClick={load} />
            </div>
          )}
          {selectedNet && (
            <div className="vm-toolbar-row">
              <ToolbarBtn onClick={() => setShowCreatePortGroupModal(true)} disabled={acting} label="New Port Group / VLAN…" />
              <ToolbarBtn onClick={() => setShowCreateVswitchModal(true)} disabled={acting} label="New vSwitch…" />
              <ToolbarBtn onClick={() => runAction('remove_portgroup', { network_id: selectedNet.id })}
                disabled={acting || vms.some(v => v.network_id === selectedNet.id)} label="Remove Port Group" red />
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

              {/* ── VCENTER / PLATFORM ───────────────────────────── */}
              {selectedNode.type === 'vcenter' && activeTab === 'summary' && (
                <div className="space-y-3">
                  <ContentPanel title="vCenter Server">
                    <InfoRow label="Version" value={`${inv.vcenter_version || '7.0.3'} (build ${inv.vcenter_build || '—'})`} />
                    <InfoRow label="Enhanced Linked Mode" value={linkedMode ? 'Enabled' : 'Disabled'} />
                    <InfoRow label="NSX-T" value={nsx.enabled ? 'Connected' : 'Not connected'} />
                    <InfoRow label="SRM" value={srm.enabled ? 'Configured' : 'Not configured'} />
                    <InfoRow label="VAMI patches pending" value={String(vami.pending_patches ?? 0)} />
                  </ContentPanel>
                  {!linkedMode && (
                    <div className="vm-panel-body border border-[#2d3a4a] rounded-lg p-3">
                      <p className="text-xs text-[#8FA5B8] mb-2">DC-DR is not visible until Enhanced Linked Mode is enabled.</p>
                      <button type="button" disabled={acting} onClick={() => runAction('enable_linked_mode')} className="vm-btn vm-btn-blue text-xs">
                        Enable Enhanced Linked Mode
                      </button>
                    </div>
                  )}
                </div>
              )}

              {selectedNode.type === 'vcenter' && activeTab === 'users' && (
                <VmwareUsersRolesPanel users={vcenterUsers} rolesCatalog={rolesCatalog} onAction={runAction} acting={acting} />
              )}

              {selectedNode.type === 'vcenter' && activeTab === 'alarms' && (
                <VmwareAlarmDefinitionsPanel alarmDefinitions={alarmDefinitions} onAction={runAction} acting={acting} />
              )}

              {selectedNode.type === 'datacenter' && activeTab === 'summary' && (
                <ContentPanel title={datacenters.find(d => d.id === selectedNode.id)?.name || 'Datacenter'}>
                  <InfoRow label="Site" value={datacenters.find(d => d.id === selectedNode.id)?.site || 'primary'} />
                  <InfoRow label="Linked" value={datacenters.find(d => d.id === selectedNode.id)?.linked !== false ? 'Yes' : 'No'} />
                  <InfoRow label="Hosts" value={String(hosts.filter(h => (h.datacenter_id || 'dc-prod') === selectedNode.id).length)} />
                  <InfoRow label="VMs" value={String(vms.filter(v => hosts.some(h => h.id === v.host_id && (h.datacenter_id || 'dc-prod') === selectedNode.id)).length)} />
                  <InfoRow label="Clusters" value={String((datacenters.find(d => d.id === selectedNode.id)?.clusters || []).length)} />
                  <div className="flex flex-wrap gap-2 mt-3">
                    <button type="button" onClick={() => setShowAddHostModal(true)} className="vm-btn vm-btn-blue text-xs">Add Host…</button>
                    <button type="button" onClick={() => setShowCreateClusterModal(true)} className="vm-btn text-xs">New Cluster…</button>
                    <button type="button" onClick={() => setShowResourcePoolModal(true)} className="vm-btn text-xs">New Resource Pool…</button>
                    <button type="button" onClick={() => setShowVappModal(true)} className="vm-btn text-xs">New vApp…</button>
                    <button type="button" onClick={() => setShowCreateDatastoreModal(true)} className="vm-btn text-xs">New Datastore…</button>
                    <button type="button" onClick={() => { setForceDvs(true); setShowCreateVswitchModal(true) }} className="vm-btn text-xs">New Distributed Switch…</button>
                    <button type="button" onClick={() => setFolderModalType('vm')} className="vm-btn text-xs">New Folder…</button>
                  </div>
                  {(datacenters.find(d => d.id === selectedNode.id)?.clusters || []).length > 0 && (
                    <table className="vm-table mt-3">
                      <thead><tr>{['Cluster', 'Hosts', 'HA', 'DRS', 'vSAN'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                      <tbody>
                        {(datacenters.find(d => d.id === selectedNode.id)?.clusters || []).map(c => (
                          <tr key={c.id}>
                            <td className="text-[#5b9bf5]">{c.name}</td>
                            <td>{(c.hosts || []).length}</td>
                            <td className={c.ha ? 'text-[#5DB85D]' : 'text-[#8fa5b8]'}>{c.ha ? 'On' : 'Off'}</td>
                            <td className={c.drs ? 'text-[#5DB85D]' : 'text-[#8fa5b8]'}>{c.drs ? 'On' : 'Off'}</td>
                            <td className={c.vsan ? 'text-[#5DB85D]' : 'text-[#8fa5b8]'}>{c.vsan ? 'On' : 'Off'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {/* Resource Pools */}
                  {resourcePools.length > 0 && (
                    <div className="mt-4">
                      <p className="text-[11px] font-semibold text-[#E8EDF2] mb-1">Resource Pools</p>
                      <table className="vm-table">
                        <thead><tr>{['Resource Pool', 'Parent', 'CPU Shares', 'Mem Shares', 'CPU Limit', ''].map(h => <th key={h || 'x'}>{h}</th>)}</tr></thead>
                        <tbody>
                          {resourcePools.map(rp => (
                            <tr key={rp.id}>
                              <td className="text-[#5b9bf5]">{rp.name}</td>
                              <td className="text-[#8FA5B8]">{rp.parent}</td>
                              <td className="capitalize">{rp.cpu_shares}</td>
                              <td className="capitalize">{rp.mem_shares}</td>
                              <td>{rp.cpu_limit_mhz === -1 ? 'Unlimited' : `${rp.cpu_limit_mhz} MHz`}</td>
                              <td>
                                <button type="button" disabled={acting} onClick={() => runAction('remove_resource_pool', { resource_pool_id: rp.id })}
                                  className="text-[10px] text-[#D9534F] hover:underline">Remove</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {/* vApps */}
                  {vapps.length > 0 && (
                    <div className="mt-4">
                      <p className="text-[11px] font-semibold text-[#E8EDF2] mb-1">vApps</p>
                      <table className="vm-table">
                        <thead><tr>{['vApp', 'Power', 'VMs', ''].map(h => <th key={h || 'x'}>{h}</th>)}</tr></thead>
                        <tbody>
                          {vapps.map(va => (
                            <tr key={va.id}>
                              <td className="text-[#5b9bf5]">{va.name}</td>
                              <td><span style={{ color: va.power === 'poweredOn' ? '#5DB85D' : '#8FA5B8' }}>{va.power}</span></td>
                              <td>{(va.vms || []).length}</td>
                              <td className="whitespace-nowrap">
                                <button type="button" disabled={acting} onClick={() => runAction('vapp_power', { vapp_id: va.id, op: va.power === 'poweredOn' ? 'off' : 'on' })}
                                  className="text-[10px] text-[#5b9bf5] hover:underline mr-2">{va.power === 'poweredOn' ? 'Power Off' : 'Power On'}</button>
                                <button type="button" disabled={acting} onClick={() => runAction('remove_vapp', { vapp_id: va.id })}
                                  className="text-[10px] text-[#D9534F] hover:underline">Delete</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {/* Folders */}
                  {folders.length > 0 && (
                    <div className="mt-4">
                      <p className="text-[11px] font-semibold text-[#E8EDF2] mb-1">Folders</p>
                      <div className="flex flex-wrap gap-2">
                        {folders.map(f => (
                          <span key={f.id} className="text-[11px] text-[#c3d3e3] bg-[#16222f] border border-[#22303f] rounded px-2 py-1">
                            📁 {f.name} <span className="text-[#8FA5B8]">({f.folder_type})</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </ContentPanel>
              )}

              {/* ── DATACENTER tabs ──────────────────────────────── */}
              {selectedNode.type === 'datacenter' && activeTab === 'datastores' && (
                <VmwareDatacenterDatastores
                  datastores={datastores}
                  datastoreClusters={datastoreClusters}
                  folders={folders}
                  onNewDatastore={() => setShowCreateDatastoreModal(true)}
                  onNewDatastoreCluster={() => setShowDatastoreClusterModal(true)}
                  onNewFolder={() => setFolderModalType('storage')}
                  onAction={runAction}
                  acting={acting}
                />
              )}
              {selectedNode.type === 'datacenter' && activeTab === 'hosts' && (
                <ContentPanel title={`Hosts in ${selectedDc?.name}`}>
                  <table className="vm-table">
                    <thead><tr>{['', 'Name', 'State', 'IP', 'CPU', 'Memory', 'Cluster'].map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
                    <tbody>
                      {hosts.filter(h => (h.datacenter_id || 'dc-prod') === selectedNode.id).map(h => (
                        <tr key={h.id} className="cursor-pointer" onClick={() => { setSelectedNode({ type: 'host', id: h.id }); setActiveTab('summary') }}
                          onContextMenu={(e) => openNodeContext(e, 'host', h)}>
                          <td><StatusIcon status={h.status} /></td>
                          <td className="text-[#5b9bf5]">{h.name}</td>
                          <td>{h.maintenance ? 'Maintenance' : h.status}</td>
                          <td className="text-[#8FA5B8] font-mono text-[10px]">{h.ip}</td>
                          <td>{h.cpu_pct}%</td>
                          <td>{h.mem_pct}%</td>
                          <td className="text-[#8FA5B8]">{(selectedDc?.clusters || []).find(c => (c.hosts || []).includes(h.id))?.name || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button type="button" onClick={() => setShowAddHostModal(true)} className="vm-btn vm-btn-blue text-[11px] mt-3">Add Host…</button>
                </ContentPanel>
              )}
              {selectedNode.type === 'datacenter' && activeTab === 'vms' && (
                <ContentPanel title={`Virtual Machines in ${selectedDc?.name}`}>
                  <VmTable vms={vms.filter(v => hosts.some(h => h.id === v.host_id && (h.datacenter_id || 'dc-prod') === selectedNode.id))}
                    onSelect={vm => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary') }}
                    onAction={runAction} acting={acting} />
                </ContentPanel>
              )}
              {selectedNode.type === 'datacenter' && activeTab === 'networks' && (
                <ContentPanel title={`Networks in ${selectedDc?.name}`}>
                  <table className="vm-table">
                    <thead><tr>{['Name', 'Type', 'VLAN', 'vSwitch', 'VMs'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                    <tbody>
                      {networks.map(net => (
                        <tr key={net.id} className="cursor-pointer" onContextMenu={(e) => openNodeContext(e, 'network', net)}
                          onClick={() => { setSelectedNode({ type: 'network', id: net.id }); setActiveTab('summary') }}>
                          <td className="text-[#5b9bf5]">{net.name}</td>
                          <td>{net.type}</td>
                          <td>{net.vlan === 0 ? 'All (0)' : net.vlan}</td>
                          <td className="text-[#8FA5B8]">{net.switch}</td>
                          <td>{vms.filter(v => v.network_id === net.id).length}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="flex gap-2 mt-3">
                    <button type="button" onClick={() => setShowCreatePortGroupModal(true)} className="vm-btn vm-btn-blue text-[11px]">New Port Group / VLAN…</button>
                    <button type="button" onClick={() => { setForceDvs(true); setShowCreateVswitchModal(true) }} className="vm-btn text-[11px]">New Distributed Switch…</button>
                  </div>
                </ContentPanel>
              )}
              {selectedNode.type === 'datacenter' && activeTab === 'permissions' && (
                <VmwarePermissionsPanel entityName={selectedDc?.name} entityId={selectedNode.id} entityType="datacenter"
                  permissions={permissions} rolesCatalog={rolesCatalog} onAction={runAction} acting={acting} />
              )}

              {/* ── ADMINISTRATION (Menu ▸ Administration) ───────── */}
              {((selectedNode.type === 'vcenter' && activeTab === 'administration') || selectedNode.type === 'admin') && (
                <VmwareAdministration users={vcenterUsers} rolesCatalog={rolesCatalog} permissions={permissions} inventory={inv} onAction={runAction} acting={acting} />
              )}

              {selectedNode.type === 'nsx' && activeTab === 'summary' && (
                <NsxMicroSegmentationPanel nsx={nsx} onAction={runAction} acting={acting} />
              )}

              {selectedNode.type === 'srm' && activeTab === 'summary' && (
                <SrmDisasterRecoveryPanel srm={srm} linkedMode={linkedMode} onAction={runAction} acting={acting} />
              )}

              {selectedNode.type === 'vami' && activeTab === 'summary' && (
                <VamiAppliancePanel vami={vami} vcenterVersion={inv.vcenter_version} onAction={runAction} acting={acting} />
              )}

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
                        <InfoRow label="DRS" value={<span className={summary.cluster_drs ? 'text-[#2db52d]' : 'text-[#8fa5b8]'}>{summary.cluster_drs ? 'Enabled' : 'Disabled'}</span>} />
                        {!summary.cluster_ha && (
                          <button type="button" onClick={() => runAction('enable_ha')} disabled={acting}
                            className="mt-1 w-full justify-center vm-btn vm-btn-blue text-[11px] py-1">
                            Enable HA
                          </button>
                        )}
                      </ContentPanel>
                      <ContentPanel title="Performance summary last hour">
                        <div className="flex items-center gap-3 mb-1 text-[10px]">
                          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#4c9be8]" /> Consumed host CPU</span>
                          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#9b59b6]" /> Consumed host memory</span>
                        </div>
                        <PerfChart cpuPct={selectedHost.cpu_pct} memPct={selectedHost.mem_pct} perfHistory={selectedHost.perf_history} />
                        <div className="flex justify-between text-[10px] text-[#8fa5b8] mt-1">
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
                          <div className="flex justify-between text-[11px] mb-1"><span className="font-semibold text-[#E8EDF2]">{label}</span><span className="text-[#8fa5b8]">{pct}%</span></div>
                          <UsageBar pct={pct} color={color} />
                          <p className="text-[10px] text-[#8fa5b8] mt-0.5">{detail}</p>
                        </div>
                      ))}
                    </div>
                  </ContentPanel>
                  <ContentPanel title="Performance charts">
                    <PerfChart cpuPct={selectedHost.cpu_pct} memPct={selectedHost.mem_pct} />
                  </ContentPanel>
                  <ContentPanel title="Alarms">
                    {activeAlarms.length === 0 ? (
                      <p className="text-[#8FA5B8] text-[11px]">No active alarms</p>
                    ) : activeAlarms.map(a => (
                      <div key={a.id} className="flex items-center gap-2 py-1.5 border-b border-[#22303f] last:border-0">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${a.severity === 'critical' ? 'bg-[rgba(217,83,79,.2)] text-[#D9534F]' : 'bg-[rgba(245,166,35,.2)] text-[#F5A623]'}`}>{a.severity}</span>
                        <span className="text-[11px] flex-1 text-[#E8EDF2]">{a.name}</span>
                        <span className="text-[10px] text-[#8FA5B8]">{a.entity}</span>
                        <button type="button" onClick={() => runAction('acknowledge_alarm', { alarm_id: a.id })} disabled={acting}
                          className="vm-btn text-[10px] py-0.5 px-2">Ack</button>
                      </div>
                    ))}
                  </ContentPanel>
                </div>
              )}

              {/* ── HOST CONFIGURE ───────────────────────────────── */}
              {selectedHost && activeTab === 'configure' && (
                <div className="space-y-3">
                  {/* Real vSphere Configure left sub-nav (Hardware / Networking /
                      Storage / System ▸ Licensing / Health) driven by host state. */}
                  <VmwareHostConfigurePanel
                    host={selectedHost}
                    datastores={datastores}
                    networks={networks}
                    vswitches={vswitches}
                    vms={vms}
                    licensing={licensing}
                    onAction={handleCtxAction}
                    acting={acting}
                  />
                  <ContentPanel title="Cluster settings">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-[11px] font-semibold mb-1 text-[#E8EDF2]">vSphere HA</p>
                        <div className="flex items-center gap-2">
                          <StatusIcon status={summary.cluster_ha ? 'connected' : 'disconnected'} />
                          <span className="text-[11px] text-[#E8EDF2]">{summary.cluster_ha ? 'Enabled' : 'Disabled'}</span>
                          {summary.cluster_ha
                            ? <button type="button" onClick={() => runAction('disable_ha')} disabled={acting} className="ml-auto vm-btn text-[11px] py-0.5 px-2.5">Disable</button>
                            : <button type="button" onClick={() => runAction('enable_ha')} disabled={acting} className="ml-auto vm-btn vm-btn-blue text-[11px] py-0.5 px-2.5">Enable</button>
                          }
                        </div>
                      </div>
                      <div>
                        <p className="text-[11px] font-semibold mb-1 text-[#E8EDF2]">vSphere DRS</p>
                        <div className="flex items-center gap-2">
                          <StatusIcon status={summary.cluster_drs ? 'connected' : 'disconnected'} />
                          <span className="text-[11px] text-[#E8EDF2]">{summary.cluster_drs ? 'Enabled' : 'Disabled'}</span>
                          {!summary.cluster_drs && (
                            <button type="button" onClick={() => runAction('enable_drs')} disabled={acting} className="ml-auto vm-btn vm-btn-blue text-[11px] py-0.5 px-2.5">Enable</button>
                          )}
                          {summary.cluster_drs && (
                            <>
                              <button type="button" onClick={() => runAction('run_drs')} disabled={acting} className="ml-auto vm-btn vm-btn-blue text-[11px] py-0.5 px-2.5">Run DRS</button>
                              <button type="button" onClick={() => runAction('disable_drs')} disabled={acting} className="vm-btn text-[11px] py-0.5 px-2.5">Disable</button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </ContentPanel>
                  <ContentPanel title="Host network adapters (vmnic)">
                    <table className="vm-table">
                      <thead>
                        <tr>{['Device', 'MAC address', 'Driver', 'Speed', 'Switch', 'Status', 'PCI'].map(h => <th key={h}>{h}</th>)}</tr>
                      </thead>
                      <tbody>
                        {(selectedHost.vmnics || []).map(vn => (
                          <tr key={vn.id}>
                            <td className="text-[#5b9bf5] font-semibold">{vn.name}</td>
                            <td className="font-mono text-[10px] text-[#8FA5B8]">{vn.mac_address}</td>
                            <td className="text-[#8FA5B8]">{vn.driver}</td>
                            <td>{vn.speed_mbps >= 1000 ? `${vn.speed_mbps / 1000} Gbps` : `${vn.speed_mbps} Mbps`}</td>
                            <td>{vn.switch}</td>
                            <td className={vn.status === 'up' ? 'text-[#5DB85D] font-semibold' : 'text-[#D9534F]'}>{vn.status}</td>
                            <td className="font-mono text-[10px] text-[#8FA5B8]">{vn.pci_id}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="flex gap-2 mt-3 mb-1">
                      <button type="button" onClick={() => setShowCreateVswitchModal(true)} disabled={acting} className="vm-btn vm-btn-blue text-[11px]">New vSwitch…</button>
                      <button type="button" onClick={() => setShowCreatePortGroupModal(true)} disabled={acting} className="vm-btn text-[11px]">New Port Group / VLAN…</button>
                      <button type="button" onClick={() => runAction('add_host_uplink', { host_id: selectedHost.id })} disabled={acting} className="vm-btn text-[11px]">Add uplink (vmnic)</button>
                    </div>
                    {(inv.vswitches || []).map(vsw => (
                      <div key={vsw.id} className="border border-[#2D3A4A] rounded p-2.5 mb-2 mt-3 bg-[#16222f]">
                        <div className="flex items-center gap-2">
                          <p className="text-[11px] font-semibold text-[#E8EDF2] m-0">{vsw.name} <span className="text-[10px] text-[#8FA5B8] font-normal">({vsw.type})</span></p>
                          <div className="flex-1" />
                          {vsw.name !== 'vSwitch0' && (
                            <button type="button" disabled={acting}
                              onClick={() => runAction('remove_vswitch', { vswitch_id: vsw.id })}
                              className="vm-btn vm-btn-red text-[10px] py-0.5 px-2">Remove</button>
                          )}
                        </div>
                        <div className="grid grid-cols-3 gap-1 mt-1 text-[10px] text-[#8FA5B8]">
                          <span>Ports: {vsw.ports}</span>
                          <span>MTU: {vsw.mtu}</span>
                          <span>Uplinks: {vsw.uplinks?.join(', ') || '—'}</span>
                        </div>
                        <p className="text-[10px] text-[#8FA5B8] mt-0.5">Port groups: {vsw.portgroups?.join(', ') || '—'}</p>
                      </div>
                    ))}
                  </ContentPanel>
                  <VmwareScenarioActions selectedVm={selectedVm} onAction={runAction} acting={acting} />
                  <VmwareDvsEditor vswitches={vswitches} onAction={runAction} acting={acting} />
                  <VmwareVsanDashboard vsan={vsan} clusterVsan={summary.cluster_vsan || inv.cluster_vsan} onAction={runAction} acting={acting} />
                  <VmwareAlarmDefinitionsPanel alarmDefinitions={alarmDefinitions} onAction={runAction} acting={acting} />
                </div>
              )}

              {/* ── TEMPLATE SUMMARY ─────────────────────────────── */}
              {selectedTemplate && activeTab === 'summary' && (
                <div className="space-y-3">
                  <ContentPanel title="Template details">
                    <InfoRow label="Name" value={selectedTemplate.name} />
                    <InfoRow label="Guest OS" value={selectedTemplate.guest_os_version || selectedTemplate.guest_os} />
                    <InfoRow label="CPUs" value={selectedTemplate.cpu} />
                    <InfoRow label="Memory" value={fmtMb(selectedTemplate.memory_mb || 4096)} />
                    <InfoRow label="Disk" value={fmtBytes(selectedTemplate.disk_gb || 40)} />
                    <div className="flex gap-2 mt-3">
                      <button type="button" onClick={() => setShowDeployTemplateModal(true)} className="vm-btn vm-btn-blue text-xs">Deploy VM from Template…</button>
                      <button type="button" onClick={() => runAction('convert_template', { template_name: selectedTemplate.name })} disabled={acting} className="vm-btn text-xs">Convert to VM</button>
                    </div>
                  </ContentPanel>
                </div>
              )}

              {/* ── HOST PERMISSIONS ─────────────────────────────── */}
              {selectedHost && activeTab === 'permissions' && (
                <VmwarePermissionsPanel entityName={selectedHost.name} entityId={selectedHost.id} entityType="host"
                  permissions={permissions} rolesCatalog={rolesCatalog} onAction={runAction} acting={acting} />
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
                            onContextMenu={(e) => openNodeContext(e, 'datastore', ds)}
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
                          onContextMenu={(e) => openNodeContext(e, 'network', net)}
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
                  <div className="flex gap-2 mt-3">
                    <button type="button" onClick={() => setShowCreatePortGroupModal(true)} className="vm-btn vm-btn-blue text-[11px]">Add port group / VLAN…</button>
                    <button type="button" onClick={() => setShowCreateVswitchModal(true)} className="vm-btn text-[11px]">Add vSwitch…</button>
                  </div>
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
                      { label: 'Resume', action: 'resume', show: selectedVm.power === 'suspended', green: true },
                      { label: 'Take Snapshot', action: '__snapshot__', show: true },
                      { label: 'Manage Snapshots', action: '__manage_snapshots__', show: true },
                      { label: 'Upgrade VMware Tools', action: 'upgrade_vmware_tools', show: (selectedVm.vmware_tools_status || (selectedVm.tools === 'ok' ? 'current' : 'notRunning')) !== 'current', amber: true },
                      { label: 'Launch Console', action: '__console__', show: true, blue: true },
                    ].filter(a => a.show).map(a => (
                      <button
                        key={a.label}
                        type="button"
                        disabled={acting}
                        onClick={() => {
                          if (a.action === '__snapshot__') setShowSnapshotModal(true)
                          else if (a.action === '__manage_snapshots__') { setActiveTab('snapshots'); setShowSnapshotManager(true) }
                          else if (a.action === '__console__') setConsoleVm(selectedVm)
                          else runAction(a.action, { vm_id: selectedVm.id })
                        }}
                        className={`vm-btn text-[11.5px] py-1.5 px-3 ${a.green ? 'vm-btn-green' : a.red ? 'vm-btn-red' : a.blue ? 'vm-btn-blue' : a.amber ? 'vm-btn-amber' : ''}`}
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
                      <InfoRow
                        label="VMware Tools"
                        value={(() => {
                          const ts = selectedVm.vmware_tools_status || (selectedVm.tools === 'ok' ? 'current' : 'notRunning')
                          const text = ts === 'current' ? 'Running (current)' : ts === 'upgradeAvailable' ? 'Upgrade available' : 'Not running'
                          return (
                            <span className="flex items-center gap-2">
                              <span style={{ color: ts === 'current' ? '#5DB85D' : ts === 'upgradeAvailable' ? '#F5A623' : '#D9534F' }}>{text}</span>
                              {ts !== 'current' && (
                                <button type="button" disabled={acting}
                                  onClick={() => runAction('upgrade_vmware_tools', { vm_id: selectedVm.id })}
                                  className="vm-btn vm-btn-amber text-[10px] py-0.5 px-2">Upgrade</button>
                              )}
                            </span>
                          )
                        })()}
                      />
                      <InfoRow label="VM hardware" value={selectedVm.hardware_version} />
                      <InfoRow label="Annotation" value={selectedVm.annotation || '—'} />
                    </ContentPanel>
                    {(selectedVm.disks?.length > 0) && (
                      <ContentPanel title="Virtual disks">
                        <table className="vm-table">
                          <thead>
                            <tr>{['Disk', 'SCSI ID', 'Size', 'Mode', 'Datastore', ''].map((h, hi) => <th key={hi}>{h}</th>)}</tr>
                          </thead>
                          <tbody>
                            {selectedVm.disks.map((d, i) => (
                              <tr key={d.id || i}>
                                <td>{d.label || `Hard disk ${i + 1}`}</td>
                                <td className="font-mono text-[10px] text-[#8FA5B8]">{d.scsi_id || `${d.scsi_controller || 0}:${d.scsi_unit ?? i}`}</td>
                                <td>{d.capacity_gb} GB</td>
                                <td>{d.thin_provisioned ? 'Thin' : 'Thick'}</td>
                                <td className="text-[#5b9bf5]">{datastores.find(ds => ds.id === d.datastore_id)?.name || d.datastore_id}</td>
                                <td className="text-right">
                                  {(d.scsi_id !== '0:0') && (
                                    <button type="button" disabled={acting}
                                      onClick={() => runAction('remove_disk', { vm_id: selectedVm.id, disk_id: d.id })}
                                      className="vm-btn vm-btn-red text-[10px] py-0.5 px-2">Remove</button>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <button type="button" disabled={acting} onClick={() => setShowAddDiskModal(true)}
                          className="mt-2 vm-btn vm-btn-blue text-[11px]">Add disk…</button>
                      </ContentPanel>
                    )}
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
                            <tr key={t.id || i} className="cursor-pointer" title="Click for task details" onClick={() => openTaskDetail(t)}>
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
                        <PerfChart cpuPct={selectedVm.cpu_pct} memPct={0} perfHistory={selectedVm.perf_history ? { cpu: selectedVm.perf_history.cpu, mem: [] } : null} />
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
                        <PerfChart cpuPct={0} memPct={selectedVm.mem_pct} perfHistory={selectedVm.perf_history ? { cpu: [], mem: selectedVm.perf_history.mem } : null} />
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
                              <tr key={t.id || i} className="cursor-pointer" title="Click for task details" onClick={() => openTaskDetail(t)}>
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
                              <tr key={i} className="cursor-pointer" title="Click for event details" onClick={() => openEventDetail(ev)}>
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
                  datastores={datastores}
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
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setShowSnapshotModal(true)} disabled={acting} className="vm-btn vm-btn-blue text-[11px] py-1 px-3">
                        Take snapshot
                      </button>
                      <button type="button" onClick={() => setShowSnapshotManager(true)} disabled={acting} className="vm-btn text-[11px] py-1 px-3">
                        Open manager
                      </button>
                    </div>
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
                <VmwarePermissionsPanel entityName={selectedVm.name} entityId={selectedVm.id} entityType="vm"
                  permissions={permissions} rolesCatalog={rolesCatalog} onAction={runAction} acting={acting} />
              )}
              {selectedVm && activeTab === 'networks' && (
                <ContentPanel title={`Network adapters — ${selectedVm.name}`}>
                  <table className="vm-table">
                    <thead>
                      <tr>
                        {['Adapter', 'Network', 'VLAN', 'MAC address', 'Status', 'Type', 'Port group', ''].map((h, hi) => <th key={hi}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedVm.nics?.length ? selectedVm.nics : [{
                        label: 'Network adapter 1',
                        network_id: selectedVm.network_id,
                        mac_address: selectedVm.mac,
                        adapter_type: 'Vmxnet3',
                        connected: !selectedVm.network_disconnected,
                      }]).map((nic, i) => {
                        const net = networks.find(n => n.id === (nic.network_id || selectedVm.network_id))
                        const canRemove = nic.id && (selectedVm.nics?.length || 0) > 1
                        return (
                          <tr key={nic.id || i}>
                            <td>{nic.label || `Network adapter ${i + 1}`}</td>
                            <td className="text-[#5b9bf5]">{nic.network_name || net?.name || 'VM Network'}</td>
                            <td className="font-mono text-[#8FA5B8]">{nic.vlan_id ?? net?.vlan_id ?? net?.vlan ?? '—'}</td>
                            <td className="font-mono text-[#8FA5B8]">{nic.mac_address || nic.mac || '—'}</td>
                            <td className={nic.connected !== false ? 'text-[#5DB85D] font-semibold' : 'text-[#D9534F] font-semibold'}>
                              {nic.connected !== false ? 'Connected' : 'Disconnected'}
                            </td>
                            <td className="text-[#8FA5B8]">{nic.adapter_type || 'VMXNET3'}</td>
                            <td className="font-mono text-[10px] text-[#8FA5B8]">{nic.portgroup_key || net?.portgroup_key || '—'}</td>
                            <td className="text-right">
                              {canRemove && (
                                <button type="button" disabled={acting}
                                  onClick={() => runAction('remove_nic', { vm_id: selectedVm.id, nic_id: nic.id })}
                                  className="vm-btn vm-btn-red text-[10px] py-0.5 px-2">Remove</button>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  <button type="button" onClick={() => setShowAddNicModal(true)} className="mt-3 vm-btn vm-btn-blue text-[11px]">Add network adapter…</button>
                </ContentPanel>
              )}
              {selectedVm && activeTab === 'updates' && (
                <VmwareLifecyclePanel target={selectedVm} targetType="vm" updates={inv.updates} onAction={runAction} acting={acting} />
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
                <div className="space-y-3">
                  <ContentPanel title={`ESXi local users — ${selectedHost.name}`}>
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
                  <VmwareUsersRolesPanel users={vcenterUsers} rolesCatalog={rolesCatalog} onAction={runAction} acting={acting} />
                </div>
              )}

              {/* ── HOST UPDATES ─────────────────────────────────── */}
              {selectedHost && activeTab === 'updates' && (
                <VmwareLifecyclePanel target={selectedHost} targetType="host" updates={inv.updates} onAction={runAction} acting={acting} />
              )}

              {/* ── DATASTORE ────────────────────────────────────── */}
              {selectedDs && activeTab === 'summary' && (
                <div className="space-y-3">
                  {selectedDs.warning === 'critical' && (
                    <div className="rounded-lg border border-[#D9534F]/50 bg-[rgba(217,83,79,.12)] px-3 py-2 text-xs text-[#f5a0a0] flex items-center gap-2">
                      <span className="font-bold uppercase text-[10px]">Alarm</span>
                      Datastore space usage is critically high — only {fmtBytes(selectedDs.free_gb)} ({selectedDs.free_pct ?? (((selectedDs.free_gb) / selectedDs.capacity_gb) * 100).toFixed(0)}%) free
                    </div>
                  )}
                  {selectedDs.warning === 'warning' && (
                    <div className="rounded-lg border border-[#F5A623]/50 bg-[rgba(245,166,35,.12)] px-3 py-2 text-xs text-[#f5c97a] flex items-center gap-2">
                      <span className="font-bold uppercase text-[10px]">Warning</span>
                      Datastore free space is below 15% — only {fmtBytes(selectedDs.free_gb)} ({selectedDs.free_pct ?? (((selectedDs.free_gb) / selectedDs.capacity_gb) * 100).toFixed(0)}%) free
                    </div>
                  )}
                  <ContentPanel title="Datastore details">
                    <InfoRow label="Type" value={selectedDs.type} />
                    <InfoRow label="Version" value={selectedDs.version} />
                    <InfoRow label="VMFS UUID" value={<span className="font-mono text-[10px]">{selectedDs.vmfs_uuid || '—'}</span>} />
                    <InfoRow label="Extent (NAA)" value={<span className="font-mono text-[10px]">{selectedDs.extent_name || '—'}</span>} />
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
                    <button type="button" onClick={() => runAction('expand_datastore', { datastore: selectedDs.name, gb: 500 })} disabled={acting}
                      className="mt-2 vm-btn vm-btn-blue text-[11px]">
                      Increase capacity (+500 GB)
                    </button>
                  </ContentPanel>
                </div>
              )}

              {/* ── DATASTORE MONITOR ────────────────────────────── */}
              {selectedDs && activeTab === 'permissions' && (
                <VmwarePermissionsPanel entityName={selectedDs.name} entityId={selectedDs.id} entityType="datastore"
                  permissions={permissions} rolesCatalog={rolesCatalog} onAction={runAction} acting={acting} />
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
                <VmwarePermissionsPanel entityName={selectedNet.name} entityId={selectedNet.id} entityType="network"
                  permissions={permissions} rolesCatalog={rolesCatalog} onAction={runAction} acting={acting} />
              )}

              {selectedNet && activeTab === 'summary' && (
                <ContentPanel title="Network / port group details">
                  <InfoRow label="Type" value={selectedNet.type === 'distributed' ? 'Distributed port group' : 'Standard port group'} />
                  <InfoRow label="VLAN ID" value={(selectedNet.vlan_id ?? selectedNet.vlan) === 0 ? 'All (0)' : String(selectedNet.vlan_id ?? selectedNet.vlan)} />
                  <InfoRow label="Port group key" value={<span className="font-mono text-[10px]">{selectedNet.portgroup_key || '—'}</span>} />
                  <InfoRow label="vSwitch / DVS" value={selectedNet.switch} />
                  <InfoRow label="Active ports" value={`${selectedNet.active_ports ?? '—'} / ${selectedNet.num_ports ?? '—'}`} />
                  <InfoRow label="Connected hosts" value={selectedNet.hosts?.length || 0} />
                  {selectedNet.type === 'distributed' && (
                    <>
                      <InfoRow label="Promiscuous mode" value={selectedNet.security_promiscuous ? 'Accept' : 'Reject'} />
                      <InfoRow label="MAC address changes" value={selectedNet.security_mac_changes ? 'Accept' : 'Reject'} />
                      <InfoRow label="Forged transmits" value={selectedNet.security_forged_transmits ? 'Accept' : 'Reject'} />
                      <InfoRow label="Teaming policy" value={selectedNet.uplink_teaming || 'loadbalance_srcid'} />
                    </>
                  )}
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
                          <tr key={i} className="cursor-pointer" title="Click for event details"
                            onClick={() => openEventDetail(ev)}>
                            <td className="font-mono whitespace-nowrap text-[#8FA5B8]">{ev.time?.slice(11, 19)}</td>
                            <td>
                              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${ev.severity === 'critical' ? 'bg-[rgba(217,83,79,.2)] text-[#D9534F]' : ev.severity === 'warning' ? 'bg-[rgba(245,166,35,.2)] text-[#F5A623]' : 'bg-[rgba(93,184,93,.2)] text-[#5DB85D]'}`}>
                                {ev.severity.toUpperCase()}
                              </span>
                            </td>
                            <td className="text-[#5b9bf5] underline decoration-dotted underline-offset-2">{ev.entity}</td>
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
                    <tr key={t.id || i} className="cursor-pointer" title="Click for task details"
                      onClick={() => openTaskDetail(t)}>
                      <td className="whitespace-nowrap">{t.name}</td>
                      <td className="text-[#5b9bf5] underline decoration-dotted underline-offset-2">{t.target}</td>
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
        <VmwareConsole vm={consoleVm} labSessionId={sessionId} onClose={() => setConsoleVm(null)} onGuestAction={handleGuestAction} />
      )}
      {ctxMenu && (
        <VmwareContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          kind={ctxMenu.kind || 'vm'}
          vm={ctxMenu.vm}
          node={ctxMenu.node}
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

      {detailItem && (
        <TaskEventDetailModal item={detailItem} onClose={() => setDetailItem(null)} />
      )}

      {/* Modals */}
      {showSnapshotModal && selectedVm && (
        <SnapshotModal vm={selectedVm} onClose={() => setShowSnapshotModal(false)} onAction={runAction} />
      )}
      {showSnapshotManager && selectedVm && (
        <SnapshotManagerModal vm={selectedVm} onClose={() => setShowSnapshotManager(false)} onAction={runAction} acting={acting} />
      )}
      {showMigrateModal && selectedVm && (
        <MigrateModal vm={selectedVm} hosts={hosts} onClose={() => setShowMigrateModal(false)} onAction={runAction} />
      )}
      {showCreateVmModal && (
        <CreateVmModal hosts={hosts} datastores={datastores} networks={networks}
          onClose={() => setShowCreateVmModal(false)} onAction={runAction} />
      )}
      {showCreateVmWizard && (
        <VmCreateWizard
          hosts={hosts}
          datastores={datastores}
          networks={networks}
          resourcePools={resourcePools}
          onClose={() => setShowCreateVmWizard(false)}
          onAction={runAction}
        />
      )}
      {showEditVmModal && selectedVm && (
        <EditVmModal vm={selectedVm} networks={networks} datastores={datastores}
          onAddDisk={() => setShowAddDiskModal(true)}
          onAddNic={() => setShowAddNicModal(true)}
          onClose={() => setShowEditVmModal(false)} onAction={runAction} />
      )}
      {showCloneVmModal && selectedVm && (
        <CloneVmModal vm={selectedVm} onClose={() => setShowCloneVmModal(false)} onAction={runAction} />
      )}
      {showDeployTemplateModal && templates.length > 0 && (
        <DeployFromTemplateModal templates={templates} hosts={hosts}
          onClose={() => setShowDeployTemplateModal(false)} onAction={runAction} />
      )}
      {showVmotionWizard && selectedVm && (
        <VmotionWizard vm={selectedVm} hosts={hosts} onClose={() => setShowVmotionWizard(false)} onAction={runAction} />
      )}
      {showStorageVmotionWizard && selectedVm && (
        <StorageVmotionWizard vm={selectedVm} datastores={datastores}
          onClose={() => setShowStorageVmotionWizard(false)} onAction={runAction} onRefresh={load} />
      )}
      {showOvfModal && contentLibrary.length > 0 && (
        <VmwareOvfDeployModal contentLibrary={contentLibrary} hosts={hosts} datastores={datastores} networks={networks}
          onClose={() => setShowOvfModal(false)} onAction={runAction} />
      )}
      {showAddDiskModal && selectedVm && (
        <AddDiskModal vm={selectedVm} datastores={datastores}
          onClose={() => setShowAddDiskModal(false)} onAction={runAction} />
      )}
      {showAddNicModal && selectedVm && (
        <AddNicModal vm={selectedVm} networks={networks}
          onClose={() => setShowAddNicModal(false)} onAction={runAction} />
      )}
      {showCreateVswitchModal && (
        <CreateVswitchModal hosts={hosts} defaultType={forceDvs ? 'distributed' : 'standard'}
          onClose={() => { setShowCreateVswitchModal(false); setForceDvs(false) }} onAction={runAction} />
      )}
      {showCreatePortGroupModal && (
        <CreatePortGroupModal vswitches={vswitches}
          onClose={() => setShowCreatePortGroupModal(false)} onAction={runAction} />
      )}
      {showCreateDatastoreModal && (
        <CreateDatastoreModal
          onClose={() => setShowCreateDatastoreModal(false)} onAction={runAction} />
      )}
      {showCreateClusterModal && (
        <CreateClusterModal datacenters={datacenters}
          onClose={() => setShowCreateClusterModal(false)} onAction={runAction} />
      )}
      {showAddHostModal && (
        <AddHostModal datacenters={datacenters}
          onClose={() => setShowAddHostModal(false)} onAction={runAction} />
      )}
      {showResourcePoolModal && (
        <CreateResourcePoolModal parentName={inv.cluster || 'Cluster-01'}
          onClose={() => setShowResourcePoolModal(false)} onAction={runAction} />
      )}
      {showVappModal && (
        <CreateVappModal parentName={inv.cluster || 'Cluster-01'} vms={vms}
          onClose={() => setShowVappModal(false)} onAction={runAction} />
      )}
      {showDatastoreClusterModal && (
        <CreateDatastoreClusterModal datastores={datastores}
          onClose={() => setShowDatastoreClusterModal(false)} onAction={runAction} />
      )}
      {folderModalType && (
        <CreateFolderModal folderType={folderModalType} datacenters={datacenters}
          onClose={() => setFolderModalType(null)} onAction={runAction} />
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
  if (type === 'template') return ['summary']
  if (type === 'vcenter') return ['summary', 'administration', 'users', 'alarms']
  if (type === 'datacenter') return ['summary', 'hosts', 'vms', 'datastores', 'networks', 'permissions']
  if (type === 'admin') return ['summary']
  if (type === 'nsx' || type === 'srm' || type === 'vami') return ['summary']
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
        <button type="button" onClick={() => toast('Permission added')} className="vm-btn vm-btn-blue text-[11px]">Add permission…</button>
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
