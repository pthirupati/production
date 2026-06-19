import { useState } from 'react'

export default function VmwareOvfDeployModal({ contentLibrary, hosts, datastores, networks, onClose, onAction }) {
  const items = (contentLibrary || []).flatMap(cl => (cl.items || []).map(i => ({ ...i, library: cl.name })))
  const [ovfName, setOvfName] = useState(items[0]?.name || '')
  const [vmName, setVmName] = useState('')
  const [hostId, setHostId] = useState(hosts[0]?.id || '')
  const [dsId, setDsId] = useState(datastores[0]?.id || '')
  const [netId, setNetId] = useState(networks[0]?.id || '')
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const deploy = async () => {
    setActing(true)
    setError('')
    try {
      await onAction('deploy_ovf', {
        ovf_name: ovfName,
        vm_name: vmName.trim() || undefined,
        host_id: hostId,
        datastore_id: dsId,
        network_id: netId,
      })
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'OVF deploy failed')
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="vm-modal-overlay">
      <div className="vm-modal w-[480px] max-w-[95vw]">
        <div className="vm-modal-header">
          <span>Deploy from Content Library (OVF/OVA)</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">OVF/OVA template</label>
            <select value={ovfName} onChange={e => setOvfName(e.target.value)} className="vm-input !pl-3">
              {items.map(i => (
                <option key={i.id} value={i.name}>{i.name} — {i.os} ({i.size_mb} MB)</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">VM name</label>
            <input value={vmName} onChange={e => setVmName(e.target.value)} placeholder="auto from OVF name" className="vm-input !pl-3" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Host</label>
              <select value={hostId} onChange={e => setHostId(e.target.value)} className="vm-input !pl-3">
                {hosts.filter(h => h.status === 'connected').map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#8fa5b8] mb-1">Datastore</label>
              <select value={dsId} onChange={e => setDsId(e.target.value)} className="vm-input !pl-3">
                {datastores.filter(d => d.accessible).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-[#8fa5b8] mb-1">Network</label>
            <select value={netId} onChange={e => setNetId(e.target.value)} className="vm-input !pl-3">
              {networks.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
            </select>
          </div>
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
        </div>
        <div className="vm-modal-footer">
          <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
          <button type="button" disabled={acting || !ovfName} onClick={deploy} className="vm-btn vm-btn-blue">
            {acting ? 'Deploying…' : 'Deploy OVF'}
          </button>
        </div>
      </div>
    </div>
  )
}
