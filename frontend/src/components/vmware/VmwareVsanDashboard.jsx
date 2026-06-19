export default function VmwareVsanDashboard({ vsan, clusterVsan, onAction, acting }) {
  const v = vsan || {}
  const healthColor = v.health === 'healthy' ? '#5DB85D' : v.health === 'warning' ? '#F5A623' : '#D9534F'

  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between">
        <span>vSAN health</span>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ background: `${healthColor}22`, color: healthColor }}>
          {v.health || 'unknown'}
        </span>
      </div>
      <div className="vm-panel-body space-y-4">
        <div className="grid grid-cols-3 gap-3 text-center">
          {[
            { label: 'Cluster status', value: v.cluster_status || (clusterVsan ? 'online' : 'off') },
            { label: 'Resync', value: `${v.resync_percent ?? 100}%` },
            { label: 'Components', value: v.components_healthy !== false ? 'Healthy' : 'Degraded' },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg border border-[#2d3a4a] p-3 bg-[#16222f]">
              <p className="text-[10px] text-[#8fa5b8] m-0">{label}</p>
              <p className="text-sm font-bold text-white m-0 mt-1">{value}</p>
            </div>
          ))}
        </div>

        {(v.unclaimed_disks || []).length > 0 && (
          <div>
            <p className="text-[11px] font-semibold text-[#F5A623] mb-2">Unclaimed disks ({v.unclaimed_disks.length})</p>
            <table className="vm-table">
              <thead><tr>{['Disk ID', 'Host', 'Size', 'Action'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {v.unclaimed_disks.map(d => (
                  <tr key={d.id}>
                    <td className="font-mono text-[10px]">{d.id}</td>
                    <td>{d.host}</td>
                    <td>{d.size_tb} TB</td>
                    <td>
                      <button type="button" disabled={acting} onClick={() => onAction('claim_vsan_disk', { disk_id: d.id })} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">
                        Claim
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {(v.disk_groups || []).length > 0 && (
          <div>
            <p className="text-[11px] font-semibold text-white mb-2">Disk groups</p>
            {v.disk_groups.map((dg, i) => (
              <div key={i} className="border border-[#2d3a4a] rounded p-2 mb-2 text-xs">
                <p className="text-[#5b9bf5] font-semibold m-0 mb-1">{dg.host}</p>
                {(dg.disks || []).map(d => (
                  <div key={d.id} className="flex justify-between text-[#8fa5b8] py-0.5">
                    <span className="font-mono">{d.id}</span>
                    <span>{d.tier} · {d.status}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
