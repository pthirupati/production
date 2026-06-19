import { useMemo, useState } from 'react'

const STEPS = [
  'Creation type',
  'Name and location',
  'Compute resource',
  'Storage',
  'Compatibility',
  'Guest OS',
  'Customize hardware',
  'CPU',
  'Memory',
  'Storage disk',
  'Network',
  'VM options',
  'Ready to complete',
  'Finishing',
]

const GUEST_OS = [
  'Ubuntu Linux (64-bit)',
  'Red Hat Enterprise Linux 8 (64-bit)',
  'CentOS 7 (64-bit)',
  'Windows Server 2019 (64-bit)',
  'Debian GNU/Linux 11 (64-bit)',
  'Other Linux (64-bit)',
]

export default function VmCreateWizard({ hosts, datastores, networks, resourcePools = [], onClose, onAction }) {
  const [step, setStep] = useState(0)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    creationType: 'Create a new virtual machine',
    name: '',
    hostId: hosts.find(h => h.status === 'connected' && !h.maintenance)?.id || '',
    datastoreId: datastores.find(d => d.accessible)?.id || '',
    hwVersion: 'vmx-19',
    guestOs: GUEST_OS[0],
    cpu: 2,
    memoryMb: 4096,
    diskGb: 40,
    networkId: networks[0]?.id || '',
    resourcePoolId: resourcePools[0]?.id || 'rp-prod',
    firmware: 'BIOS',
    cdDvd: 'Client Device',
    powerOn: false,
    annotation: '',
  })

  const connectedHosts = useMemo(
    () => hosts.filter(h => h.status === 'connected' && !h.maintenance),
    [hosts],
  )

  const set = (patch) => setForm(f => ({ ...f, ...patch }))

  const next = () => {
    if (step === 1 && !form.name.trim()) {
      setError('VM name is required')
      return
    }
    setError('')
    if (step === 12) {
      finish()
      return
    }
    setStep(s => Math.min(s + 1, STEPS.length - 1))
  }

  const back = () => {
    setError('')
    setStep(s => Math.max(s - 1, 0))
  }

  const finish = async () => {
    setActing(true)
    setStep(13)
    setError('')
    try {
      await onAction('create_vm_wizard', {
        name: form.name.trim(),
        host_id: form.hostId,
        datastore_id: form.datastoreId,
        network_id: form.networkId,
        resource_pool_id: form.resourcePoolId,
        guest_os: form.guestOs,
        guest_os_version: form.guestOs,
        cpu: form.cpu,
        memory_mb: form.memoryMb,
        disk_gb: form.diskGb,
        hardware_version: form.hwVersion,
        firmware: form.firmware,
        cd_dvd: form.cdDvd,
        power: form.powerOn ? 'poweredOn' : 'poweredOff',
        annotation: form.annotation || 'Created via New Virtual Machine wizard',
      })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Wizard failed')
      setStep(12)
    } finally {
      setActing(false)
    }
  }

  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <div className="space-y-2">
            <p className="text-xs text-[#8fa5b8]">Select the type of creation for your new virtual machine.</p>
            {['Create a new virtual machine', 'Deploy from template', 'Register an existing VM'].map(opt => (
              <label key={opt} className="flex items-center gap-2 text-sm text-[#E8EDF2] cursor-pointer">
                <input
                  type="radio"
                  checked={form.creationType === opt}
                  onChange={() => set({ creationType: opt })}
                  disabled={opt !== 'Create a new virtual machine'}
                />
                {opt}
                {opt !== 'Create a new virtual machine' && <span className="text-[10px] text-[#8fa5b8]">(use inventory actions)</span>}
              </label>
            ))}
          </div>
        )
      case 1:
        return (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Virtual machine name</label>
              <input value={form.name} onChange={e => set({ name: e.target.value })} className="vm-input !pl-3" placeholder="app-server-01" />
            </div>
            <p className="text-xs text-[#8fa5b8]">Location: DC-Prod / Cluster-01 / Production</p>
          </div>
        )
      case 2:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Compute resource</label>
            <select value={form.hostId} onChange={e => set({ hostId: e.target.value })} className="vm-input !pl-3">
              {connectedHosts.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
        )
      case 3:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Datastore</label>
            <select value={form.datastoreId} onChange={e => set({ datastoreId: e.target.value })} className="vm-input !pl-3">
              {datastores.filter(d => d.accessible).map(d => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
        )
      case 4:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Virtual hardware compatibility</label>
            <select value={form.hwVersion} onChange={e => set({ hwVersion: e.target.value })} className="vm-input !pl-3">
              {['vmx-19', 'vmx-18', 'vmx-17'].map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
        )
      case 5:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Guest OS family</label>
            <select value={form.guestOs} onChange={e => set({ guestOs: e.target.value })} className="vm-input !pl-3">
              {GUEST_OS.map(o => <option key={o}>{o}</option>)}
            </select>
          </div>
        )
      case 6:
        return <p className="text-sm text-[#E8EDF2]">Customize hardware for CPU, memory, disk, and network in the next steps.</p>
      case 7:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Number of virtual CPUs</label>
            <select value={form.cpu} onChange={e => set({ cpu: parseInt(e.target.value, 10) })} className="vm-input !pl-3">
              {[1, 2, 4, 8, 16].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        )
      case 8:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Memory (MB)</label>
            <select value={form.memoryMb} onChange={e => set({ memoryMb: parseInt(e.target.value, 10) })} className="vm-input !pl-3">
              {[1024, 2048, 4096, 8192, 16384, 32768].map(n => <option key={n} value={n}>{n / 1024} GB</option>)}
            </select>
          </div>
        )
      case 9:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">New hard disk (GB)</label>
            <input type="number" min={10} value={form.diskGb} onChange={e => set({ diskGb: parseInt(e.target.value, 10) || 40 })} className="vm-input !pl-3" />
          </div>
        )
      case 10:
        return (
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Network adapter</label>
            <select value={form.networkId} onChange={e => set({ networkId: e.target.value })} className="vm-input !pl-3">
              {networks.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
            </select>
          </div>
        )
      case 11:
        return (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Firmware</label>
              <select value={form.firmware} onChange={e => set({ firmware: e.target.value })} className="vm-input !pl-3">
                <option>BIOS</option>
                <option>EFI</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-[#E8EDF2]">
              <input type="checkbox" checked={form.powerOn} onChange={e => set({ powerOn: e.target.checked })} />
              Power on VM after creation
            </label>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Notes</label>
              <textarea value={form.annotation} onChange={e => set({ annotation: e.target.value })} rows={2} className="vm-input resize-none !pl-3" />
            </div>
          </div>
        )
      case 12:
        return (
          <div className="text-sm text-[#E8EDF2] space-y-1">
            <p><strong>Name:</strong> {form.name}</p>
            <p><strong>Host:</strong> {connectedHosts.find(h => h.id === form.hostId)?.name}</p>
            <p><strong>Guest OS:</strong> {form.guestOs}</p>
            <p><strong>CPU / Memory / Disk:</strong> {form.cpu} vCPU · {form.memoryMb / 1024} GB · {form.diskGb} GB</p>
          </div>
        )
      case 13:
        return (
          <div className="text-center py-6">
            <div className="w-10 h-10 border-2 border-[#2D7CFF] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-[#E8EDF2]">{acting ? 'Creating virtual machine…' : 'Complete'}</p>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[560px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>New Virtual Machine Wizard — Step {step + 1} of 14: {STEPS[step]}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="px-4 pt-2">
          <div className="h-1 bg-[#2d3a4a] rounded overflow-hidden">
            <div className="h-full bg-[#2D7CFF] transition-all" style={{ width: `${((step + 1) / 14) * 100}%` }} />
          </div>
        </div>
        <div className="vm-modal-body min-h-[180px]">{renderStep()}</div>
        {error && <p className="px-4 pb-2 text-xs text-[#D9534F]">{error}</p>}
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          {step > 0 && step < 13 && (
            <button type="button" onClick={back} className="vm-btn">Back</button>
          )}
          {step < 13 && (
            <button type="button" disabled={acting} onClick={next} className="vm-btn vm-btn-blue">
              {step === 12 ? 'Finish' : 'Next'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
