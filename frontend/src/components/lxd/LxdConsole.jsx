import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Box, HardDrive, Network, Layers, Server, Settings, Image as ImageIcon,
  Activity, Play, Square, RotateCcw, Terminal, ArrowLeft, Plus, Cpu,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { baremetalApi } from '../../api/baremetal'
import LabChromeBar from '../lab/LabChromeBar'
import { simPanelRoot } from '../../utils/simLayout'
import './lxd.css'

const ACCENT = '#E95420'

const NAV = [
  { key: 'instances', label: 'Instances', icon: Box, section: 'Compute' },
  { key: 'images', label: 'Images', icon: ImageIcon, section: 'Compute' },
  { key: 'profiles', label: 'Profiles', icon: Layers, section: 'Compute' },
  { key: 'storage', label: 'Storage', icon: HardDrive, section: 'Storage' },
  { key: 'networks', label: 'Networks', icon: Network, section: 'Networking' },
  { key: 'projects', label: 'Projects', icon: Server, section: 'Organisation' },
  { key: 'cluster', label: 'Cluster', icon: Cpu, section: 'Organisation' },
  { key: 'operations', label: 'Operations', icon: Activity, section: 'Ops' },
  { key: 'settings', label: 'Settings', icon: Settings, section: 'Ops' },
]

const DETAIL_TABS = [
  'Overview', 'Configuration', 'Devices', 'Snapshots', 'Terminal', 'Logs',
]

function StatusPill({ status }) {
  const running = (status || '').toLowerCase() === 'running'
  return (
    <span className={`lxd-pill ${running ? 'lxd-pill-running' : 'lxd-pill-stopped'}`}>
      {status || 'Stopped'}
    </span>
  )
}

function profileYaml(profile) {
  if (!profile) return ''
  const lines = [`name: ${profile.name || ''}`]
  if (profile.description) lines.push(`description: ${profile.description}`)
  lines.push('config:')
  const cfg = profile.config || {}
  const keys = Object.keys(cfg)
  if (!keys.length) lines.push('  {}')
  else keys.forEach((k) => lines.push(`  ${k}: "${cfg[k]}"`))
  lines.push('devices:')
  const devices = profile.devices || {}
  const dkeys = Object.keys(devices)
  if (!dkeys.length) lines.push('  {}')
  else {
    dkeys.forEach((dk) => {
      lines.push(`  ${dk}:`)
      const d = devices[dk] || {}
      Object.entries(d).forEach(([kk, vv]) => lines.push(`    ${kk}: ${vv}`))
    })
  }
  return lines.join('\n')
}

function parseSimpleYaml(text) {
  const config = {}
  const devices = {}
  let mode = null
  let curDevice = null
  String(text || '').split('\n').forEach((raw) => {
    const line = raw.replace(/\t/g, '  ')
    if (/^config:\s*$/.test(line)) { mode = 'config'; curDevice = null; return }
    if (/^devices:\s*$/.test(line)) { mode = 'devices'; curDevice = null; return }
    if (mode === 'config') {
      const m = line.match(/^\s{2}([^:\s{}]+):\s*"?(.*?)"?\s*$/)
      if (m) config[m[1]] = m[2]
    }
    if (mode === 'devices') {
      const dm = line.match(/^\s{2}([^:\s{}]+):\s*$/)
      if (dm) { curDevice = dm[1]; devices[curDevice] = {}; return }
      if (curDevice) {
        const km = line.match(/^\s{4}([^:]+):\s*(.*)$/)
        if (km) devices[curDevice][km[1].trim()] = km[2].trim()
      }
    }
  })
  return { config, devices }
}

