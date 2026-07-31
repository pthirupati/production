import { useState } from 'react'
import {
  CircuitBoard, Cpu, HardDrive, MonitorCog, Shield, Zap, RefreshCw, Disc,
} from 'lucide-react'
import { BusAnimPanel } from './OpsPhysicsPanels'

/** Interactive motherboard map — component pickers + bus util bars */
export function MotherboardPanel({
  motherboard, busy, onToggleCover, onReplaceDimm, onApplyPaste, onMbOp,
}) {
  const [selected, setSelected] = useState(null)
  if (!motherboard) return <p className="dc-muted">No motherboard data.</p>
  const sel = selected && (
    motherboard.cpu_sockets?.find((c) => c.id === selected)
    || motherboard.dimm_slots?.find((d) => d.id === selected)
    || motherboard.pcie_slots?.find((p) => p.id === selected)
    || motherboard.storage_connectors?.find((s) => s.id === selected)
    || motherboard.chips?.find((c) => c.id === selected)
  )
  const coverOpen = !!motherboard.cover_open

  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><CircuitBoard size={13} /> {motherboard.model}</span>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={onToggleCover}>
          {coverOpen ? 'Close cover' : 'Open cover / service mode'}
        </button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => onMbOp?.('pulse_buses')}>Pulse buses</button>
      </div>
      {motherboard.maintenance_mode && (
        <div className="dc-objective-note">Maintenance mode — cover open. Remove/install CPU, reseat DIMMs, PCIe FRUs, reapply paste, then close cover.</div>
      )}
      {motherboard.vrm && (
        <div className="dc-muted">VRM: {motherboard.vrm.phases_per_socket}-phase · {motherboard.vrm.controller} · {motherboard.vrm.mosfets_per_phase} MOSFET/phase</div>
      )}
      <div className="dc-mb-canvas">
        <div className="dc-mb-zone">
          <div className="dc-mb-zone-label">CPU / VRM</div>
          {(motherboard.cpu_sockets || []).map((c) => (
            <button key={c.id} type="button"
              className={`dc-mb-chip ${selected === c.id ? 'dc-mb-chip-sel' : ''} ${c.status !== 'healthy' ? 'dc-mb-chip-bad' : ''}`}
              onClick={() => setSelected(c.id)}>
              <Cpu size={12} /> {c.id}<br /><span>{c.populated ? c.die : 'empty'}</span>
            </button>
          ))}
        </div>
        <div className="dc-mb-zone">
          <div className="dc-mb-zone-label">DIMM</div>
          <div className="dc-mb-dimm-grid">
            {(motherboard.dimm_slots || []).map((d) => (
              <button key={d.id} type="button"
                className={`dc-mb-dimm ${selected === d.id ? 'dc-mb-chip-sel' : ''} ${d.status !== 'healthy' ? 'dc-mb-chip-bad' : ''}`}
                onClick={() => setSelected(d.id)} title={d.module}>
                {d.id}
              </button>
            ))}
          </div>
        </div>
        <div className="dc-mb-zone">
          <div className="dc-mb-zone-label">PCIe</div>
          {(motherboard.pcie_slots || []).map((p) => (
            <button key={p.id} type="button"
              className={`dc-mb-chip ${selected === p.id ? 'dc-mb-chip-sel' : ''}`}
              onClick={() => setSelected(p.id)}>
              {p.id} Gen{p.gen} x{p.lanes} · {p.device || 'empty'}
            </button>
          ))}
        </div>
        <div className="dc-mb-zone">
          <div className="dc-mb-zone-label">Storage connectors</div>
          {(motherboard.storage_connectors || []).map((s) => (
            <button key={s.id} type="button"
              className={`dc-mb-chip ${selected === s.id ? 'dc-mb-chip-sel' : ''}`}
              onClick={() => setSelected(s.id)}>
              {s.id}: {s.type} · {s.status}
            </button>
          ))}
        </div>
        <div className="dc-mb-zone">
          <div className="dc-mb-zone-label">BMC / BIOS / TPM</div>
          {(motherboard.chips || []).map((c) => (
            <button key={c.id} type="button"
              className={`dc-mb-chip ${selected === c.id ? 'dc-mb-chip-sel' : ''}`}
              onClick={() => setSelected(c.id)}>
              {c.id}: {c.model}
            </button>
          ))}
        </div>
      </div>
      <div className="dc-bus-bars">
        <BusAnimPanel buses={motherboard.buses} />
      </div>
      {sel && (
        <div className="dc-mb-detail">
          <strong>{sel.id || sel.model}</strong>
          <pre className="dc-mb-json">{JSON.stringify(sel, null, 2)}</pre>
          <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
            {sel.module && (
              <>
                <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs"
                  onClick={() => onReplaceDimm?.(sel.id)}>Replace DIMM</button>
                <button type="button" disabled={busy || !coverOpen} className="dc-btn-outline dc-btn-xs"
                  onClick={() => onMbOp?.('reseat_dimm', { slot_id: sel.id })}>
                  {sel.clips_locked === false ? 'Seat / lock clips' : 'Unseat clips'}
                </button>
              </>
            )}
            {sel.die !== undefined && (
              <>
                <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                  onClick={() => onApplyPaste?.(sel.id)}>Reapply thermal paste</button>
                {sel.populated ? (
                  <button type="button" disabled={busy || !coverOpen} className="dc-btn-danger dc-btn-xs"
                    onClick={() => onMbOp?.('remove_cpu', { socket_id: sel.id })}>Remove CPU</button>
                ) : (
                  <button type="button" disabled={busy || !coverOpen} className="dc-btn-primary dc-btn-xs"
                    onClick={() => onMbOp?.('install_cpu', { socket_id: sel.id })}>Install CPU</button>
                )}
                <button type="button" disabled={busy || !coverOpen} className="dc-btn-outline dc-btn-xs"
                  onClick={() => onMbOp?.(sel.heatsink ? 'remove_heatsink' : 'install_heatsink', { socket_id: sel.id })}>
                  {sel.heatsink ? 'Remove heatsink' : 'Install heatsink'}
                </button>
              </>
            )}
            {sel.lanes !== undefined && (
              sel.device ? (
                <button type="button" disabled={busy || !coverOpen} className="dc-btn-danger dc-btn-xs"
                  onClick={() => onMbOp?.('remove_pcie', { slot_id: sel.id })}>Remove PCIe card</button>
              ) : (
                <button type="button" disabled={busy || !coverOpen} className="dc-btn-primary dc-btn-xs"
                  onClick={() => onMbOp?.('install_pcie', { slot_id: sel.id, device: 'ConnectX-7 100GbE' })}>
                  Install NIC
                </button>
              )
            )}
          </div>
          {!coverOpen && (sel.die !== undefined || sel.lanes !== undefined || sel.module) && (
            <p className="dc-muted mt-1">Open cover to enable FRU remove/install.</p>
          )}
        </div>
      )}
    </div>
  )
}

