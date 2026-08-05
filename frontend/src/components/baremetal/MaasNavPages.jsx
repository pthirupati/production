import { useMemo, useState } from 'react'
import { Play, Square, Power, RefreshCw, Plus } from 'lucide-react'
import { MaasStatusBadge, PowerIcon } from './MaasStatusBadge'
import { baremetalApi } from '../../api/baremetal'

function healthClass(h) {
  const v = (h || 'ok').toLowerCase()
  if (v === 'ok' || v === 'running' || v === 'healthy') return 'maas-health-ok'
  if (v === 'degraded' || v === 'warning') return 'maas-health-degraded'
  return 'maas-health-down'
}

export function DevicesPage({ state, busy, run }) {
  const devices = state?.maas?.devices || state?.devices || []
  return (
    <div>
      <h1 className="maas-page-title">Devices</h1>
      <p className="maas-page-sub">Non-deployable network devices with IP reservations</p>
      <div className="maas-table-wrap">
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Hostname</th>
              <th className="no-sort">IP</th>
              <th className="no-sort">MAC</th>
              <th className="no-sort">Zone</th>
              <th className="no-sort">Owner</th>
              <th className="no-sort">Parent</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id || d.hostname || d.mac}>
                <td>{d.hostname || d.name}</td>
                <td className="mono">{d.ip || d.ip_address || '—'}</td>
                <td className="mono">{d.mac || '—'}</td>
                <td>{d.zone || 'default'}</td>
                <td>{d.owner || '—'}</td>
                <td>{d.parent || '—'}</td>
              </tr>
            ))}
            {!devices.length && (
              <tr><td colSpan={6}><div className="maas-empty">No devices registered.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
      {!busy && devices.length === 0 && run && (
        <p className="maas-page-sub" style={{ marginTop: 12 }}>
          Devices appear when the region controller has IP reservations for printers, switches, and other fixed hardware.
        </p>
      )}
    </div>
  )
}

