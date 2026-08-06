import { useMemo, useState } from 'react'
import { Plus, Trash2, UploadCloud } from 'lucide-react'
import { baremetalApi } from '../../api/baremetal'
import { MaasStatusBadge } from './MaasStatusBadge'

/**
 * Canonical MAAS Settings leaf navigation:
 * General, Commissioning, Deploy, Kernel parameters, Storage, Network
 * discovery, Proxy, DNS, NTP, Syslog, Package repositories, Users, Scripts,
 * License keys. Each leaf is a self-contained form/list persisted via
 * baremetalApi.updateSettings (generic key merge) or dedicated user/script
 * endpoints.
 */
const LEAVES = [
  { key: 'general', label: 'General' },
  { key: 'commissioning', label: 'Commissioning' },
  { key: 'deploy', label: 'Deploy' },
  { key: 'kernel', label: 'Kernel parameters' },
  { key: 'storage', label: 'Storage' },
  { key: 'discovery', label: 'Network discovery' },
  { key: 'proxy', label: 'Proxy' },
  { key: 'dns', label: 'DNS' },
  { key: 'ntp', label: 'NTP' },
  { key: 'syslog', label: 'Syslog' },
  { key: 'repositories', label: 'Package repositories' },
  { key: 'users', label: 'Users' },
  { key: 'scripts', label: 'Scripts' },
  { key: 'license', label: 'License keys' },
]

/**
 * Field descriptors for the simple key/value leaves — rendered generically.
 * Keys are chosen to match the region's seeded `maas.settings` (see
 * `_maas_infra_seed` in baremetal_engine.py) so a leaf's initial values are
 * populated from real state, and saving clears the matching `broken` flags
 * (e.g. ntp_servers / commissioning_distro_series) server-side.
 */
