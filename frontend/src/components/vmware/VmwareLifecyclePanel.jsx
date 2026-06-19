import { useState } from 'react'

export default function VmwareLifecyclePanel({ target, targetType, updates, onAction, acting }) {
  const [pending, setPending] = useState(null)
  const [checking, setChecking] = useState(false)

  const check = async () => {
    setChecking(true)
    try {
      const res = await onAction('check_updates', { target: targetType }, { silent: true })
      setPending(res?.pending || [])
    } finally {
      setChecking(false)
    }
  }

  const install = async () => {
    await onAction('install_updates', {
      target_type: targetType,
      host_name: targetType === 'host' ? target?.name : undefined,
      vm_id: targetType === 'vm' ? target?.id : undefined,
    })
    setPending([])
  }

  const toolsOld = target?.tools === 'old'
  const hostPatches = target?.pending_patches > 0

  return (
    <div className="space-y-3">
      <div className="vm-panel p-4 flex items-center gap-3.5">
        <span className={`w-11 h-11 rounded-[11px] flex items-center justify-center text-lg ${(toolsOld || hostPatches || pending?.length) ? 'bg-[rgba(245,166,35,.12)] text-[#F5A623]' : 'bg-[rgba(93,184,93,.12)] text-[#5DB85D]'}`}>
          {(toolsOld || hostPatches || pending?.length) ? '!' : '✓'}
        </span>
        <div className="flex-1">
          <p className="text-sm font-bold text-white m-0">
            {(toolsOld || hostPatches || pending?.length) ? 'Updates available' : 'Up to date'}
          </p>
          <p className="text-xs text-[#8FA5B8] m-0 mt-1">
            {targetType === 'vm' ? `${target?.name} · VMware Tools ${target?.tools_version || '—'}` : `${target?.name} · ESXi ${target?.version}`}
          </p>
        </div>
        <button type="button" disabled={checking} onClick={check} className="vm-btn vm-btn-blue text-xs py-2 px-4">
          {checking ? 'Checking…' : 'Check for updates'}
        </button>
      </div>

      {pending?.length > 0 && (
        <div className="vm-panel-body border border-[#2d3a4a] rounded-lg p-3">
          <p className="text-xs font-semibold text-[#F5A623] mb-2">Pending updates</p>
          <ul className="text-xs text-[#E8EDF2] space-y-1 mb-3">
            {pending.map((p, i) => <li key={i}>• {p}</li>)}
          </ul>
          <button type="button" disabled={acting} onClick={install} className="vm-btn vm-btn-green text-xs">Install updates</button>
        </div>
      )}

      {targetType === 'vm' && (
        <div className="vm-panel">
          <div className="vm-panel-header">Lifecycle — VMware Tools</div>
          <div className="vm-panel-body">
            <p className="text-xs text-[#8fa5b8] mb-2">Upgrade Tools to match host compatibility and enable guest quiesced snapshots.</p>
            <button type="button" disabled={acting || target?.power !== 'poweredOn'} onClick={() => onAction('install_tools_update', { vm_id: target.id })} className="vm-btn vm-btn-blue text-xs">
              Upgrade VMware Tools
            </button>
          </div>
        </div>
      )}

      {updates?.vcenter?.available && (
        <p className="text-xs text-[#8fa5b8]">vCenter update {updates.vcenter.latest} available (maintenance window required)</p>
      )}
    </div>
  )
}
