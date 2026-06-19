import { useState } from 'react'

/** vCenter SSO Users & Roles — list, create user, reset password, assign role. */
export default function VmwareUsersRolesPanel({ users = [], rolesCatalog = [], onAction, acting }) {
  const roles = rolesCatalog.length ? rolesCatalog : ['Administrator', 'Read Only', 'Virtual Machine User']
  const [showAdd, setShowAdd] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState(roles[1] || 'Read Only')
  const [error, setError] = useState('')
  // Inline password reset
  const [resetFor, setResetFor] = useState(null)
  const [resetPw, setResetPw] = useState('')

  const create = async () => {
    if (!username.trim()) { setError('Username is required'); return }
    if (password.length < 6) { setError('Password must be at least 6 characters'); return }
    setError('')
    try {
      await onAction('create_vcenter_user', { username: username.trim(), password, role })
      setUsername(''); setPassword(''); setShowAdd(false)
    } catch (e) {
      setError(e?.response?.data?.error || 'Create failed')
    }
  }

  const doReset = async (user) => {
    if (resetPw.length < 6) return
    await onAction('reset_user_password', { user_id: user.id, username: user.username, password: resetPw })
    setResetFor(null); setResetPw('')
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between">
        <span>Users &amp; Roles — vsphere.local</span>
        <button type="button" onClick={() => setShowAdd(v => !v)} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">
          {showAdd ? 'Cancel' : 'Add user…'}
        </button>
      </div>
      <div className="vm-panel-body">
        <div className="text-[11px] text-[#8FA5B8] mb-3 bg-[#16222f] border border-[#22303f] rounded px-2.5 py-1.5">
          Default lab operator: <span className="font-mono text-[#E8EDF2]">lab_vmware</span> / <span className="font-mono text-[#E8EDF2]">lab_vmware@123</span>
        </div>
        {showAdd && (
          <div className="mb-4 p-3 border border-[#2d3a4a] rounded-lg space-y-2 bg-[#16222f]">
            <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Username (e.g. ops_user)" className="vm-input !pl-3 w-full text-xs" autoComplete="off" />
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password (min 6 chars)" className="vm-input !pl-3 w-full text-xs" autoComplete="new-password" />
            <select value={role} onChange={e => setRole(e.target.value)} className="vm-input !pl-3 w-full text-xs">
              {roles.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            {error && <p className="text-[11px] text-[#D9534F]">{error}</p>}
            <button type="button" disabled={acting} onClick={create} className="vm-btn vm-btn-green text-xs w-full justify-center">Create user</button>
          </div>
        )}
        <table className="vm-table">
          <thead>
            <tr>{['Username', 'Role', 'Status', 'Last login', ''].map(h => <th key={h || 'x'}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}>
                <td className="text-[#5b9bf5]">{u.username}{u.builtin && <span className="ml-1 text-[9px] text-[#8FA5B8]">(built-in)</span>}</td>
                <td>
                  <select
                    value={u.role}
                    disabled={acting}
                    onChange={e => onAction('assign_user_role', { user_id: u.id, username: u.username, role: e.target.value })}
                    className="bg-[#243447] border border-[#2d3a4a] rounded text-[11px] text-[#E8EDF2] px-1.5 py-0.5"
                  >
                    {roles.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className={u.enabled ? 'text-[#5DB85D] font-semibold' : 'text-[#8FA5B8]'}>{u.enabled ? 'Enabled' : 'Disabled'}</td>
                <td className="text-[#8FA5B8]">{u.last_login || 'Never'}</td>
                <td className="whitespace-nowrap">
                  {resetFor === u.id ? (
                    <span className="flex items-center gap-1">
                      <input type="password" value={resetPw} onChange={e => setResetPw(e.target.value)} placeholder="New password"
                        className="bg-[#0f1722] border border-[#2d3a4a] rounded text-[10px] text-[#E8EDF2] px-1.5 py-0.5 w-24" autoComplete="new-password" />
                      <button type="button" disabled={acting || resetPw.length < 6} onClick={() => doReset(u)} className="text-[10px] text-[#5DB85D] hover:underline disabled:opacity-40">Save</button>
                      <button type="button" onClick={() => { setResetFor(null); setResetPw('') }} className="text-[10px] text-[#8FA5B8] hover:underline">Cancel</button>
                    </span>
                  ) : (
                    <>
                      <button type="button" onClick={() => { setResetFor(u.id); setResetPw('') }} className="text-[10px] text-[#5b9bf5] hover:underline mr-2">Reset password</button>
                      {!u.builtin && (
                        <button type="button" disabled={acting} onClick={() => onAction('delete_vcenter_user', { user_id: u.id, username: u.username })} className="text-[10px] text-[#D9534F] hover:underline">Remove</button>
                      )}
                    </>
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
