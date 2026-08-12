import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  LayoutDashboard, Users, RefreshCw, Settings2, ArrowLeft,
  XCircle, CheckCircle2, AlertTriangle, Lock, Server,
  ShieldCheck, Network, Globe, HardDrive, Cpu, ChevronRight, Plus,
  Play, Square, RotateCw, Download, UserCog, FolderTree, Power, Trash2,
  FolderOpen, Wifi, Monitor, Terminal, Settings, User, KeyRound, Package,
} from 'lucide-react'
import { windowsApi } from '../../api/windows'
import { LabChromeControls } from '../lab/LabChromeBar'
import AddRolesWizard from './AddRolesWizard'
import NewUserWizard from './NewUserWizard'
import WindowsServer2022 from './os/WindowsServer2022'

/* ── Scoped, self-contained Windows Server chrome (no shared CSS). Windows
   blue (#0078D4) accents on a light "Server Manager" surface, a dark taskbar,
   and a flat Fluent-ish control set. ── */
const SCOPED_CSS = `
.win-sim {
  --win-blue: #0078D4;
  --win-blue-dark: #005a9e;
  --win-bg: #f3f3f3;
  --win-panel: #ffffff;
  --win-border: #e1e1e1;
  --win-border-2: #d0d0d0;
  --win-text: #1b1b1b;
  --win-muted: #616161;
  --win-nav: #1f1f1f;
  --win-nav-hover: #2d2d2d;
  --win-green: #107c10;
  --win-amber: #9d5d00;
  --win-red: #c42b1c;
  --win-taskbar: #1d2230;
  color: var(--win-text);
  font-family: 'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--win-bg);
  min-height: 100%;
  display: flex;
  flex-direction: column;
}
.win-sim .win-titlebar {
  display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;
  padding: 0.45rem 0.9rem; background: var(--win-blue); color: #fff;
  position: sticky; top: 0; z-index: 20;
}
.win-sim .win-btn {
  display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 4px;
  padding: 0.4rem 0.75rem; font-size: 0.8rem; font-weight: 600; cursor: pointer;
  border: 1px solid rgba(255,255,255,.5); background: rgba(255,255,255,.12); color: #fff;
  transition: background 0.12s;
}
.win-sim .win-btn:hover { background: rgba(255,255,255,.24); }
.win-sim .win-light-btn {
  display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 4px;
  padding: 0.4rem 0.75rem; font-size: 0.8rem; font-weight: 600; cursor: pointer;
  border: 1px solid var(--win-border-2); background: #fafafa; color: var(--win-text);
  transition: background 0.12s, border-color 0.12s;
}
.win-sim .win-light-btn:hover { background: #f0f0f0; border-color: var(--win-blue); }
.win-sim .win-light-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.win-sim .win-primary {
  border: none; background: var(--win-blue); color: #fff;
}
.win-sim .win-primary:hover { background: var(--win-blue-dark); }
.win-sim .win-primary:disabled { opacity: 0.55; cursor: not-allowed; }
.win-sim .win-body { flex: 1; display: flex; min-height: 0; }
.win-sim .win-nav {
  width: 230px; background: var(--win-nav); color: #e6e6e6; flex-shrink: 0;
  display: flex; flex-direction: column; padding-top: 0.5rem;
}
.win-sim .win-nav-item {
  display: flex; align-items: center; gap: 0.65rem; padding: 0.7rem 1rem;
  font-size: 0.85rem; cursor: pointer; border-left: 3px solid transparent; color: #d4d4d4;
}
.win-sim .win-nav-item:hover { background: var(--win-nav-hover); color: #fff; }
.win-sim .win-nav-item.active {
  background: var(--win-nav-hover); color: #fff; border-left-color: var(--win-blue);
}
.win-sim .win-content { flex: 1; overflow-y: auto; padding: 1.25rem 1.5rem; min-width: 0; }
.win-sim .win-h1 { font-size: 1.35rem; font-weight: 600; color: #323130; margin-bottom: 0.15rem; }
.win-sim .win-sub { font-size: 0.8rem; color: var(--win-muted); }
.win-sim .win-card {
  background: var(--win-panel); border: 1px solid var(--win-border); border-radius: 4px;
}
.win-sim .win-card-head {
  padding: 0.7rem 1rem; border-bottom: 1px solid var(--win-border);
  font-size: 0.9rem; font-weight: 600; color: #323130; display: flex; align-items: center; gap: 0.5rem;
}
.win-sim .win-tile {
  background: var(--win-panel); border: 1px solid var(--win-border); border-radius: 4px;
  padding: 0.9rem 1rem;
}
.win-sim .win-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.win-sim .win-table th {
  text-align: left; color: var(--win-muted); font-weight: 600; padding: 0.55rem 0.85rem;
  border-bottom: 1px solid var(--win-border); background: #fafafa; white-space: nowrap;
}
.win-sim .win-table td { padding: 0.55rem 0.85rem; border-bottom: 1px solid #f0f0f0; }
.win-sim .win-table tr:hover td { background: #f7fbff; }
.win-sim .win-badge {
  display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.7rem; font-weight: 700;
  padding: 0.1rem 0.5rem; border-radius: 3px; letter-spacing: 0.01em; white-space: nowrap;
}
.win-sim .win-b-ok { background: rgba(16,124,16,.12); color: var(--win-green); }
.win-sim .win-b-bad { background: rgba(196,43,28,.12); color: var(--win-red); }
.win-sim .win-b-warn { background: rgba(157,93,0,.12); color: var(--win-amber); }
.win-sim .win-b-info { background: rgba(0,120,212,.12); color: var(--win-blue); }
.win-sim .win-b-muted { background: #ededed; color: var(--win-muted); }
.win-sim .win-banner {
  display: flex; align-items: flex-start; gap: 0.55rem; font-size: 0.82rem;
  padding: 0.7rem 0.9rem; border-radius: 4px; margin-bottom: 1rem; line-height: 1.45;
}
.win-sim .win-banner-goal { background: #eef6fd; border: 1px solid #c7e0f4; color: #1b4f72; }
.win-sim .win-banner-err { background: #fdf3f2; border: 1px solid #f1c7c2; color: #8a2018; }
.win-sim .win-banner-ok { background: #f1f8f1; border: 1px solid #c8e6c8; color: #0b5c0b; }
.win-sim .win-input {
  background: #fff; border: 1px solid var(--win-border-2); border-radius: 4px;
  padding: 0.5rem 0.65rem; color: var(--win-text); font-size: 0.85rem; outline: none; width: 100%;
}
.win-sim .win-input:focus { border-color: var(--win-blue); box-shadow: 0 0 0 1px var(--win-blue); }
.win-sim .win-select {
  background: #fff; border: 1px solid var(--win-border-2); border-radius: 4px;
  padding: 0.45rem 0.55rem; color: var(--win-text); font-size: 0.82rem; outline: none;
}
.win-sim .win-taskbar {
  height: 44px; background: var(--win-taskbar); display: flex; align-items: center;
  gap: 0.5rem; padding: 0 0.6rem; flex-shrink: 0; border-top: 1px solid #0b0e16;
}
.win-sim .win-start {
  width: 30px; height: 30px; border-radius: 4px; display: grid; place-items: center;
  cursor: pointer; background: transparent;
}
.win-sim .win-start:hover { background: rgba(255,255,255,.1); }
.win-sim .win-taskitem {
  display: inline-flex; align-items: center; gap: 0.4rem; height: 32px; padding: 0 0.7rem;
  border-radius: 4px; font-size: 0.78rem; color: #e6e6e6; cursor: pointer;
  border-bottom: 2px solid transparent;
}
.win-sim .win-taskitem.active { background: rgba(255,255,255,.12); border-bottom-color: var(--win-blue); }
.win-sim .win-taskitem:hover { background: rgba(255,255,255,.08); }
.win-sim .win-clock { margin-left: auto; color: #cfcfcf; font-size: 0.75rem; text-align: right; line-height: 1.1; padding-right: 0.4rem; }
.win-sim .win-dialog-backdrop {
  position: absolute; inset: 0; background: rgba(0,0,0,.35); display: grid; place-items: center; z-index: 40;
}
.win-sim .win-dialog {
  background: #fff; border-radius: 6px; width: 440px; max-width: 92vw; overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,.3); border: 1px solid var(--win-border);
}
.win-sim .win-dialog-head { background: var(--win-blue); color: #fff; padding: 0.7rem 1rem; font-weight: 600; font-size: 0.9rem; }
.win-sim .win-dialog-body { padding: 1.1rem; }
.win-sim .win-dialog-foot { padding: 0.8rem 1.1rem; border-top: 1px solid var(--win-border); display: flex; justify-content: flex-end; gap: 0.5rem; background: #fafafa; }
/* ── login / lock screen ── */
.win-sim .win-lock {
  position: absolute; inset: 0; z-index: 50;
  background: linear-gradient(135deg, #0a2342 0%, #0078D4 60%, #1b4f8a 100%);
  display: flex; flex-direction: column; align-items: center; justify-content: center; color: #fff;
}
.win-sim .win-avatar {
  width: 96px; height: 96px; border-radius: 50%; background: rgba(255,255,255,.16);
  display: grid; place-items: center; margin-bottom: 1rem; border: 2px solid rgba(255,255,255,.3);
}
.win-sim .win-event { display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.78rem; padding: 0.35rem 0; }
.win-sim .win-lock-field {
  display: flex; align-items: center; gap: 0.5rem; width: 260px;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28);
  border-radius: 4px; padding: 0.5rem 0.65rem; color: #fff; margin-bottom: 0.6rem;
}
.win-sim .win-lock-field:focus-within { border-color: #fff; background: rgba(255,255,255,.22); }
.win-sim .win-lock-input {
  flex: 1; min-width: 0; background: transparent; border: 0; outline: none;
  color: #fff; font-size: 0.85rem;
}
.win-sim .win-lock-input::placeholder { color: rgba(255,255,255,.6); }
.win-sim .win-lock-error {
  width: 260px; font-size: 0.72rem; color: #fff; background: rgba(232,17,35,.35);
  border: 1px solid rgba(255,255,255,.35); border-radius: 4px; padding: 0.4rem 0.55rem; margin-bottom: 0.6rem;
}
.win-sim .win-lock-hint {
  width: 260px; font-size: 0.7rem; color: rgba(255,255,255,.7); text-align: center; margin-top: 0.4rem;
}
.win-sim .win-lock-hint b { color: #fff; font-weight: 600; }
`

