import { useState } from 'react'

/* vSphere "Administration" area — reachable from Menu ▸ Administration.
   Left rail with Access Control ▸ (Users and Groups / Roles / Global
   Permissions). Styled like vSphere SSO. Builds on the existing
   create_vcenter_user / assign_user_role / create_role / assign_role actions. */

// Privilege groups shown for each role (read-only catalogue, like vSphere).
const ROLE_PRIVILEGES = {
  Administrator: ['All Privileges'],
  'Read Only': ['System.Anonymous', 'System.View', 'System.Read'],
  'No Access': [],
  'Virtual Machine User': ['Virtual machine.Interaction', 'Virtual machine.Snapshot management'],
  'Virtual Machine Power User': ['Virtual machine.Interaction', 'Virtual machine.Configuration', 'Virtual machine.Snapshot management', 'Datastore.Browse'],
  'Virtual Machine Administrator': ['Virtual machine.*', 'Datastore.*', 'Network.Assign', 'Resource.*'],
  'Network Administrator': ['Network.*', 'Host.Config.Network', 'dvPort group.*'],
  'Storage Administrator': ['Datastore.*', 'Host.Config.Storage', 'Profile-driven storage.*'],
}

const PRIVILEGE_GROUPS = [
  'Alarms', 'Datacenter', 'Datastore', 'dvPort group', 'Folder', 'Global',
  'Host', 'Network', 'Permissions', 'Resource', 'Scheduled task', 'Sessions',
  'Tasks', 'vApp', 'Virtual machine', 'vSphere Tagging',
]

