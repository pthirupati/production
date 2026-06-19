import { useState } from 'react'

export default function VmwareDvsEditor({ vswitches, onAction, acting }) {
  const dvsList = (vswitches || []).filter(v => v.type === 'distributed')
  const [selected, setSelected] = useState(dvsList[0]?.name || '')
  const [mtu, setMtu] = useState(String(dvsList[0]?.mtu || 1500))
  const [teaming, setTeaming] = useState(dvsList[0]?.teaming || 'loadbalance_srcmac')
  const dvs = dvsList.find(v => v.name === selected)

  const save = () => {
    onAction('update_dvs', { dvs_name: selected, mtu: parseInt(mtu, 10), teaming })
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header">Distributed switch editor</div>
      <div className="vm-panel-body space-y-3">
        <div>
          <label className="block text-[10px] text-[#8fa5b8] mb-1 uppercase">Distributed switch</label>
          <select value={selected} onChange={e => { setSelected(e.target.value); const d = dvsList.find(v => v.name === e.target.value); setMtu(String(d?.mtu || 1500)) }} className="vm-input !pl-3 w-full">
            {dvsList.map(v => <option key={v.id} value={v.name}>{v.name}</option>)}
          </select>
        </div>
        {dvs && (
          <>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div><span className="text-[#8fa5b8]">Version</span><p className="text-white m-0">{dvs.version || '7.0.0'}</p></div>
              <div><span className="text-[#8fa5b8]">Ports</span><p className="text-white m-0">{dvs.ports}</p></div>
              <div><span className="text-[#8fa5b8]">Uplinks</span><p className="text-white m-0">{dvs.uplinks?.join(', ')}</p></div>
              <div><span className="text-[#8fa5b8]">Port groups</span><p className="text-white m-0">{dvs.portgroups?.join(', ')}</p></div>
            </div>
            <div>
              <label className="block text-[10px] text-[#8fa5b8] mb-1">MTU</label>
              <select value={mtu} onChange={e => setMtu(e.target.value)} className="vm-input !pl-3 w-full">
                <option value="1500">1500 (Standard)</option>
                <option value="9000">9000 (Jumbo frames)</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-[#8fa5b8] mb-1">Teaming policy</label>
              <select value={teaming} onChange={e => setTeaming(e.target.value)} className="vm-input !pl-3 w-full">
                <option value="loadbalance_srcmac">Route based on originating virtual port</option>
                <option value="loadbalance_ip">Route based on IP hash</option>
                <option value="failover_explicit">Failover explicit</option>
              </select>
            </div>
            <button type="button" disabled={acting} onClick={save} className="vm-btn vm-btn-blue text-xs">Apply DVS settings</button>
          </>
        )}
      </div>
    </div>
  )
}
