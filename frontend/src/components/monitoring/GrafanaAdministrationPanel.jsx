import { useMemo, useState } from 'react'
import {
  Users, UsersRound, KeyRound, SlidersHorizontal, Settings2,
  Search, Shield, ShieldCheck, Plus, Copy, Check, Mail, Clock, Lock,
} from 'lucide-react'
import '../../styles/monitoring-sim.css'

/* ── role badge: maps a Grafana org role to a mon-badge variant ── */
function RoleBadge({ role }) {
  const r = String(role || '').toLowerCase()
  const cls = r === 'admin' ? 'mon-badge-down' : r === 'editor' ? 'mon-badge-warn' : 'mon-badge-up'
  return <span className={`mon-badge ${cls}`}>{role || 'Viewer'}</span>
}

/* ── a labelled, visual-only select (does not drive any real state change) ── */
function PrefSelect({ label, value, options }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="mon-panel-sub">{label}</span>
      <select className="mon-input" defaultValue={value}>
        {(options || []).map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  )
}

/* ── default sample data: original, Grafana-flavoured, never from the engine ── */
const SAMPLE_USERS = [
  { login: 'admin', name: 'Org Admin', email: 'admin@fixitlab.local', role: 'Admin', lastSeen: '2 minutes ago', seenAt: 'now' },
  { login: 'j.editor', name: 'Jordan Lee', email: 'jordan.lee@fixitlab.local', role: 'Editor', lastSeen: '3 hours ago', seenAt: 'today' },
  { login: 'v.viewer', name: 'Vik Rao', email: 'vik.rao@fixitlab.local', role: 'Viewer', lastSeen: '2 days ago', seenAt: 'recent' },
  { login: 'oncall-bot', name: 'On-call Bot', email: 'oncall@fixitlab.local', role: 'Editor', lastSeen: '14 minutes ago', seenAt: 'today' },
  { login: 's.intern', name: 'Sam Park', email: 'sam.park@fixitlab.local', role: 'Viewer', lastSeen: 'Never', seenAt: 'never' },
]

const SAMPLE_TEAMS = [
  { name: 'Observability', email: 'obs@fixitlab.local', members: 6, role: 'Admin' },
  { name: 'Platform', email: 'platform@fixitlab.local', members: 9, role: 'Editor' },
  { name: 'SRE On-call', email: 'sre@fixitlab.local', members: 4, role: 'Editor' },
  { name: 'Frontend', email: 'frontend@fixitlab.local', members: 7, role: 'Viewer' },
]

const SAMPLE_SERVICE_ACCOUNTS = [
  { name: 'ci-dashboards', role: 'Editor', tokens: 2, token: 'glsa_8fK2nQ7xR4', disabled: false },
  { name: 'terraform-provisioner', role: 'Admin', tokens: 1, token: 'glsa_Lp9wZ3mT0v', disabled: false },
  { name: 'readonly-exporter', role: 'Viewer', tokens: 3, token: 'glsa_Qb1cV6yH8s', disabled: false },
  { name: 'legacy-sync', role: 'Editor', tokens: 0, token: 'glsa_Xr5dN2kJ7p', disabled: true },
]

const SETTINGS_SECTIONS = [
  {
    section: 'server',
    items: [
      ['http_port', '3000'],
      ['domain', 'grafana.fixitlab.local'],
      ['root_url', 'https://grafana.fixitlab.local/'],
      ['enforce_domain', 'false'],
    ],
  },
  {
    section: 'auth',
    items: [
      ['disable_login_form', 'false'],
      ['oauth_auto_login', 'false'],
      ['login_maximum_inactive_lifetime_duration', '7d'],
      ['login_maximum_lifetime_duration', '30d'],
    ],
  },
  {
    section: 'auth.basic',
    items: [['enabled', 'true']],
  },
  {
    section: 'security',
    items: [
      ['admin_user', 'admin'],
      ['admin_password', '********'],
      ['secret_key', '********'],
      ['cookie_secure', 'true'],
      ['cookie_samesite', 'lax'],
      ['allow_embedding', 'false'],
      ['content_security_policy', 'true'],
    ],
  },
  {
    section: 'smtp',
    items: [
      ['enabled', 'true'],
      ['host', 'smtp.fixitlab.local:587'],
      ['user', 'grafana@fixitlab.local'],
      ['password', '********'],
      ['from_address', 'grafana@fixitlab.local'],
      ['skip_verify', 'false'],
    ],
  },
  {
    section: 'users',
    items: [
      ['allow_sign_up', 'false'],
      ['auto_assign_org', 'true'],
      ['auto_assign_org_role', 'Viewer'],
      ['default_theme', 'dark'],
    ],
  },
]

