import { useState } from 'react'
import { ChevronLeft, Power, Rocket, LifeBuoy } from 'lucide-react'
import { MaasStatusBadge, PowerIcon, TRANSIENT_STATUSES } from './MaasStatusBadge'

const TABS = [
  'Summary',
  'Network',
  'Storage',
  'PCI',
  'USB',
  'Commissioning',
  'Tests',
  'Events',
  'Logs',
  'Configuration',
]

const LAYOUTS = [
  { id: 'flat', label: 'Flat' },
  { id: 'lvm', label: 'LVM' },
  { id: 'raid10', label: 'RAID 10' },
  { id: 'bcache', label: 'Bcache' },
]

function bannerClass(status) {
  if (status === 'Rescue mode' || status === 'Entering rescue mode' || status === 'Exiting rescue mode') return 'maas-banner-rescue'
  if (TRANSIENT_STATUSES.has(status)) return 'maas-banner-transient'
  if (status === 'Ready' || status === 'Deployed') return 'maas-banner-ready'
  if (status === 'Failed' || status === 'Broken' || (status || '').startsWith('Failed')) return 'maas-banner-failed'
  return 'maas-banner-neutral'
}

function primaryAction(status) {
  if (status === 'New' || status === 'Failed' || status === 'Failed commissioning') return 'commission'
  if (status === 'Ready' || status === 'Allocated') return 'deploy'
  if (status === 'Deployed') return 'release'
  if (status === 'Rescue mode') return 'exitRescue'
  if (TRANSIENT_STATUSES.has(status)) return 'abort'
  if (status === 'Broken') return 'markFixed'
  if (status === 'Failed testing') return 'override'
  return null
}

