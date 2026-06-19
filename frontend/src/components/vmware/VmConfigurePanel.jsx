import { useEffect, useState } from 'react'

/** VM Configure tab — Claude mockup sliders + save banner. */
export default function VmConfigurePanel({ vm, networks, acting, onSave, onAddDisk, onEditNetwork }) {
  const [cpu, setCpu] = useState(vm.cpu)
  const [memGb, setMemGb] = useState(Math.round(vm.memory_mb / 1024))
  const [name, setName] = useState(vm.name)
  const [notes, setNotes] = useState(vm.annotation || '')
  const poweredOn = vm.power === 'poweredOn'

  useEffect(() => {
    setCpu(vm.cpu)
    setMemGb(Math.round(vm.memory_mb / 1024))
    setName(vm.name)
    setNotes(vm.annotation || '')
  }, [vm.id, vm.cpu, vm.memory_mb, vm.name, vm.annotation])

  const unsaved = name !== vm.name || notes !== (vm.annotation || '')
    || (!poweredOn && (cpu !== vm.cpu || memGb !== Math.round(vm.memory_mb / 1024)))

  const save = () => {
    const payload = { vm_id: vm.id, annotation: notes }
    if (!poweredOn) {
      payload.cpu = cpu
      payload.memory_mb = memGb * 1024
    }
    onSave(payload)
  }

  return (
    <div className="space-y-3.5">
      {unsaved && (
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-[rgba(245,166,35,.12)] border border-[rgba(245,166,35,.4)]">
          <span className="text-[#F5A623] text-xs font-semibold">You have unsaved changes</span>
          <div className="flex-1" />
          <button type="button" onClick={save} disabled={acting} className="vm-btn vm-btn-blue text-xs py-1.5 px-4">
            Save all
          </button>
        </div>
      )}

      <div className="vm-panel">
        <div className="vm-panel-header">VM options</div>
        <div className="vm-panel-body space-y-3.5">
          <div>
            <label className="block text-[11px] text-[#8FA5B8] mb-1.5">Name</label>
            <input value={name} onChange={e => setName(e.target.value)} className="vm-input !pl-3 max-w-xs" />
          </div>
          <div>
            <label className="block text-[11px] text-[#8FA5B8] mb-1.5">Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} placeholder="Add notes…" className="vm-input !pl-3 resize-none max-w-md" />
          </div>
          <div className="vm-info-row">
            <span className="vm-info-label">Compatibility</span>
            <span className="vm-info-value">ESXi 8.0 · {vm.hardware_version || 'Hardware v20'}</span>
          </div>
        </div>
      </div>

      <div className="vm-panel">
        <div className="vm-panel-header">Virtual hardware</div>
        <div className="vm-panel-body space-y-4">
          <div className="flex items-center gap-3.5 flex-wrap">
            <span className="w-[120px] text-[#8FA5B8] text-xs shrink-0">CPUs</span>
            <div className="flex items-center gap-2">
              <button type="button" disabled={poweredOn || cpu <= 1 || acting} onClick={() => setCpu(c => c - 1)}
                className="w-7 h-7 rounded-md border border-[#2D3A4A] bg-[#243447] text-[#E8EDF2] text-base disabled:opacity-40">−</button>
              <span className="w-9 text-center text-sm font-semibold text-white">{cpu}</span>
              <button type="button" disabled={poweredOn || cpu >= 16 || acting} onClick={() => setCpu(c => c + 1)}
                className="w-7 h-7 rounded-md border border-[#2D3A4A] bg-[#243447] text-[#E8EDF2] text-base disabled:opacity-40">+</button>
            </div>
            {poweredOn && <span className="text-[10px] text-[#8FA5B8]">Power off to change CPU</span>}
          </div>

          <div className="flex items-center gap-3.5 flex-wrap">
            <span className="w-[120px] text-[#8FA5B8] text-xs shrink-0">Memory</span>
            <input type="range" min={1} max={64} value={memGb} disabled={poweredOn || acting}
              onChange={e => setMemGb(parseInt(e.target.value, 10))}
              className="flex-1 min-w-[160px] max-w-[240px] accent-[#00C8FF] disabled:opacity-40" />
            <span className="text-sm font-semibold text-white w-[60px]">{memGb} GB</span>
          </div>

          <div className="flex items-center gap-3.5 flex-wrap">
            <span className="w-[120px] text-[#8FA5B8] text-xs shrink-0">Hard disk 1</span>
            <span className="text-xs text-[#E8EDF2] flex-1">{vm.disk_gb} GB (Thin)</span>
            <button type="button" onClick={onAddDisk} disabled={acting} className="vm-btn text-[11px] py-1 px-3">
              Add disk +100 GB
            </button>
          </div>

          <div className="flex items-center gap-3.5 flex-wrap">
            <span className="w-[120px] text-[#8FA5B8] text-xs shrink-0">Network adapter 1</span>
            <span className="text-xs text-[#E8EDF2] flex-1">
              {networks.find(n => n.id === vm.network_id)?.name || 'VM Network'} — VMXNET3
            </span>
            <button type="button" onClick={onEditNetwork} disabled={acting} className="vm-btn text-[11px] py-1 px-3">
              Edit
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
