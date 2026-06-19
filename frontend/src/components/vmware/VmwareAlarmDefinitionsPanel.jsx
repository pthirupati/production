import { useState } from 'react'

const ENTITY_TYPES = ['VirtualMachine', 'HostSystem', 'Datastore', 'ClusterComputeResource', 'Network']
const METRICS = ['cpu.usage', 'mem.usage', 'disk.used', 'disk.latency', 'net.usage', 'host.connection']
const SEVERITIES = ['warning', 'critical']

/** vCenter Alarm/Alert definitions — list, create, enable/disable, delete. */
export default function VmwareAlarmDefinitionsPanel({ alarmDefinitions = [], onAction, acting }) {
  const [showAdd, setShowAdd] = useState(false)
  const [name, setName] = useState('')
  const [entityType, setEntityType] = useState('VirtualMachine')
  const [metric, setMetric] = useState('cpu.usage')
  const [operator, setOperator] = useState('>')
  const [threshold, setThreshold] = useState('90')
  const [severity, setSeverity] = useState('warning')
  const [error, setError] = useState('')

  const create = async () => {
    if (!name.trim()) { setError('Alarm name is required'); return }
    setError('')
    await onAction('create_alarm_definition', {
      name: name.trim(), entity_type: entityType, metric,
      operator, threshold: parseInt(threshold) || 90, severity,
    })
    setName('')
    setShowAdd(false)
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between">
        <span>Alarm Definitions</span>
        <button type="button" onClick={() => setShowAdd(v => !v)} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">
          {showAdd ? 'Cancel' : 'New alarm definition…'}
        </button>
      </div>
      <div className="vm-panel-body">
        {showAdd && (
          <div className="mb-4 p-3 border border-[#2d3a4a] rounded-lg space-y-2 bg-[#16222f]">
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Alarm name (e.g. VM CPU saturation)" className="vm-input !pl-3 w-full text-xs" />
            <div className="grid grid-cols-2 gap-2">
              <select value={entityType} onChange={e => setEntityType(e.target.value)} className="vm-input !pl-3 text-xs">
                {ENTITY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={metric} onChange={e => setMetric(e.target.value)} className="vm-input !pl-3 text-xs">
                {METRICS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <select value={operator} onChange={e => setOperator(e.target.value)} className="vm-input !pl-3 text-xs">
                {['>', '>=', '<', '<='].map(o => <option key={o} value={o}>{o}</option>)}
              </select>
              <input type="number" value={threshold} onChange={e => setThreshold(e.target.value)} placeholder="Threshold" className="vm-input !pl-3 text-xs" />
              <select value={severity} onChange={e => setSeverity(e.target.value)} className="vm-input !pl-3 text-xs col-span-2">
                {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            {error && <p className="text-[11px] text-[#D9534F]">{error}</p>}
            <button type="button" disabled={acting} onClick={create} className="vm-btn vm-btn-green text-xs w-full justify-center">Create alarm</button>
          </div>
        )}
        {alarmDefinitions.length === 0 ? (
          <p className="text-[#8FA5B8] text-[11px]">No alarm definitions configured.</p>
        ) : (
          <table className="vm-table">
            <thead>
              <tr>{['Name', 'Entity', 'Condition', 'Severity', 'State', ''].map(h => <th key={h || 'x'}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {alarmDefinitions.map(a => (
                <tr key={a.id}>
                  <td className="text-[#E8EDF2]">{a.name}</td>
                  <td className="text-[#8FA5B8]">{a.entity_type}</td>
                  <td className="font-mono text-[10px] text-[#8FA5B8]">{a.metric} {a.operator} {a.threshold}</td>
                  <td>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${a.severity === 'critical' ? 'bg-[rgba(217,83,79,.2)] text-[#D9534F]' : 'bg-[rgba(245,166,35,.2)] text-[#F5A623]'}`}>{a.severity}</span>
                  </td>
                  <td>
                    <span className={a.enabled ? 'text-[#5DB85D] font-semibold' : 'text-[#8FA5B8]'}>{a.enabled ? 'Enabled' : 'Disabled'}</span>
                  </td>
                  <td className="whitespace-nowrap">
                    <button type="button" disabled={acting} onClick={() => onAction('toggle_alarm_definition', { alarm_def_id: a.id })}
                      className="text-[10px] text-[#5b9bf5] hover:underline mr-2">{a.enabled ? 'Disable' : 'Enable'}</button>
                    <button type="button" disabled={acting} onClick={() => onAction('delete_alarm_definition', { alarm_def_id: a.id })}
                      className="text-[10px] text-[#D9534F] hover:underline">Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
