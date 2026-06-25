import { useMemo, useState } from 'react'
import { ChevronRight, Users, User, Folder, UserPlus, Search } from 'lucide-react'
import { useOS } from '../store'
import { useCtxMenu, Dialog, Tabs } from '../ui'

export default function ADUC() {
  const os = useOS()
  const ctx = useCtxMenu()
  const [selOU, setSelOU] = useState('Engineering')
  const [expanded, setExpanded] = useState({ 'lab.local': true, Corp: true })
  const [selUser, setSelUser] = useState(null)
  const [wizard, setWizard] = useState(false)
  const [props, setProps] = useState(null)
  const [reset, setReset] = useState(null)
  const [find, setFind] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = (m) => { setToast(m); setTimeout(() => setToast(null), 2500) }

  const objects = useMemo(() => {
    if (selOU === 'Users') return os.adUsers.filter((u) => u.ou.startsWith('CN=Users'))
    return os.adUsers.filter((u) => u.dept === selOU)
  }, [selOU, os.adUsers])

  const groupsForOU = selOU && selOU !== 'Users' ? os.adGroups.filter((g) => g.name.startsWith(selOU)) : []

  const renderOU = (node, depth = 1) => {
    const kids = node.children || []
    const id = node.name
    return (
      <div key={id}>
        <div className={`winos-tree-row ${selOU === id ? 'sel' : ''}`} style={{ paddingLeft: 8 + depth * 14 }}
          onClick={() => { if (node.type === 'ou' || node.type === 'container') setSelOU(id); if (kids.length) setExpanded((x) => ({ ...x, [id]: !x[id] })) }}>
          {kids.length ? <ChevronRight size={12} style={{ transform: expanded[id] ? 'rotate(90deg)' : '' }} /> : <span style={{ width: 12, display: 'inline-block' }} />}
          <Folder size={13} color={node.type === 'ou' ? '#c98a00' : '#999'} /> {node.name}
        </div>
        {expanded[id] && kids.map((c) => renderOU(c, depth + 1))}
      </div>
    )
  }

  const userCtx = (u) => (e) => {
    e.preventDefault(); setSelUser(u.sam)
    ctx.open(e.clientX, e.clientY, [
      { label: 'Copy…' }, { label: 'Add to a group…' }, { label: 'Name Mappings…' },
      { label: u.enabled ? 'Disable Account' : 'Enable Account', onClick: () => os.modifyADUser(u.sam, { enabled: !u.enabled }) },
      { label: 'Reset Password…', onClick: () => setReset(u) },
      { label: 'Move…' }, { label: 'Open Home Page' }, { label: 'Send Mail' }, { sep: true },
      { label: 'Delete', onClick: () => os.deleteADUser(u.sam) }, { label: 'Rename' }, { sep: true },
      { label: 'Properties', onClick: () => setProps(u) },
    ])
  }

  return (
    <div className="winos-app">
      <div className="winos-toolbar">
        <span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Help</span>
        <span style={{ width: 1, height: 20, background: '#ddd' }} />
        <button className="winos-btn" onClick={() => setWizard(true)}><UserPlus size={13} /> New User</button>
        <button className="winos-btn" onClick={() => setFind(true)}><Search size={13} /> Find</button>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: '#888' }}>{os.adUsers.length} users in directory</span>
      </div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 270 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}><Users size={13} /> Active Directory Users and Computers [SERVER01.lab.local]</div>
          <div className="winos-tree-row" style={{ paddingLeft: 22 }}><Search size={12} /> Saved Queries</div>
          {renderOU(os.ouTree)}
        </div>
        <div className="winos-main">
          <table className="winos-table">
            <thead><tr><th style={{ width: '28%' }}>Name</th><th>Type</th><th>Description</th></tr></thead>
            <tbody>
              {groupsForOU.map((g) => (
                <tr key={g.name}><td><Users size={13} /> {g.name}</td><td>Security Group - {g.scope}</td><td>{g.desc}</td></tr>
              ))}
              {objects.map((u) => (
                <tr key={u.sam} className={selUser === u.sam ? 'sel' : ''} onClick={() => setSelUser(u.sam)} onDoubleClick={() => setProps(u)} onContextMenu={userCtx(u)}>
                  <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, opacity: u.enabled ? 1 : 0.5 }}><User size={13} color={u.locked ? '#c42b1c' : '#0078d4'} /> {u.display}{u.locked ? ' 🔒' : ''}{!u.enabled ? ' (disabled)' : ''}</span></td>
                  <td>User</td><td>{u.title}</td>
                </tr>
              ))}
              {objects.length === 0 && groupsForOU.length === 0 && <tr><td colSpan={3} style={{ color: '#888', padding: 14 }}>There are no items to show in this view.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div className="winos-status"><span>{objects.length + groupsForOU.length} object(s)</span><span>lab.local/Corp/{selOU}</span></div>

      {wizard && <NewUserWizard ou={selOU} onClose={() => setWizard(false)} onDone={(n) => showToast(`User "${n}" created.`)} />}
      {props && <UserProps user={props} onClose={() => setProps(null)} />}
      {reset && <ResetDialog user={reset} onClose={() => setReset(null)} onDone={() => showToast(`The password for ${reset.sam} has been changed.`)} />}
      {find && <FindDialog onClose={() => setFind(false)} onOpen={(u) => { setProps(u); setFind(false) }} />}
      {toast && <div style={{ position: 'absolute', bottom: 30, right: 16, background: '#323130', color: '#fff', padding: '10px 16px', borderRadius: 4, fontSize: 12.5, zIndex: 100 }}>{toast}</div>}
    </div>
  )
}

