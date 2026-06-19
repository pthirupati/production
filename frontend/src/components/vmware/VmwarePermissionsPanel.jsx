import { useState } from 'react'

export default function VmwarePermissionsPanel({ entityName, entityId, entityType, permissions, rolesCatalog, onAction, acting }) {
  const [showAdd, setShowAdd] = useState(false)
  const [principal, setPrincipal] = useState('')
  const [role, setRole] = useState(rolesCatalog?.[1] || 'Read Only')
  const [propagate, setPropagate] = useState(true)

  const rows = (permissions || []).filter(p =>
    !entityName || p.entity === entityName || p.entity_id === entityId || p.entity === 'vCenter'
  )

  const add = async () => {
    if (!principal.trim()) return
    await onAction('assign_permission', {
      entity: entityName,
      entity_id: entityId,
      entity_type: entityType,
      principal: principal.trim(),
      role,
      propagate,
    })
    setPrincipal('')
    setShowAdd(false)
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between">
        <span>Roles & Permissions — {entityName}</span>
        <button type="button" onClick={() => setShowAdd(v => !v)} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">Add permission…</button>
      </div>
      <div className="vm-panel-body">
        {showAdd && (
          <div className="mb-4 p-3 border border-[#2d3a4a] rounded-lg space-y-2 bg-[#16222f]">
            <input value={principal} onChange={e => setPrincipal(e.target.value)} placeholder="User or group (e.g. lab_vmware)" className="vm-input !pl-3 w-full text-xs" />
            <select value={role} onChange={e => setRole(e.target.value)} className="vm-input !pl-3 w-full text-xs">
              {(rolesCatalog || ['Administrator', 'Read Only', 'Virtual Machine User']).map(r => <option key={r}>{r}</option>)}
            </select>
            <label className="flex items-center gap-2 text-xs text-[#8fa5b8]">
              <input type="checkbox" checked={propagate} onChange={e => setPropagate(e.target.checked)} />
              Propagate to children
            </label>
            <button type="button" disabled={acting} onClick={add} className="vm-btn vm-btn-green text-xs w-full justify-center">Assign role</button>
          </div>
        )}
        <table className="vm-table">
          <thead>
            <tr>{['User / Group', 'Role', 'Propagate', 'Defined In', ''].map(h => <th key={h || 'x'}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id}>
                <td className="text-[#5b9bf5]">{r.principal}</td>
                <td>{r.role}</td>
                <td>{r.propagate ? 'Yes' : 'No'}</td>
                <td className="text-[#8FA5B8]">{r.entity}</td>
                <td>
                  {r.id !== 'perm-root' && (
                    <button type="button" disabled={acting} onClick={() => onAction('revoke_permission', { permission_id: r.id, entity: entityName })} className="text-[10px] text-[#D9534F] hover:underline">Remove</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