export default function MachineDetail({
  machine,
  busy,
  bootResources = [],
  deployImage = '',
  onDeployImageChange,
  onBack,
  onAction,
}) {
  const [tab, setTab] = useState('Summary')
  const [layout, setLayout] = useState(machine?.storage_layout || 'flat')
  const [eraseOnRelease, setEraseOnRelease] = useState(false)
  const m = machine || {}
  const fqdn = m.fqdn || `${m.hostname || 'node'}.${m.domain || 'maas'}`
  const action = primaryAction(m.status)
  const ifaces = m.interfaces || m.network_interfaces || []
  const events = [...(m.events || [])].reverse()
  const logs = [...(m.log || [])].reverse()
  const siteEvents = []

  const run = (name, extra) => onAction?.(name, extra)

  return (
    <div>
      <div className="maas-toolbar">
        <button type="button" className="maas-btn" onClick={onBack}>
          <ChevronLeft size={14} /> Machines
        </button>
        <h1 className="maas-page-title" style={{ margin: 0 }}>{fqdn}</h1>
        <MaasStatusBadge status={m.status} />
        {m.locked && <span className="maas-badge maas-badge-allocated">Locked</span>}
        <div className="maas-toolbar-spacer" />
        {(m.status === 'Ready' || m.status === 'Allocated') && (
          <label className="maas-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            Image
            <select
              className="maas-select"
              value={deployImage}
              onChange={(e) => onDeployImageChange?.(e.target.value)}
            >
              {bootResources.map((r) => (
                <option key={r.name} value={r.name}>{r.name}</option>
              ))}
              {!bootResources.length && <option value="">ubuntu/jammy</option>}
            </select>
          </label>
        )}
        {m.status === 'Deployed' && (
          <button
            type="button"
            className="maas-btn"
            disabled={busy}
            onClick={() => run('enterRescue')}
            title="Boot into an ephemeral rescue environment without releasing the machine"
          >
            <LifeBuoy size={13} /> Enter rescue mode
          </button>
        )}
        <button
          type="button"
          className="maas-btn"
          disabled={busy}
          onClick={() => run('power', { power: m.power === 'on' ? 'off' : 'on' })}
        >
          <Power size={13} /> Power {m.power === 'on' ? 'off' : 'on'}
        </button>
      </div>

      <div className={`maas-banner ${bannerClass(m.status)}`}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 500 }}>{m.status}</div>
          <div style={{ fontSize: '0.8rem', color: '#555' }}>
            {m.arch || 'amd64/generic'} · {m.cpu_count ?? '—'} cores · {m.ram_gb ?? '—'} GiB ·{' '}
            <PowerIcon power={m.power} />
            {m.os ? ` · ${m.os}` : ''}
            {m.boot_resource ? ` · ${m.boot_resource}` : ''}
          </div>
          {TRANSIENT_STATUSES.has(m.status) && (
            <div className="maas-progress">
              <div className="maas-progress-track">
                <div className="maas-progress-fill" style={{ width: `${Math.max(0, Math.min(100, Number(m.progress) || 0))}%` }} />
              </div>
            </div>
          )}
        </div>
        {action === 'commission' && (
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={() => run('commission')}>
            Commission
          </button>
        )}
        {action === 'deploy' && (
          <button type="button" className="maas-btn maas-btn-brand" disabled={busy} onClick={() => run('deploy')}>
            <Rocket size={13} /> Deploy
          </button>
        )}
        {action === 'release' && (
          <button type="button" className="maas-btn" disabled={busy} onClick={() => run('release')}>Release</button>
        )}
        {action === 'exitRescue' && (
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={() => run('exitRescue')}>
            <LifeBuoy size={13} /> Exit rescue mode
          </button>
        )}
        {action === 'abort' && (
          <button type="button" className="maas-btn maas-btn-negative" disabled={busy} onClick={() => run('abort')}>Abort</button>
        )}
        {action === 'markFixed' && (
          <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={() => run('markFixed')}>Mark fixed</button>
        )}
        {action === 'override' && (
          <button type="button" className="maas-btn" disabled={busy} onClick={() => run('overrideFailedTesting')}>
            Override failed testing
          </button>
        )}
      </div>

      <div className="maas-tabs">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={`maas-tab ${tab === t ? 'is-active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'Summary' && (
        <div className="maas-card">
          <div className="maas-card-head">Hardware summary</div>
          <div className="maas-card-body">
            <dl className="maas-kv">
              <dt>FQDN</dt><dd className="mono">{fqdn}</dd>
              <dt>Status</dt><dd><MaasStatusBadge status={m.status} /></dd>
              <dt>Owner</dt><dd>{m.owner || '—'}</dd>
              <dt>Pool</dt><dd>{m.pool || 'default'}</dd>
              <dt>Zone</dt><dd>{m.zone || 'default'}</dd>
              <dt>Domain</dt><dd>{m.domain || 'maas'}</dd>
              <dt>Architecture</dt><dd>{m.arch || 'amd64/generic'}</dd>
              <dt>CPU</dt><dd>{m.cpu_count ?? '—'} cores</dd>
              <dt>Memory</dt><dd>{m.ram_gb != null ? `${m.ram_gb} GiB` : '—'}</dd>
              <dt>Storage</dt><dd>{m.storage_gb != null ? `${m.storage_gb} GB` : `${(m.storage || []).reduce((s, d) => s + (d.size_gb || 0), 0)} GB`} ({m.disk_count ?? (m.storage || []).length} disks)</dd>
              <dt>Power type</dt><dd>{m.power_type || 'ipmi'}</dd>
              <dt>Power</dt><dd><PowerIcon power={m.power} /></dd>
              <dt>Fabric</dt><dd>{m.fabric || 'fabric-0'}</dd>
              <dt>Tags</dt>
              <dd>
                <div className="maas-tags">
                  {(m.tags || []).map((t) => <span key={t} className="maas-tag">{t}</span>)}
                  {!(m.tags || []).length && '—'}
                </div>
              </dd>
              <dt>IP</dt><dd className="mono">{m.ip || '—'}</dd>
            </dl>
          </div>
        </div>
      )}

      {tab === 'Network' && (
        <div className="maas-card">
          <div className="maas-card-head" style={{ display: 'flex', alignItems: 'center' }}>
            <span>Network interfaces</span>
            <div className="maas-toolbar-spacer" />
            <button
              type="button"
              className="maas-btn maas-btn-sm"
              disabled={busy || ifaces.filter((i) => (i.name || '').startsWith('eth')).length < 2}
              onClick={() => run('createBond', {
                interfaces: ifaces.filter((i) => (i.name || '').startsWith('eth')).slice(0, 2).map((i) => i.name),
                name: 'bond0',
              })}
            >
              Create bond
            </button>
          </div>
          <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
            <table className="maas-table">
              <thead>
                <tr>
                  <th className="no-sort">Name</th>
                  <th className="no-sort">MAC</th>
                  <th className="no-sort">Link</th>
                  <th className="no-sort">Fabric / VLAN</th>
                  <th className="no-sort">Subnet</th>
                  <th className="no-sort">IP mode</th>
                  <th className="no-sort">Speed</th>
                  <th className="no-sort">Boot</th>
                  <th className="no-sort" />
                </tr>
              </thead>
              <tbody>
                {ifaces.map((iface) => (
                  <tr key={iface.name || iface.mac}>
                    <td className="mono">
                      {iface.name}
                      {(iface.bond_members || []).length > 0 && (
                        <span style={{ color: '#666', fontSize: '0.75rem' }}>
                          {' '}({(iface.bond_members || []).join('+')})
                        </span>
                      )}
                      {iface.bond && !iface.bond_members && (
                        <span style={{ color: '#666', fontSize: '0.75rem' }}> → {iface.bond}</span>
                      )}
                    </td>
                    <td className="mono">{iface.mac}</td>
                    <td>{iface.link || '—'}</td>
                    <td>{iface.fabric || m.fabric || 'fabric-0'} / {iface.vlan || '—'}</td>
                    <td className="mono">{iface.subnet || '—'}</td>
                    <td>{iface.ip_mode || 'auto'}</td>
                    <td>{iface.link_speed ? `${iface.link_speed} Mb/s` : '—'}</td>
                    <td>{iface.boot || iface.is_boot ? 'Yes' : ''}</td>
                    <td>
                      <button
                        type="button"
                        className="maas-btn maas-btn-sm"
                        disabled={busy}
                        onClick={() => run('setBootInterface', { iface: iface.name })}
                      >
                        Set boot
                      </button>
                    </td>
                  </tr>
                ))}
                {!ifaces.length && (
                  <tr><td colSpan={9}><div className="maas-empty">No interfaces discovered.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'Storage' && (
        <div className="maas-card">
          <div className="maas-card-head" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span>Storage</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#666' }}>
              Layout: {m.storage_layout || layout || 'flat'}
            </span>
            <div className="maas-toolbar-spacer" />
            <select className="maas-select" value={layout} onChange={(e) => setLayout(e.target.value)}>
              {LAYOUTS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
            </select>
            <button
              type="button"
              className="maas-btn maas-btn-sm maas-btn-positive"
              disabled={busy}
              onClick={() => run('applyStorageLayout', { layout })}
            >
              Apply layout
            </button>
          </div>
          <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
            <table className="maas-table">
              <thead>
                <tr>
                  <th className="no-sort">Name</th>
                  <th className="no-sort">Size</th>
                  <th className="no-sort">Type</th>
                  <th className="no-sort">Role</th>
                </tr>
              </thead>
              <tbody>
                {(m.storage || []).map((d) => (
                  <tr key={d.name}>
                    <td className="mono">{d.name}</td>
                    <td>{d.size_gb} GB</td>
                    <td>{d.type}</td>
                    <td>{d.role || d.tags?.join(', ') || '—'}</td>
                  </tr>
                ))}
                {!(m.storage || []).length && (
                  <tr><td colSpan={4}><div className="maas-empty">No storage discovered.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'PCI' && (
        <div className="maas-card">
          <div className="maas-card-head">PCI devices</div>
          <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
            <table className="maas-table">
              <thead>
                <tr>
                  <th className="no-sort">Slot</th>
                  <th className="no-sort">Vendor</th>
                  <th className="no-sort">Product</th>
                  <th className="no-sort">Type</th>
                </tr>
              </thead>
              <tbody>
                {(m.pci_devices || []).map((d, i) => (
                  <tr key={`${d.slot}-${i}`}>
                    <td className="mono">{d.slot}</td>
                    <td>{d.vendor}</td>
                    <td>{d.product}</td>
                    <td>{d.type}</td>
                  </tr>
                ))}
                {!(m.pci_devices || []).length && (
                  <tr>
                    <td colSpan={4}>
                      <div className="maas-empty">
                        No PCI inventory yet — commission the machine to discover GPUs and NICs.
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'USB' && (
        <div className="maas-card">
          <div className="maas-card-head">USB devices</div>
          <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
            <table className="maas-table">
              <thead>
                <tr>
                  <th className="no-sort">Bus</th>
                  <th className="no-sort">Device</th>
                  <th className="no-sort">Vendor</th>
                  <th className="no-sort">Product</th>
                  <th className="no-sort">IDs</th>
                </tr>
              </thead>
              <tbody>
                {(m.usb_devices || []).map((d, i) => (
                  <tr key={`${d.bus}-${d.device}-${i}`}>
                    <td className="mono">{d.bus}</td>
                    <td className="mono">{d.device}</td>
                    <td>{d.vendor}</td>
                    <td>{d.product}</td>
                    <td className="mono">{d.vendor_id}:{d.product_id}</td>
                  </tr>
                ))}
                {!(m.usb_devices || []).length && (
                  <tr>
                    <td colSpan={5}>
                      <div className="maas-empty">
                        No USB inventory yet — commission the machine to discover attached devices.
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'Commissioning' && (
        <div className="maas-card">
          <div className="maas-card-head">Commissioning results</div>
          <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
            <table className="maas-table">
              <thead>
                <tr>
                  <th className="no-sort">Script</th>
                  <th className="no-sort">Status</th>
                  <th className="no-sort">Runtime</th>
                </tr>
              </thead>
              <tbody>
                {(m.commissioning_results || []).map((r) => (
                  <tr key={r.name}>
                    <td className="mono">{r.name}</td>
                    <td><MaasStatusBadge status={r.status} /></td>
                    <td>{r.runtime != null ? `${r.runtime}s` : '—'}</td>
                  </tr>
                ))}
                {!(m.commissioning_results || []).length && (
                  <tr><td colSpan={3}><div className="maas-empty">No commissioning results.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'Tests' && (
        <div className="maas-card">
          <div className="maas-card-head" style={{ display: 'flex', alignItems: 'center' }}>
            <span>Hardware tests</span>
            <div className="maas-toolbar-spacer" />
            <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => run('test')}>
              Test hardware
            </button>
          </div>
          <div className="maas-table-wrap" style={{ maxHeight: 'none', border: 'none' }}>
            <table className="maas-table">
              <thead>
                <tr>
                  <th className="no-sort">Test</th>
                  <th className="no-sort">Status</th>
                </tr>
              </thead>
              <tbody>
                {(m.test_results || []).map((r) => (
                  <tr key={r.name}>
                    <td className="mono">{r.name}</td>
                    <td><MaasStatusBadge status={r.status} /></td>
                  </tr>
                ))}
                {!(m.test_results || []).length && (
                  <tr><td colSpan={2}><div className="maas-empty">No test results yet.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'Events' && (
        <div className="maas-card">
          <div className="maas-card-head">Events</div>
          <div className="maas-log">
            {events.length === 0 && siteEvents.length === 0 && (
              <div style={{ color: '#888' }}>No events recorded.</div>
            )}
            {events.map((e, i) => (
              <div key={`${e.time}-${i}`}>
                <span className="maas-log-time">{e.time || e.created}</span>
                {e.message || e.description || JSON.stringify(e)}
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'Logs' && (
        <div className="maas-card">
          <div className="maas-card-head">Installation / commissioning log</div>
          <div className="maas-log">
            {logs.length === 0 && <div style={{ color: '#888' }}>No log output yet.</div>}
            {logs.map((e, i) => (
              <div key={`${e.time}-${i}`}>
                <span className="maas-log-time">{e.time}</span>
                {e.message}
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'Configuration' && (
        <div className="maas-card">
          <div className="maas-card-head">Configuration</div>
          <div className="maas-card-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <dl className="maas-kv">
              <dt>Power type</dt><dd>{m.power_type || 'ipmi'}</dd>
              <dt>BMC address</dt><dd className="mono">{m.bmc_address || '—'}</dd>
              <dt>BMC user</dt><dd className="mono">{m.bmc_user || '—'}</dd>
              <dt>Locked</dt><dd>{m.locked ? 'Yes' : 'No'}</dd>
            </dl>
            <div className="maas-toolbar">
              {m.locked ? (
                <button type="button" className="maas-btn" disabled={busy} onClick={() => run('unlock')}>Unlock</button>
              ) : (
                <button type="button" className="maas-btn" disabled={busy} onClick={() => run('lock')}>Lock</button>
              )}
              {(m.status === 'Deployed' || m.status === 'Allocated') && (
                <label className="maas-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <input
                    type="checkbox"
                    checked={eraseOnRelease}
                    onChange={(e) => setEraseOnRelease(e.target.checked)}
                  />
                  Erase disks on release
                </label>
              )}
              {(m.status === 'Deployed' || m.status === 'Allocated') && (
                <button
                  type="button"
                  className="maas-btn"
                  disabled={busy}
                  onClick={() => run('release', { erase: eraseOnRelease })}
                >
                  Release{eraseOnRelease ? ' & erase' : ''}
                </button>
              )}
              {m.status !== 'Broken' && (
                <button type="button" className="maas-btn" disabled={busy} onClick={() => run('markBroken')}>Mark broken</button>
              )}
              {m.status === 'Broken' && (
                <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={() => run('markFixed')}>Mark fixed</button>
              )}
              <button type="button" className="maas-btn maas-btn-negative" disabled={busy} onClick={() => run('delete')}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {tab === 'Configuration' && (
        <div className={`maas-card ${bannerClass(m.status) === 'maas-banner-rescue' ? 'maas-card-rescue' : ''}`}>
          <div className="maas-card-head">Rescue mode</div>
          <div className="maas-card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#555' }}>
              Rescue mode boots an ephemeral in-memory environment over SSH so you can repair a
              deployed machine without releasing it or losing its disks.
            </p>
            {(m.status === 'Entering rescue mode' || m.status === 'Exiting rescue mode') && (
              <div className="maas-banner maas-banner-rescue" style={{ margin: 0 }}>
                <span className="maas-spinner" aria-hidden /> {m.status}…
              </div>
            )}
            <div className="maas-toolbar" style={{ margin: 0 }}>
              {m.status === 'Deployed' && (
                <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={() => run('enterRescue')}>
                  <LifeBuoy size={13} /> Enter rescue mode
                </button>
              )}
              {m.status === 'Rescue mode' && (
                <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={() => run('exitRescue')}>
                  <LifeBuoy size={13} /> Exit rescue mode
                </button>
              )}
              {m.status !== 'Deployed' && m.status !== 'Rescue mode'
                && m.status !== 'Entering rescue mode' && m.status !== 'Exiting rescue mode' && (
                <span style={{ fontSize: '0.8rem', color: '#888' }}>
                  Only available once the machine is Deployed.
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