function NewUserWizard({ ou, onClose, onDone }) {
  const os = useOS()
  const [page, setPage] = useState(1)
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [sam, setSam] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [opts, setOpts] = useState({ mustChange: true, cantChange: false, neverExpire: false, disabled: false })
  const display = `${first} ${last}`.trim()

  const finish = () => {
    os.createADUser({
      sam: sam || (first[0] + last).toLowerCase(), first, last, display, upn: `${sam || (first[0] + last).toLowerCase()}@lab.local`,
      email: '', dept: ou, title: '', ou: `OU=${ou},OU=Corp,DC=lab,DC=local`, enabled: !opts.disabled, locked: false,
      phone: '', office: '', company: 'Lab Industries', manager: '', employeeId: '',
      groups: ['Domain Users'], pwLastSet: '2024-01-17', lastLogon: 'Never',
    })
    onDone(display); onClose()
  }

  return (
    <Dialog title="New Object - User" onClose={onClose} width={460}
      footer={<>
        {page > 1 && <button className="winos-btn" onClick={() => setPage(page - 1)}>&lt; Back</button>}
        {page < 3 ? <button className="winos-btn primary" disabled={page === 1 && (!first || !last)} onClick={() => setPage(page + 1)}>Next &gt;</button>
          : <button className="winos-btn primary" onClick={finish}>Finish</button>}
        <button className="winos-btn" onClick={onClose}>Cancel</button>
      </>}>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 10 }}>Create in: lab.local/Corp/{ou}</div>
      {page === 1 && (
        <div className="winos-grid2">
          <span>First name:</span><input className="winos-input" value={first} onChange={(e) => { setFirst(e.target.value); setSam((e.target.value[0] || '' + last).toLowerCase() + last.toLowerCase()) }} />
          <span>Last name:</span><input className="winos-input" value={last} onChange={(e) => { setLast(e.target.value); setSam(((first[0] || '') + e.target.value).toLowerCase()) }} />
          <span>Full name:</span><input className="winos-input" value={display} readOnly />
          <span>User logon name:</span><span><input className="winos-input" value={sam} onChange={(e) => setSam(e.target.value)} style={{ width: 130 }} /> @lab.local</span>
        </div>
      )}
      {page === 2 && (
        <div>
          <div className="winos-grid2" style={{ marginBottom: 12 }}>
            <span>Password:</span><input className="winos-input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} />
            <span>Confirm password:</span><input className="winos-input" type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} />
          </div>
          {pw && pw2 && pw !== pw2 && <div style={{ color: '#c42b1c', fontSize: 12, marginBottom: 8 }}>The passwords do not match.</div>}
          {[['mustChange', 'User must change password at next logon'], ['cantChange', 'User cannot change password'], ['neverExpire', 'Password never expires'], ['disabled', 'Account is disabled']].map(([k, l]) => (
            <label key={k} style={{ display: 'block', marginBottom: 4 }}><input type="checkbox" checked={opts[k]} onChange={(e) => setOpts((o) => ({ ...o, [k]: e.target.checked }))} /> {l}</label>
          ))}
        </div>
      )}
      {page === 3 && (
        <div style={{ fontSize: 12.5 }}>
          <p>When you click Finish, the following object will be created:</p>
          <ul style={{ paddingLeft: 18, lineHeight: 1.7 }}>
            <li>Full name: {display}</li>
            <li>User logon name: {sam}@lab.local</li>
            <li>The user {opts.mustChange ? 'must' : 'need not'} change password at next logon.</li>
            {opts.disabled && <li>The account is disabled.</li>}
          </ul>
        </div>
      )}
    </Dialog>
  )
}