function Badge({ kind, children }) {
  const cls = { ok: 'win-b-ok', bad: 'win-b-bad', warn: 'win-b-warn', info: 'win-b-info', muted: 'win-b-muted' }[kind] || 'win-b-muted'
  return <span className={`win-badge ${cls}`}>{children}</span>
}

/* ── Lab sign-in credentials (consistent with the other simulators:
   lab_<product> / lab_<product>@123). The built-in CORP\Administrator is also
   accepted with the same lab password so domain-flavoured scenarios still work. ── */
/* SIMULATED-CREDENTIAL: lab-console flavour, not a real secret. Shown to the
   learner on screen (with an autofill button) so the fake console feels real, and
   the gate is bypassed entirely once a provisioned lab session exists. Grants no
   access to anything. Secret scanners should allowlist this marker rather than
   flagging these lines. See docs/AUDIT_2026_08_TODO.md §Y2e. */
const WIN_LAB_USER = 'lab_windows'
const WIN_LAB_PASS = 'lab_windows@123'

/* ── Login / lock gate — Windows-style sign-in screen with real credentials ── */
function LockScreen({ locked, currentUser, onSignIn, signing }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [error, setError] = useState('')

  // Accept the lab user, or the built-in administrator (with the lab password),
  // with or without the CORP\ domain prefix.
  const normalize = (u) => (u || '').includes('\\') ? u.split('\\').pop() : u

  const submit = (e) => {
    e.preventDefault()
    if (signing) return
    const u = normalize(user).trim().toLowerCase()
    const ok = (u === WIN_LAB_USER && pass === WIN_LAB_PASS)
      || (u === 'administrator' && pass === WIN_LAB_PASS)
    if (ok) {
      setError('')
      onSignIn()
    } else {
      setError(`Invalid credentials. Use ${WIN_LAB_USER} / ${WIN_LAB_PASS} for training labs.`)
    }
  }

  return (
    <div className="win-lock">
      <div className="win-avatar"><UserCog size={42} /></div>
      <div className="text-lg font-semibold mb-0.5">{currentUser || 'CORP\\Administrator'}</div>
      <div className="text-sm opacity-80 mb-5">{locked ? 'This workstation is locked' : 'Windows Server 2022'}</div>

      <form onSubmit={submit} className="flex flex-col items-center">
        <div className="win-lock-field">
          <User size={15} className="opacity-80" />
          <input
            className="win-lock-input"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            placeholder="lab_windows"
            autoComplete="username"
            autoFocus
          />
        </div>
        <div className="win-lock-field">
          <KeyRound size={15} className="opacity-80" />
          <input
            type="password"
            className="win-lock-input"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            placeholder="Password"
            autoComplete="current-password"
          />
        </div>
        {error && <div className="win-lock-error">{error}</div>}
        <button
          type="submit"
          className="win-btn !bg-white !text-[#0078D4] !border-white px-6 py-2 text-sm"
          style={{ width: 260, justifyContent: 'center' }}
          disabled={signing}
        >
          {signing ? <RefreshCw size={14} className="animate-spin" /> : <ChevronRight size={15} />}
          {locked ? 'Unlock' : 'Sign in'}
        </button>
        <button
          type="button"
          className="win-btn px-4 py-1.5 text-xs mt-2"
          style={{ width: 260, justifyContent: 'center', background: 'rgba(255,255,255,.14)', color: '#fff', borderColor: 'rgba(255,255,255,.3)' }}
          onClick={() => { setUser(WIN_LAB_USER); setPass(WIN_LAB_PASS); setError('') }}
        >
          Use lab credentials (autofill)
        </button>
      </form>

      <div className="win-lock-hint">
        <Lock size={11} className="inline mb-0.5 mr-1" />
        Training credentials: <b>{WIN_LAB_USER}</b> / <b>{WIN_LAB_PASS}</b>
      </div>
    </div>
  )
}

