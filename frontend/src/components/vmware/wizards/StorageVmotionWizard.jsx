import { useState } from 'react'

const STEPS = ['Select VM', 'Target datastore', 'Migration type', 'Progress', 'Complete']

export default function StorageVmotionWizard({ vm, datastores, onClose, onAction, onRefresh }) {
  const [step, setStep] = useState(0)
  const [targetDs, setTargetDs] = useState('')
  const [, setJobId] = useState(null)
  const [progress, setProgress] = useState(0)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const accessible = datastores.filter(d => d.accessible && d.id !== vm.datastore_id)

  const start = async () => {
    setActing(true)
    setError('')
    try {
      const res = await onAction('start_storage_vmotion', {
        vm_id: vm.id,
        target_datastore_id: targetDs,
      }, { silent: true })
      setJobId(res.job_id)
      setProgress(res.progress || 0)
      setStep(3)
      advanceLoop(res.job_id)
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to start storage vMotion')
    } finally {
      setActing(false)
    }
  }

  const advanceLoop = async (jid) => {
    let p = 0
    while (p < 100) {
      await new Promise(r => setTimeout(r, 600))
      try {
        const res = await onAction('advance_storage_vmotion', { job_id: jid, step: 25 }, { silent: true })
        p = res.progress || 100
        setProgress(p)
        if (res.status === 'completed') {
          setStep(4)
          onRefresh?.()
          break
        }
      } catch { break }
    }
  }

  const dsName = datastores.find(d => d.id === targetDs)?.name

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[520px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>Storage vMotion Wizard — {vm.name}</span>
          <button type="button" onClick={onClose} aria-label="Close dialog" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="px-4 py-2 border-b border-[#2d3a4a] flex gap-1 flex-wrap">
          {STEPS.map((s, i) => (
            <span key={s} className={`text-[10px] px-2 py-0.5 rounded ${i <= step ? 'bg-[#2D7CFF] text-white' : 'bg-[#243447] text-[#8fa5b8]'}`}>{i + 1}. {s}</span>
          ))}
        </div>
        <div className="vm-modal-body space-y-3 min-h-[180px]">
          {step === 0 && (
            <p className="text-sm text-[#E8EDF2]">Relocate <strong>{vm.name}</strong> disks to another datastore without powering off the VM.</p>
          )}
          {step === 1 && (
            <>
              <p className="text-xs text-[#8fa5b8]">Select target datastore:</p>
              {accessible.map(ds => (
                <label key={ds.id} className="flex items-center gap-2 cursor-pointer text-sm p-2 rounded border border-[#2d3a4a] hover:bg-[#243447]">
                  <input type="radio" checked={targetDs === ds.id} onChange={() => setTargetDs(ds.id)} />
                  <span className="text-[#E8EDF2] flex-1">{ds.name}</span>
                  <span className="text-[10px] text-[#8fa5b8]">{ds.free_gb} GB free</span>
                </label>
              ))}
            </>
          )}
          {step === 2 && (
            <p className="text-sm text-[#E8EDF2]">Migrate all virtual disks from current datastore to <strong>{dsName}</strong>. Thin provisioning preserved.</p>
          )}
          {step === 3 && (
            <div>
              <p className="text-sm text-[#E8EDF2] mb-2">Relocating virtual machine files…</p>
              <div className="vm-usage-bar h-3">
                <div className="vm-usage-bar-fill" style={{ width: `${progress}%`, background: '#2D7CFF' }} />
              </div>
              <p className="text-xs text-[#8fa5b8] mt-1">{progress}% complete</p>
            </div>
          )}
          {step === 4 && (
            <p className="text-sm text-[#5DB85D]">Storage vMotion completed. {vm.name} is now on {dsName}.</p>
          )}
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer flex-wrap gap-2">
          <button type="button" onClick={onClose} className="vm-btn">{step === 4 ? 'Close' : 'Cancel'}</button>
          {step === 0 && <button type="button" onClick={() => setStep(1)} className="vm-btn vm-btn-blue">Next</button>}
          {step === 1 && <button type="button" disabled={!targetDs} onClick={() => setStep(2)} className="vm-btn vm-btn-blue">Next</button>}
          {step === 2 && <button type="button" disabled={acting} onClick={start} className="vm-btn vm-btn-blue">{acting ? 'Starting…' : 'Start storage vMotion'}</button>}
        </div>
      </div>
    </div>
  )
}