/** PERC / Smart Array style RAID manager */
export function RaidPanel({
  raid, busy, onFailDisk, onRebuild, onSetCache, onCreateVd, onDeleteVd,
  onPatrol, onConsistency, onImportForeign, onAssignHotspare, onExpandVd, onInitializeVd,
}) {
  const [level, setLevel] = useState('RAID1')
  const [name, setName] = useState('NEWVD')
  if (!raid) return <p className="dc-muted">No RAID controller.</p>
  const levels = raid.supported_levels || ['RAID0', 'RAID1', 'RAID5', 'RAID6', 'RAID10', 'RAID50', 'RAID60']
  const vdMembers = new Set((raid.virtual_disks || []).flatMap((vd) => vd.members || []))
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><HardDrive size={13} /> {raid.controller}</span>
        <span className="dc-muted">FW {raid.firmware}</span>
      </div>
      <div className="dc-raid-cache">
        Cache: <strong>{raid.cache?.mode}</strong> · BBU {raid.cache?.bbu} ({raid.cache?.bbu_charge_pct}%)
        <div className="dc-action-row mt-1">
          {['WriteBack', 'WriteThrough'].map((m) => (
            <button key={m} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
              onClick={() => onSetCache?.(m)}>{m}</button>
          ))}
        </div>
      </div>
      <div className="dc-drawer-label">Physical disks</div>
      <table className="dc-port-table">
        <thead><tr><th>ID</th><th>Bay</th><th>Model</th><th>Size</th><th>Status</th><th>SMART</th><th /></tr></thead>
        <tbody>
          {(raid.physical_disks || []).map((d) => (
            <tr key={d.id}>
              <td>{d.id}</td><td>{d.bay}</td><td>{d.model}</td>
              <td>{d.size_gb}G</td>
              <td><span className={`dc-port-badge ${d.status === 'online' || d.status === 'hotspare' ? 'dc-port-up' : 'dc-port-down'}`}>{d.status}</span></td>
              <td>{d.smart} · {d.temp_c}°C · wear {d.wear_pct}%</td>
              <td>
                <div className="dc-action-row">
                  {d.status !== 'failed' && (
                    <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs"
                      onClick={() => onFailDisk?.(d.id)}>Fail</button>
                  )}
                  {d.status === 'online' && !vdMembers.has(d.id) && (
                    <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                      onClick={() => onAssignHotspare?.(d.id)}>Hot spare</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="dc-drawer-label mt-2">Virtual disks</div>
      {(raid.virtual_disks || []).map((vd) => (
        <div key={vd.id} className="dc-vd-card">
          <div className="dc-vd-head">
            <strong>{vd.id} · {vd.name}</strong>
            <span>{vd.raid_level} · {vd.size_gb} GB · {vd.status}</span>
          </div>
          <div className="dc-muted">Members: {(vd.members || []).join(', ')} · {vd.write_policy}
            {vd.init_pct != null ? ` · init ${vd.init_pct}% (${vd.init_mode || 'fast'})` : ''}
          </div>
          <div className="dc-action-row mt-1" style={{ flexWrap: 'wrap' }}>
            {vd.status === 'degraded' && (
              <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs"
                onClick={() => onRebuild?.(vd.id)}><RefreshCw size={11} /> Rebuild / promote hotspare</button>
            )}
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
              onClick={() => onExpandVd?.(vd.id, 500)}>Expand +500G</button>
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
              onClick={() => onInitializeVd?.(vd.id, 'fast')}>Initialize (fast)</button>
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
              onClick={() => onInitializeVd?.(vd.id, 'full')}>Initialize (full)</button>
            <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs"
              onClick={() => onDeleteVd?.(vd.id)}>Delete VD</button>
          </div>
        </div>
      ))}
      <div className="dc-drawer-label mt-2">Controller ops</div>
      <div className="dc-action-row">
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onPatrol?.()}>
          Patrol Read {raid.patrol_read?.status === 'completed' ? '✓' : ''}
        </button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onConsistency?.()}>
          Consistency Check {raid.consistency_check?.status === 'completed' ? '✓' : ''}
        </button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onImportForeign?.()}>
          Import Foreign Config
        </button>
      </div>
      <div className="dc-drawer-label mt-2">Create virtual disk</div>
      <div className="dc-action-row">
        <input className="dc-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
        <select className="dc-input" value={level} onChange={(e) => setLevel(e.target.value)}>
          {levels.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => onCreateVd?.({ name, raid_level: level, members: ['PD0', 'PD1'], size_gb: 1920 })}>
          Create VD
        </button>
      </div>
    </div>
  )
}

/** BIOS / UEFI setup screen */
export function BiosPanel({ bios, busy, onEnter, onExit, onSet, onCmosReset, onPost, onFlash, onSetPassword }) {
  if (!bios) return <p className="dc-muted">No BIOS data.</p>
  if (!bios.setup_open) {
    return (
      <div className="dc-twin-panel">
        <div className="dc-twin-title"><MonitorCog size={13} /> UEFI {bios.version} · {bios.mode}</div>
        <p className="dc-muted">Secure Boot {bios.secure_boot ? 'On' : 'Off'} · TPM {bios.tpm} · Password {bios.password_set ? 'Set' : 'None'}</p>
        <p className="dc-muted">POST: {bios.post_state}</p>
        {(bios.post_log || []).length > 0 && (
          <div className="dc-bios-screen" style={{ marginBottom: '0.5rem' }}>
            {bios.post_log.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        )}
        <div className="dc-action-row">
          <button type="button" disabled={busy} className="dc-btn-primary" onClick={onEnter}>Enter Setup (F2)</button>
          <button type="button" disabled={busy} className="dc-btn-outline" onClick={onPost}>Run POST</button>
          <button type="button" disabled={busy} className="dc-btn-outline" onClick={() => onFlash?.('2.14.0')}>Flash BIOS 2.14.0</button>
          <button type="button" disabled={busy} className="dc-btn-outline" onClick={onCmosReset}>CMOS Reset</button>
          <button type="button" disabled={busy} className="dc-btn-outline" onClick={() => onSetPassword?.('lab')}>Set password</button>
        </div>
      </div>
    )
  }
  return (
    <div className="dc-bios-screen">
      <div className="dc-bios-bar">System Setup — {bios.vendor} UEFI {bios.version}
        <button type="button" className="dc-btn-outline dc-btn-xs" onClick={onExit} disabled={busy}>Exit</button>
      </div>
      <div className="dc-bios-grid">
        <div>
          <div className="dc-drawer-label">Boot Order</div>
          <ol className="dc-bios-boot">
            {(bios.boot_order || []).map((b) => <li key={b}>{b}</li>)}
          </ol>
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => {
              const o = [...(bios.boot_order || [])]
              if (o.length > 1) { const x = o.shift(); o.push(x); onSet?.('boot_order', o) }
            }}>Rotate boot order</button>
        </div>
        <div>
          <div className="dc-drawer-label">Settings</div>
          {Object.entries(bios.settings || {}).map(([k, v]) => (
            <div key={k} className="dc-bios-row">
              <span>{k}</span>
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                onClick={() => onSet?.(k, v === 'Enabled' ? 'Disabled' : (v === 'Disabled' ? 'Enabled' : v))}>
                {String(v)}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/** iDRAC / iLO / IPMI web UI — requires login before management controls. */
export function BmcPanel({
  bmc, vendor, busy, onPower, onMountIso, onDiag, onUpdateNet, onNmi, onFlash, onKvm, onSetGeneration,
  onLogin, onLogout,
}) {
  const [iso, setIso] = useState('rhel-9.4-x86_64-dvd.iso')
  const [user, setUser] = useState('root')
  const [pass, setPass] = useState('')
  const [loginErr, setLoginErr] = useState('')
  if (!bmc) return <p className="dc-muted">No BMC.</p>
  const s = bmc.sensors || {}
  const gens = bmc.generations_available || []
  const product = bmc.product || 'BMC'
  const authed = !!bmc.session?.authenticated
  const isHpe = /ilo/i.test(product) || /hpe|hp/i.test(vendor || '')
  const brandTitle = isHpe ? 'HPE iLO' : /xclarity|lenovo/i.test(product) ? 'Lenovo XClarity' : /supermicro/i.test(product) ? 'Supermicro IPMI' : 'Dell iDRAC'

  if (!authed) {
    return (
      <div className="dc-bmc-login">
        <div className="dc-bmc-login-chrome">
          <div className="dc-bmc-login-brand">{brandTitle}</div>
          <div className="dc-bmc-login-sub">{product} · {bmc.firmware} · {bmc.chip}</div>
          <div className="dc-bmc-login-url">{bmc.endpoint}</div>
          <div className="dc-bmc-login-ip">Dedicated NIC · {bmc.network?.ipv4}</div>
          <label className="dc-bmc-login-label">Username
            <input className="dc-input" value={user} onChange={(e) => setUser(e.target.value)} autoComplete="username" />
          </label>
          <label className="dc-bmc-login-label">Password
            <input className="dc-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} autoComplete="current-password" />
          </label>
          {loginErr && <div className="dc-bmc-login-err">{loginErr}</div>}
          <button
            type="button"
            disabled={busy || !user || !pass}
            className="dc-btn-primary"
            onClick={async () => {
              setLoginErr('')
              try {
                await onLogin?.(user, pass)
              } catch (e) {
                setLoginErr(e?.response?.data?.error || e?.message || 'Login failed')
              }
            }}
          >
            Sign in to {product}
          </button>
          <p className="dc-muted mt-2">Lab hint: {bmc.login_hint || 'root / calvin'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Shield size={13} /> {product} · {bmc.chip}</span>
        <span className="dc-muted">FW {bmc.firmware} · signed in as {bmc.session?.user}</span>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onLogout?.()}>
          Log out
        </button>
      </div>
      {gens.length > 0 && (
        <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
          <span className="dc-muted">Generation:</span>
          {gens.map((g) => (
            <button key={g} type="button" disabled={busy}
              className={`dc-btn-xs ${bmc.product === g ? 'dc-btn-primary' : 'dc-btn-outline'}`}
              onClick={() => onSetGeneration?.(g)}>{g}</button>
          ))}
        </div>
      )}
      <div className="dc-bmc-row"><span className="dc-bmc-key">URL</span><span className="dc-bmc-mono">{bmc.endpoint}</span></div>
      <div className="dc-bmc-row"><span className="dc-bmc-key">IP</span>
        <span className="dc-bmc-val">{bmc.network?.ipv4} · VLAN {bmc.network?.vlan} · {bmc.network?.mode}</span>
      </div>
      <div className="dc-bmc-sensors">
        <span>Inlet {s.inlet_c}°C</span>
        <span>CPU1 {s.cpu1_c}°C</span>
        <span>CPU2 {s.cpu2_c}°C</span>
        <span>Fans {s.fans_rpm} RPM</span>
        <span>PSU {s.psu1_w}/{s.psu2_w} W</span>
        <span>12V {s['12v']}V</span>
      </div>
      <div className="dc-action-row">
        {['on', 'off', 'reset', 'cycle'].map((m) => (
          <button key={m} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onPower?.(m)}>{m}</button>
        ))}
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onNmi?.()}>NMI</button>
        <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onKvm?.()}>HTML5 KVM</button>
      </div>
      <div className="dc-drawer-label mt-2">Virtual media</div>
      <div className="dc-action-row">
        <input className="dc-input" value={iso} onChange={(e) => setIso(e.target.value)} />
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => onMountIso?.(iso)}>
          <Disc size={11} /> Mount ISO
        </button>
        {bmc.virtual_media?.mounted && <span className="dc-text-ok">Mounted: {bmc.virtual_media.image}</span>}
      </div>
      <div className="dc-drawer-label mt-2">Firmware targets</div>
      <div className="dc-action-row">
        {(bmc.firmware_targets || ['BIOS', 'BMC', 'RAID']).map((t) => (
          <button key={t} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onFlash?.(t, 'next')}>{t}</button>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">{(() => {
        const v = (vendor || '').toUpperCase()
        if (v === 'HPE' || v === 'HP') return 'Insight Diagnostics'
        if (v === 'LENOVO') return 'XClarity Diagnostics'
        if (v === 'SUPERMICRO') return 'IPMI Diagnostics'
        if (v === 'CISCO') return 'IMC Diagnostics'
        return 'ePSA Diagnostics'
      })()}</div>
      <div className="dc-action-row">
        {(bmc.diagnostics?.suites || ['Memory', 'CPU', 'Storage']).map((suite) => (
          <button key={suite} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onDiag?.(suite)}>{suite}</button>
        ))}
      </div>
      {bmc.diagnostics?.last_run && (
        <div className="dc-muted mt-1">Last: {bmc.diagnostics.suite} → {bmc.diagnostics.result} @ {bmc.diagnostics.last_run}</div>
      )}
      <div className="dc-drawer-label mt-2">RBAC users</div>
      <div className="dc-action-row">
        {(bmc.users || []).map((u) => (
          <span key={u.name} className="dc-topology-chip">{u.name}:{u.role}{u.mfa ? '+MFA' : ''}</span>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">SEL</div>
      <div className="dc-bmc-sel">
        {(bmc.sel || []).slice(0, 5).map((e, i) => (
          <div key={i} className="dc-bmc-sel-row"><span className="dc-bmc-sel-time">{e.time}</span> {e.message}</div>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">Protocols</div>
      <div className="dc-action-row">
        {(bmc.protocols_enabled || []).map((p) => <span key={p} className="dc-topology-chip">{p}</span>)}
      </div>
      <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs mt-2"
        onClick={() => onUpdateNet?.({ vlan: 90 })}>
        <Zap size={11} /> Refresh BMC network
      </button>
    </div>
  )
}

/** Field service checklist */
export function ServiceModePanel({ serviceMode, busy, onOp }) {
  const sm = serviceMode || {}
  const steps = [
    ['extend_rails', 'Extend rails', sm.rails_extended],
    ['open_cover', 'Open cover', sm.cover_open],
    ['remove_air_shroud', 'Remove air shroud', sm.air_shroud_removed],
    ['disconnect_power', 'Disconnect power', sm.power_cables_disconnected],
    ['disconnect_network', 'Disconnect network', sm.network_cables_disconnected],
    ['remove_cpu', 'Remove CPU1', (sm.cpu_removed || []).includes('CPU1')],
    ['install_cpu', 'Install CPU1', !(sm.cpu_removed || []).includes('CPU1') && sm.rails_extended],
    ['replace_cmos', 'Replace CMOS', sm.cmos_battery_ok],
    ['replace_tpm', 'Replace TPM', sm.tpm_present],
    ['hotswap_psu', 'Hot-swap PSU1', true],
    ['install_air_shroud', 'Install shroud', !sm.air_shroud_removed],
    ['close_cover', 'Close cover', !sm.cover_open],
    ['reconnect_power', 'Reconnect power', !sm.power_cables_disconnected],
    ['reconnect_network', 'Reconnect network', !sm.network_cables_disconnected],
    ['retract_rails', 'Retract rails', !sm.rails_extended],
  ]
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-title">Service & maintenance mode</div>
      <p className="dc-muted">{sm.notes || 'Follow field procedure in order.'}</p>
      <div className="dc-service-grid">
        {steps.map(([op, label, done]) => (
          <button key={op} type="button" disabled={busy}
            className={`dc-btn-outline dc-btn-xs ${done ? 'dc-service-done' : ''}`}
            onClick={() => onOp?.(op, op.includes('cpu') ? { socket_id: 'CPU1' } : op === 'hotswap_psu' ? { psu_id: 'PSU1' } : {})}>
            {done ? '✓ ' : ''}{label}
          </button>
        ))}
      </div>
    </div>
  )
}

/** CMDB inventory card */
export function InventoryPanel({ inventory }) {
  if (!inventory) return <p className="dc-muted">No inventory record.</p>
  const w = inventory.warranty || {}
  const fw = inventory.firmware || {}
  const life = inventory.lifecycle || {}
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-title">CMDB / Asset</div>
      <div className="dc-hw-meta">
        <div><span className="dc-hw-k">Asset tag</span> {inventory.asset_tag}</div>
        <div><span className="dc-hw-k">Serial</span> {inventory.serial}</div>
        <div><span className="dc-hw-k">Model</span> {inventory.vendor} {inventory.model}</div>
        <div><span className="dc-hw-k">Purchase</span> {inventory.purchase_date}</div>
        <div><span className="dc-hw-k">Warranty</span> {w.type} · {w.status} · exp {w.expires}</div>
        <div><span className="dc-hw-k">Firmware</span> BIOS {fw.bios} · BMC {fw.bmc} · RAID {fw.raid}</div>
        <div><span className="dc-hw-k">Lifecycle</span> {life.stage} · EOS {life.eos} · EOL {life.eol}</div>
      </div>
      {(inventory.replacement_history || []).length > 0 && (
        <>
          <div className="dc-drawer-label mt-2">Replacement history</div>
          {(inventory.replacement_history || []).slice(0, 5).map((h, i) => (
            <div key={i} className="dc-muted">{h.time} · {h.part} · {h.action}</div>
          ))}
        </>
      )}
      {inventory.fru_labels && (
        <>
          <div className="dc-drawer-label mt-2">Chassis labels / QR</div>
          <div className="dc-hw-meta">
            <div><span className="dc-hw-k">QR</span> {inventory.fru_labels.chassis_qr}</div>
            <div><span className="dc-hw-k">Serial plate</span> {inventory.fru_labels.serial_plate}</div>
            <div><span className="dc-hw-k">Warranty sticker</span> {inventory.fru_labels.warranty_sticker}</div>
            <div><span className="dc-hw-k">Ports</span> {(inventory.fru_labels.port_labels || []).join(', ')}</div>
            <div><span className="dc-hw-k">PSU</span> {(inventory.fru_labels.psu_labels || []).join(', ')}</div>
            <div><span className="dc-hw-k">Bays</span> {(inventory.fru_labels.drive_bay_labels || []).join(', ')}</div>
          </div>
        </>
      )}
    </div>
  )
}

/** Failure injection toolbar — grouped by target (server / facility / network) */
export function FailureInjectBar({ presets, busy, onInject, onClear, broken, assetId }) {
  const list = presets || []
  if (!list.length && !broken) return null
  const groups = [
    { key: 'server', label: 'Server' },
    { key: 'facility', label: 'Facility' },
    { key: 'network', label: 'Network' },
  ]
  const byTarget = (t) => list.filter((p) => (p.target || 'server') === t)
  return (
    <div className="dc-failure-bar">
      <div className="dc-action-row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <span className="dc-drawer-label" style={{ margin: 0 }}>Failure injection</span>
        {broken?.component && (
          <span className="dc-alert-row" style={{ margin: 0 }}>
            Open fault: {broken.component}{broken.server ? ` · ${broken.server}` : ''}{broken.target ? ` · ${broken.target}` : ''}
          </span>
        )}
        {onClear && (
          <button type="button" disabled={busy || !broken?.component} className="dc-btn-primary dc-btn-xs" onClick={() => onClear?.()}>
            Clear fault
          </button>
        )}
      </div>
      {groups.map((g) => {
        const items = byTarget(g.key)
        if (!items.length) return null
        return (
          <div key={g.key} style={{ marginTop: '0.45rem' }}>
            <div className="dc-muted" style={{ fontSize: '0.68rem', marginBottom: '0.25rem' }}>{g.label}</div>
            <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
              {items.map((p) => (
                <button key={p.id} type="button" disabled={busy} className="dc-btn-danger dc-btn-xs"
                  onClick={() => onInject?.(p.id, assetId)} title={p.inject ? `Linked drill inject` : p.label}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** Campus / plant room overview cards with light live ops */
export function CampusRoomView({ room, campus, busy = false, onOp }) {
  if (!room) return null
  const c = campus || {}
  const act = (op, extra = {}) => onOp?.(op, extra)

  if (room.type === 'campus' || room.id === 'campus') {
    return (
      <div className="dc-campus-grid">
        <CampusCard
          title="Parking"
          body={`${c.parking?.occupied ?? 0} / ${c.parking?.spaces ?? 0} occupied`}
          actions={onOp && (
            <>
              <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('parking_in')}>Badge in</button>
              <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('parking_out')}>Exit</button>
            </>
          )}
        />
        <CampusCard title="Access" body={`Gate ${c.access?.gate} · Biometrics ${c.access?.biometrics} · ${c.access?.cameras} cameras`} />
        <CampusCard title="Generators" body={(c.generators || []).map((g) => `${g.id} ${g.status} ${g.fuel_pct}% fuel`).join(' · ')} />
        <CampusCard title="Diesel" body={(c.diesel_tanks || []).map((t) => `${t.id} ${t.level_pct}%`).join(' · ')} />
        <CampusCard title="Cooling towers" body={(c.cooling_towers || []).map((t) => `${t.id} ${t.status}`).join(' · ')} />
        <CampusCard title="Chillers" body={(c.chillers || []).map((t) => `${t.id} ${t.status}`).join(' · ')} />
        <CampusCard title="Transformers" body={(c.transformers || []).map((t) => `${t.id} ${t.load_pct}%`).join(' · ')} />
        <CampusCard
          title="Loading dock"
          body={`${c.loading_dock?.occupied_bays ?? 0}/${c.loading_dock?.bays ?? 0} bays · ${c.loading_dock?.received_today ?? 0} received today`}
        />
      </div>
    )
  }
  if (room.id === 'generator-yard') {
    return (
      <div className="dc-campus-grid">
        {(c.generators || []).map((g) => (
          <CampusCard key={g.id} title={g.id} body={`${g.kw} kW · ${g.status} · fuel ${g.fuel_pct}%`} />
        ))}
        {(c.diesel_tanks || []).map((t) => (
          <CampusCard key={t.id} title={t.id} body={`${t.liters} L · ${t.level_pct}%`} />
        ))}
      </div>
    )
  }
  if (room.id === 'chillers') {
    return (
      <div className="dc-campus-grid">
        {(c.chillers || []).map((ch) => (
          <CampusCard
            key={ch.id}
            title={ch.id}
            body={`${ch.tons} tons · ${ch.status}${ch.cop ? ` · COP ${ch.cop}` : ''}`}
            actions={onOp && (
              ch.status === 'running' ? (
                <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('stop_chiller', { chiller_id: ch.id })}>Stop</button>
              ) : (
                <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('start_chiller', { chiller_id: ch.id })}>Start</button>
              )
            )}
          />
        ))}
        {(c.cooling_towers || []).map((t) => (
          <CampusCard key={t.id} title={t.id} body={`${t.status} · approach ${t.approach_c}°C`} />
        ))}
      </div>
    )
  }
  if (room.id === 'substation') {
    return (
      <div className="dc-campus-grid">
        {(c.transformers || []).map((x) => (
          <CampusCard
            key={x.id}
            title={x.id}
            body={`${x.kva} kVA · ${x.status} · load ${x.load_pct}%`}
            actions={onOp && (
              <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('note_xfmr_load', { transformer_id: x.id })}>
                Take load reading
              </button>
            )}
          />
        ))}
      </div>
    )
  }
  if (room.id === 'battery') {
    return (
      <div className="dc-campus-grid">
        {(c.battery_strings || []).map((s) => (
          <CampusCard
            key={s.id}
            title={s.id}
            body={`${s.chemistry} · ${s.cells} cells · SoC ${s.soc_pct}% · ${s.status} · ${s.temp_c}°C`}
          />
        ))}
        <CampusCard
          title="String sync"
          body="Pull SoC from UPS telemetry (float vs discharge)"
          actions={onOp && (
            <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('sync_battery')}>Sync from UPS</button>
          )}
        />
      </div>
    )
  }
  if (room.id === 'loading-dock') {
    const dock = c.loading_dock || {}
    return (
      <div className="dc-campus-grid">
        <CampusCard
          title="Dock status"
          body={`${dock.occupied_bays ?? 0}/${dock.bays ?? 0} bays occupied · ${dock.received_today ?? 0} received today`}
          actions={onOp && (
            <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('arrive_dock')}>Truck arrive</button>
          )}
        />
        {(dock.queue || []).map((q) => (
          <CampusCard
            key={q.id}
            title={q.id}
            body={`${q.carrier} · ${q.contents} · ${q.status}`}
            actions={onOp && q.status !== 'received' && (
              <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('receive_dock', { asn_id: q.id })}>
                Receive FRU
              </button>
            )}
          />
        ))}
      </div>
    )
  }
  if (room.id === 'spares') {
    const spares = c.spares || {}
    return (
      <div className="dc-campus-grid">
        <CampusCard
          title="Stockroom"
          body={`Issued today ${spares.issued_today ?? 0} · Quarantine ${(spares.quarantine || []).length}`}
        />
        {(spares.bins || []).map((b) => {
          const low = intOr(b.qty, 0) <= intOr(b.min_qty, 0)
          return (
            <CampusCard
              key={b.id}
              title={`${b.id}${low ? ' · LOW' : ''}`}
              body={`${b.label} · ${b.sku} · qty ${b.qty} (min ${b.min_qty}) · bin ${b.location}`}
              actions={onOp && (
                <>
                  <button type="button" className="dc-btn-sm" disabled={busy || intOr(b.qty, 0) <= 0} onClick={() => act('issue_spare', { bin_id: b.id })}>Issue</button>
                  <button type="button" className="dc-btn-sm" disabled={busy} onClick={() => act('restock_spare', { bin_id: b.id })}>Restock</button>
                  <button type="button" className="dc-btn-sm" disabled={busy || intOr(b.qty, 0) <= 0} onClick={() => act('quarantine_spare', { bin_id: b.id })}>Quarantine</button>
                </>
              )}
            />
          )
        })}
        {(spares.kits_staged || []).slice(0, 4).map((k) => (
          <CampusCard key={k.id} title={k.id} body={`${k.sku} → ${k.for_asset} · ${k.status}`} />
        ))}
      </div>
    )
  }
  return (
    <div className="dc-campus-empty">
      <BuildingHint room={room} />
    </div>
  )
}

function intOr(v, d) {
  const n = Number(v)
  return Number.isFinite(n) ? n : d
}

function CampusCard({ title, body, actions = null }) {
  return (
    <div className="dc-crac-card">
      <div className="dc-crac-id">{title}</div>
      <div className="dc-crac-zone">{body}</div>
      {actions ? <div className="dc-campus-card-actions" style={{ display: 'flex', gap: '0.35rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>{actions}</div> : null}
    </div>
  )
}

function BuildingHint({ room }) {
  return (
    <div className="dc-crac-card" style={{ maxWidth: 480 }}>
      <div className="dc-crac-id">{room.name}</div>
      <div className="dc-crac-zone">Zone: {room.zone || room.type}. Use Data Hall / MDF / Mechanical / Electrical for live rack and plant controls. This zone is part of the digital-twin campus map for training navigation.</div>
    </div>
  )
}
