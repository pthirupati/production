import { useState } from 'react'

export default function SrmDisasterRecoveryPanel({ srm, linkedMode, onAction, acting }) {
  const [confirmFailover, setConfirmFailover] = useState(false)

  return (
    <div className="space-y-3">
      <div className="vm-panel p-4 flex items-center gap-3">
        <span className={`w-11 h-11 rounded-[11px] flex items-center justify-center text-lg ${srm?.enabled ? 'bg-[rgba(93,184,93,.12)] text-[#5DB85D]' : 'bg-[rgba(217,83,79,.12)] text-[#D9534F]'}`}>
          {srm?.enabled ? '✓' : '!'}
        </span>
        <div className="flex-1">
          <p className="text-sm font-bold text-white m-0">Site Recovery Manager</p>
          <p className="text-xs text-[#8FA5B8] m-0 mt-1">
            {linkedMode ? 'Linked mode active · DC-Prod ↔ DC-DR' : 'Enable linked mode before SRM pairing'}
          </p>
        </div>
        {!srm?.enabled && (
          <button type="button" disabled={acting || !linkedMode} onClick={() => onAction('configure_srm')} className="vm-btn vm-btn-blue text-xs py-2 px-4">
            Configure SRM
          </button>
        )}
      </div>

      {srm?.enabled && (
        <>
          <div className="vm-panel">
            <div className="vm-panel-header">Protection Groups</div>
            <div className="vm-panel-body">
              <ul className="text-xs text-[#E8EDF2] space-y-1">
                {(srm.protection_groups || []).map(pg => (
                  <li key={pg.name}>• {pg.name}: {(pg.vms || []).join(', ')}</li>
                ))}
              </ul>
              <p className="text-xs text-[#8FA5B8] mt-2">Replication: {srm.replication_ok ? 'OK' : 'Not configured'}</p>
            </div>
          </div>

          <div className="vm-panel">
            <div className="vm-panel-header">Recovery Plans</div>
            <div className="vm-panel-body space-y-2">
              {(srm.recovery_plans || []).map(rp => (
                <div key={rp.name} className="flex items-center justify-between text-sm">
                  <span className="text-[#E8EDF2]">{rp.name}</span>
                  <span className="text-xs text-[#5DB85D]">{rp.status}</span>
                </div>
              ))}
              {srm.last_test && (
                <p className="text-xs text-[#8FA5B8]">Last test: {new Date(srm.last_test).toLocaleString()}</p>
              )}
              <div className="flex gap-2 pt-2">
                <button type="button" disabled={acting} onClick={() => onAction('srm_test_recovery')} className="vm-btn vm-btn-blue text-xs">
                  Test Recovery Plan
                </button>
                <button
                  type="button"
                  disabled={acting || (!srm.failover_ready && !srm.replication_ok)}
                  onClick={() => setConfirmFailover(true)}
                  className="vm-btn vm-btn-red text-xs"
                >
                  Planned Migration
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {confirmFailover && (
        <div className="vm-panel border border-[#D9534F] p-3">
          <p className="text-xs text-[#E8EDF2] mb-2">Execute planned migration to DC-DR?</p>
          <div className="flex gap-2">
            <button type="button" onClick={() => setConfirmFailover(false)} className="vm-btn text-xs">Cancel</button>
            <button
              type="button"
              disabled={acting}
              onClick={async () => {
                await onAction('srm_failover')
                setConfirmFailover(false)
              }}
              className="vm-btn vm-btn-red text-xs"
            >
              Confirm Failover
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
