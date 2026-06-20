import { useState } from 'react'

/* Datacenter ▸ Datastores tab with sub-tabs:
   Datastores / Datastore Clusters / Datastore Folders.
   New Datastore Cluster create (SDRS toggle) + listing. */

const fmtBytes = (gb) => gb >= 1024 ? `${(gb / 1024).toFixed(1)} TB` : `${gb} GB`

export default function VmwareDatacenterDatastores({
  datastores = [], datastoreClusters = [], folders = [],
  onNewDatastore, onNewDatastoreCluster, onNewFolder, onAction, acting,
}) {
  const [sub, setSub] = useState('datastores')
  const storageFolders = folders.filter(f => f.folder_type === 'storage')

  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center gap-1 p-0 pr-3">
        {[['datastores', 'Datastores'], ['clusters', 'Datastore Clusters'], ['folders', 'Datastore Folders']].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setSub(id)}
            className={`px-3.5 py-2.5 text-[12px] font-semibold border-b-2 ${sub === id ? 'border-[#00C8FF] text-white bg-[rgba(0,200,255,.08)]' : 'border-transparent text-[#8fa5b8] hover:text-white'}`}>
            {label}
          </button>
        ))}
        <div className="flex-1" />
        {sub === 'datastores' && <button type="button" onClick={onNewDatastore} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">New Datastore…</button>}
        {sub === 'clusters' && <button type="button" onClick={onNewDatastoreCluster} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">New Datastore Cluster…</button>}
        {sub === 'folders' && <button type="button" onClick={onNewFolder} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">New Storage Folder…</button>}
      </div>
      <div className="vm-panel-body">
        {sub === 'datastores' && (
          <table className="vm-table">
            <thead><tr>{['Name', 'Type', 'Capacity', 'Free', 'Cluster', 'VMs'].map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {datastores.map(ds => (
                <tr key={ds.id}>
                  <td className="text-[#5b9bf5]">{ds.name}</td>
                  <td>{ds.type}</td>
                  <td>{fmtBytes(ds.capacity_gb)}</td>
                  <td className={ds.free_gb < 50 ? 'text-[#D9534F]' : 'text-[#5DB85D]'}>{fmtBytes(ds.free_gb)}</td>
                  <td className="text-[#8FA5B8]">{datastoreClusters.find(c => c.id === ds.datastore_cluster_id)?.name || '—'}</td>
                  <td>{(ds.vms || []).length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {sub === 'clusters' && (
          datastoreClusters.length === 0 ? (
            <p className="text-[#8FA5B8] text-[11px]">No datastore clusters. Create one to enable Storage DRS across multiple datastores.</p>
          ) : (
            <table className="vm-table">
              <thead><tr>{['Name', 'Storage DRS', 'Automation', 'Members', 'Total Capacity', ''].map(h => <th key={h || 'x'}>{h}</th>)}</tr></thead>
              <tbody>
                {datastoreClusters.map(c => {
                  const members = datastores.filter(d => (c.datastore_ids || []).includes(d.id))
                  const cap = members.reduce((s, d) => s + (d.capacity_gb || 0), 0)
                  return (
                    <tr key={c.id}>
                      <td className="text-[#5b9bf5]">{c.name}</td>
                      <td className={c.sdrs_enabled ? 'text-[#5DB85D] font-semibold' : 'text-[#8FA5B8]'}>{c.sdrs_enabled ? 'Enabled' : 'Disabled'}</td>
                      <td className="text-[#8FA5B8]">{c.automation_level === 'fullyAutomated' ? 'Fully Automated' : 'Manual'}</td>
                      <td>{members.length}</td>
                      <td>{fmtBytes(cap)}</td>
                      <td>
                        <button type="button" disabled={acting} onClick={() => onAction('toggle_datastore_sdrs', { datastore_cluster_id: c.id, sdrs_enabled: !c.sdrs_enabled })}
                          className="text-[10px] text-[#5b9bf5] hover:underline">{c.sdrs_enabled ? 'Disable SDRS' : 'Enable SDRS'}</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )
        )}
        {sub === 'folders' && (
          storageFolders.length === 0 ? (
            <p className="text-[#8FA5B8] text-[11px]">No storage folders. Create folders to organise datastores in the inventory.</p>
          ) : (
            <table className="vm-table">
              <thead><tr>{['Folder', 'Type'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {storageFolders.map(f => (
                  <tr key={f.id}><td className="text-[#5b9bf5]">📁 {f.name}</td><td className="text-[#8FA5B8]">Storage folder</td></tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  )
}
