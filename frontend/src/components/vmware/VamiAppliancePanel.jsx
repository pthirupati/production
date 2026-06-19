import { useState } from 'react'

export default function VamiAppliancePanel({ vami, vcenterVersion, onAction, acting }) {
  const [pending, setPending] = useState(null)
  const [stageProgress, setStageProgress] = useState(0)

  const check = async () => {
    const res = await onAction('vami_check_patches', {}, { silent: true })
    setPending(res?.pending || [])
  }

  const stage = async () => {
    await onAction('vami_stage_patches')
    setStageProgress(0)
    for (let i = 0; i < 4; i += 1) {
      const res = await onAction('vami_advance_stage', { step: 25 }, { silent: true })
      setStageProgress(res?.progress ?? (i + 1) * 25)
    }
  }

  const install = async () => {
    await onAction('vami_install_patches')
    setPending([])
    setStageProgress(100)
  }

  const count = vami?.pending_patches ?? 0
  const inProgress = vami?.stage && vami.stage !== 'idle'

  return (
    <div className="space-y-3">
      <div className="vm-panel p-4 flex items-center gap-3">
        <span className={`w-11 h-11 rounded-[11px] flex items-center justify-center text-lg ${count === 0 ? 'bg-[rgba(93,184,93,.12)] text-[#5DB85D]' : 'bg-[rgba(245,166,35,.12)] text-[#F5A623]'}`}>
          {count === 0 ? '✓' : count}
        </span>
        <div className="flex-1">
          <p className="text-sm font-bold text-white m-0">VAMI — vCenter Appliance</p>
          <p className="text-xs text-[#8FA5B8] m-0 mt-1">Version {vcenterVersion || vami?.version || '7.0.3'} · {count} pending patch{count !== 1 ? 'es' : ''}</p>
        </div>
        <button type="button" disabled={acting} onClick={check} className="vm-btn vm-btn-blue text-xs py-2 px-4">
          Check Updates
        </button>
      </div>

      {(pending?.length > 0 || count > 0) && (
        <div className="vm-panel">
          <div className="vm-panel-header">Appliance Patches</div>
          <div className="vm-panel-body space-y-3">
            <ul className="text-xs text-[#E8EDF2] space-y-1">
              {(pending || [`vCenter patch ${vcenterVersion} build+1`]).slice(0, count || pending?.length || 1).map((p, i) => (
                <li key={i}>• {p}</li>
              ))}
            </ul>
            {inProgress && (
              <div>
                <p className="text-xs text-[#8FA5B8] mb-1">Stage: {vami.stage} ({stageProgress || vami.stage_progress || 0}%)</p>
                <div className="vm-usage-bar"><div className="vm-usage-bar-fill" style={{ width: `${stageProgress || vami.stage_progress || 0}%` }} /></div>
              </div>
            )}
            <div className="flex gap-2">
              <button type="button" disabled={acting || inProgress} onClick={stage} className="vm-btn text-xs">Stage Patches</button>
              <button type="button" disabled={acting || vami?.stage !== 'installing'} onClick={install} className="vm-btn vm-btn-green text-xs">
                Install & Reboot
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