function NavItem({ active, label, indent = 1, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left py-1.5 text-[11.5px] ${active ? 'bg-[rgba(45,124,255,.15)] text-white border-l-2 border-[#2D7CFF]' : 'text-[#c3d3e3] hover:bg-white/[0.05] border-l-2 border-transparent'}`}
      style={{ paddingLeft: 8 + indent * 12 }}
    >
      {label}
    </button>
  )
}

function UsersAndGroups({ users, roles, onAction, acting }) {
  const [showAdd, setShowAdd] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState(roles[1] || 'Read Only')
  const [error, setError] = useState('')
  const [resetFor, setResetFor] = useState(null)
  const [resetPw, setResetPw] = useState('')

  const create = async () => {
    if (!username.trim()) { setError('Username is required'); return }
    if (password.length < 6) { setError('Password must be at least 6 characters'); return }
    setError('')
    try {
      await onAction('create_vcenter_user', { username: username.trim(), password, role })
      setUsername(''); setPassword(''); setShowAdd(false)
    } catch (e) { setError(e?.response?.data?.error || 'Create failed') }
  }
  const doReset = async (u) => {
    if (resetPw.length < 6) return
    await onAction('reset_user_password', { user_id: u.id, username: u.username, password: resetPw })
    setResetFor(null); setResetPw('')
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between">
        <span>Users and Groups — vsphere.local</span>
        <button type="button" onClick={() => setShowAdd(v => !v)} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">
          {showAdd ? 'Cancel' : 'Add User…'}
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
                  <select value={u.role} disabled={acting}
                    onChange={e => onAction('assign_user_role', { user_id: u.id, username: u.username, role: e.target.value })}
                    className="bg-[#243447] border border-[#2d3a4a] rounded text-[11px] text-[#E8EDF2] px-1.5 py-0.5">
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

function Roles({ roles, onAction, acting }) {
  const [selected, setSelected] = useState(roles[0] || 'Administrator')
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [selPrivs, setSelPrivs] = useState([])
  const [error, setError] = useState('')
  const privileges = ROLE_PRIVILEGES[selected] || ['Custom privilege set']
  const togglePriv = (p) => setSelPrivs(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p])

  const createRole = async () => {
    if (!newName.trim()) { setError('Role name is required'); return }
    setError('')
    try {
      await onAction('create_role', { name: newName.trim(), privilege_groups: selPrivs })
      setNewName(''); setSelPrivs([]); setShowNew(false)
    } catch (e) { setError(e?.response?.data?.error || 'Create failed') }
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between">
        <span>Roles</span>
        <button type="button" onClick={() => setShowNew(v => !v)} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">
          {showNew ? 'Cancel' : 'New Role…'}
        </button>
      </div>
      <div className="vm-panel-body">
        {showNew && (
          <div className="mb-4 p-3 border border-[#2d3a4a] rounded-lg space-y-2 bg-[#16222f]">
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Role name (e.g. Backup Operator)" className="vm-input !pl-3 w-full text-xs" />
            <p className="text-[10px] text-[#8fa5b8]">Select privilege groups:</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 max-h-44 overflow-y-auto">
              {PRIVILEGE_GROUPS.map(g => (
                <label key={g} className="flex items-center gap-1.5 text-[11px] text-[#E8EDF2] cursor-pointer">
                  <input type="checkbox" checked={selPrivs.includes(g)} onChange={() => togglePriv(g)} />
                  {g}
                </label>
              ))}
            </div>
            {error && <p className="text-[11px] text-[#D9534F]">{error}</p>}
            <button type="button" disabled={acting} onClick={createRole} className="vm-btn vm-btn-green text-xs w-full justify-center">Create role</button>
          </div>
        )}
        <div className="flex gap-3 min-h-0">
          <div className="w-44 shrink-0 border border-[#2D3A4A] rounded bg-[#16222f] py-1 max-h-72 overflow-y-auto">
            {roles.map(r => (
              <button key={r} type="button" onClick={() => setSelected(r)}
                className={`w-full text-left px-3 py-1.5 text-[11.5px] ${selected === r ? 'bg-[rgba(45,124,255,.15)] text-white' : 'text-[#c3d3e3] hover:bg-white/[0.05]'}`}>
                {r}
              </button>
            ))}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-semibold text-white mb-1">{selected}</p>
            <p className="text-[10px] text-[#8FA5B8] mb-2">Privileges granted by this role:</p>
            <div className="border border-[#2D3A4A] rounded bg-[#16222f] p-2 space-y-1 max-h-60 overflow-y-auto">
              {privileges.map(p => (
                <div key={p} className="flex items-center gap-1.5 text-[11px] text-[#c3d3e3]">
                  <span className="text-[#5DB85D]">✓</span>{p}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function GlobalPermissions({ permissions, roles, onAction, acting }) {
  const [principal, setPrincipal] = useState('')
  const [role, setRole] = useState(roles[0] || 'Administrator')
  const [propagate, setPropagate] = useState(true)
  const [error, setError] = useState('')

  const add = async () => {
    if (!principal.trim()) { setError('User or group is required'); return }
    setError('')
    try {
      await onAction('assign_role', { principal: principal.trim(), role, propagate, entity: 'Global', entity_id: 'global', entity_type: 'global' })
      setPrincipal('')
    } catch (e) { setError(e?.response?.data?.error || 'Assign failed') }
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header">Global Permissions</div>
      <div className="vm-panel-body">
        <div className="mb-3 p-3 border border-[#2d3a4a] rounded-lg bg-[#16222f] grid grid-cols-[1fr_auto_auto_auto] gap-2 items-end">
          <div>
            <label className="block text-[10px] text-[#8fa5b8] mb-1">User / Group</label>
            <input value={principal} onChange={e => setPrincipal(e.target.value)} placeholder="vsphere.local\ops_user" className="vm-input !pl-3 text-xs" />
          </div>
          <div>
            <label className="block text-[10px] text-[#8fa5b8] mb-1">Role</label>
            <select value={role} onChange={e => setRole(e.target.value)} className="vm-input !pl-3 text-xs">
              {roles.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-1.5 text-[11px] text-[#E8EDF2] cursor-pointer pb-1.5">
            <input type="checkbox" checked={propagate} onChange={e => setPropagate(e.target.checked)} />
            Propagate
          </label>
          <button type="button" disabled={acting} onClick={add} className="vm-btn vm-btn-blue text-xs">Add</button>
        </div>
        {error && <p className="text-[11px] text-[#D9534F] mb-2">{error}</p>}
        <table className="vm-table">
          <thead><tr>{['User / Group', 'Role', 'Defined In', 'Propagate', ''].map(h => <th key={h || 'x'}>{h}</th>)}</tr></thead>
          <tbody>
            {permissions.map(p => (
              <tr key={p.id}>
                <td className="text-[#5b9bf5]">{p.principal}</td>
                <td>{p.role}</td>
                <td className="text-[#8FA5B8]">{p.entity}</td>
                <td>{p.propagate ? 'Yes' : 'No'}</td>
                <td>
                  <button type="button" disabled={acting} onClick={() => onAction('revoke_permission', { permission_id: p.id, entity: p.entity })}
                    className="text-[10px] text-[#D9534F] hover:underline">Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function VmwareAdministration({ users = [], rolesCatalog = [], permissions = [], onAction, acting }) {
  const roles = rolesCatalog.length ? rolesCatalog : ['Administrator', 'Read Only', 'No Access']
  const [view, setView] = useState('users')

  return (
    <div className="flex gap-3 min-h-0">
      <div className="w-52 shrink-0 border border-[#2D3A4A] rounded-lg bg-[#16222f] overflow-y-auto py-1.5">
        <p className="px-3 py-1 text-[10px] font-bold text-[#6880a0] uppercase tracking-wider m-0">Access Control</p>
        <NavItem active={view === 'users'} label="Users and Groups" onClick={() => setView('users')} />
        <NavItem active={view === 'roles'} label="Roles" onClick={() => setView('roles')} />
        <NavItem active={view === 'permissions'} label="Global Permissions" onClick={() => setView('permissions')} />
        <p className="px-3 py-1 mt-2 text-[10px] font-bold text-[#6880a0] uppercase tracking-wider m-0">Single Sign On</p>
        <NavItem active={view === 'users'} label="Configuration" indent={1} onClick={() => setView('users')} />
      </div>
      <div className="flex-1 min-w-0">
        {view === 'users' && <UsersAndGroups users={users} roles={roles} onAction={onAction} acting={acting} />}
        {view === 'roles' && <Roles roles={roles} onAction={onAction} acting={acting} />}
        {view === 'permissions' && <GlobalPermissions permissions={permissions} roles={roles} onAction={onAction} acting={acting} />}
      </div>
    </div>
  )
}