function ResetDialog({ user, onClose, onDone }) {
  const [pw, setPw] = useState(''); const [pw2, setPw2] = useState('')
  const os = useOS()
  return (
    <Dialog title="Reset Password" onClose={onClose} width={420}
      footer={<><button className="winos-btn primary" disabled={!pw || pw !== pw2} onClick={() => { os.modifyADUser(user.sam, { locked: false, pwLastSet: '2024-01-17' }); onDone(); onClose() }}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button></>}>
      <div className="winos-grid2" style={{ fontSize: 12.5 }}>
        <span>New password:</span><input className="winos-input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} />
        <span>Confirm password:</span><input className="winos-input" type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} />
      </div>
      <label style={{ display: 'block', marginTop: 10, fontSize: 12.5 }}><input type="checkbox" defaultChecked /> User must change password at next logon</label>
      <label style={{ display: 'block', fontSize: 12.5 }}><input type="checkbox" defaultChecked /> Unlock the user's account</label>
    </Dialog>
  )
}

function FindDialog({ onClose, onOpen }) {
  const os = useOS()
  const [q, setQ] = useState('')
  const results = q ? os.adUsers.filter((u) => u.display.toLowerCase().includes(q.toLowerCase()) || u.sam.toLowerCase().includes(q.toLowerCase())) : []
  return (
    <Dialog title="Find Users, Contacts, and Groups" onClose={onClose} width={500}
      footer={<button className="winos-btn" onClick={onClose}>Close</button>}>
      <div style={{ fontSize: 12.5 }}>
        <div style={{ marginBottom: 8 }}>Name: <input className="winos-input" style={{ width: 280 }} value={q} onChange={(e) => setQ(e.target.value)} autoFocus /> <button className="winos-btn primary">Find Now</button></div>
        <div style={{ border: '1px solid #ddd', height: 220, overflow: 'auto' }}>
          <table className="winos-table"><thead><tr><th>Name</th><th>Type</th><th>Description</th></tr></thead>
            <tbody>{results.map((u) => (<tr key={u.sam} onDoubleClick={() => onOpen(u)}><td><User size={12} /> {u.display}</td><td>User</td><td>{u.title}</td></tr>))}</tbody>
          </table>
          {q && results.length === 0 && <div style={{ padding: 12, color: '#888' }}>No items found.</div>}
        </div>
      </div>
    </Dialog>
  )
}

const TABS = ['General', 'Address', 'Account', 'Profile', 'Telephones', 'Organization', 'Member Of', 'Dial-in']