/* ── Server Manager dashboard ── */
function ServerManager({ state, busy, onAction }) {
  const roles = state.roles || []
  const domain = state.domain || {}
  const summary = state.summary || {}
  const installable = roles.filter(r => !r.installed)
  const [wizardOpen, setWizardOpen] = useState(false)

  return (
    <div>
      <div className="win-h1">Server Manager · Dashboard</div>
      <div className="win-sub mb-4">Local Server · {state.computer_name} · {state.os}</div>

      {/* Local server properties tile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <div className="win-tile">
          <div className="font-semibold text-sm mb-2 flex items-center gap-1.5"><Server size={14} className="text-[#0078D4]" /> Local server</div>
          <dl className="text-[0.8rem] grid grid-cols-[120px_1fr] gap-y-1.5">
            <dt className="text-[#616161]">Computer name</dt><dd className="font-medium">{state.computer_name}</dd>
            <dt className="text-[#616161]">Domain</dt>
            <dd className="font-medium flex items-center gap-1.5">
              {domain.joined ? domain.name : 'WORKGROUP'}
              {domain.joined ? <Badge kind="ok">Joined</Badge> : <Badge kind="warn">Workgroup</Badge>}
            </dd>
            <dt className="text-[#616161]">Operating system</dt><dd className="font-medium">{state.os}</dd>
            <dt className="text-[#616161]">Domain controllers</dt><dd className="font-medium">{(domain.dcs || []).join(', ') || '—'}</dd>
          </dl>
        </div>
        <div className="win-tile">
          <div className="font-semibold text-sm mb-2 flex items-center gap-1.5"><ShieldCheck size={14} className="text-[#0078D4]" /> Readiness</div>
          <div className="grid grid-cols-2 gap-3">
            {[
              ['Roles installed', `${summary.roles_installed ?? 0}/${summary.roles_total ?? 0}`, 'info', Cpu],
              ['AD users', summary.ad_users ?? 0, 'info', Users],
              ['Updates pending', summary.updates_pending ?? 0, (summary.updates_pending ? 'warn' : 'ok'), Download],
              ['Services stopped', summary.services_stopped ?? 0, (summary.services_stopped ? 'bad' : 'ok'), Settings2],
            ].map(([label, val, _kind, Icon]) => (
              <div key={label} className="flex items-center gap-2">
                <Icon size={16} className="text-[#616161]" />
                <div>
                  <div className="text-base font-semibold leading-none">{val}</div>
                  <div className="text-[11px] text-[#616161] mt-0.5">{label}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Roles and features */}
      <div className="win-card">
        <div className="win-card-head justify-between">
          <span className="flex items-center gap-2"><LayoutDashboard size={15} className="text-[#0078D4]" /> Roles and Features</span>
          <button className="win-light-btn" onClick={() => setWizardOpen(true)} disabled={!installable.length}>
            <Plus size={13} /> Add Roles and Features
          </button>
        </div>
        <table className="win-table">
          <thead><tr><th>Role / Feature</th><th>Type</th><th>Status</th><th className="text-right">Action</th></tr></thead>
          <tbody>
            {roles.map(r => (
              <tr key={r.id}>
                <td>
                  <div className="font-medium">{r.name}</div>
                  {r.description && <div className="text-[11px] text-[#616161]">{r.description}</div>}
                </td>
                <td><span className="capitalize text-[#616161]">{r.category}</span></td>
                <td>{r.installed ? <Badge kind="ok"><CheckCircle2 size={11} /> Installed</Badge> : <Badge kind="muted">Available</Badge>}</td>
                <td className="text-right">
                  {r.installed ? (
                    <div className="inline-flex gap-1.5">
                      {(r.id === 'DNS' || r.id === 'DHCP') && (
                        <button className="win-light-btn" disabled={busy}
                          onClick={() => onAction(r.id === 'DNS' ? 'configure_dns' : 'configure_dhcp', {})}>
                          <Settings2 size={12} /> Configure
                        </button>
                      )}
                      <button className="win-light-btn" disabled={busy} onClick={() => onAction('uninstall_role', { role: r.id })}>Remove</button>
                    </div>
                  ) : (
                    <button className="win-light-btn win-primary !text-white" disabled={busy} onClick={() => { setWizardOpen(true) }}>
                      <Plus size={12} /> Install
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AddRolesWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        installable={installable}
        roles={roles}
        computerName={state.computer_name}
        busy={busy}
        onInstall={async (roleId) => { await onAction('install_role', { role: roleId }) }}
      />
    </div>
  )
}

/* ── Active Directory Users and Computers ── */
function ActiveDirectory({ state, busy, onAction }) {
  const ad = state.ad || {}
  const ous = ad.ous || []
  const users = ad.users || []
  const groups = ad.groups || []
  const [selectedOu, setSelectedOu] = useState('Users')
  const [selectedUser, setSelectedUser] = useState(null)
  const [groupDialog, setGroupDialog] = useState(null) // { user }
  const [newUserOpen, setNewUserOpen] = useState(false)

  const ouUsers = users.filter(u => (u.ou || 'Users') === selectedOu)
  const active = users.find(u => u.name === selectedUser) || ouUsers[0] || users[0] || null

  return (
    <div>
      <div className="win-h1">Active Directory Users and Computers</div>
      <div className="win-sub mb-4 flex items-center justify-between gap-2 flex-wrap">
        <span>{(state.domain || {}).name || 'WORKGROUP'}</span>
        <button type="button" className="win-light-btn win-primary !text-white" disabled={busy} onClick={() => setNewUserOpen(true)}>
          <Plus size={12} /> New User
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[230px_1fr_280px] gap-3">
        {/* OU tree */}
        <div className="win-card overflow-hidden">
          <div className="win-card-head"><FolderTree size={14} className="text-[#0078D4]" /> Console tree</div>
          <div className="p-1">
            {ous.map(ou => (
              <button key={ou}
                onClick={() => { setSelectedOu(ou); setSelectedUser(null) }}
                className={`w-full text-left px-3 py-2 rounded text-[0.82rem] flex items-center gap-2 ${ou === selectedOu ? 'bg-[#eef6fd] text-[#0a2342] font-medium' : 'hover:bg-[#f5f5f5]'}`}>
                <Users size={13} className="text-[#616161]" /> {ou}
                <span className="ml-auto text-[11px] text-[#999]">{users.filter(u => (u.ou || 'Users') === ou).length}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Users list */}
        <div className="win-card overflow-hidden">
          <div className="win-card-head">{selectedOu}</div>
          <table className="win-table">
            <thead><tr><th>Name</th><th>Status</th><th>Primary group</th></tr></thead>
            <tbody>
              {ouUsers.length === 0 ? (
                <tr><td colSpan={3} className="text-center text-[#616161] py-5">No objects in this container.</td></tr>
              ) : ouUsers.map(u => (
                <tr key={u.name} onClick={() => setSelectedUser(u.name)} style={{ cursor: 'pointer', background: u.name === active?.name ? '#f7fbff' : undefined }}>
                  <td>
                    <div className="font-medium">{u.display}</div>
                    <div className="text-[11px] text-[#616161]">{u.name}</div>
                  </td>
                  <td className="space-x-1">
                    {u.locked && <Badge kind="bad"><Lock size={10} /> Locked</Badge>}
                    {!u.enabled && <Badge kind="warn">Disabled</Badge>}
                    {u.enabled && !u.locked && <Badge kind="ok">Enabled</Badge>}
                  </td>
                  <td className="text-[#616161]">{u.group}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Properties / actions for the selected user */}
        <div className="win-card overflow-hidden">
          <div className="win-card-head"><UserCog size={14} className="text-[#0078D4]" /> Properties</div>
          {!active ? (
            <div className="p-4 text-[0.82rem] text-[#616161]">Select a user.</div>
          ) : (
            <div className="p-3.5 space-y-3">
              <div>
                <div className="font-semibold text-sm">{active.display}</div>
                <div className="text-[11px] text-[#616161]">{(state.domain || {}).netbios || 'CORP'}\\{active.name}</div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {active.locked && <Badge kind="bad"><Lock size={10} /> Locked out</Badge>}
                <Badge kind={active.enabled ? 'ok' : 'warn'}>{active.enabled ? 'Account enabled' : 'Account disabled'}</Badge>
              </div>
              <div>
                <div className="text-[11px] text-[#616161] mb-1">Member of</div>
                <div className="flex flex-wrap gap-1">
                  {(active.groups || []).map(g => <Badge key={g} kind="info">{g}</Badge>)}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-1.5 pt-1">
                {active.locked && (
                  <button className="win-light-btn justify-center" disabled={busy} onClick={() => onAction('unlock_ad_user', { user: active.name })}>
                    <Lock size={12} /> Unlock account
                  </button>
                )}
                {!active.enabled ? (
                  <button className="win-light-btn justify-center" disabled={busy} onClick={() => onAction('enable_ad_user', { user: active.name })}>
                    <CheckCircle2 size={12} /> Enable account
                  </button>
                ) : (
                  <button className="win-light-btn justify-center" disabled={busy} onClick={() => onAction('disable_ad_user', { user: active.name })}>
                    <Square size={12} /> Disable account
                  </button>
                )}
                <button className="win-light-btn justify-center" disabled={busy} onClick={() => onAction('reset_password', { user: active.name })}>
                  <RotateCw size={12} /> Reset password
                </button>
                <button className="win-light-btn justify-center" disabled={busy} onClick={() => setGroupDialog({ user: active.name })}>
                  <Plus size={12} /> Add to group
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add to group dialog */}
      {groupDialog && (
        <AddToGroupDialog
          userName={groupDialog.user}
          groups={groups}
          currentGroups={(users.find(u => u.name === groupDialog.user)?.groups) || []}
          busy={busy}
          onCancel={() => setGroupDialog(null)}
          onAdd={async (group) => { await onAction('add_user_to_group', { user: groupDialog.user, group }); setGroupDialog(null) }}
          onRemove={(group) => onAction('remove_user_from_group', { user: groupDialog.user, group })}
        />
      )}

      <NewUserWizard open={newUserOpen} onClose={() => setNewUserOpen(false)} ous={ous} busy={busy}
        onCreate={async (u) => {
          await onAction('create_ad_user', u)
          setSelectedOu(u.ou || 'Users')
          setSelectedUser(u.name)
        }} />
    </div>
  )
}

function AddToGroupDialog({ userName, groups, currentGroups, busy, onCancel, onAdd, onRemove }) {
  const memberSet = new Set((currentGroups || []).map(g => g.toLowerCase()))
  const available = groups.filter(g => !memberSet.has(g.name.toLowerCase()))
  const [group, setGroup] = useState(available[0]?.name || '')
  return (
    <div className="win-dialog-backdrop" onClick={onCancel}>
      <div className="win-dialog" onClick={e => e.stopPropagation()}>
        <div className="win-dialog-head">Member Of — {userName}</div>
        <div className="win-dialog-body space-y-3">
          <div>
            <div className="text-[11px] text-[#616161] mb-1">Current membership</div>
            <div className="flex flex-wrap gap-1">
              {(currentGroups || []).map(g => (
                <span key={g} className="win-badge win-b-info flex items-center gap-1">
                  {g}
                  <button title="Remove" className="hover:text-[#c42b1c]" disabled={busy} onClick={() => onRemove(g)}>×</button>
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-[#616161] mb-1">Add to group</div>
            {available.length === 0 ? (
              <p className="text-[0.8rem] text-[#616161]">Already a member of every group.</p>
            ) : (
              <select className="win-select w-full" value={group} onChange={e => setGroup(e.target.value)}>
                {available.map(g => <option key={g.name} value={g.name}>{g.name} — {g.description}</option>)}
              </select>
            )}
          </div>
        </div>
        <div className="win-dialog-foot">
          <button className="win-light-btn" onClick={onCancel}>Close</button>
          <button className="win-light-btn win-primary !text-white" disabled={busy || !group || !available.length} onClick={() => onAdd(group)}>Add</button>
        </div>
      </div>
    </div>
  )
}

/* ── Windows Update ── */
function WindowsUpdate({ state, busy, onAction }) {
  const updates = state.updates || []
  const pending = updates.filter(u => u.status !== 'installed')
  return (
    <div>
      <div className="win-h1">Windows Update</div>
      <div className="win-sub mb-4">
        {pending.length === 0 ? 'You\'re up to date' : `${pending.length} update${pending.length !== 1 ? 's' : ''} need attention`}
      </div>

      <div className="flex gap-2 mb-4">
        <button className="win-light-btn" disabled={busy} onClick={() => onAction('check_updates', {})}>
          <RefreshCw size={13} /> Check for updates
        </button>
        {pending.length > 0 && (
          <button className="win-light-btn win-primary !text-white" disabled={busy} onClick={() => onAction('install_update', {})}>
            <Download size={13} /> Install all
          </button>
        )}
      </div>

      <div className="win-card overflow-hidden">
        <table className="win-table">
          <thead><tr><th>Update</th><th>Severity</th><th>Status</th><th className="text-right">Action</th></tr></thead>
          <tbody>
            {updates.map(u => {
              const failed = u.status === 'failed'
              return (
                <tr key={u.kb}>
                  <td>
                    <div className="font-medium">{u.title}</div>
                    <div className="text-[11px] text-[#616161]">
                      {u.kb}{u.reboot_required ? ' · restart required' : ''}{failed && u.error_code ? ` · error ${u.error_code}` : ''}
                    </div>
                  </td>
                  <td><Badge kind={u.severity === 'Critical' ? 'bad' : 'warn'}>{u.severity}</Badge></td>
                  <td>
                    {u.status === 'installed' ? <Badge kind="ok"><CheckCircle2 size={11} /> Installed</Badge>
                      : failed ? <Badge kind="bad"><AlertTriangle size={11} /> Failed</Badge>
                      : <Badge kind="warn">{u.status}</Badge>}
                  </td>
                  <td className="text-right">
                    {u.status === 'installed' ? <span className="text-[#616161] text-[0.78rem]">—</span> : (
                      <button className="win-light-btn win-primary !text-white" disabled={busy}
                        onClick={() => onAction(failed ? 'retry_update' : 'install_update', { kb: u.kb })}>
                        {failed ? <><RotateCw size={12} /> Retry</> : <><Download size={12} /> Install</>}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ── Services console ── */
function ServicesConsole({ state, busy, onAction }) {
  const services = state.services || []
  const STARTUPS = ['automatic', 'automatic-delayed', 'manual', 'disabled']
  return (
    <div>
      <div className="win-h1">Services</div>
      <div className="win-sub mb-4">Local services on {state.computer_name}</div>

      <div className="win-card overflow-hidden">
        <table className="win-table">
          <thead><tr><th>Name</th><th>Status</th><th>Startup type</th><th className="text-right">Actions</th></tr></thead>
          <tbody>
            {services.map(s => {
              const running = s.status === 'running'
              return (
                <tr key={s.name}>
                  <td>
                    <div className="font-medium">{s.display}</div>
                    <div className="text-[11px] text-[#616161]">{s.name}</div>
                  </td>
                  <td>{running ? <Badge kind="ok"><Play size={10} /> Running</Badge> : <Badge kind="bad"><Square size={10} /> Stopped</Badge>}</td>
                  <td>
                    <select className="win-select capitalize" value={s.startup} disabled={busy}
                      onChange={e => onAction('set_startup', { service: s.name, startup: e.target.value })}>
                      {STARTUPS.map(st => <option key={st} value={st}>{st === 'automatic-delayed' ? 'Automatic (Delayed)' : st.charAt(0).toUpperCase() + st.slice(1)}</option>)}
                    </select>
                  </td>
                  <td className="text-right space-x-1.5 whitespace-nowrap">
                    {running ? (
                      <>
                        <button className="win-light-btn" disabled={busy} onClick={() => onAction('stop_service', { service: s.name })}><Square size={12} /> Stop</button>
                        <button className="win-light-btn" disabled={busy} onClick={() => onAction('restart_service', { service: s.name })}><RotateCw size={12} /> Restart</button>
                      </>
                    ) : (
                      <button className="win-light-btn win-primary !text-white" disabled={busy} onClick={() => onAction('start_service', { service: s.name })}><Play size={12} /> Start</button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ── Group Policy Management Editor ── */
function GroupPolicyEditor({ state, busy, onAction }) {
  const gp = state?.group_policy || {}
  const gpos = gp.gpos || []
  const forest = gp.forest || state?.domain?.name || 'corp.fixitlab.local'
  const [selectedId, setSelectedId] = useState(() => gpos[0]?.id || null)
  const [newName, setNewName] = useState('')
  const [linkTarget, setLinkTarget] = useState(forest)
  const [draft, setDraft] = useState({ key: '', value: '' })

  const selected = gpos.find((g) => g.id === selectedId) || gpos[0] || null

  return (
    <div>
      <div className="win-h1">Group Policy Management</div>
      <div className="win-sub mb-4 flex items-center justify-between gap-2 flex-wrap">
        <span>{forest}</span>
        <div className="flex gap-2 items-center">
          <input className="win-input !w-44 !text-xs" placeholder="New GPO name" value={newName}
            onChange={(e) => setNewName(e.target.value)} />
          <button type="button" className="win-light-btn win-primary !text-white" disabled={busy || !newName.trim()}
            onClick={async () => { await onAction('create_gpo', { name: newName.trim() }); setNewName('') }}>
            <Plus size={12} /> New GPO
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-3 min-h-[380px]">
        <div className="win-card overflow-hidden">
          <div className="win-card-head"><FolderTree size={14} className="text-[#0078D4]" /> Group Policy Objects</div>
          <div className="p-1 text-xs">
            <div className="px-2 py-1 font-semibold text-[#616161]">Forest → {forest}</div>
            {gpos.length === 0 ? (
              <div className="px-3 py-4 text-[#616161]">No GPOs defined.</div>
            ) : gpos.map((g) => (
              <button key={g.id} type="button" onClick={() => setSelectedId(g.id)}
                className={`w-full text-left px-3 py-2 rounded flex items-center gap-2 ${selected?.id === g.id ? 'bg-[#eef6fd] font-medium' : 'hover:bg-[#f5f5f5]'}`}>
                <FolderTree size={12} className="text-[#0078D4] shrink-0" />
                <span className="truncate">{g.name}</span>
                <Badge kind={g.status === 'Enabled' ? 'ok' : 'warn'}>{g.status === 'Enabled' ? 'On' : 'Off'}</Badge>
              </button>
            ))}
          </div>
        </div>

        <div className="win-card overflow-hidden">
          {!selected ? (
            <div className="p-6 text-[#616161] text-sm">Select a Group Policy Object.</div>
          ) : (
            <>
              <div className="win-card-head flex items-center justify-between gap-2">
                <span>{selected.name}</span>
                <div className="flex gap-1">
                  <button type="button" className="win-light-btn !text-xs" disabled={busy}
                    onClick={() => onAction(selected.status === 'Enabled' ? 'disable_gpo' : 'enable_gpo', { gpo: selected.id })}>
                    {selected.status === 'Enabled' ? 'Disable' : 'Enable'}
                  </button>
                  {selected.id !== 'default-domain-policy' && (
                    <button type="button" className="win-light-btn !text-xs text-[#c42b1c]" disabled={busy}
                      onClick={() => onAction('delete_gpo', { gpo: selected.id })}>
                      <Trash2 size={11} /> Delete
                    </button>
                  )}
                </div>
              </div>
              <div className="p-3 space-y-3">
                <div>
                  <div className="text-[11px] font-semibold text-[#616161] mb-1">Links</div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {(selected.links || []).length === 0 ? (
                      <span className="text-xs text-[#999]">Not linked</span>
                    ) : (selected.links || []).map((l) => (
                      <span key={l} className="win-badge win-b-info flex items-center gap-1">
                        {l}
                        <button type="button" className="hover:text-[#c42b1c]" disabled={busy}
                          onClick={() => onAction('unlink_gpo', { gpo: selected.id, ou: l })}>×</button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input className="win-input flex-1 !text-xs" value={linkTarget} onChange={(e) => setLinkTarget(e.target.value)} />
                    <button type="button" className="win-light-btn !text-xs" disabled={busy}
                      onClick={() => onAction('link_gpo', { gpo: selected.id, ou: linkTarget.trim() || forest })}>Link</button>
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold text-[#616161] mb-2">Settings</div>
                  <table className="win-table text-xs">
                    <thead><tr><th>Setting</th><th>Value</th><th /></tr></thead>
                    <tbody>
                      {(selected.settings || []).map((s) => (
                        <tr key={s.key}>
                          <td>{s.key}</td>
                          <td>
                            {draft.key === s.key ? (
                              <input className="win-input !text-xs w-full" value={draft.value}
                                onChange={(e) => setDraft({ key: s.key, value: e.target.value })} />
                            ) : (
                              <span className="text-[#0078D4]">{s.value}</span>
                            )}
                          </td>
                          <td className="text-right">
                            {draft.key === s.key ? (
                              <button type="button" className="win-light-btn !text-xs" disabled={busy}
                                onClick={async () => {
                                  await onAction('update_gpo_setting', { gpo: selected.id, key: s.key, value: draft.value })
                                  setDraft({ key: '', value: '' })
                                }}>Save</button>
                            ) : (
                              <button type="button" className="win-light-btn !text-xs" disabled={busy}
                                onClick={() => setDraft({ key: s.key, value: s.value })}>Edit</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Software Center (Microsoft Endpoint Configuration Manager / SCCM / MECM) ── */
function SoftwareCenter({ state, busy, onAction }) {
  const sccm = state.sccm || {}
  const deployments = sccm.deployments || []
  const clientActive = sccm.client_status === 'active'

  return (
    <div>
      <div className="win-h1">Software Center</div>
      <div className="win-sub mb-4">Microsoft Endpoint Configuration Manager — Software Center</div>

      <div className={`win-banner ${clientActive ? 'win-banner-ok' : 'win-banner-err'}`}>
        {clientActive ? <CheckCircle2 size={15} className="shrink-0 mt-0.5" /> : <AlertTriangle size={15} className="shrink-0 mt-0.5" />}
        <span>
          Site code <b>{sccm.site_code || '—'}</b> ({sccm.site_name || 'Configuration Manager'}) ·
          {' '}Client: <b>{sccm.client_installed ? 'Installed' : 'Not installed'}</b> ·
          {' '}Status: <b className="capitalize">{sccm.client_status || 'unknown'}</b>
        </span>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <button className="win-light-btn" disabled={busy} onClick={() => onAction('sccm_open_software_center', {})}>
          <Package size={13} /> Open Software Center
        </button>
        <button className="win-light-btn" disabled={busy} onClick={() => onAction('sccm_sync_updates', {})}>
          <RefreshCw size={13} /> Sync software updates
        </button>
        <button className="win-light-btn" disabled={busy} onClick={() => onAction('sccm_machine_policy_cycle', {})}>
          <RotateCw size={13} /> Machine Policy Retrieval &amp; Evaluation Cycle
        </button>
      </div>

      <div className="win-card overflow-hidden">
        <div className="win-card-head"><Package size={15} className="text-[#0078D4]" /> Deployments</div>
        <table className="win-table">
          <thead><tr><th>Name</th><th>Status</th><th>Deadline</th><th className="text-right">Action</th></tr></thead>
          <tbody>
            {deployments.length === 0 ? (
              <tr><td colSpan={4} className="text-center text-[#616161] py-5">No deployments targeted at this device.</td></tr>
            ) : deployments.map((d) => {
              const failed = d.status === 'Failed'
              const needsAction = d.status === 'Required' || failed
              return (
                <tr key={d.id}>
                  <td>
                    <div className="font-medium">{d.name}</div>
                    <div className="text-[11px] text-[#616161]">
                      {d.kb}{failed && d.error ? ` · error ${d.error}` : ''}
                    </div>
                  </td>
                  <td>
                    {d.status === 'Installed' ? <Badge kind="ok"><CheckCircle2 size={11} /> Installed</Badge>
                      : failed ? <Badge kind="bad"><AlertTriangle size={11} /> Failed</Badge>
                      : d.status === 'Required' ? <Badge kind="warn">Required</Badge>
                      : <Badge kind="muted">Available</Badge>}
                  </td>
                  <td className="text-[#616161]">{d.deadline ? d.deadline.replace('T', ' ').replace('Z', '') : '—'}</td>
                  <td className="text-right">
                    {!needsAction ? <span className="text-[#616161] text-[0.78rem]">—</span> : (
                      <button className="win-light-btn win-primary !text-white" disabled={busy}
                        onClick={() => onAction(failed ? 'sccm_retry_deployment' : 'sccm_install_deployment', { deployment_id: d.id })}>
                        {failed ? <><RotateCw size={12} /> Retry</> : <><Download size={12} /> Install</>}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const NAV = [
  { key: 'dashboard', label: 'Server Manager', icon: LayoutDashboard },
  { key: 'explorer', label: 'File Explorer', icon: FolderOpen },
  { key: 'storage', label: 'Disk Management', icon: HardDrive },
  { key: 'network', label: 'Network', icon: Wifi },
  { key: 'devices', label: 'Device Manager', icon: Monitor },
  { key: 'settings', label: 'Settings', icon: Settings },
  { key: 'ad', label: 'Active Directory', icon: Users },
  { key: 'gpo', label: 'Group Policy', icon: FolderTree },
  { key: 'update', label: 'Windows Update', icon: Download },
  { key: 'sccm', label: 'Software Center', icon: Package },
  { key: 'services', label: 'Services', icon: Settings2 },
  { key: 'system', label: 'System (Domain)', icon: Globe },
]

function FileExplorerPanel({ state }) {
  const explorer = state.explorer || {}
  const [path, setPath] = useState('C:\\')
  const folders = explorer.folders?.[path] || []
  const drives = explorer.drives || []
  return (
    <div>
      <div className="win-h1">File Explorer</div>
      <div className="win-sub mb-4">Browse local disks and folders on {state.computer_name}</div>
      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4">
        <div className="win-card !p-2">
          <div className="win-card-head text-xs">This PC</div>
          {drives.map((d) => (
            <button key={d.path} type="button" className={`w-full text-left px-3 py-2 text-sm rounded hover:bg-[#f3f3f3] ${path === d.path ? 'bg-[#e8f4fc] font-medium' : ''}`}
              onClick={() => setPath(d.path)}>
              <HardDrive size={14} className="inline mr-2 text-[#0078D4]" /> {d.label} ({d.path})
            </button>
          ))}
        </div>
        <div className="win-card">
          <div className="win-card-head flex items-center gap-2">
            <FolderOpen size={14} className="text-[#0078D4]" />
            <span className="font-mono text-sm">{path}</span>
          </div>
          <div className="p-3 grid sm:grid-cols-2 gap-2">
            {path !== 'C:\\' && (
              <button type="button" className="win-light-btn text-left" onClick={() => setPath(path.replace(/\\[^\\]+$/, '') || 'C:\\')}>
                <ArrowLeft size={13} /> ..
              </button>
            )}
            {folders.map((f) => (
              <button key={f} type="button" className="win-light-btn text-left"
                onClick={() => setPath(path.endsWith('\\') ? `${path}${f}` : `${path}\\${f}`)}>
                <FolderOpen size={13} className="text-[#f4b400]" /> {f}
              </button>
            ))}
            {folders.length === 0 && <p className="text-sm text-[#616161] col-span-2">This folder is empty.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}

function StoragePanel({ state, busy, onAction }) {
  const storage = state.storage || {}
  const disks = storage.disks || []
  const volumes = storage.volumes || []
  const [letter, setLetter] = useState('D:')
  const [label, setLabel] = useState('Data')
  const rawDisk = disks.find((d) => d.partition_style === 'RAW')
  return (
    <div>
      <div className="win-h1">Disk Management</div>
      <div className="win-sub mb-4">Manage disks and volumes — VMware hot-added disks appear after rescan</div>
      <div className="flex flex-wrap gap-2 mb-4">
        <button className="win-light-btn win-primary !text-white" disabled={busy} onClick={() => onAction('rescan_disks', {})}>
          <RefreshCw size={13} /> Rescan disks
        </button>
        {rawDisk && (
          <button className="win-light-btn" disabled={busy} onClick={() => onAction('initialize_disk', { disk_id: rawDisk.id })}>
            Initialize disk {rawDisk.number}
          </button>
        )}
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="win-card !p-0 overflow-hidden">
          <div className="win-card-head">Disks</div>
          <table className="w-full text-sm">
            <thead><tr className="text-[#616161] text-xs border-b"><th className="px-3 py-2 text-left">Disk</th><th className="px-3 py-2 text-left">Size</th><th className="px-3 py-2 text-left">Style</th><th className="px-3 py-2 text-left">Status</th></tr></thead>
            <tbody>
              {disks.map((d) => (
                <tr key={d.id} className="border-b border-[#f3f3f3]">
                  <td className="px-3 py-2">Disk {d.number}<div className="text-[11px] text-[#616161]">{d.model}</div></td>
                  <td className="px-3 py-2">{d.size_gb} GB</td>
                  <td className="px-3 py-2 font-mono text-xs">{d.partition_style}</td>
                  <td className="px-3 py-2"><Badge kind={d.status === 'Online' ? 'ok' : 'warn'}>{d.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="win-card !p-0 overflow-hidden">
          <div className="win-card-head">Volumes</div>
          <table className="w-full text-sm">
            <thead><tr className="text-[#616161] text-xs border-b"><th className="px-3 py-2 text-left">Drive</th><th className="px-3 py-2 text-left">Label</th><th className="px-3 py-2 text-left">FS</th><th className="px-3 py-2 text-left">Free</th></tr></thead>
            <tbody>
              {volumes.map((v) => (
                <tr key={v.letter} className="border-b border-[#f3f3f3]">
                  <td className="px-3 py-2 font-medium">{v.letter}</td>
                  <td className="px-3 py-2">{v.label}</td>
                  <td className="px-3 py-2">{v.fs}</td>
                  <td className="px-3 py-2">{v.free_gb} / {v.size_gb} GB</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rawDisk && (
            <div className="p-3 border-t flex flex-wrap gap-2 items-end">
              <div><label className="text-[11px] text-[#616161]">Letter</label><input className="win-input w-20" value={letter} onChange={(e) => setLetter(e.target.value)} /></div>
              <div><label className="text-[11px] text-[#616161]">Label</label><input className="win-input" value={label} onChange={(e) => setLabel(e.target.value)} /></div>
              <button className="win-light-btn win-primary !text-white" disabled={busy}
                onClick={() => onAction('create_volume', { disk_id: rawDisk.id, letter, label, size_gb: rawDisk.size_gb })}>
                <Plus size={13} /> New simple volume
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function NetworkPanel({ state, busy, onAction }) {
  const net = state.network || {}
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ ipv4: '', mask: '255.255.255.0', gw: '', dhcp: false })
  const startEdit = (a) => { setEditing(a.id); setForm({ ipv4: a.ipv4, mask: a.mask, gw: a.gw, dhcp: a.dhcp }) }
  return (
    <div>
      <div className="win-h1">Network &amp; Internet</div>
      <div className="win-sub mb-4">Hostname: {net.hostname || state.computer_name}</div>
      {(net.adapters || []).map((a) => (
        <div key={a.id} className="win-card mb-3">
          <div className="win-card-head flex justify-between items-center">
            <span>{a.name} — {a.desc}</span>
            <Badge kind={a.status === 'Connected' ? 'ok' : 'warn'}>{a.status}</Badge>
          </div>
          <div className="p-4 text-sm space-y-1">
            <div><span className="text-[#616161] w-24 inline-block">MAC</span><span className="font-mono">{a.mac}</span></div>
            <div><span className="text-[#616161] w-24 inline-block">IPv4</span>{a.dhcp ? 'DHCP' : (a.ipv4 || '—')}</div>
            {!a.dhcp && a.ipv4 && <div><span className="text-[#616161] w-24 inline-block">Gateway</span>{a.gw || '—'}</div>}
            {editing === a.id ? (
              <div className="pt-3 space-y-2 border-t mt-2">
                <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.dhcp} onChange={(e) => setForm((p) => ({ ...p, dhcp: e.target.checked }))} /> Obtain IP automatically (DHCP)</label>
                {!form.dhcp && (
                  <>
                    <input className="win-input w-full" placeholder="IPv4" value={form.ipv4} onChange={(e) => setForm((p) => ({ ...p, ipv4: e.target.value }))} />
                    <input className="win-input w-full" placeholder="Subnet mask" value={form.mask} onChange={(e) => setForm((p) => ({ ...p, mask: e.target.value }))} />
                    <input className="win-input w-full" placeholder="Gateway" value={form.gw} onChange={(e) => setForm((p) => ({ ...p, gw: e.target.value }))} />
                  </>
                )}
                <div className="flex gap-2">
                  <button className="win-light-btn win-primary !text-white" disabled={busy}
                    onClick={() => { onAction('set_adapter_ip', { adapter_id: a.id, ...form }); setEditing(null) }}>Save</button>
                  <button className="win-light-btn" onClick={() => setEditing(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <button className="win-light-btn mt-2" disabled={busy} onClick={() => startEdit(a)}>Edit IP settings</button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function DevicesPanel({ state, busy, onAction }) {
  const devices = state.devices || []
  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <div><div className="win-h1">Device Manager</div><div className="win-sub">Drivers and hardware devices</div></div>
        <button className="win-light-btn" disabled={busy} onClick={() => onAction('scan_devices', {})}><RefreshCw size={13} /> Scan for hardware changes</button>
      </div>
      <div className="win-card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[#616161] text-xs border-b"><th className="px-3 py-2 text-left">Device</th><th className="px-3 py-2 text-left">Class</th><th className="px-3 py-2 text-left">Driver</th><th className="px-3 py-2 text-left">Status</th></tr></thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id} className="border-b border-[#f3f3f3]">
                <td className="px-3 py-2">{d.name}</td>
                <td className="px-3 py-2 text-[#616161]">{d.class}</td>
                <td className="px-3 py-2 font-mono text-xs">{d.driver}</td>
                <td className="px-3 py-2"><Badge kind={d.status === 'OK' ? 'ok' : 'warn'}>{d.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SettingsPanel({ state }) {
  const settings = state.settings || {}
  return (
    <div>
      <div className="win-h1">Settings</div>
      <div className="win-sub mb-4">System configuration for {state.computer_name}</div>
      <div className="grid sm:grid-cols-2 gap-3 max-w-2xl">
        {[
          ['Edition', settings.edition || state.os],
          ['Build', settings.build || '20348'],
          ['Activation', settings.activated ? 'Activated' : 'Not activated'],
          ['Time zone', settings.time_zone || 'UTC'],
          ['Remote Desktop', settings.remote_desktop ? 'Enabled' : 'Disabled'],
          ['Computer name', state.computer_name],
          ['Domain', state.domain?.joined ? state.domain.name : 'WORKGROUP'],
        ].map(([k, v]) => (
          <div key={k} className="win-card p-3">
            <div className="text-[11px] text-[#616161]">{k}</div>
            <div className="font-medium text-sm mt-0.5">{v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── System Properties (domain join) panel ── */
function SystemPanel({ state, busy, onAction }) {
  const domain = state.domain || {}
  const [target, setTarget] = useState(domain.name || 'corp.fixitlab.local')
  return (
    <div>
      <div className="win-h1">System Properties · Computer Name / Domain</div>
      <div className="win-sub mb-4">Membership for {state.computer_name}</div>
      <div className="win-card max-w-xl">
        <div className="win-card-head"><Network size={14} className="text-[#0078D4]" /> Domain membership</div>
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2 text-[0.85rem]">
            <span className="text-[#616161] w-32">Current membership</span>
            {domain.joined
              ? <span className="font-medium flex items-center gap-1.5">{domain.name} <Badge kind="ok">Domain</Badge></span>
              : <span className="font-medium flex items-center gap-1.5">WORKGROUP <Badge kind="warn">Workgroup</Badge></span>}
          </div>
          {!domain.joined ? (
            <>
              <div>
                <label className="text-[11px] text-[#616161] block mb-1">Domain to join</label>
                <input className="win-input" value={target} spellCheck={false} onChange={e => setTarget(e.target.value)} />
              </div>
              <button className="win-light-btn win-primary !text-white" disabled={busy || !target.trim()}
                onClick={() => onAction('join_domain', { domain: target.trim() })}>
                <Globe size={13} /> Join domain
              </button>
              <p className="text-[0.78rem] text-[#616161]">Joining the domain registers this server with a domain controller and starts the Netlogon service.</p>
            </>
          ) : (
            <button className="win-light-btn" disabled={busy} onClick={() => onAction('leave_domain', {})}>
              <Power size={13} /> Leave domain (join WORKGROUP)
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Windows Server GUI simulator. Rendered INLINE by LabRunner for Windows Server
 * GUI labs (simulation_type 'windows-server') — no new route. The learner
 * administers a Windows Server 2022 world through Server Manager, Active
 * Directory Users and Computers, Windows Update, and the Services console to
 * fix the broken state, then runs Check Solution (graded by validate_windows_lab
 * via the engine — never auto-passes).
 */
export default function WindowsServerSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [signedIn, setSignedIn] = useState(false)
  const [signing, setSigning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [view, setView] = useState('dashboard')
  const [desktopMode, setDesktopMode] = useState(true)
  const [flash, setFlash] = useState(null) // { kind, message }
  const [now, setNow] = useState(new Date())
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await windowsApi.getState(sessionId, slug)
      setState(data)
      setError('')
      // Reflect the engine's own session/lock flags into the gate the first time.
      if (data?.session?.logged_in) setSignedIn(true)
    } catch {
      setError('Could not load Windows Server Manager')
    }
  }, [sessionId, slug])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 20000)
    return () => clearInterval(pollRef.current)
  }, [load])

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(id)
  }, [])

  // Auto-dismiss the flash toast.
  useEffect(() => {
    if (!flash) return
    const id = setTimeout(() => setFlash(null), 4000)
    return () => clearTimeout(id)
  }, [flash])

  const signIn = useCallback(async () => {
    setSigning(true)
    try {
      await windowsApi.action(sessionId, 'login', {})
      setSignedIn(true)
      load()
    } finally {
      setSigning(false)
    }
  }, [sessionId, load])

  // Every GUI verb routes through here: apply the action, surface its message,
  // and refresh from the returned `state` (or re-fetch) so the UI is live.
  const runAction = useCallback(async (action, payload) => {
    if (busy) return null
    setBusy(true)
    try {
      const res = await windowsApi.action(sessionId, action, payload)
      if (res?.ok === false) {
        setFlash({ kind: 'err', message: res.error || res.message || 'Action failed' })
      } else {
        setFlash({ kind: 'ok', message: res?.message || 'Done' })
      }
      // The action endpoint echoes the fresh state — use it when present.
      if (res?.state) setState(res.state)
      else load()
      return res
    } catch {
      setFlash({ kind: 'err', message: 'Action failed — try again' })
      return null
    } finally {
      setBusy(false)
    }
  }, [busy, sessionId, load])

  const goal = state?.goal || {}
  const locked = state?.session?.locked
  const currentUser = state?.session?.current_user

  const clock = useMemo(() => ({
    time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    date: now.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }),
  }), [now])

  return (
    <div className={`win-sim relative ${embedded ? 'h-full min-h-0 flex flex-col overflow-hidden' : (desktopMode ? 'h-screen flex flex-col overflow-hidden' : 'min-h-screen')}`}>
      <style>{SCOPED_CSS}</style>

      {/* Title bar — lab chrome lives here (hints / stop / back to lab). */}
      <div className="win-titlebar">
        <div className="flex items-center gap-2.5 min-w-0">
          <Server size={17} />
          <span className="font-semibold text-sm">Windows Server 2022</span>
          <span className="text-[11px] opacity-80 hidden sm:inline truncate">{scenario?.title || slug}</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button type="button" className={`win-btn ${desktopMode ? 'ring-2 ring-white/60' : ''}`} onClick={() => setDesktopMode((d) => !d)}>
            <Monitor size={13} /> {desktopMode ? 'Lab view' : 'Full Desktop'}
          </button>
          <button className="win-btn" onClick={load}><RefreshCw size={13} /> Refresh</button>
          <button className="win-btn" onClick={() => runAction('reset', {})} disabled={busy}><RotateCw size={13} /> Reset</button>
          {onToggleTerminal && (
            <button type="button" className={`win-btn ${simTerminalOpen ? 'ring-2 ring-white/60' : ''}`} onClick={onToggleTerminal}>
              <Terminal size={13} /> {simTerminalOpen ? 'Hide terminal' : 'Terminal'}
            </button>
          )}
          <LabChromeControls
            buttonClass="win-btn"
            vmwareHref={vmwareHref}
            onHints={onHints}
            onCheck={onCheck}
            onExtend={onExtend}
            onStop={onStop}
            onBackToTerminal={embedded ? undefined : onExit}
            backLabel={simTerminalOpen ? 'Hide terminal' : 'Terminal'}
            hintsLabel={hintsLabel || 'Hints'}
            checkDisabled={checkDisabled}
            extendDisabled={extendDisabled}
          />
        </div>
      </div>

      {/* Full pixel-perfect Windows Server 2022 desktop (client-side OS) */}
      {desktopMode && signedIn && !locked && (
        <div className="flex-1 relative min-h-0 overflow-hidden">
          <WindowsServer2022 backendState={state} onLabAction={runAction} />
        </div>
      )}

      {/* Lab view: nav + content + taskbar (graded backend panels) */}
      {!desktopMode && (
      <>
      <div className="win-body">
        <div className="win-nav">
          {NAV.map(({ key, label, icon: Icon }) => (
            <button key={key} className={`win-nav-item ${view === key ? 'active' : ''}`} onClick={() => setView(key)}>
              <Icon size={16} /> {label}
            </button>
          ))}
          <div className="mt-auto px-4 py-3 text-[11px] text-[#9a9a9a] border-t border-[#2d2d2d]">
            <div className="flex items-center gap-1.5"><HardDrive size={12} /> {state?.computer_name || 'WIN-SRV'}</div>
            <div className="mt-1 truncate">{currentUser || 'CORP\\Administrator'}</div>
          </div>
        </div>

        <div className="win-content">
          {error && <div className="win-banner win-banner-err"><XCircle size={15} className="shrink-0 mt-0.5" /> {error}</div>}

          {/* Objective banner */}
          {(goal.objective || goal.title) && (
            <div className="win-banner win-banner-goal">
              <AlertTriangle size={15} className="shrink-0 mt-0.5 text-[#0078D4]" />
              <span><b>{goal.title || 'Objective'}:</b> {goal.objective}</span>
            </div>
          )}

          {/* Flash result toast */}
          {flash && (
            <div className={`win-banner ${flash.kind === 'err' ? 'win-banner-err' : 'win-banner-ok'}`}>
              {flash.kind === 'err' ? <XCircle size={15} className="shrink-0 mt-0.5" /> : <CheckCircle2 size={15} className="shrink-0 mt-0.5" />}
              <span>{flash.message}</span>
            </div>
          )}

          {!state ? (
            <div className="text-center text-[#616161] py-20">Loading Windows Server…</div>
          ) : (
            <>
              {view === 'dashboard' && <ServerManager state={state} busy={busy} onAction={runAction} />}
              {view === 'explorer' && <FileExplorerPanel state={state} />}
              {view === 'storage' && <StoragePanel state={state} busy={busy} onAction={runAction} />}
              {view === 'network' && <NetworkPanel state={state} busy={busy} onAction={runAction} />}
              {view === 'devices' && <DevicesPanel state={state} busy={busy} onAction={runAction} />}
              {view === 'settings' && <SettingsPanel state={state} />}
              {view === 'ad' && <ActiveDirectory state={state} busy={busy} onAction={runAction} />}
              {view === 'gpo' && <GroupPolicyEditor state={state} busy={busy} onAction={runAction} />}
              {view === 'update' && <WindowsUpdate state={state} busy={busy} onAction={runAction} />}
              {view === 'sccm' && <SoftwareCenter state={state} busy={busy} onAction={runAction} />}
              {view === 'services' && <ServicesConsole state={state} busy={busy} onAction={runAction} />}
              {view === 'system' && <SystemPanel state={state} busy={busy} onAction={runAction} />}

              {/* Recent events */}
              {(state.events || []).length > 0 && (
                <div className="win-card mt-4">
                  <div className="win-card-head">Recent activity</div>
                  <div className="px-4 py-2 max-h-40 overflow-y-auto">
                    {(state.events || []).slice(0, 8).map((ev, i) => (
                      <div key={i} className="win-event border-b border-[#f3f3f3] last:border-0">
                        <CheckCircle2 size={13} className="text-[#107c10] mt-0.5 shrink-0" />
                        <span className="flex-1">{ev.message}</span>
                        <span className="text-[#999] text-[11px] shrink-0">{(ev.time || '').replace('T', ' ').replace('Z', '')}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Taskbar */}
      <div className="win-taskbar">
        <div className="win-start" title="Start"><Server size={17} className="text-[#0078D4]" /></div>
        {NAV.slice(0, 4).map(({ key, label, icon: Icon }) => (
          <button key={key} className={`win-taskitem ${view === key ? 'active' : ''}`} onClick={() => setView(key)} title={label}>
            <Icon size={14} /> <span className="hidden md:inline">{label}</span>
          </button>
        ))}
        <div className="win-clock">
          <div>{clock.time}</div>
          <div>{clock.date}</div>
        </div>
      </div>
      </>
      )}

      {/* Login / lock gate — sits above everything until the admin signs in. */}
      {(!signedIn || locked) && (
        <LockScreen locked={locked} currentUser={currentUser} onSignIn={signIn} signing={signing} />
      )}
    </div>
  )
}