const SUB_TABS = [
  ['users', 'Users', Users],
  ['teams', 'Teams', UsersRound],
  ['service-accounts', 'Service accounts', KeyRound],
  ['preferences', 'Default preferences', SlidersHorizontal],
  ['settings', 'Settings', Settings2],
]

/* ── one service-account row: holds its own token reveal/copy state ── */
function ServiceAccountRow({ acct }) {
  const [revealed, setRevealed] = useState(false)
  const [copied, setCopied] = useState(false)
  const masked = `${acct.token?.slice(0, 5) || 'glsa_'}••••••••••`

  const copy = () => {
    try {
      if (navigator?.clipboard?.writeText) navigator.clipboard.writeText(acct.token || '')
    } catch { /* clipboard unavailable in some sandboxes — ignore */ }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <tr>
      <td className="font-medium text-[#d8def0] flex items-center gap-2">
        <KeyRound size={13} style={{ color: '#f7913b' }} /> {acct.name}
      </td>
      <td><RoleBadge role={acct.role} /></td>
      <td>
        <span className="font-mono text-xs text-[#8a93b2]">{revealed ? (acct.token || '') : masked}</span>
        <button type="button" className="mon-tab !py-0.5 !px-1.5 ml-2 !text-[11px]"
                onClick={() => setRevealed(v => !v)}>
          {revealed ? 'Hide' : 'Reveal'}
        </button>
        <button type="button" className="mon-tab !py-0.5 !px-1.5 ml-1 !text-[11px] inline-flex items-center gap-1"
                onClick={copy}>
          {copied ? <Check size={11} /> : <Copy size={11} />}{copied ? 'Copied' : 'Copy'}
        </button>
      </td>
      <td className="font-mono">{acct.tokens ?? 0}</td>
      <td>
        <span className={`mon-badge ${acct.disabled ? 'mon-badge-down' : 'mon-badge-up'}`}>
          {acct.disabled ? 'Disabled' : 'Enabled'}
        </span>
      </td>
    </tr>
  )
}

/**
 * GrafanaAdministrationPanel — an original functional emulation of Grafana's
 * "Administration" section for a hands-on learning lab. Purely presentational:
 * it synthesizes original sample org data (the engine has none) so the panel
 * always renders. Resilient to a missing/empty `scenario` prop.
 *
 * Props: { scenario }
 */
