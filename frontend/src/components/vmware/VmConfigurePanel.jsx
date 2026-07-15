import { useEffect, useState } from 'react'

function fmtDisk(d, datastores) {
  const ds = datastores?.find(x => x.id === d.datastore_id)
  const thin = d.thin_provisioned ? 'Thin' : 'Thick'
  return `${d.capacity_gb} GB · ${thin} · ${ds?.name || d.datastore_id}`
}

/** VM Configure tab — hardware with SCSI IDs and NIC details. */
export default function VmConfigurePanel({ vm, networks, datastores, acting, onSave, onAddDisk, onEditNetwork }) {
  const [cpu, setCpu] = useState(vm.cpu)
  const [memGb, setMemGb] = useState(Math.round(vm.memory_mb / 1024))
  const [name, setName] = useState(vm.name)
  const [notes, setNotes] = useState(vm.annotation || '')
  const poweredOn = vm.power === 'poweredOn'
  const disks = vm.disks?.length ? vm.disks : [{ id: 'legacy', scsi_id: '0:0', label: 'Hard disk 1', capacity_gb: vm.disk_gb, thin_provisioned: true }]
  const nics = vm.nics?.length ? vm.nics : [{
    id: 'legacy-nic',
    label: 'Network adapter 1',
    network_id: vm.network_id,
    network_name: networks.find(n => n.id === vm.network_id)?.name || 'VM Network',
    mac_address: vm.mac || '00:50:56:aa:bb:cc',
    adapter_type: 'Vmxnet3',
    connected: !vm.network_disconnected,
    vlan_id: networks.find(n => n.id === vm.network_id)?.vlan,
  }]

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
            <span className="vm-info-value">ESXi 7.0 U3 · {vm.hardware_version || 'vmx-19'}</span>
          </div>
          {vm.scsi_controllers?.map(ctrl => (
            <div key={ctrl.id} className="vm-info-row">
              <span className="vm-info-label">{ctrl.id.toUpperCase()}</span>
              <span className="vm-info-value">{ctrl.type} · Bus sharing: {ctrl.shared_bus || 'none'}</span>
            </div>
          ))}
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

          {disks.map((d, i) => (
            <div key={d.id || i} className="flex items-start gap-3.5 flex-wrap border-t border-[#22303f] pt-3 first:border-0 first:pt-0">
              <span className="w-[120px] text-[#8FA5B8] text-xs shrink-0">{d.label || `Hard disk ${i + 1}`}</span>
              <div className="flex-1 min-w-[200px]">
                <p className="text-xs text-[#E8EDF2] m-0">{fmtDisk(d, datastores)}</p>
                <p className="text-[10px] text-[#8FA5B8] font-mono mt-0.5 m-0">
                  SCSI {d.scsi_id || `${d.scsi_controller || 0}:${d.scsi_unit ?? i}`} · UUID {d.uuid || '—'}
                </p>
              </div>
            </div>
          ))}
          <button type="button" onClick={onAddDisk} disabled={acting} className="vm-btn vm-btn-blue text-[11px] py-1 px-3">
            Add hard disk…
          </button>

          {nics.map((nic, i) => (
            <div key={nic.id || i} className="flex items-start gap-3.5 flex-wrap border-t border-[#22303f] pt-3">
              <span className="w-[120px] text-[#8FA5B8] text-xs shrink-0">{nic.label || `Network adapter ${i + 1}`}</span>
              <div className="flex-1 min-w-[200px]">
                <p className="text-xs text-[#E8EDF2] m-0">
                  {nic.network_name || networks.find(n => n.id === nic.network_id)?.name || 'VM Network'} · {nic.adapter_type || 'Vmxnet3'}
                </p>
                <p className="text-[10px] text-[#8FA5B8] font-mono mt-0.5 m-0">
                  MAC {nic.mac_address || nic.mac} · VLAN {nic.vlan_id ?? '—'} · {nic.connected !== false ? 'Connected' : 'Disconnected'}
                </p>
                {nic.portgroup_key && (
                  <p className="text-[10px] text-[#5a6a7d] mt-0.5 m-0">Port group key: {nic.portgroup_key}</p>
                )}
              </div>
              <button type="button" onClick={() => onEditNetwork?.(nic)} disabled={acting} className="vm-btn text-[11px] py-1 px-3">
                Edit
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