export default function LxdConsole({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref,
}) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [nav, setNav] = useState('instances')
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState(null)
  const [detailTab, setDetailTab] = useState('Overview')
  const [profileEdit, setProfileEdit] = useState('')
  const [activeProfile, setActiveProfile] = useState('default')
  const [termOut, setTermOut] = useState('')
  const [launchName, setLaunchName] = useState('')
  const slug = scenario?.slug || ''

  const refresh = useCallback(async () => {
    const data = await baremetalApi.getState(sessionId, slug)
    setState(data)
    setLoading(false)
  }, [sessionId, slug])

  useEffect(() => { refresh() }, [refresh])

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const lxd = st?.lxd || {}
  const instances = useMemo(() => lxd.containers || lxd.instances || [], [lxd])
  const profiles = useMemo(() => (lxd.profiles || []).map((p) => (
    typeof p === 'string' ? { name: p, config: {}, devices: {} } : p
  )), [lxd.profiles])
  const images = lxd.images || []
  const storage = lxd.storage_pools || []
  const networks = lxd.networks || []
  const projects = lxd.projects || []
  const cluster = lxd.cluster || []
  const operations = lxd.operations || []
  const settings = lxd.settings || {}
  const events = st?.events || []
  const user = st?.session?.user || 'admin'

  const selectedInst = useMemo(
    () => instances.find((i) => i.name === selected) || null,
    [instances, selected],
  )

  useEffect(() => {
    if (!profiles.length) return
    if (!profiles.some((p) => p.name === activeProfile)) {
      setActiveProfile(profiles[0].name)
    }
  }, [profiles, activeProfile])

  useEffect(() => {
    const p = profiles.find((x) => x.name === activeProfile)
    setProfileEdit(profileYaml(p))
  }, [activeProfile, profiles])

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: onExit || onToggleTerminal,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : (onExit ? 'Close' : 'Terminal'),
    vmwareHref,
  }

  const run = async (fn, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await fn()
      if (res?.ok === false) toast.error(res.error || 'Action failed')
      else if (okMsg) toast.success(res?.message || okMsg)
      await refresh()
      return res
    } finally {
      setBusy(false)
    }
  }

  const sections = []
  NAV.forEach((item) => {
    const last = sections[sections.length - 1]
    if (!last || last.section !== item.section) {
      sections.push({ section: item.section, items: [item] })
    } else {
      last.items.push(item)
    }
  })

  if (!loading && state && !loggedIn) {
    return (
      <div className={simPanelRoot(embedded, 'lxd-app')}>
        <LabChromeBar title="LXD" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="lxd-login-wrap">
          <div className="lxd-login-card">
            <div className="lxd-login-head">
              <span className="lxd-wordmark-mark">LX</span>
              <div>
                <div style={{ fontWeight: 500, fontSize: '1.1rem' }}>LXD</div>
                <div style={{ fontSize: '0.75rem', opacity: 0.8 }}>Container &amp; VM management</div>
              </div>
            </div>
            <div className="lxd-login-body">
              <p>Sign in to manage instances, profiles, storage, and cluster members.</p>
              <label className="lxd-label">
                Username
                <input className="lxd-input" defaultValue="admin" readOnly />
              </label>
              <label className="lxd-label">
                Password
                <input className="lxd-input" type="password" defaultValue="••••••••" readOnly />
              </label>
              <button
                type="button"
                className="lxd-btn lxd-btn-primary"
                style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
                disabled={busy}
                onClick={() => run(() => baremetalApi.login(sessionId), 'Signed in')}
              >
                Sign in
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderInstances = () => {
    if (selectedInst) {
      return (
        <div>
          <div className="lxd-detail-head">
            <button type="button" className="lxd-btn lxd-btn-sm" onClick={() => setSelected(null)}>
              <ArrowLeft size={14} /> Instances
            </button>
            <h1 className="lxd-page-title" style={{ margin: 0 }}>{selectedInst.name}</h1>
            <StatusPill status={selectedInst.status} />
            <div style={{ flex: 1 }} />
            {selectedInst.status === 'Running' ? (
              <>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={() => run(() => baremetalApi.lxdStop(sessionId, selectedInst.name), 'Stopped')}>
                  <Square size={12} /> Stop
                </button>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={() => run(() => baremetalApi.lxdRestart(sessionId, selectedInst.name), 'Restarted')}>
                  <RotateCcw size={12} /> Restart
                </button>
              </>
            ) : (
              <button type="button" className="lxd-btn lxd-btn-sm lxd-btn-primary" disabled={busy}
                onClick={() => run(() => baremetalApi.startLxd(sessionId, selectedInst.name), 'Started')}>
                <Play size={12} /> Start
              </button>
            )}
          </div>
          <div className="lxd-tabs">
            {DETAIL_TABS.map((t) => (
              <button key={t} type="button" className={`lxd-tab ${detailTab === t ? 'active' : ''}`}
                onClick={() => setDetailTab(t)}>{t}</button>
            ))}
          </div>
          {detailTab === 'Overview' && (
            <div className="lxd-panel">
              <dl className="lxd-kv">
                <dt>Status</dt><dd>{selectedInst.status}</dd>
                <dt>Type</dt><dd>{selectedInst.type || 'container'}</dd>
                <dt>Image</dt><dd>{selectedInst.image}</dd>
                <dt>IPv4</dt><dd>{selectedInst.ipv4 || '—'}</dd>
                <dt>IPv6</dt><dd>{selectedInst.ipv6 || '—'}</dd>
                <dt>Profiles</dt><dd>{(selectedInst.profiles || []).join(', ')}</dd>
                <dt>Project</dt><dd>{selectedInst.project || 'default'}</dd>
                <dt>Location</dt><dd>{selectedInst.location || 'none'}</dd>
                <dt>GPU</dt><dd>{selectedInst.nvidia_smi_ok ? 'nvidia-smi OK' : '—'}</dd>
              </dl>
            </div>
          )}
          {detailTab === 'Configuration' && (
            <div className="lxd-panel">
              <dl className="lxd-kv">
                {Object.entries(selectedInst.config || {}).map(([k, v]) => (
                  <div key={k} style={{ display: 'contents' }}>
                    <dt>{k}</dt><dd>{String(v)}</dd>
                  </div>
                ))}
                {!Object.keys(selectedInst.config || {}).length && (
                  <div className="lxd-empty">No instance config keys set.</div>
                )}
              </dl>
              <div className="lxd-toolbar" style={{ marginTop: '1rem' }}>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={() => run(
                    () => baremetalApi.lxdConfigSet(sessionId, selectedInst.name, 'limits.cpu', '4'),
                    'limits.cpu set',
                  )}>
                  Set limits.cpu=4
                </button>
              </div>
            </div>
          )}
          {detailTab === 'Devices' && (
            <div className="lxd-panel">
              <div className="lxd-table-wrap">
                <table className="lxd-table">
                  <thead><tr><th>Name</th><th>Type</th><th>Details</th></tr></thead>
                  <tbody>
                    {Object.entries(selectedInst.devices || {}).map(([name, d]) => (
                      <tr key={name}>
                        <td>{name}</td>
                        <td>{d?.type || '—'}</td>
                        <td className="mono">{JSON.stringify(d)}</td>
                      </tr>
                    ))}
                    {!Object.keys(selectedInst.devices || {}).length && (
                      <tr><td colSpan={3}><div className="lxd-empty">No devices.</div></td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="lxd-toolbar" style={{ marginTop: '0.75rem' }}>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={() => run(
                    () => baremetalApi.lxdDeviceAdd(sessionId, selectedInst.name, 'gpu', 'gpu'),
                    'GPU attached',
                  )}>
                  Add GPU
                </button>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={() => run(
                    () => baremetalApi.lxdDeviceAdd(sessionId, selectedInst.name, 'eth1', 'nic', { network: 'lxdbr0' }),
                    'NIC added',
                  )}>
                  Add NIC
                </button>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={() => run(
                    () => baremetalApi.lxdDeviceAdd(sessionId, selectedInst.name, 'data', 'disk', { path: '/data', pool: 'default' }),
                    'Disk added',
                  )}>
                  Add disk
                </button>
              </div>
            </div>
          )}
          {detailTab === 'Snapshots' && (
            <div className="lxd-panel">
              <div className="lxd-toolbar">
                <button type="button" className="lxd-btn lxd-btn-primary lxd-btn-sm" disabled={busy}
                  onClick={() => run(
                    () => baremetalApi.lxdSnapshot(sessionId, selectedInst.name),
                    'Snapshot created',
                  )}>
                  <Plus size={12} /> Create snapshot
                </button>
              </div>
              <div className="lxd-table-wrap">
                <table className="lxd-table">
                  <thead><tr><th>Name</th><th>Created</th><th>Stateful</th><th /></tr></thead>
                  <tbody>
                    {(selectedInst.snapshots || []).map((s) => (
                      <tr key={s.name}>
                        <td>{s.name}</td>
                        <td className="mono">{s.created_at || '—'}</td>
                        <td>{s.stateful ? 'yes' : 'no'}</td>
                        <td>
                          <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                            onClick={() => run(
                              () => baremetalApi.lxdRestore(sessionId, selectedInst.name, s.name),
                              'Restored',
                            )}>
                            Restore
                          </button>
                        </td>
                      </tr>
                    ))}
                    {!(selectedInst.snapshots || []).length && (
                      <tr><td colSpan={4}><div className="lxd-empty">No snapshots.</div></td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {detailTab === 'Terminal' && (
            <div className="lxd-panel">
              <div className="lxd-term">
                <div><span className="lxd-term-prompt">root@{selectedInst.name}:~#</span> </div>
                {termOut && <div style={{ marginTop: '0.5rem' }}>{termOut}</div>}
              </div>
              <div className="lxd-toolbar" style={{ marginTop: '0.75rem' }}>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={async () => {
                    const res = await run(
                      () => baremetalApi.lxdExec(sessionId, selectedInst.name, 'uname -a'),
                    )
                    if (res?.output) setTermOut(res.output)
                  }}>
                  <Terminal size={12} /> uname -a
                </button>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={async () => {
                    const res = await run(
                      () => baremetalApi.lxdExec(sessionId, selectedInst.name, 'nvidia-smi'),
                    )
                    if (res?.output) setTermOut(res.output)
                  }}>
                  nvidia-smi
                </button>
                <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                  onClick={async () => {
                    const res = await run(
                      () => baremetalApi.lxdExec(sessionId, selectedInst.name, 'bash'),
                    )
                    setTermOut(
                      (res?.output || `root@${selectedInst.name}:~#`)
                      + `\n# LXD session marker: root@${selectedInst.name}`,
                    )
                  }}>
                  Open shell
                </button>
              </div>
            </div>
          )}
          {detailTab === 'Logs' && (
            <div className="lxd-logs">
              {(events || []).slice(0, 40).map((e, i) => (
                <div key={`${e.time}-${i}`}>
                  [{e.time || '—'}] {e.message}
                </div>
              ))}
              {!(events || []).length && <div>No events yet.</div>}
            </div>
          )}
        </div>
      )
    }

    return (
      <div>
        <h1 className="lxd-page-title">Instances</h1>
        <p className="lxd-page-sub">Containers and virtual machines on this LXD cluster</p>
        <div className="lxd-toolbar">
          <input
            className="lxd-input"
            style={{ maxWidth: 200 }}
            placeholder="Name"
            value={launchName}
            onChange={(e) => setLaunchName(e.target.value)}
          />
          <button
            type="button"
            className="lxd-btn lxd-btn-primary"
            disabled={busy || !launchName.trim()}
            onClick={() => run(
              () => baremetalApi.lxdLaunch(sessionId, launchName.trim()),
              'Launched',
            ).then(() => setLaunchName(''))}
          >
            <Plus size={14} /> Launch
          </button>
        </div>
        <div className="lxd-table-wrap">
          <table className="lxd-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>IPv4</th>
                <th>Type</th>
                <th>Snapshots</th>
                <th>Project</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {instances.map((c) => (
                <tr
                  key={c.name}
                  className={selected === c.name ? 'selected' : ''}
                  style={{ cursor: 'pointer' }}
                  onClick={() => { setSelected(c.name); setDetailTab('Overview'); setTermOut('') }}
                >
                  <td>{c.name}</td>
                  <td><StatusPill status={c.status} /></td>
                  <td className="mono">{c.ipv4 || '—'}</td>
                  <td>{c.type || 'container'}</td>
                  <td>{(c.snapshots || []).length}</td>
                  <td>{c.project || 'default'}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {c.status === 'Running' ? (
                      <button type="button" className="lxd-btn lxd-btn-sm" disabled={busy}
                        onClick={() => run(() => baremetalApi.lxdStop(sessionId, c.name), 'Stopped')}>
                        <Square size={12} /> Stop
                      </button>
                    ) : (
                      <button type="button" className="lxd-btn lxd-btn-sm lxd-btn-primary" disabled={busy}
                        onClick={() => run(() => baremetalApi.startLxd(sessionId, c.name), 'Started')}>
                        <Play size={12} /> Start
                      </button>
                    )}
                    <button type="button" className="lxd-btn lxd-btn-sm" style={{ marginLeft: 4 }} disabled={busy}
                      onClick={() => { setSelected(c.name); setDetailTab('Terminal') }}
                      title="Console">
                      <Terminal size={12} />
                    </button>
                  </td>
                </tr>
              ))}
              {!instances.length && (
                <tr><td colSpan={7}><div className="lxd-empty">No instances.</div></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const renderProfiles = () => (
    <div>
      <h1 className="lxd-page-title">Profiles</h1>
      <p className="lxd-page-sub">Reusable instance configuration and devices</p>
      <div className="lxd-toolbar">
        <select className="lxd-select" style={{ maxWidth: 220 }} value={activeProfile}
          onChange={(e) => setActiveProfile(e.target.value)}>
          {profiles.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
        </select>
        <button type="button" className="lxd-btn" disabled={busy}
          onClick={() => {
            const name = `profile-${profiles.length + 1}`
            run(() => baremetalApi.lxdProfileCreate(sessionId, name), `Created ${name}`)
              .then(() => setActiveProfile(name))
          }}>
          <Plus size={14} /> Create
        </button>
      </div>
      <textarea className="lxd-textarea" value={profileEdit} onChange={(e) => setProfileEdit(e.target.value)} />
      <div className="lxd-yaml-actions">
        <button type="button" className="lxd-btn lxd-btn-primary" disabled={busy}
          onClick={() => {
            const parsed = parseSimpleYaml(profileEdit)
            run(
              () => baremetalApi.lxdProfileSet(sessionId, activeProfile, {
                config: parsed.config,
                devices: parsed.devices,
              }),
              'Profile saved',
            )
          }}>
          Save profile
        </button>
      </div>
    </div>
  )

  const renderTablePage = (title, sub, columns, rows) => (
    <div>
      <h1 className="lxd-page-title">{title}</h1>
      <p className="lxd-page-sub">{sub}</p>
      <div className="lxd-table-wrap">
        <table className="lxd-table">
          <thead>
            <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {rows}
            {!rows?.length && (
              <tr><td colSpan={columns.length}><div className="lxd-empty">None found.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )

  let main = null
  if (nav === 'instances') main = renderInstances()
  else if (nav === 'images') {
    main = renderTablePage(
      'Images',
      'Local and remote image aliases',
      ['Alias', 'Fingerprint', 'Type', 'Public', 'Description'],
      images.map((img) => (
        <tr key={img.alias || img.fingerprint}>
          <td>{img.alias}</td>
          <td className="mono">{(img.fingerprint || '').slice(0, 12)}</td>
          <td>{img.type}</td>
          <td>{img.public ? 'yes' : 'no'}</td>
          <td>{img.description}</td>
        </tr>
      )),
    )
  } else if (nav === 'profiles') main = renderProfiles()
  else if (nav === 'storage') {
    main = renderTablePage(
      'Storage',
      'Storage pools available to instances',
      ['Name', 'Driver', 'Source', 'Used by'],
      storage.map((p) => (
        <tr key={p.name}>
          <td>{p.name}</td>
          <td>{p.driver}</td>
          <td className="mono">{p.source}</td>
          <td>{p.used_by ?? '—'}</td>
        </tr>
      )),
    )
  } else if (nav === 'networks') {
    main = renderTablePage(
      'Networks',
      'Managed and unmanaged networks',
      ['Name', 'Type', 'Managed', 'IPv4', 'IPv6'],
      networks.map((n) => (
        <tr key={n.name}>
          <td>{n.name}</td>
          <td>{n.type}</td>
          <td>{n.managed ? 'yes' : 'no'}</td>
          <td className="mono">{n.ipv4 || '—'}</td>
          <td className="mono">{n.ipv6 || '—'}</td>
        </tr>
      )),
    )
  } else if (nav === 'projects') {
    main = (
      <div>
        <h1 className="lxd-page-title">Projects</h1>
        <p className="lxd-page-sub">Isolated LXD projects</p>
        <div className="lxd-toolbar">
          <button type="button" className="lxd-btn lxd-btn-primary" disabled={busy}
            onClick={() => run(
              () => baremetalApi.lxdProjectCreate(sessionId, `project-${projects.length + 1}`),
              'Project created',
            )}>
            <Plus size={14} /> Create project
          </button>
        </div>
        <div className="lxd-table-wrap">
          <table className="lxd-table">
            <thead><tr><th>Name</th><th>Description</th><th>Used by</th></tr></thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.name}>
                  <td>{p.name}</td>
                  <td>{p.description || '—'}</td>
                  <td>{p.used_by ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  } else if (nav === 'cluster') {
    main = renderTablePage(
      'Cluster',
      'Cluster member nodes',
      ['Name', 'URL', 'Roles', 'Architecture', 'Failure domain', 'Status'],
      cluster.map((m) => (
        <tr key={m.name}>
          <td>{m.name}</td>
          <td className="mono">{m.url}</td>
          <td>{Array.isArray(m.roles) ? m.roles.join(', ') : m.roles}</td>
          <td>{m.architecture}</td>
          <td>{m.failure_domain}</td>
          <td>{m.status || 'Online'}</td>
        </tr>
      )),
    )
  } else if (nav === 'operations') {
    main = (
      <div>
        <h1 className="lxd-page-title">Operations / Events</h1>
        <p className="lxd-page-sub">Recent LXD operations and console events</p>
        <div className="lxd-logs">
          {(operations.length ? operations : events).slice(0, 50).map((e, i) => (
            <div key={e.id || `${e.time}-${i}`}>
              [{e.created_at || e.time || '—'}] {e.description || e.message}
              {e.status ? ` (${e.status})` : ''}
            </div>
          ))}
          {!operations.length && !events.length && <div>No operations yet.</div>}
        </div>
      </div>
    )
  } else if (nav === 'settings') {
    main = (
      <div>
        <h1 className="lxd-page-title">Settings</h1>
        <p className="lxd-page-sub">Server configuration keys</p>
        <div className="lxd-panel">
          <dl className="lxd-kv">
            {Object.entries(settings).map(([k, v]) => (
              <div key={k} style={{ display: 'contents' }}>
                <dt>{k}</dt>
                <dd>{String(v)}</dd>
              </div>
            ))}
            {!Object.keys(settings).length && <div className="lxd-empty">No settings.</div>}
          </dl>
        </div>
      </div>
    )
  }

  return (
    <div className={simPanelRoot(embedded, 'lxd-app')}>
      <LabChromeBar title="LXD" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
      <header className="lxd-header">
        <div className="lxd-wordmark">
          <span className="lxd-wordmark-mark">LX</span>
          LXD
        </div>
        <div className="lxd-header-meta">
          <span>{user}</span>
          <span>·</span>
          <span>{instances.length} instances</span>
        </div>
      </header>
      <div className="lxd-body">
        <nav className="lxd-sidebar">
          {sections.map((sec) => (
            <div key={sec.section}>
              <div className="lxd-nav-section">{sec.section}</div>
              {sec.items.map((item) => {
                const Icon = item.icon
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`lxd-nav-item ${nav === item.key ? 'active' : ''}`}
                    onClick={() => { setNav(item.key); setSelected(null) }}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
          ))}
        </nav>
        <main className="lxd-main">
          {loading ? <div className="lxd-empty">Loading…</div> : main}
        </main>
      </div>
    </div>
  )
}