const FIELD_SPECS = {
  general: [
    { key: 'maas_name', label: 'MAAS name', type: 'text', placeholder: 'maas' },
    { key: 'maas_url', label: 'MAAS URL', type: 'text', placeholder: 'http://region.maas:5240/MAAS' },
    { key: 'maas_auto_ipmi_user', label: 'Auto-enrolled IPMI username', type: 'text', placeholder: 'maas' },
    { key: 'maas_auto_ipmi_user_privilege_level', label: 'Auto-enrolled IPMI privilege level', type: 'text', placeholder: 'ADMIN' },
  ],
  commissioning: [
    { key: 'commissioning_distro_series', label: 'Default commissioning release', type: 'text', placeholder: 'jammy' },
    { key: 'default_min_hwe_kernel', label: 'Default minimum kernel version', type: 'text', placeholder: 'ga-22.04' },
    { key: 'hardware_sync_interval', label: 'Hardware sync interval', type: 'text', placeholder: '15m' },
  ],
  deploy: [
    { key: 'default_osystem', label: 'Default operating system', type: 'text', placeholder: 'ubuntu' },
    { key: 'default_distro', label: 'Default OS release', type: 'text', placeholder: 'ubuntu/jammy' },
    { key: 'curtin_verbose', label: 'Verbose curtin install logging', type: 'checkbox' },
  ],
  kernel: [
    { key: 'kernel_opts', label: 'Global boot kernel parameters', type: 'textarea', placeholder: 'console=tty1 console=ttyS0' },
  ],
  storage: [
    { key: 'default_storage_layout', label: 'Default storage layout', type: 'text', placeholder: 'flat' },
    { key: 'enable_disk_erasing_on_release', label: 'Erase disks by default on release', type: 'checkbox' },
  ],
  discovery: [
    { key: 'network_discovery', label: 'Network discovery', type: 'select', options: ['enabled', 'disabled'] },
    { key: 'active_discovery_interval', label: 'Active subnet mapping interval', type: 'text', placeholder: '10m' },
  ],
  proxy: [
    { key: 'enable_http_proxy', label: 'Enable HTTP proxy for machines', type: 'checkbox' },
    { key: 'http_proxy', label: 'HTTP proxy URL', type: 'text', placeholder: 'http://squid.internal:3128' },
    { key: 'apt_http_proxy', label: 'APT HTTP proxy URL', type: 'text', placeholder: 'http://squid.internal:3128' },
    { key: 'use_peer_proxy', label: 'Use MAAS built-in proxy as peer proxy', type: 'checkbox' },
    { key: 'prefer_v4_proxy', label: 'Prefer IPv4 over IPv6 for the built-in proxy', type: 'checkbox' },
  ],
  dns: [
    { key: 'dns_forwarder', label: 'Upstream DNS (forwarders)', type: 'text', placeholder: '8.8.8.8' },
    { key: 'dnssec_validation', label: 'DNSSEC validation', type: 'text', placeholder: 'auto' },
  ],
  ntp: [
    { key: 'ntp_servers', label: 'NTP servers', type: 'text', placeholder: 'ntp.ubuntu.com' },
  ],
  syslog: [
    { key: 'remote_syslog', label: 'Remote syslog server', type: 'text', placeholder: 'syslog.internal:514' },
    { key: 'syslog_host', label: 'Rack syslog forwarding host', type: 'text', placeholder: '10.10.1.2' },
  ],
  repositories: [
    { key: 'package_repositories', label: 'Enabled Ubuntu components (comma-separated)', type: 'list', placeholder: 'main, restricted, universe, multiverse' },
    { key: 'main_archive', label: 'Ubuntu archive (main)', type: 'text', placeholder: 'http://archive.ubuntu.com/ubuntu' },
    { key: 'ports_archive', label: 'Ubuntu extra architectures (ports)', type: 'text', placeholder: 'http://ports.ubuntu.com/ubuntu-ports' },
  ],
  license: [
    { key: 'windows_kms_host', label: 'Windows KMS activation host', type: 'text', placeholder: 'kms.internal' },
    { key: 'license_key_windows', label: 'Windows license key', type: 'text', placeholder: 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX' },
  ],
}

function readSettings(state) {
  return state?.settings || state?.maas?.settings || {}
}

function GenericSettingsForm({ leafKey, state, busy, sessionId, run }) {
  const specs = FIELD_SPECS[leafKey] || []
  const settings = readSettings(state)
  const [form, setForm] = useState(() => {
    const initial = {}
    specs.forEach((f) => {
      if (f.type === 'checkbox') initial[f.key] = !!settings[f.key]
      else if (f.type === 'list') initial[f.key] = (settings[f.key] || []).join(', ')
      else initial[f.key] = settings[f.key] ?? (f.type === 'select' ? (f.options || [])[0] : '')
    })
    return initial
  })
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const save = () => {
    const payload = {}
    specs.forEach((f) => {
      payload[f.key] = f.type === 'list'
        ? String(form[f.key] || '').split(',').map((s) => s.trim()).filter(Boolean)
        : form[f.key]
    })
    run(() => baremetalApi.updateSettings(sessionId, payload), 'Settings saved')
  }

  return (
    <div className="maas-card">
      <div className="maas-card-body maas-form-grid">
        {specs.map((f) => (
          f.type === 'checkbox' ? (
            <label key={f.key} className="maas-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={!!form[f.key]} onChange={(e) => set(f.key, e.target.checked)} />
              {f.label}
            </label>
          ) : f.type === 'textarea' ? (
            <label key={f.key} className="maas-label" style={{ gridColumn: '1 / -1' }}>
              {f.label}
              <textarea
                className="maas-textarea"
                rows={3}
                value={form[f.key]}
                placeholder={f.placeholder}
                onChange={(e) => set(f.key, e.target.value)}
              />
            </label>
          ) : f.type === 'select' ? (
            <label key={f.key} className="maas-label">
              {f.label}
              <select className="maas-select" value={form[f.key]} onChange={(e) => set(f.key, e.target.value)}>
                {(f.options || []).map((opt) => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </label>
          ) : (
            <label key={f.key} className="maas-label" style={f.type === 'list' ? { gridColumn: '1 / -1' } : undefined}>
              {f.label}
              <input
                className="maas-input"
                value={form[f.key]}
                placeholder={f.placeholder}
                onChange={(e) => set(f.key, e.target.value)}
              />
            </label>
          )
        ))}
      </div>
      <div className="maas-dialog-foot">
        <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={save}>
          Save
        </button>
      </div>
    </div>
  )
}

function UsersLeaf({ state, busy, sessionId, run }) {
  const users = state?.maas?.users || state?.users || []
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)

  const create = () => {
    if (!username.trim()) return
    run(
      () => baremetalApi.createUser(sessionId, { username: username.trim(), email, is_admin: isAdmin }),
      'User created',
    )
    setUsername('')
    setEmail('')
    setIsAdmin(false)
  }

  return (
    <div>
      <div className="maas-table-wrap" style={{ marginBottom: '1rem' }}>
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Username</th>
              <th className="no-sort">Email</th>
              <th className="no-sort">Role</th>
              <th className="no-sort" />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username}>
                <td className="mono">{u.username}</td>
                <td>{u.email || '—'}</td>
                <td>{u.is_admin ? 'Admin' : 'User'}</td>
                <td>
                  {u.username !== 'admin' && (
                    <button
                      type="button"
                      className="maas-btn maas-btn-sm maas-btn-negative"
                      disabled={busy}
                      onClick={() => run(() => baremetalApi.deleteUser(sessionId, u.username), 'User deleted')}
                    >
                      <Trash2 size={12} /> Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!users.length && <tr><td colSpan={4}><div className="maas-empty">No users.</div></td></tr>}
          </tbody>
        </table>
      </div>
      <div className="maas-card">
        <div className="maas-card-head">Add user</div>
        <div className="maas-card-body maas-form-grid">
          <label className="maas-label">
            Username
            <input className="maas-input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="jdoe" />
          </label>
          <label className="maas-label">
            Email
            <input className="maas-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jdoe@example.com" />
          </label>
          <label className="maas-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
            MAAS administrator
          </label>
        </div>
        <div className="maas-dialog-foot">
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy || !username.trim()} onClick={create}>
            <Plus size={13} /> Add user
          </button>
        </div>
      </div>
    </div>
  )
}

function ScriptsLeaf({ state, busy, sessionId, run }) {
  const scripts = state?.maas?.commissioning_scripts || state?.commissioning_scripts || []
  const [name, setName] = useState('')

  const attach = () => {
    if (!name.trim()) return
    run(() => baremetalApi.attachScript(sessionId, name.trim()), 'Script attached')
    setName('')
  }

  return (
    <div>
      <div className="maas-table-wrap" style={{ marginBottom: '1rem' }}>
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">Applied to</th>
              <th className="no-sort">Status</th>
            </tr>
          </thead>
          <tbody>
            {scripts.map((s) => (
              <tr key={s.name}>
                <td className="mono">{s.name}</td>
                <td>{(s.applied_to || s.tags || ['*']).join(', ')}</td>
                <td><MaasStatusBadge status={s.status || 'Ready'} /></td>
              </tr>
            ))}
            {!scripts.length && <tr><td colSpan={3}><div className="maas-empty">No commissioning scripts attached.</div></td></tr>}
          </tbody>
        </table>
      </div>
      <div className="maas-card">
        <div className="maas-card-head">Attach commissioning script</div>
        <div className="maas-card-body maas-form-grid">
          <label className="maas-label">
            Script name
            <input className="maas-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="50-check-gpu" />
          </label>
        </div>
        <div className="maas-dialog-foot">
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy || !name.trim()} onClick={attach}>
            <UploadCloud size={13} /> Attach script
          </button>
        </div>
      </div>
    </div>
  )
}