export function ControllersPage({ state }) {
  const controllers = state?.controllers || state?.maas?.controllers || []
  return (
    <div>
      <h1 className="maas-page-title">Controllers</h1>
      <p className="maas-page-sub">Region and rack controller services</p>
      {controllers.map((c) => (
        <div key={c.name || c.hostname} className="maas-card">
          <div className="maas-card-head" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{c.name || c.hostname} · {c.type || 'rack'}</span>
            <span className={healthClass(c.health || c.status)}>{c.health || c.status || 'ok'}</span>
          </div>
          <div className="maas-card-body">
            <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
              <table className="maas-table">
                <thead>
                  <tr>
                    <th className="no-sort">Service</th>
                    <th className="no-sort">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(c.services || {}).map(([name, status]) => (
                    <tr key={name}>
                      <td className="mono">{name}</td>
                      <td className={healthClass(typeof status === 'string' ? status : status?.status)}>
                        {typeof status === 'string' ? status : status?.status || 'ok'}
                      </td>
                    </tr>
                  ))}
                  {!Object.keys(c.services || {}).length && (
                    <tr><td colSpan={2}><div className="maas-empty">No service inventory.</div></td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ))}
      {!controllers.length && <div className="maas-empty">No controllers in this region.</div>}
    </div>
  )
}

export function KvmPage({ state, busy, sessionId, run }) {
  const vms = state?.kvm?.vms || []
  const containers = state?.lxd?.containers || []
  return (
    <div>
      <h1 className="maas-page-title">KVM</h1>
      <p className="maas-page-sub">KVM hosts and LXD instances managed alongside MAAS</p>

      <h2 style={{ fontSize: '1.1rem', fontWeight: 400, margin: '1rem 0 0.5rem' }}>Virtual machines</h2>
      <div className="maas-table-wrap" style={{ marginBottom: '1.5rem' }}>
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">State</th>
              <th className="no-sort">vCPU</th>
              <th className="no-sort">RAM</th>
              <th className="no-sort">IP</th>
              <th className="no-sort" />
            </tr>
          </thead>
          <tbody>
            {vms.map((v) => (
              <tr key={v.name}>
                <td>{v.name}</td>
                <td><MaasStatusBadge status={v.state === 'running' ? 'Deployed' : 'New'} /></td>
                <td>{v.vcpu}</td>
                <td>{v.ram_gb} GiB</td>
                <td className="mono">{v.ip || '—'}</td>
                <td>
                  {v.state === 'running' ? (
                    <button
                      type="button"
                      className="maas-btn maas-btn-sm"
                      disabled={busy}
                      onClick={() => run(() => baremetalApi.action(sessionId, 'kvm_stop', { name: v.name }), 'Stopped')}
                    >
                      <Square size={12} /> Stop
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="maas-btn maas-btn-sm maas-btn-positive"
                      disabled={busy}
                      onClick={() => run(() => baremetalApi.startKvm(sessionId, v.name), 'Started')}
                    >
                      <Play size={12} /> Start
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!vms.length && <tr><td colSpan={6}><div className="maas-empty">No KVM VMs.</div></td></tr>}
          </tbody>
        </table>
      </div>

      <h2 style={{ fontSize: '1.1rem', fontWeight: 400, margin: '1rem 0 0.5rem' }}>LXD containers</h2>
      <div className="maas-table-wrap">
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">Status</th>
              <th className="no-sort">Image</th>
              <th className="no-sort">IPv4</th>
              <th className="no-sort" />
            </tr>
          </thead>
          <tbody>
            {containers.map((c) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td><MaasStatusBadge status={c.status === 'Running' ? 'Deployed' : 'New'} /></td>
                <td className="mono">{c.image}</td>
                <td className="mono">{c.ipv4 || '—'}</td>
                <td>
                  {c.status === 'Running' ? (
                    <button
                      type="button"
                      className="maas-btn maas-btn-sm"
                      disabled={busy}
                      onClick={() => run(() => baremetalApi.action(sessionId, 'lxd_stop', { name: c.name }), 'Stopped')}
                    >
                      <Square size={12} /> Stop
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="maas-btn maas-btn-sm maas-btn-positive"
                      disabled={busy}
                      onClick={() => run(() => baremetalApi.startLxd(sessionId, c.name), 'Started')}
                    >
                      <Play size={12} /> Start
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!containers.length && <tr><td colSpan={5}><div className="maas-empty">No LXD containers.</div></td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function ImagesPage({ state, busy, sessionId, run }) {
  const resources = state?.maas?.boot_resources || []
  return (
    <div>
      <div className="maas-toolbar">
        <div>
          <h1 className="maas-page-title">Images</h1>
          <p className="maas-page-sub">Boot resources synced from images.maas.io and custom uploads</p>
        </div>
        <div className="maas-toolbar-spacer" />
        <button
          type="button"
          className="maas-btn maas-btn-positive"
          disabled={busy}
          onClick={() => run(
            () => baremetalApi.publishBootResource(sessionId, { sku: 'h100', source: 'manual upload' }),
            'Boot resource published',
          )}
        >
          <Plus size={14} /> Import custom/h100-jammy
        </button>
      </div>
      <div className="maas-table-wrap">
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">Architecture</th>
              <th className="no-sort">Type</th>
              <th className="no-sort">Size</th>
              <th className="no-sort">Status</th>
              <th className="no-sort">Source</th>
            </tr>
          </thead>
          <tbody>
            {resources.map((r) => (
              <tr key={r.name}>
                <td className="mono">{r.name}</td>
                <td>{r.architecture || 'amd64/generic'}</td>
                <td>{r.type || 'Synced'}</td>
                <td>{r.size_gb != null ? `${r.size_gb} GB` : '—'}</td>
                <td><MaasStatusBadge status={r.status || 'Synced'} /></td>
                <td style={{ fontSize: '0.75rem', color: '#666' }}>{r.source || 'images.maas.io'}</td>
              </tr>
            ))}
            {!resources.length && (
              <tr><td colSpan={6}><div className="maas-empty">No boot resources — import or sync images.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function DomainsPage({ state, busy, sessionId, run }) {
  const domains = state?.domains || state?.maas?.domains || []
  const [name, setName] = useState('')
  const [type, setType] = useState('A')
  const [data, setData] = useState('')
  const [domainName, setDomainName] = useState(domains[0]?.name || 'maas')

  return (
    <div>
      <h1 className="maas-page-title">DNS</h1>
      <p className="maas-page-sub">Authoritative domains and resource records</p>
      {domains.map((d) => (
        <div key={d.name} className="maas-card">
          <div className="maas-card-head">
            {d.name} {d.authoritative !== false ? '(authoritative)' : ''}
          </div>
          <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
            <table className="maas-table">
              <thead>
                <tr>
                  <th className="no-sort">Type</th>
                  <th className="no-sort">Name</th>
                  <th className="no-sort">Data</th>
                </tr>
              </thead>
              <tbody>
                {(d.records || []).map((r, i) => (
                  <tr key={`${r.name}-${i}`}>
                    <td>{r.type}</td>
                    <td className="mono">{r.name}</td>
                    <td className="mono">{r.data}</td>
                  </tr>
                ))}
                {!(d.records || []).length && (
                  <tr><td colSpan={3}><div className="maas-empty">No records.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {!domains.length && <div className="maas-empty">No DNS domains configured.</div>}
      <div className="maas-card">
        <div className="maas-card-head">Add record</div>
        <div className="maas-card-body maas-form-grid">
          <label className="maas-label">
            Domain
            <select className="maas-select" value={domainName} onChange={(e) => setDomainName(e.target.value)}>
              {(domains.length ? domains : [{ name: 'maas' }]).map((d) => (
                <option key={d.name} value={d.name}>{d.name}</option>
              ))}
            </select>
          </label>
          <label className="maas-label">
            Type
            <select className="maas-select" value={type} onChange={(e) => setType(e.target.value)}>
              {['A', 'AAAA', 'CNAME', 'TXT', 'MX'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label className="maas-label">
            Name
            <input className="maas-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="node-01" />
          </label>
          <label className="maas-label">
            Data
            <input className="maas-input" value={data} onChange={(e) => setData(e.target.value)} placeholder="10.10.1.11" />
          </label>
        </div>
        <div className="maas-dialog-foot">
          <button
            type="button"
            className="maas-btn maas-btn-positive"
            disabled={busy || !name || !data}
            onClick={() => run(
              () => baremetalApi.action(sessionId, 'maas_add_dns_record', {
                domain: domainName, type, name, data,
              }),
              'DNS record added',
            )}
          >
            Add record
          </button>
        </div>
      </div>
    </div>
  )
}

export function ZonesPage({ state, busy, sessionId, run }) {
  const zones = state?.zones || state?.maas?.zones || []
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  return (
    <div>
      <div className="maas-toolbar">
        <div>
          <h1 className="maas-page-title">Availability zones</h1>
          <p className="maas-page-sub">Logical groupings for physical failure domains</p>
        </div>
      </div>
      <div className="maas-table-wrap" style={{ marginBottom: '1rem' }}>
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">Description</th>
            </tr>
          </thead>
          <tbody>
            {zones.map((z) => (
              <tr key={z.name}>
                <td>{z.name}</td>
                <td>{z.description || '—'}</td>
              </tr>
            ))}
            {!zones.length && <tr><td colSpan={2}><div className="maas-empty">No zones.</div></td></tr>}
          </tbody>
        </table>
      </div>
      <div className="maas-card">
        <div className="maas-card-head">Add zone</div>
        <div className="maas-card-body maas-form-grid">
          <label className="maas-label">
            Name
            <input className="maas-input" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="maas-label">
            Description
            <input className="maas-input" value={desc} onChange={(e) => setDesc(e.target.value)} />
          </label>
        </div>
        <div className="maas-dialog-foot">
          <button
            type="button"
            className="maas-btn maas-btn-positive"
            disabled={busy || !name}
            onClick={() => run(
              () => baremetalApi.action(sessionId, 'maas_add_zone', { name, description: desc }),
              'Zone created',
            )}
          >
            Add zone
          </button>
        </div>
      </div>
    </div>
  )
}

export function PoolsPage({ state, busy, sessionId, run }) {
  const pools = state?.resource_pools || state?.maas?.resource_pools || []
  const machines = state?.maas?.machines || []
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const rows = pools.length
    ? pools
    : [{ name: 'default', description: 'Default pool', machine_count: machines.length }]
  return (
    <div>
      <h1 className="maas-page-title">Resource pools</h1>
      <p className="maas-page-sub">Allocate machines into named pools for multi-tenancy</p>
      <div className="maas-table-wrap" style={{ marginBottom: '1rem' }}>
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">Description</th>
              <th className="no-sort">Machines</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.name}>
                <td>{p.name}</td>
                <td>{p.description || '—'}</td>
                <td>
                  {p.machine_count ?? machines.filter((m) => (m.pool || 'default') === p.name).length}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="maas-card">
        <div className="maas-card-head">Add pool</div>
        <div className="maas-card-body maas-form-grid">
          <label className="maas-label">
            Name
            <input className="maas-input" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="maas-label">
            Description
            <input className="maas-input" value={desc} onChange={(e) => setDesc(e.target.value)} />
          </label>
        </div>
        <div className="maas-dialog-foot">
          <button
            type="button"
            className="maas-btn maas-btn-positive"
            disabled={busy || !name}
            onClick={() => run(
              () => baremetalApi.action(sessionId, 'maas_add_pool', { name, description: desc }),
              'Pool created',
            )}
          >
            Add pool
          </button>
        </div>
      </div>
    </div>
  )
}

export function TagsPage({ state, busy, sessionId, run }) {
  const tags = state?.maas?.tags || []
  const machines = state?.maas?.machines || []
  const [tagName, setTagName] = useState('')
  const [hostname, setHostname] = useState(machines[0]?.hostname || '')
  return (
    <div>
      <h1 className="maas-page-title">Tags</h1>
      <p className="maas-page-sub">Automatic and manual tags applied to machines</p>
      <div className="maas-table-wrap" style={{ marginBottom: '1rem' }}>
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">Definition</th>
              <th className="no-sort">Machines</th>
            </tr>
          </thead>
          <tbody>
            {tags.map((t) => (
              <tr key={t.name}>
                <td><span className="maas-tag">{t.name}</span></td>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{t.definition || '—'}</td>
                <td>{(t.machines || []).join(', ') || '—'}</td>
              </tr>
            ))}
            {!tags.length && <tr><td colSpan={3}><div className="maas-empty">No tags.</div></td></tr>}
          </tbody>
        </table>
      </div>
      <div className="maas-card">
        <div className="maas-card-head">Tag a machine</div>
        <div className="maas-card-body maas-form-grid">
          <label className="maas-label">
            Machine
            <select className="maas-select" value={hostname} onChange={(e) => setHostname(e.target.value)}>
              {machines.map((m) => <option key={m.id} value={m.hostname}>{m.hostname}</option>)}
            </select>
          </label>
          <label className="maas-label">
            Tag
            <input className="maas-input" value={tagName} onChange={(e) => setTagName(e.target.value)} placeholder="gpu" />
          </label>
        </div>
        <div className="maas-dialog-foot">
          <button
            type="button"
            className="maas-btn maas-btn-positive"
            disabled={busy || !tagName || !hostname}
            onClick={() => run(
              () => baremetalApi.tagMachine(sessionId, hostname, tagName),
              'Tagged',
            )}
          >
            Apply tag
          </button>
        </div>
      </div>
    </div>
  )
}

export function SubnetsPage({ state, busy, sessionId, run }) {
  const fabrics = state?.maas?.fabrics || []
  const spaces = state?.maas?.spaces || []
  const tree = useMemo(() => {
    if (fabrics.length) {
      return fabrics.map((f) => ({
        name: f.name,
        vlans: (f.vlans || []).map((v) => {
          const vlanName = typeof v === 'string' ? v : v.name
          const subs = (typeof v === 'object' && v.subnets)
            ? v.subnets
            : spaces.flatMap((s) => (s.subnets || []).map((cidr) => ({ cidr, space: s.name, vlan: vlanName })))
              .filter((s) => !vlanName || true)
          return { name: vlanName, subnets: subs }
        }),
      }))
    }
    return [{
      name: 'fabric-0',
      vlans: [{
        name: 'untagged',
        subnets: spaces.flatMap((s) => (s.subnets || []).map((cidr) => ({
          cidr: typeof cidr === 'string' ? cidr : cidr.cidr,
          space: s.name,
        }))),
      }],
    }]
  }, [fabrics, spaces])

  return (
    <div>
      <div className="maas-toolbar">
        <div>
          <h1 className="maas-page-title">Subnets</h1>
          <p className="maas-page-sub">Fabric → VLAN → subnet topology</p>
        </div>
        <div className="maas-toolbar-spacer" />
        <button
          type="button"
          className="maas-btn"
          disabled={busy}
          onClick={() => run(
            () => baremetalApi.createSpace(sessionId, `space-${Date.now().toString(36).slice(-3)}`),
            'Space created',
          )}
        >
          <Plus size={12} /> Create space
        </button>
      </div>
      <div className="maas-subnet-tree maas-card">
        <div className="maas-card-body">
          {tree.map((fab) => (
            <div key={fab.name}>
              <div className="maas-subnet-fabric">{fab.name}</div>
              {(fab.vlans || []).map((vlan) => (
                <div key={vlan.name}>
                  <div className="maas-subnet-vlan">VLAN {vlan.name}</div>
                  {(vlan.subnets || []).map((s) => {
                    const cidr = typeof s === 'string' ? s : s.cidr
                    const space = typeof s === 'object' ? s.space : ''
                    return (
                      <div key={cidr} className="maas-subnet-cidr">
                        {cidr}{space ? ` · space ${space}` : ''}
                      </div>
                    )
                  })}
                  {!(vlan.subnets || []).length && (
                    <div className="maas-subnet-cidr" style={{ color: '#888' }}>No subnets</div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div style={{ marginTop: '1rem' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 500 }}>Spaces</h2>
        {(spaces || []).map((s) => (
          <div key={s.id || s.name} className="maas-card" style={{ marginTop: 8 }}>
            <div className="maas-card-body" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div>
                <div style={{ fontWeight: 500 }}>{s.name}</div>
                <div className="mono" style={{ fontSize: '0.75rem', color: '#666' }}>
                  {(s.subnets || []).join(', ')}
                </div>
              </div>
              <button
                type="button"
                className="maas-btn maas-btn-sm"
                disabled={busy}
                onClick={() => run(
                  () => baremetalApi.addSubnet(sessionId, s.name, `10.${40 + (s.subnets || []).length}.0.0/24`),
                  'Subnet added',
                )}
              >
                + Subnet
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function SettingsPage({ state, busy, sessionId, run }) {
  const settings = state?.settings || state?.maas?.settings || {}
  const [form, setForm] = useState({
    maas_name: settings.maas_name || 'maas',
    maas_url: settings.maas_url || 'http://region.maas:5240/MAAS',
    default_distro: settings.default_distro || 'ubuntu/jammy',
    ntp_servers: settings.ntp_servers || 'ntp.ubuntu.com',
    dns_forwarder: settings.dns_forwarder || '8.8.8.8',
    http_proxy: settings.http_proxy || settings.proxy || '',
    enable_http_proxy: settings.enable_http_proxy ?? false,
  })
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  return (
    <div>
      <h1 className="maas-page-title">Settings</h1>
      <p className="maas-page-sub">Region configuration</p>
      <div className="maas-card">
        <div className="maas-card-body maas-form-grid">
          <label className="maas-label">
            MAAS name
            <input className="maas-input" value={form.maas_name} onChange={(e) => set('maas_name', e.target.value)} />
          </label>
          <label className="maas-label">
            MAAS URL
            <input className="maas-input" value={form.maas_url} onChange={(e) => set('maas_url', e.target.value)} />
          </label>
          <label className="maas-label">
            Default distro series
            <input className="maas-input" value={form.default_distro} onChange={(e) => set('default_distro', e.target.value)} />
          </label>
          <label className="maas-label">
            NTP servers
            <input className="maas-input" value={form.ntp_servers} onChange={(e) => set('ntp_servers', e.target.value)} />
          </label>
          <label className="maas-label">
            Upstream DNS
            <input className="maas-input" value={form.dns_forwarder} onChange={(e) => set('dns_forwarder', e.target.value)} />
          </label>
          <label className="maas-label">
            HTTP proxy
            <input className="maas-input" value={form.http_proxy} onChange={(e) => set('http_proxy', e.target.value)} />
          </label>
          <label className="maas-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={!!form.enable_http_proxy}
              onChange={(e) => set('enable_http_proxy', e.target.checked)}
            />
            Enable HTTP proxy
          </label>
        </div>
        <div className="maas-dialog-foot">
          <button
            type="button"
            className="maas-btn maas-btn-positive"
            disabled={busy}
            onClick={() => run(() => baremetalApi.updateSettings(sessionId, form), 'Settings saved')}
          >
            Save configuration
          </button>
        </div>
      </div>
    </div>
  )
}

export function DhcpPage({ state, busy, sessionId, run }) {
  const dhcp = state?.dhcp || state?.maas?.dhcp || {}
  const enabled = dhcp.enabled !== false
  return (
    <div>
      <h1 className="maas-page-title">DHCP</h1>
      <p className="maas-page-sub">Dynamic host configuration for PXE and enlisted nodes</p>
      <div className="maas-card">
        <div className="maas-card-body">
          <dl className="maas-kv">
            <dt>Status</dt>
            <dd className={enabled ? 'maas-health-ok' : 'maas-health-down'}>
              {enabled ? 'Enabled' : 'Disabled'}
            </dd>
            <dt>VLAN</dt><dd>{dhcp.vlan || 'untagged'}</dd>
            <dt>Primary rack</dt><dd>{dhcp.primary_rack || 'rack-01'}</dd>
            <dt>Dynamic ranges</dt>
            <dd className="mono">
              {(dhcp.dynamic_ranges || ['10.10.1.100-10.10.1.200']).join(', ')}
            </dd>
          </dl>
          <div className="maas-toolbar" style={{ marginTop: 16 }}>
            <button
              type="button"
              className="maas-btn maas-btn-positive"
              disabled={busy}
              onClick={() => run(
                () => baremetalApi.action(sessionId, 'maas_dhcp_configure', {
                  enabled: true,
                  vlan: dhcp.vlan || 'untagged',
                }),
                'DHCP enabled',
              )}
            >
              Enable DHCP
            </button>
            <button
              type="button"
              className="maas-btn"
              disabled={busy}
              onClick={() => run(
                () => baremetalApi.action(sessionId, 'maas_dhcp_configure', { enabled: false }),
                'DHCP disabled',
              )}
            >
              Disable DHCP
            </button>
          </div>
        </div>
      </div>
      <div className="maas-card">
        <div className="maas-card-head">DHCP snippets</div>
        <div className="maas-card-body">
          {(dhcp.snippets || []).length === 0 && (
            <div className="maas-empty" style={{ padding: 0 }}>No custom snippets.</div>
          )}
          {(dhcp.snippets || []).map((s, i) => (
            <pre key={i} className="mono" style={{ fontSize: '0.75rem', background: '#f5f5f5', padding: 8 }}>
              {typeof s === 'string' ? s : s.value || JSON.stringify(s)}
            </pre>
          ))}
        </div>
      </div>
    </div>
  )
}

export function LxdPage({ state, busy, sessionId, run }) {
  const containers = state?.lxd?.containers || []
  return (
    <div>
      <h1 className="maas-page-title">LXD</h1>
      <p className="maas-page-sub">
        Instances on the shared LXD inventory — open the LXD console for full management
      </p>
      <div className="maas-table-wrap">
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Name</th>
              <th className="no-sort">Status</th>
              <th className="no-sort">Type</th>
              <th className="no-sort">Image</th>
              <th className="no-sort">IPv4</th>
              <th className="no-sort">Snapshots</th>
              <th className="no-sort" />
            </tr>
          </thead>
          <tbody>
            {containers.map((c) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td><MaasStatusBadge status={c.status === 'Running' ? 'Deployed' : 'New'} /></td>
                <td>{c.type || 'container'}</td>
                <td className="mono">{c.image}</td>
                <td className="mono">{c.ipv4 || '—'}</td>
                <td>{(c.snapshots || []).length}</td>
                <td>
                  {c.status === 'Running' ? (
                    <button
                      type="button"
                      className="maas-btn maas-btn-sm"
                      disabled={busy}
                      onClick={() => run(() => baremetalApi.action(sessionId, 'lxd_stop', { name: c.name }), 'Stopped')}
                    >
                      <Square size={12} /> Stop
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="maas-btn maas-btn-sm maas-btn-positive"
                      disabled={busy}
                      onClick={() => run(() => baremetalApi.startLxd(sessionId, c.name), 'Started')}
                    >
                      <Play size={12} /> Start
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!containers.length && <tr><td colSpan={7}><div className="maas-empty">No LXD instances.</div></td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function IpmiPage({ state, busy, sessionId, run, machines = [] }) {
  const hosts = state?.ipmi?.bmc_hosts || []
  const broken = state?.broken || {}
  return (
    <div>
      <h1 className="maas-page-title">IPMI / BMC</h1>
      <p className="maas-page-sub">Out-of-band power control for enlisted hardware</p>
      <div className="maas-table-wrap" style={{ marginBottom: '1rem' }}>
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort">Host</th>
              <th className="no-sort">Reachable</th>
              <th className="no-sort">Chassis</th>
              <th className="no-sort">Actions</th>
            </tr>
          </thead>
          <tbody>
            {hosts.map((b) => {
              const mach = machines.find((m) => m.hostname === b.name)
              const mid = mach?.id
              return (
                <tr key={b.name}>
                  <td className="mono">{b.name}</td>
                  <td className={b.reachable ? 'maas-health-ok' : 'maas-health-down'}>
                    {b.reachable ? 'reachable' : 'unreachable'}
                  </td>
                  <td><PowerIcon power={mach?.power ?? b.power} /></td>
                  <td>
                    {mid != null && b.reachable && (
                      <div className="maas-toolbar" style={{ margin: 0 }}>
                        <button type="button" className="maas-btn maas-btn-sm" disabled={busy}
                          onClick={() => run(() => baremetalApi.action(sessionId, 'ipmi_power', { machine_id: mid, verb: 'on' }), 'Power on')}>
                          <Power size={12} /> On
                        </button>
                        <button type="button" className="maas-btn maas-btn-sm" disabled={busy}
                          onClick={() => run(() => baremetalApi.action(sessionId, 'ipmi_power', { machine_id: mid, verb: 'off' }), 'Power off')}>
                          Off
                        </button>
                        <button type="button" className="maas-btn maas-btn-sm" disabled={busy}
                          onClick={() => run(() => baremetalApi.action(sessionId, 'ipmi_power', { machine_id: mid, verb: 'cycle' }), 'Power cycle')}>
                          <RefreshCw size={12} /> Cycle
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
            {!hosts.length && <tr><td colSpan={4}><div className="maas-empty">No BMC hosts.</div></td></tr>}
          </tbody>
        </table>
      </div>
      <div className="maas-toolbar">
        {broken.bmc_unreachable && (
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy}
            onClick={() => run(() => baremetalApi.ipmiPowerOn(sessionId), 'BMC online')}>
            Restore BMC connectivity
          </button>
        )}
        {broken.pxe_vlan_wrong && (
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy}
            onClick={() => run(() => baremetalApi.fixPxeVlan(sessionId), 'PXE fixed')}>
            Fix PXE VLAN
          </button>
        )}
        {broken.thermal_alert && (
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy}
            onClick={() => run(() => baremetalApi.clearThermal(sessionId), 'Thermal cleared')}>
            Clear thermal alert
          </button>
        )}
        {broken.commission_stuck && (
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy}
            onClick={() => run(() => baremetalApi.resetCommission(sessionId, broken.commission_stuck), 'Commission reset')}>
            Reset stuck commission
          </button>
        )}
      </div>
    </div>
  )
}

export default function MaasNavPages({ page, state, busy, sessionId, run, machines }) {
  switch (page) {
    case 'devices':
      return <DevicesPage state={state} busy={busy} run={run} />
    case 'controllers':
      return <ControllersPage state={state} />
    case 'kvm':
      return <KvmPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'images':
      return <ImagesPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'domains':
      return <DomainsPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'zones':
      return <ZonesPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'pools':
      return <PoolsPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'tags':
      return <TagsPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'subnets':
      return <SubnetsPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'settings':
      return <SettingsPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'dhcp':
      return <DhcpPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'lxd':
      return <LxdPage state={state} busy={busy} sessionId={sessionId} run={run} />
    case 'ipmi':
      return <IpmiPage state={state} busy={busy} sessionId={sessionId} run={run} machines={machines} />
    default:
      return <div className="maas-empty">Unknown section.</div>
  }
}