export default function GrafanaAdministrationPanel({ scenario }) {
  const [sub, setSub] = useState('users')
  const [userFilter, setUserFilter] = useState('')

  const orgName = scenario?.title || scenario?.slug || 'Main Org.'

  const filteredUsers = useMemo(() => {
    const q = userFilter.trim().toLowerCase()
    if (!q) return SAMPLE_USERS
    return SAMPLE_USERS.filter(u =>
      [u.login, u.name, u.email, u.role].some(f => String(f).toLowerCase().includes(q)))
  }, [userFilter])

  return (
    <div className="mon-sim">
      {/* page header */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Shield size={18} style={{ color: '#f7913b' }} />
          <div>
            <div className="mon-panel-title !text-[0.95rem]">Administration</div>
            <div className="mon-panel-sub">Manage org settings, users and access · {orgName}</div>
          </div>
        </div>
      </div>

      {/* sub-tabs */}
      <div className="flex items-center gap-2 mb-4 flex-wrap border-b border-[#262a45] pb-3">
        {SUB_TABS.map(([key, label, Icon]) => (
          <button key={key} type="button" onClick={() => setSub(key)}
                  className={`mon-tab flex items-center gap-2 ${sub === key ? 'mon-tab-active' : ''}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* ── Users ── */}
      {sub === 'users' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[220px]">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8a93b2]" />
              <input className="mon-input w-full !pl-8" placeholder="Search users by login, name, email or role"
                     value={userFilter} onChange={e => setUserFilter(e.target.value)} spellCheck={false} />
            </div>
            <button type="button" className="mon-btn-primary" style={{ background: '#f7913b' }}>
              <Plus size={14} /> New user
            </button>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            <table className="mon-table">
              <thead>
                <tr><th>Login</th><th>Name</th><th>Email</th><th>Role</th><th>Last seen</th></tr>
              </thead>
              <tbody>
                {filteredUsers.map(u => (
                  <tr key={u.login}>
                    <td className="font-mono text-[#d8def0]">{u.login}</td>
                    <td>{u.name}</td>
                    <td className="flex items-center gap-1.5 text-[#8a93b2]">
                      <Mail size={12} className="opacity-70" /> {u.email}
                    </td>
                    <td><RoleBadge role={u.role} /></td>
                    <td className="flex items-center gap-1.5 text-[#8a93b2]">
                      <Clock size={12} className="opacity-70" /> {u.lastSeen}
                    </td>
                  </tr>
                ))}
                {filteredUsers.length === 0 && (
                  <tr><td colSpan={5} className="text-center text-[#8a93b2] py-6">No users match “{userFilter}”</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="mon-panel-sub">{filteredUsers.length} of {SAMPLE_USERS.length} users</div>
        </div>
      )}

      {/* ── Teams ── */}
      {sub === 'teams' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="mon-panel-sub">Teams group users so dashboard and folder permissions can be granted in bulk.</div>
            <button type="button" className="mon-btn-primary" style={{ background: '#f7913b' }}>
              <Plus size={14} /> New team
            </button>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            <table className="mon-table">
              <thead>
                <tr><th>Name</th><th>Email</th><th>Members</th><th>Your role</th></tr>
              </thead>
              <tbody>
                {SAMPLE_TEAMS.map(t => (
                  <tr key={t.name}>
                    <td className="font-medium text-[#d8def0] flex items-center gap-2">
                      <UsersRound size={13} style={{ color: '#f7913b' }} /> {t.name}
                    </td>
                    <td className="text-[#8a93b2]">{t.email}</td>
                    <td className="font-mono">{t.members}</td>
                    <td><RoleBadge role={t.role} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Service accounts ── */}
      {sub === 'service-accounts' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="mon-panel-sub">Service accounts and their tokens authenticate automation, CI and provisioning to the Grafana API.</div>
            <button type="button" className="mon-btn-primary" style={{ background: '#f7913b' }}>
              <Plus size={14} /> Add service account
            </button>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            <table className="mon-table">
              <thead>
                <tr><th>Name</th><th>Role</th><th>Token</th><th>Tokens</th><th>State</th></tr>
              </thead>
              <tbody>
                {SAMPLE_SERVICE_ACCOUNTS.map(a => <ServiceAccountRow key={a.name} acct={a} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Default preferences ── */}
      {sub === 'preferences' && (
        <div className="space-y-3">
          <div className="mon-card">
            <div className="mon-panel-title mb-1 flex items-center gap-2">
              <SlidersHorizontal size={14} style={{ color: '#f7913b' }} /> Default preferences
            </div>
            <div className="mon-panel-sub mb-4">Org-wide defaults applied to users who have not set their own preferences.</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <PrefSelect label="Home dashboard"
                          value="Cluster overview"
                          options={['Default', 'Cluster overview', 'Node exporter / Nodes', 'API latency (SLO)', 'Kubernetes / Pods']} />
              <PrefSelect label="Timezone"
                          value="Browser default"
                          options={['Browser default', 'Coordinated Universal Time', 'America/New_York', 'Europe/London', 'Asia/Kolkata']} />
              <PrefSelect label="Interface theme"
                          value="Dark"
                          options={['Dark', 'Light', 'System preference']} />
              <PrefSelect label="Week start"
                          value="Monday"
                          options={['Browser default', 'Saturday', 'Sunday', 'Monday']} />
            </div>
            <div className="flex items-center gap-2 mt-5">
              <button type="button" className="mon-btn-primary" style={{ background: '#f7913b' }}>Save</button>
              <button type="button" className="mon-btn">Reset</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Settings ── */}
      {sub === 'settings' && (
        <div className="space-y-3">
          <div className="mon-banner">
            <Lock size={15} className="shrink-0 mt-0.5" />
            <span>These settings are read-only. They reflect the merged <span className="font-mono">grafana.ini</span> and environment configuration on the running instance.</span>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            <table className="mon-table">
              <thead>
                <tr><th className="w-1/2">Setting</th><th>Value</th></tr>
              </thead>
              <tbody>
                {SETTINGS_SECTIONS.map(group => [
                  <tr key={`s-${group.section}`}>
                    <td colSpan={2} className="!py-1.5">
                      <span className="mon-badge mon-badge-warn font-mono inline-flex items-center gap-1">
                        <ShieldCheck size={11} /> [{group.section}]
                      </span>
                    </td>
                  </tr>,
                  ...group.items.map(([k, v]) => (
                    <tr key={`${group.section}.${k}`}>
                      <td className="font-mono text-[#8a93b2] pl-6">{k}</td>
                      <td className="font-mono text-[#d8def0]">{v}</td>
                    </tr>
                  )),
                ])}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
