import { useState } from 'react'
import StatusIcon from '../StatusIconInline'

const STEPS = ['Select VM', 'Destination', 'Compatibility', 'Review', 'Migrate']

export default function VmotionWizard({ vm, hosts, onClose, onAction }) {
  const [step, setStep] = useState(0)
  const [targetHost, setTargetHost] = useState('')
  const [checks, setChecks] = useState(null)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const available = hosts.filter(h => h.id !== vm.host_id && h.status === 'connected')

  const runPrecheck = async () => {
    setActing(true)
    setError('')
    try {
      const res = await onAction('vmotion_precheck', { vm_id: vm.id, target_host: targetHost }, { silent: true })
      setChecks(res.checks || [])
      if (res.ready !== false) setStep(2)
      else setError('Compatibility check failed')
    } catch (e) {
      setError(e?.response?.data?.error || 'Precheck failed')
    } finally {
      setActing(false)
    }
  }

  const migrate = async () => {
    setActing(true)
    try {
      if (vm.vmotion_failed) await onAction('resolve_vmotion', { vm_id: vm.id })
      await onAction('migrate_vm', { vm_id: vm.id, vm_name: vm.name, target_host: targetHost })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Migration failed')
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[520px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>vMotion Wizard — {vm.name}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="px-4 py-2 border-b border-[#2d3a4a] flex gap-1 flex-wrap">
          {STEPS.map((s, i) => (
            <span key={s} className={`text-[10px] px-2 py-0.5 rounded ${i <= step ? 'bg-[#2D7CFF] text-white' : 'bg-[#243447] text-[#8fa5b8]'}`}>{i + 1}. {s}</span>
          ))}
        </div>
        <div className="vm-modal-body space-y-3 min-h-[200px]">
          {step === 0 && (
            <>
              <p className="text-sm text-[#E8EDF2]">Migrate <strong>{vm.name}</strong> to another ESXi host with zero downtime.</p>
              <InfoRow label="Current host" value={hosts.find(h => h.id === vm.host_id)?.name || '—'} />
              <InfoRow label="Power state" value={vm.power} />
              <InfoRow label="Memory" value={`${Math.round(vm.memory_mb / 1024)} GB`} />
            </>
          )}
          {step === 1 && (
            <>
              <p className="text-xs text-[#8fa5b8]">Select destination host:</p>
              {available.length === 0 ? (
                <p className="text-sm text-[#D9534F]">No compatible hosts available</p>
              ) : available.map(h => (
                <label key={h.id} className="flex items-center gap-2 cursor-pointer text-sm text-[#E8EDF2] p-2 rounded border border-[#2d3a4a] hover:bg-[#243447]">
                  <input type="radio" name="host" checked={targetHost === h.name} onChange={() => setTargetHost(h.name)} />
                  <StatusIcon status={h.status} />
                  <span className="flex-1">{h.name}</span>
                  <span className="text-[10px] text-[#8fa5b8]">CPU {h.cpu_pct}% · Mem {h.mem_pct}%</span>
                </label>
              ))}
            </>
          )}
          {step === 2 && checks && (
            <div className="space-y-2">
              {checks.map(c => (
                <div key={c.name} className="flex items-center gap-2 text-sm">
                  <span className={c.passed ? 'text-[#5DB85D]' : 'text-[#D9534F]'}>{c.passed ? '✓' : '✗'}</span>
                  <span className="font-semibold text-white">{c.name}</span>
                  <span className="text-[#8fa5b8] text-xs">{c.detail}</span>
                </div>
              ))}
            </div>
          )}
          {step === 3 && (
            <div className="space-y-2 text-sm text-[#E8EDF2]">
              <p>Ready to migrate <strong>{vm.name}</strong> to <strong>{targetHost}</strong>.</p>
              <p className="text-xs text-[#8fa5b8]">Migration type: Change compute resource only (vMotion)</p>
              {vm.vmotion_failed && (
                <p className="text-xs text-[#F5A623]">Previous vMotion failed — wizard will resolve before migrating.</p>
              )}
            </div>
          )}
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer flex-wrap gap-2">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          {step > 0 && step < 4 && (
            <button type="button" onClick={() => setStep(s => s - 1)} className="vm-btn">Back</button>
          )}
          {step === 0 && (
            <button type="button" onClick={() => setStep(1)} className="vm-btn vm-btn-blue">Next</button>
          )}
          {step === 1 && (
            <button type="button" disabled={!targetHost || acting} onClick={runPrecheck} className="vm-btn vm-btn-blue">{acting ? 'Checking…' : 'Run compatibility check'}</button>
          )}
          {step === 2 && checks && (
            <button type="button" onClick={() => setStep(3)} className="vm-btn vm-btn-blue">Next — Review</button>
          )}
          {step === 3 && (
            <button type="button" disabled={acting} onClick={migrate} className="vm-btn vm-btn-blue">
              {acting ? 'Migrating…' : 'Start vMotion'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between text-xs border-b border-[#2d3a4a] py-1.5">
      <span className="text-[#8fa5b8]">{label}</span>
      <span className="text-[#E8EDF2]">{value}</span>
    </div>
  )
}
