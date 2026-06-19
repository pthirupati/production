import { useState } from 'react'

export default function NsxMicroSegmentationPanel({ nsx, onAction, acting }) {
  const [ruleName, setRuleName] = useState('Allow-App-Tier')
  const [source, setSource] = useState('10.20.30.0/24')
  const [dest, setDest] = useState('10.20.40.0/24')
  const [service, setService] = useState('HTTPS')

  const enabled = nsx?.enabled
  const rules = nsx?.firewall_rules || []
  const segments = nsx?.segments || []

  return (
    <div className="space-y-3">
      <div className="vm-panel p-4 flex items-center gap-3">
        <span className={`w-11 h-11 rounded-[11px] flex items-center justify-center text-lg ${enabled ? 'bg-[rgba(93,184,93,.12)] text-[#5DB85D]' : 'bg-[rgba(245,166,35,.12)] text-[#F5A623]'}`}>
          {enabled ? '✓' : '!'}
        </span>
        <div className="flex-1">
          <p className="text-sm font-bold text-white m-0">NSX-T {nsx?.manager || 'Manager'}</p>
          <p className="text-xs text-[#8FA5B8] m-0 mt-1">
            {enabled ? `Micro-segmentation active · v${nsx?.version || '—'}` : 'NSX-T not connected — enable to configure DFW'}
          </p>
        </div>
        {!enabled && (
          <button type="button" disabled={acting} onClick={() => onAction('enable_nsx')} className="vm-btn vm-btn-blue text-xs py-2 px-4">
            Connect NSX
          </button>
        )}
      </div>

      {enabled && (
        <>
          <div className="vm-panel">
            <div className="vm-panel-header">Transport Segments</div>
            <div className="vm-panel-body">
              <table className="vm-table">
                <thead><tr><th>Name</th><th>VLAN</th><th>Subnets</th></tr></thead>
                <tbody>
                  {segments.map(s => (
                    <tr key={s.id}>
                      <td>{s.name}</td>
                      <td>{s.vlan}</td>
                      <td>{(s.subnets || []).join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="vm-panel">
            <div className="vm-panel-header">Distributed Firewall Rules</div>
            <div className="vm-panel-body space-y-3">
              {nsx?.microseg_missing && (
                <p className="text-xs text-[#F5A623]">Required micro-segmentation rule missing for prod tier.</p>
              )}
              <table className="vm-table">
                <thead><tr><th>Name</th><th>Action</th><th>Source</th><th>Dest</th><th>Service</th></tr></thead>
                <tbody>
                  {rules.map(r => (
                    <tr key={r.id}>
                      <td>{r.name}</td>
                      <td>{r.action}</td>
                      <td>{r.source}</td>
                      <td>{r.dest}</td>
                      <td>{r.service}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="grid grid-cols-2 gap-2">
                <input value={ruleName} onChange={e => setRuleName(e.target.value)} placeholder="Rule name" className="vm-input !pl-2 text-xs" />
                <select value={service} onChange={e => setService(e.target.value)} className="vm-input !pl-2 text-xs">
                  {['ANY', 'SSH', 'HTTPS', 'HTTP', 'RDP'].map(s => <option key={s}>{s}</option>)}
                </select>
                <input value={source} onChange={e => setSource(e.target.value)} placeholder="Source" className="vm-input !pl-2 text-xs" />
                <input value={dest} onChange={e => setDest(e.target.value)} placeholder="Destination" className="vm-input !pl-2 text-xs" />
              </div>
              <button
                type="button"
                disabled={acting || !ruleName.trim()}
                onClick={() => onAction('create_nsx_firewall_rule', { name: ruleName, source, dest, service, action: 'ALLOW' })}
                className="vm-btn vm-btn-green text-xs"
              >
                Add DFW Rule
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