function SettingsLeaf({ leafKey, state, busy, sessionId, run }) {
  if (leafKey === 'users') return <UsersLeaf state={state} busy={busy} sessionId={sessionId} run={run} />
  if (leafKey === 'scripts') return <ScriptsLeaf state={state} busy={busy} sessionId={sessionId} run={run} />
  return <GenericSettingsForm leafKey={leafKey} state={state} busy={busy} sessionId={sessionId} run={run} />
}

/** Left leaf list + right form, nested under the "Settings" top-level nav item. */
export default function MaasSettingsPages({ state, busy, sessionId, run }) {
  const [leaf, setLeaf] = useState('general')
  const activeLabel = useMemo(() => LEAVES.find((l) => l.key === leaf)?.label || 'General', [leaf])

  return (
    <div>
      <h1 className="maas-page-title">Settings</h1>
      <p className="maas-page-sub">Region configuration</p>
      <div className="maas-settings-layout">
        <nav className="maas-settings-nav p-side-navigation" aria-label="Settings sections">
          <ul className="p-side-navigation__list">
            {LEAVES.map((l) => (
              <li key={l.key} className="p-side-navigation__item">
                <button
                  type="button"
                  className={`maas-settings-leaf p-side-navigation__link ${leaf === l.key ? 'is-active' : ''}`}
                  aria-current={leaf === l.key ? 'page' : undefined}
                  onClick={() => setLeaf(l.key)}
                >
                  {l.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div className="maas-settings-content">
          <h2 className="maas-settings-heading">{activeLabel}</h2>
          <SettingsLeaf leafKey={leaf} state={state} busy={busy} sessionId={sessionId} run={run} />
        </div>
      </div>
    </div>
  )
}