function UserProps({ user, onClose }) {
  const os = useOS()
  const live = os.adUsers.find((u) => u.sam === user.sam) || user
  const [tab, setTab] = useState('General')
  const [form, setForm] = useState(live)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const allGroups = os.adGroups.map((g) => g.name)

  return (
    <Dialog title={`${live.display} Properties`} onClose={onClose} width={520}
      footer={<><button className="winos-btn primary" onClick={() => { os.modifyADUser(user.sam, form); onClose() }}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button><button className="winos-btn" onClick={() => os.modifyADUser(user.sam, form)}>Apply</button></>}>
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      <div style={{ paddingTop: 12, fontSize: 12.5, minHeight: 240 }}>
        {tab === 'General' && (
          <div className="winos-grid2">
            <span>First name:</span><input className="winos-input" value={form.first} onChange={(e) => set('first', e.target.value)} />
            <span>Last name:</span><input className="winos-input" value={form.last} onChange={(e) => set('last', e.target.value)} />
            <span>Display name:</span><input className="winos-input" value={form.display} onChange={(e) => set('display', e.target.value)} />
            <span>Description:</span><input className="winos-input" value={form.title} onChange={(e) => set('title', e.target.value)} />
            <span>Office:</span><input className="winos-input" value={form.office} onChange={(e) => set('office', e.target.value)} />
            <span>Telephone number:</span><input className="winos-input" value={form.phone} onChange={(e) => set('phone', e.target.value)} />
            <span>E-mail:</span><input className="winos-input" value={form.email} onChange={(e) => set('email', e.target.value)} />
          </div>
        )}
        {tab === 'Address' && (
          <div className="winos-grid2">
            <span>Street:</span><textarea className="winos-input" rows={2} defaultValue="123 Lab Street" />
            <span>City:</span><input className="winos-input" defaultValue="Metropolis" />
            <span>State/province:</span><input className="winos-input" defaultValue="NY" />
            <span>Zip/Postal Code:</span><input className="winos-input" defaultValue="10001" />
            <span>Country/region:</span><select className="winos-input"><option>United States</option></select>
          </div>
        )}
        {tab === 'Account' && (
          <div className="winos-grid2">
            <span>User logon name:</span><span><input className="winos-input" value={form.sam} readOnly style={{ width: 120 }} /> @lab.local</span>
            <span>Logon Hours:</span><button className="winos-btn" style={{ width: 'fit-content' }}>Logon Hours…</button>
            <span>Log On To:</span><button className="winos-btn" style={{ width: 'fit-content' }}>Log On To…</button>
            <span style={{ alignSelf: 'start' }}>Account options:</span>
            <div>
              <label style={{ display: 'block' }}><input type="checkbox" /> User must change password at next logon</label>
              <label style={{ display: 'block' }}><input type="checkbox" /> User cannot change password</label>
              <label style={{ display: 'block' }}><input type="checkbox" /> Password never expires</label>
              <label style={{ display: 'block' }}><input type="checkbox" checked={!form.enabled} onChange={(e) => set('enabled', !e.target.checked)} /> Account is disabled</label>
              <label style={{ display: 'block' }}><input type="checkbox" checked={form.locked} onChange={(e) => set('locked', e.target.checked)} /> Unlock account (currently {form.locked ? 'locked' : 'unlocked'})</label>
            </div>
            <span>Account expires:</span><span><label><input type="radio" name="exp" defaultChecked /> Never</label> <label><input type="radio" name="exp" /> End of:</label></span>
          </div>
        )}
        {tab === 'Profile' && (
          <div className="winos-grid2">
            <span>Profile path:</span><input className="winos-input" defaultValue={`\\\\server01\\profiles\\${form.sam}`} />
            <span>Logon script:</span><input className="winos-input" defaultValue="logon.bat" />
            <span>Home folder:</span><span><label><input type="radio" name="hf" defaultChecked /> Connect</label> <select className="winos-input"><option>Z:</option></select> to <input className="winos-input" defaultValue={`\\\\server01\\home\\${form.sam}`} style={{ width: 150 }} /></span>
          </div>
        )}
        {tab === 'Telephones' && (
          <div className="winos-grid2">
            <span>Home:</span><input className="winos-input" />
            <span>Pager:</span><input className="winos-input" />
            <span>Mobile:</span><input className="winos-input" value={form.phone} onChange={(e) => set('phone', e.target.value)} />
            <span>Fax:</span><input className="winos-input" />
            <span>IP phone:</span><input className="winos-input" />
            <span style={{ alignSelf: 'start' }}>Notes:</span><textarea className="winos-input" rows={3} />
          </div>
        )}
        {tab === 'Organization' && (
          <div className="winos-grid2">
            <span>Title:</span><input className="winos-input" value={form.title} onChange={(e) => set('title', e.target.value)} />
            <span>Department:</span><input className="winos-input" value={form.dept} onChange={(e) => set('dept', e.target.value)} />
            <span>Company:</span><input className="winos-input" value={form.company} onChange={(e) => set('company', e.target.value)} />
            <span>Manager:</span><span><input className="winos-input" value={form.manager} readOnly style={{ width: 180 }} /> <button className="winos-btn">Change…</button></span>
          </div>
        )}
        {tab === 'Member Of' && (
          <div>
            <div style={{ color: '#666', marginBottom: 6 }}>Member of:</div>
            <div style={{ border: '1px solid #ddd', height: 150, overflow: 'auto', marginBottom: 8 }}>
              {form.groups.map((g) => <div key={g} className="winos-tree-row"><Users size={12} /> {g}</div>)}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <select className="winos-input" id="grpadd" style={{ flex: 1 }}>{allGroups.filter((g) => !form.groups.includes(g)).map((g) => <option key={g}>{g}</option>)}</select>
              <button className="winos-btn" onClick={() => { const v = document.getElementById('grpadd').value; if (v && !form.groups.includes(v)) set('groups', [...form.groups, v]) }}>Add…</button>
              <button className="winos-btn" onClick={() => set('groups', form.groups.slice(0, -1))}>Remove</button>
            </div>
          </div>
        )}
        {tab === 'Dial-in' && (
          <div>
            <div style={{ color: '#666', marginBottom: 6 }}>Network Access Permission:</div>
            <label style={{ display: 'block' }}><input type="radio" name="dialin" /> Allow access</label>
            <label style={{ display: 'block' }}><input type="radio" name="dialin" /> Deny access</label>
            <label style={{ display: 'block' }}><input type="radio" name="dialin" defaultChecked /> Control access through NPS Network Policy</label>
          </div>
        )}
      </div>
    </Dialog>
  )
}
