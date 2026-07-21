import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Boxes, ClipboardList, Cpu, Gauge, Network, ShieldCheck, Ticket } from 'lucide-react'

/** Animated motherboard bus packets */
export function BusAnimPanel({ buses }) {
  const list = buses || []
  return (
    <div className="dc-bus-anim">
      {list.map((b) => (
        <div key={b.id} className="dc-bus-anim-row">
          <div className="dc-bus-anim-meta">
            <span style={{ color: b.color }} className="dc-bus-name">{b.id}</span>
            <span className="dc-muted">{b.util_pct}% · {b.packets_per_s || 0} pkt/s · {b.latency_ns || '—'}ns · err {b.errors || 0}</span>
          </div>
          <div className="dc-bus-track dc-bus-track-tall">
            <div className="dc-bus-fill" style={{ width: `${b.util_pct}%`, background: b.color }} />
            {(b.packets || []).map((p) => (
              <span
                key={p.id}
                className="dc-bus-packet"
                style={{ left: `${p.pos}%`, background: b.color, boxShadow: `0 0 6px ${b.color}` }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/** Rack physics + FRU detail when rack expanded */
export function RackPhysicsFruPanel({ rack, busy, onToggleCasters, onBlanking, onOutlet, onFruOp }) {
  if (!rack) return null
  const phy = rack.physics || {}
  const fru = rack.fru || {}
  return (
    <div className="dc-rack-detail" onClick={(e) => e.stopPropagation()}>
      <div className="dc-twin-title"><Gauge size={12} /> Physics · {rack.id}</div>
      <div className="dc-physics-grid">
        <span>Mass <strong>{phy.mass_kg ?? '—'} kg</strong></span>
        <span>CoG <strong>{phy.cog_height_mm ?? '—'} mm</strong></span>
        <span>Tip <strong className={phy.tip_risk === 'high' ? 'dc-text-bad' : ''}>{phy.tip_risk} ({phy.tip_score})</strong></span>
        <span>Heat <strong>{phy.heat_kw ?? '—'} kW</strong></span>
        <span>In/Out <strong>{phy.inlet_c}→{phy.outlet_c}°C</strong></span>
        <span>Airflow <strong>{phy.airflow_cfm} CFM</strong></span>
        <span>Fan ΔP <strong>{phy.fan_pressure_mmH2O} mmH₂O</strong></span>
        <span>Vibe <strong>{phy.vibration_mm_s} mm/s</strong></span>
        <span>Expansion <strong>{phy.thermal_expansion_um} µm</strong></span>
        <span>Floor <strong>{phy.floor_loading_ok ? 'OK' : 'OVER'}</strong></span>
      </div>
      <div className="dc-action-row mt-1">
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => onToggleCasters?.(rack.id)}>
          Casters {phy.casters_locked ? 'LOCKED' : 'UNLOCKED'}
        </button>
      </div>
      {fru.serial && (
        <>
          <div className="dc-drawer-label mt-2">Rack FRU · {fru.manufacturer} {fru.model}</div>
          <div className="dc-hw-meta">
            <div><span className="dc-hw-k">Serial</span> {fru.serial} · {fru.asset_tag}</div>
            <div><span className="dc-hw-k">QR</span> {fru.qr_code}
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" style={{ marginLeft: 6 }}
                onClick={() => onFruOp?.(rack.id, 'scan_qr')}>Scan</button>
            </div>
            <div><span className="dc-hw-k">Warranty</span> {(fru.warranty_stickers || [fru.warranty_sticker]).filter(Boolean).map((w) => `${w.vendor} exp ${w.expires}`).join(' · ')}</div>
            <div><span className="dc-hw-k">Rails</span> {fru.rails?.front?.type} · kit M6×{fru.screw_kit?.m6_screws ?? fru.rails?.screws} · {fru.cage_nuts_installed} cage nuts · washers {fru.screw_kit?.washers ?? fru.washers}</div>
            <div><span className="dc-hw-k">Ground</span> {fru.grounding_strap?.status} @ {fru.grounding_strap?.torque_nm} N·m
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" style={{ marginLeft: 6 }}
                onClick={() => onFruOp?.(rack.id, 'torque_ground', { torque_nm: 5 })}>Re-torque</button>
            </div>
            <div><span className="dc-hw-k">Blanking</span> {(fru.blanking_panels || []).filter((p) => p.installed).length} panels · ties {fru.cable_ties} · velcro {fru.velcro_straps}</div>
            <div><span className="dc-hw-k">Baffles</span> {(fru.airflow_baffles || []).map((b) => `${b.id}:${b.status}`).join(' · ')}
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" style={{ marginLeft: 6 }}
                onClick={() => onFruOp?.(rack.id, 'toggle_baffle', { baffle_id: 'BAF-TOP' })}>Toggle top</button>
            </div>
          </div>
          {fru.last_qr_scan && (
            <div className="dc-muted mt-1">Last QR scan: {fru.last_qr_scan.code} @ {fru.last_qr_scan.time}</div>
          )}
          <div className="dc-drawer-label mt-2">U labels / QR (sample)</div>
          <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
            {(fru.labels || []).slice(0, 8).map((l) => (
              <span key={l.u} className="dc-topology-chip" title={l.qr}>{l.text}</span>
            ))}
          </div>
          <div className="dc-drawer-label mt-2">Cage nuts (interactive)</div>
          <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
            {(fru.cage_nuts || []).slice(0, 8).map((cn) => (
              <button key={cn.u} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                onClick={() => onFruOp?.(rack.id, cn.front_left ? 'remove_cage_nut' : 'install_cage_nut', { u: cn.u, side: 'front_left' })}>
                U{cn.u} FL {cn.front_left ? '●' : '○'}
              </button>
            ))}
          </div>
          <div className="dc-action-row mt-1">
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
              onClick={() => onBlanking?.(rack.id, 11)}>Install blanking U11</button>
          </div>
          <div className="dc-drawer-label mt-2">PDU outlets (sample)</div>
          <div className="dc-outlet-grid">
            {(fru.pdu_outlets || []).slice(0, 12).map((o) => (
              <button key={o.id} type="button" disabled={busy}
                className={`dc-outlet ${o.energized ? 'dc-outlet-on' : 'dc-outlet-off'}`}
                onClick={() => onOutlet?.(rack.id, o.id)}
                title={`${o.id} ${o.type} ${o.load_w}W`}>
                <span className={`dc-port-led ${o.led === 'green' ? 'dc-led-green' : 'dc-led-red'}`} />
                {o.type}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

/** CDU / DLC liquid cooling plant */
export function LiquidCoolingPanel({ liquid, busy, onOp }) {
  const loop = liquid || {}
  if (!loop.cdus) return <p className="dc-muted">No liquid cooling loop.</p>
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Gauge size={13} /> Liquid loop · {loop.fluid}</span>
        <span className={loop.leak_detected ? 'dc-text-bad' : 'dc-text-ok'}>
          {loop.loop_status}{loop.leak_detected ? ' · LEAK' : ''}
        </span>
      </div>
      <div className="dc-crac-grid">
        {(loop.cdus || []).map((c) => (
          <div key={c.id} className={`dc-crac-card ${c.status !== 'running' ? 'dc-crac-alert' : ''}`}>
            <div className="dc-crac-id">{c.id} · {c.model}</div>
            <div className="dc-crac-zone">{c.status} · {c.load_kw}/{c.capacity_kw} kW · pump {c.pump_rpm} RPM</div>
            <div className="dc-crac-metrics">
              <div><span className="dc-crac-metric-label">Supply</span><span className="dc-crac-metric-val">{c.supply_temp_c}°C</span></div>
              <div><span className="dc-crac-metric-label">Return</span><span className="dc-crac-metric-val">{c.return_temp_c}°C</span></div>
              <div><span className="dc-crac-metric-label">Flow</span><span className="dc-crac-metric-val">{c.flow_lpm} L/min</span></div>
            </div>
            <div className="dc-action-row mt-1">
              {c.status === 'running' ? (
                <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('stop_cdu', { cdu_id: c.id })}>Stop</button>
              ) : (
                <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('start_cdu', { cdu_id: c.id })}>Start</button>
              )}
              <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                onClick={() => onOp?.('set_setpoint', { cdu_id: c.id, temp_c: 18 })}>Set 18°C</button>
            </div>
          </div>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">Rack manifolds / QD couplings</div>
      {(loop.manifolds || []).map((m) => (
        <div key={m.id} className="dc-vd-card">
          <div className="dc-vd-head">
            <strong>{m.id}</strong>
            <span>{m.rack} · {m.status} · {m.flow_lpm} L/min · {m.supply_temp_c}→{m.return_temp_c}°C</span>
          </div>
          <div className="dc-action-row">
            {(m.qd_couplings || []).map((qd) => (
              <button key={qd.id} type="button" disabled={busy}
                className={`dc-btn-xs ${qd.connected ? 'dc-btn-primary' : 'dc-btn-outline'}`}
                onClick={() => onOp?.('toggle_qd', { qd_id: qd.id })}>
                {qd.id} {qd.connected ? '●' : '○'} ({qd.side})
              </button>
            ))}
          </div>
        </div>
      ))}
      <div className="dc-action-row mt-2">
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('inject_leak')}>Inject leak</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('clear_leak')}>Clear leak</button>
      </div>
      <div className="dc-drawer-label mt-2">Events</div>
      {(loop.events || []).slice(0, 4).map((e, i) => (
        <div key={i} className="dc-muted">{e.time} · {e.message}</div>
      ))}
    </div>
  )
}

/** MAAS / PXE bare-metal provisioning */
export function PxeMaasPanel({ pxeMaas, busy, selectedServerId, onOp }) {
  const p = pxeMaas || {}
  const region = p.region || {}
  if (!region.id) return <p className="dc-muted">No MAAS region.</p>
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Boxes size={13} /> MAAS {region.version}</span>
        <span className={region.status === 'healthy' ? 'dc-text-ok' : 'dc-text-bad'}>{region.status}</span>
      </div>
      <div className="dc-muted">{region.url}</div>
      <div className="dc-hw-meta">
        <div><span className="dc-hw-k">DHCP</span> {region.dhcp ? 'on' : 'OFF'} · TFTP {region.tftp ? 'on' : 'off'} · HTTP boot {region.http_boot ? 'on' : 'off'}</div>
        <div><span className="dc-hw-k">Leases</span> {p.dhcp_leases} · rack controllers {(p.rack_controllers || []).length}</div>
      </div>
      <div className="dc-action-row mt-1">
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('fix_dhcp')}>Fix DHCP/TFTP</button>
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('break_dhcp')}>Break DHCP</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('sync_image', { image: 'centos/stream9' })}>Sync Stream9</button>
      </div>
      <div className="dc-drawer-label mt-2">Images</div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {(p.images || []).map((img) => (
          <span key={img.name} className={`dc-topology-chip ${img.synced ? '' : 'dc-text-bad'}`}>
            {img.name}{img.synced ? '' : ' ✗'}
          </span>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">PXE menu</div>
      <div className="dc-muted">{(p.pxe_menu || []).join(' · ')}</div>
      <div className="dc-drawer-label mt-2">Machines</div>
      <table className="dc-port-table">
        <thead><tr><th>Host</th><th>Status</th><th>OS</th><th /></tr></thead>
        <tbody>
          {(p.machines || []).map((m) => (
            <tr key={m.id} className={m.id === selectedServerId ? 'dc-row-sel' : ''}>
              <td>{m.hostname}</td>
              <td>{m.status}</td>
              <td>{m.os || '—'}</td>
              <td>
                <div className="dc-action-row">
                  <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                    onClick={() => onOp?.('enlist', { machine_id: m.id })}>Enlist</button>
                  <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                    onClick={() => onOp?.('commission', { machine_id: m.id })}>Commission</button>
                  <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs"
                    onClick={() => onOp?.('deploy', { machine_id: m.id, image: m.os || 'ubuntu/22.04' })}>Deploy</button>
                  <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                    onClick={() => onOp?.('pxe_boot', { machine_id: m.id })}>PXE</button>
                  <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs"
                    onClick={() => onOp?.('release', { machine_id: m.id })}>Release</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="dc-drawer-label mt-2">Events</div>
      {(p.events || []).slice(0, 4).map((e, i) => (
        <div key={i} className="dc-muted">{e.time} · {e.message}</div>
      ))}
    </div>
  )
}

/** Monitoring / Alertmanager style dashboard */
export function MonitoringPanel({ monitoring, busy, onRefresh, onReplay, twinJournal }) {
  const m = monitoring || {}
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 4000)
    return () => clearInterval(id)
  }, [])
  const journalLen = (twinJournal?.persisted_changes || []).length
  const lastReplay = twinJournal?.last_replay
  return (
    <div className="dc-ops-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Activity size={13} /> Monitoring · scrape #{tick}</span>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={onRefresh}>Refresh</button>
        {onReplay && (
          <button type="button" disabled={busy || journalLen === 0} className="dc-btn-outline dc-btn-xs"
            onClick={onReplay} title="Reset twin and replay journaled actions">
            Replay journal ({journalLen})
          </button>
        )}
      </div>
      <div className="dc-muted">Exporters: {(m.exporters || []).join(', ')} · targets {m.targets_up}/{m.targets_total} · PUE {m.pue}</div>
      {lastReplay && (
        <div className="dc-muted">Last replay {lastReplay.time}: {lastReplay.replayed} ok / {lastReplay.skipped} skipped</div>
      )}
      <div className="dc-drawer-label mt-2">Alerts</div>
      {(m.alerts || []).length === 0 && <div className="dc-text-ok">No firing alerts</div>}
      {(m.alerts || []).slice(0, 8).map((a, i) => (
        <div key={i} className={`dc-alert-row ${a.severity === 'critical' ? 'dc-alert-crit' : ''}`}>
          <AlertTriangle size={11} /> [{a.severity}] {a.alertname} · {a.instance} — {a.summary}
        </div>
      ))}
      <div className="dc-drawer-label mt-2">Series samples</div>
      <div className="dc-metrics-mini">
        {(m.series?.redfish_inlet_c || []).slice(0, 4).map((s) => (
          <span key={s.instance} className="dc-topology-chip">{s.instance} inlet {s.value}°C</span>
        ))}
        {(m.series?.dcgm_gpu_utilization || []).map((s) => (
          <span key={s.instance} className="dc-topology-chip">GPU {s.instance} {s.value}%</span>
        ))}
      </div>
    </div>
  )
}

/** Extended ticketing / RMA */
export function OpsTicketsPanel({ tickets, busy, onCreate, onAdvance }) {
  return (
    <div className="dc-ops-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Ticket size={13} /> Ops tickets / RMA</span>
      </div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {['Dell', 'HPE', 'Lenovo', 'Supermicro', 'Cisco', 'NVIDIA'].map((v) => (
          <button key={v} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onCreate?.(v, 'incident')}>{v} Incident</button>
        ))}
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => onCreate?.('Dell', 'change')}>Change Request</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => onCreate?.('Dell', 'problem')}>Problem</button>
      </div>
      {(tickets || []).slice(0, 6).map((t) => (
        <div key={t.id} className="dc-ticket-card">
          <div className="dc-ticket-id">{t.id} · {t.vendor} · {t.type || 'incident'} · {t.status}</div>
          <div className="dc-ticket-sum">{t.summary} · P{t.priority} · {t.assignee || 'unassigned'} · esc L{t.escalation || 0}</div>
          {t.rma && <div className="dc-muted">RMA {t.rma.rma_number} · {t.rma.part} · {t.rma.status}</div>}
          {t.rca && <div className="dc-muted">RCA: {t.rca.root_cause}</div>}
          <div className="dc-action-row mt-1">
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onAdvance?.(t.id, 'assign')}>Assign</button>
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onAdvance?.(t.id, 'escalate')}>Escalate</button>
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onAdvance?.(t.id, 'ship_rma')}>Ship RMA</button>
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onAdvance?.(t.id, 'schedule_visit')}>Field visit</button>
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onAdvance?.(t.id, 'add_rca')}>RCA</button>
            <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onAdvance?.(t.id, 'resolve')}>Resolve</button>
          </div>
        </div>
      ))}
    </div>
  )
}

/** Guided training roles */
export function TrainingPanel({ training, busy, onStart, onStep }) {
  const t = training || {}
  const active = (t.scenarios || []).find((s) => s.id === t.active)
  return (
    <div className="dc-ops-panel">
      <div className="dc-twin-title"><ClipboardList size={13} /> Training mode</div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {(t.scenarios || []).map((s) => (
          <button key={s.id} type="button" disabled={busy}
            className={`dc-btn-outline dc-btn-xs ${t.active === s.id ? 'dc-service-done' : ''}`}
            onClick={() => onStart?.(s.id)}>{s.role}</button>
        ))}
      </div>
      {active && (
        <>
          <div className="dc-muted mt-1">{t.feedback}</div>
          <ol className="dc-bios-boot">
            {active.steps.map((step) => (
              <li key={step}>
                <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                  onClick={() => onStep?.(step)}>
                  {(t.progress || []).includes(step) ? '✓ ' : ''}{step}
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}

/** Phase 6 — hypervisor + K8s / GPU-AI lab surfaces */
export function ComputeAiPanel({ hypervisors, aiPlatform, busy, onHv, onAi }) {
  const hosts = hypervisors?.hosts || []
  const snaps = hypervisors?.snapshots || []
  const migs = hypervisors?.migrations || []
  const k8s = aiPlatform?.kubernetes || {}
  const slurm = aiPlatform?.slurm || {}
  const mig = aiPlatform?.mig || {}
  const inference = aiPlatform?.inference || []

  return (
    <div className="dc-ops-room">
      <div className="dc-ops-panel">
        <div className="dc-twin-title"><Boxes size={13} /> Hypervisor fleet</div>
        <div className="dc-muted mb-1">
          Platforms: {(hypervisors?.platforms || []).slice(0, 5).join(', ')}
          {(hypervisors?.platforms || []).length > 5 ? '…' : ''}
        </div>
        <div className="dc-action-row" style={{ flexWrap: 'wrap', marginBottom: '0.5rem' }}>
          <button type="button" disabled={busy || !hosts.length} className="dc-btn-outline dc-btn-xs"
            onClick={() => onHv?.('create_vm', { name: `lab-vm-${Date.now() % 10000}`, cpus: 2, mem_gb: 4 })}>
            Create VM
          </button>
        </div>
        {hosts.map((h) => (
          <div key={h.id} className="dc-cmdb-card" style={{ marginBottom: '0.5rem' }}>
            <div className="dc-twin-subtitle">{h.hostname} · {h.hypervisor} {h.version}</div>
            <div className="dc-muted">{h.cpu_cores}c / {h.mem_gb} GB · {(h.vms || []).length} VMs</div>
            <ul className="dc-bios-boot">
              {(h.vms || []).map((vm) => (
                <li key={vm.id}>
                  <span>{vm.name} ({vm.cpus}c/{vm.mem_gb}G) — {vm.power}</span>
                  <span className="dc-action-row" style={{ display: 'inline-flex', gap: 4, marginLeft: 8 }}>
                    <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                      onClick={() => onHv?.('power_vm', { vm_id: vm.id, mode: vm.power === 'on' ? 'off' : 'on' })}>
                      Power {vm.power === 'on' ? 'off' : 'on'}
                    </button>
                    <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                      onClick={() => onHv?.('snapshot_vm', { vm_id: vm.id })}>
                      Snapshot
                    </button>
                    {hosts.length > 1 && (
                      <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                        onClick={() => {
                          const dest = hosts.find((x) => x.id !== h.id)
                          if (dest) onHv?.('migrate_vm', { vm_id: vm.id, dest_host: dest.id })
                        }}>
                        Migrate
                      </button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {snaps.length > 0 && (
          <div className="dc-muted mt-1">Snapshots: {snaps.slice(0, 3).map((s) => s.name).join(', ')}</div>
        )}
        {migs.length > 0 && (
          <div className="dc-muted">Migrations: {migs.slice(0, 2).map((m) => `${m.vm_id} ${m.type}`).join('; ')}</div>
        )}
      </div>

      <div className="dc-ops-panel" style={{ marginTop: '0.75rem' }}>
        <div className="dc-twin-title"><Cpu size={13} /> Kubernetes · GPU · AI</div>
        <div className="dc-muted">
          K8s {k8s.version} · GPU operator {k8s.gpu_operator?.version} ({k8s.gpu_operator?.status})
          · CUDA {aiPlatform?.cuda?.version} · NCCL {aiPlatform?.nccl?.version}
        </div>
        <div className="dc-action-row" style={{ flexWrap: 'wrap', margin: '0.5rem 0' }}>
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onAi?.('deploy_pod', { name: `job-${Date.now() % 10000}`, gpus: 1 })}>
            Deploy GPU pod
          </button>
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onAi?.('helm_install', { chart: 'nvidia-device-plugin' })}>
            Helm install
          </button>
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onAi?.('enable_mig', { profile: '1g.10gb' })}>
            Enable MIG {mig.enabled ? `(${mig.active_profile || 'on'})` : ''}
          </button>
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onAi?.('slurm_submit', { name: 'train-batch', gpus: 2 })}>
            Slurm submit
          </button>
          <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onAi?.('scale_inference', { replicas: 2 })}>
            Scale inference
          </button>
        </div>
        <div className="dc-twin-subtitle">Pods</div>
        <ul className="dc-bios-boot">
          {(k8s.pods || []).slice(0, 6).map((p) => (
            <li key={`${p.ns}-${p.name}`}>{p.ns}/{p.name} — {p.status}{p.gpus ? ` · ${p.gpus} GPU` : ''}</li>
          ))}
        </ul>
        <div className="dc-twin-subtitle mt-1">Helm · Slurm · Inference</div>
        <div className="dc-muted">
          Releases: {(k8s.helm_releases || []).join(', ') || '—'}
        </div>
        <div className="dc-muted">
          Slurm [{slurm.partition}]: {(slurm.jobs || []).map((j) => `#${j.id} ${j.name} ${j.state}`).join('; ') || 'idle'}
        </div>
        <div className="dc-muted">
          Ray {aiPlatform?.ray?.status} · Inference: {inference.map((i) => `${i.name}×${i.replicas}`).join(', ') || '—'}
        </div>
      </div>
    </div>
  )
}

/** Fire suppression / VESDA */
export function FireSafetyPanel({ fire, busy, onOp }) {
  const fs = fire || {}
  if (!fs.system) return <p className="dc-muted">No fire system.</p>
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><AlertTriangle size={13} /> {fs.system}</span>
        <span className={fs.status === 'armed' ? 'dc-text-ok' : 'dc-text-bad'}>{fs.status}</span>
      </div>
      <div className="dc-crac-grid">
        {(fs.zones || []).map((z) => (
          <div key={z.id} className={`dc-crac-card ${z.status !== 'normal' ? 'dc-crac-alert' : ''}`}>
            <div className="dc-crac-id">{z.id} · {z.name}</div>
            <div className="dc-crac-zone">{z.status} · smoke {z.smoke_pct}%</div>
            <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs mt-1"
              onClick={() => onOp?.('smoke_alarm', { zone_id: z.id })}>Smoke alarm</button>
          </div>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">Cylinders</div>
      {(fs.cylinders || []).map((c) => (
        <div key={c.id} className="dc-muted">{c.id} {c.agent} · {c.pressure_bar} bar · {c.weight_kg} kg · {c.status}</div>
      ))}
      <div className="dc-action-row mt-2">
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('manual_release')}>Manual release</button>
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('discharge', { force: true })}>Discharge</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('silence')}>Silence / reset</button>
        <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('rearm')}>Rearm</button>
      </div>
      {(fs.events || []).slice(0, 3).map((e, i) => (
        <div key={i} className="dc-muted">{e.time} · {e.message}</div>
      ))}
    </div>
  )
}

/** Environmental sensors */
export function EnvironmentalPanel({ environmental, busy, onOp }) {
  const env = environmental || {}
  if (!(env.sensors || []).length) return <p className="dc-muted">No environmental sensors.</p>
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Activity size={13} /> Environmental · ASHRAE {env.ashrae_class}</span>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('normalize')}>Normalize</button>
      </div>
      <table className="dc-port-table">
        <thead><tr><th>ID</th><th>Type</th><th>Location</th><th>Reading</th><th>Status</th><th /></tr></thead>
        <tbody>
          {(env.sensors || []).map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.type}</td>
              <td>{s.location}</td>
              <td>
                {s.type === 'temp_humidity' && `${s.temp_c}°C / ${s.humidity_pct}%`}
                {s.type === 'water_leak' && (s.wet ? 'WET' : 'dry')}
                {s.type === 'door' && (s.open ? 'OPEN' : 'closed')}
                {s.type === 'differential_pressure' && `${s.pa} Pa`}
              </td>
              <td><span className={`dc-port-badge ${s.status === 'ok' ? 'dc-port-up' : 'dc-port-down'}`}>{s.status}</span></td>
              <td>
                {s.type === 'water_leak' && (
                  <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('trip_leak', { sensor_id: s.id })}>Trip</button>
                )}
                {s.type === 'door' && (
                  <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                    onClick={() => onOp?.(s.open ? 'close_door' : 'open_door', { sensor_id: s.id })}>
                    {s.open ? 'Close' : 'Open'}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="dc-action-row mt-1">
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('hotspot')}>Inject hotspot</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('clear_leak')}>Clear leaks</button>
      </div>
      {(env.alerts || []).slice(0, 4).map((a, i) => (
        <div key={i} className="dc-alert-row">[{a.severity}] {a.message}</div>
      ))}
    </div>
  )
}

/** FEF / MMR / MPO optical plant */
export function OpticalPanel({ optical, busy, onOp }) {
  const opt = optical || {}
  if (!opt.fef) return <p className="dc-muted">No optical plant.</p>
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-title"><Network size={13} /> Optical · FEF / MMR / MPO</div>
      <div className="dc-drawer-label">Fiber entrance (FEF)</div>
      {(opt.fef?.carriers || []).map((c) => (
        <div key={c.id} className="dc-action-row">
          <span className="dc-topology-chip">{c.id} · {c.circuit} · {c.status}</span>
          {c.status === 'up' ? (
            <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('carrier_down', { carrier_id: c.id })}>Down</button>
          ) : (
            <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('carrier_up', { carrier_id: c.id })}>Restore</button>
          )}
        </div>
      ))}
      <div className="dc-drawer-label mt-2">Meet-Me cross-connects</div>
      {(opt.mmr?.cross_connects || []).map((x) => (
        <div key={x.id} className="dc-action-row">
          <span className="dc-muted">{x.id}: {x.a} → {x.z} ({x.media}) · {x.status}</span>
          {x.status === 'active' ? (
            <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('deactivate_xc', { xc_id: x.id })}>Dark</button>
          ) : (
            <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('activate_xc', { xc_id: x.id })}>Activate</button>
          )}
        </div>
      ))}
      <div className="dc-drawer-label mt-2">MPO trunks</div>
      {(opt.trunks || []).map((t) => (
        <div key={t.id} className={`dc-vd-card ${t.status === 'cut' ? 'dc-crac-alert' : ''}`}>
          <div className="dc-vd-head">
            <strong>{t.id}</strong>
            <span>{t.type} · {t.from}→{t.to} · {t.length_m}m · {t.loss_db} dB · {t.status}</span>
          </div>
          <div className="dc-action-row">
            {t.status === 'cut' ? (
              <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('repair_fiber', { trunk_id: t.id })}>Repair / splice</button>
            ) : (
              <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('cut_fiber', { trunk_id: t.id })}>Cut fiber</button>
            )}
          </div>
        </div>
      ))}
      <div className="dc-drawer-label mt-2">Patch panels</div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {(opt.patch_panels || []).map((p) => (
          <span key={p.id} className="dc-topology-chip">{p.id}: {p.populated}/{p.ports} {p.media}</span>
        ))}
      </div>
    </div>
  )
}

/** Capacity planning + predictive maintenance */
export function CapacityPdmPanel({ capacity, predictive, busy, onRefresh }) {
  const cap = capacity || {}
  const pdm = predictive || {}
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><ClipboardList size={13} /> Capacity & predictive</span>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={onRefresh}>Refresh</button>
      </div>
      <div className="dc-facility-metrics">
        <div className="dc-facility-metric"><span>Space</span><strong>{cap.space?.pct ?? '—'}%</strong><div className="dc-muted">{cap.space?.used_u}/{cap.space?.total_u} U</div></div>
        <div className="dc-facility-metric"><span>Power</span><strong>{cap.power?.pct ?? '—'}%</strong><div className="dc-muted">{cap.power?.it_kw}/{cap.power?.capacity_kw} kW</div></div>
        <div className="dc-facility-metric"><span>Cooling</span><strong>{cap.cooling?.pct ?? '—'}%</strong><div className="dc-muted">{cap.cooling?.load_kw}/{cap.cooling?.capacity_kw} kW</div></div>
        <div className="dc-facility-metric dc-facility-pue"><span>PUE</span><strong>{cap.pue ?? '—'}</strong></div>
      </div>
      {(cap.bottlenecks || []).length > 0 && (
        <>
          <div className="dc-drawer-label mt-2">Bottlenecks</div>
          {(cap.bottlenecks || []).map((b, i) => (
            <div key={i} className="dc-alert-row">{b.resource} {b.pct}% — {b.note}</div>
          ))}
        </>
      )}
      <div className="dc-drawer-label mt-2">6-month forecast</div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {(cap.forecast_6m || []).map((f) => (
          <span key={f.month} className="dc-topology-chip">M{f.month}: S{f.space_pct}% P{f.power_pct}% C{f.cooling_pct}%</span>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">Predictive · high {pdm.high_risk_count || 0} · med {pdm.medium_risk_count || 0}</div>
      {(pdm.items || []).slice(0, 8).map((it, i) => (
        <div key={i} className={`dc-muted ${it.risk === 'high' ? 'dc-text-bad' : ''}`}>
          [{it.risk}] {it.asset} · {it.part} · {it.metric}={it.value} — {it.recommendation}
        </div>
      ))}
    </div>
  )
}


/** Disaster recovery / ATS / generator */
export function DrFailoverPanel({ dr, powerChain, busy, onOp }) {
  const d = dr || {}
  const pc = powerChain || {}
  const gen = pc.generator || {}
  const ats = pc.ats || {}
  const util = pc.utility || {}
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><AlertTriangle size={13} /> DR / Failover · {d.mode || '—'}</span>
        <span className="dc-muted">RTO {d.rto_min}m · RPO {d.rpo_min}m</span>
      </div>
      <div className="dc-hw-meta">
        <div><span className="dc-hw-k">Utility</span> {util.status} · {util.voltage_v || '—'}V</div>
        <div><span className="dc-hw-k">ATS</span> {ats.status} · transfer {ats.transfer_time_ms}ms</div>
        <div><span className="dc-hw-k">Generator</span> {gen.status} · fuel {gen.fuel_pct}% · {gen.runtime_hours}h</div>
      </div>
      <div className="dc-action-row mt-1" style={{ flexWrap: 'wrap' }}>
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('utility_fail')}>Utility fail</button>
        <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('start_generator')}>Start generator</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('stop_generator')}>Stop gen</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('restore_utility')}>Restore utility</button>
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('site_failover')}>Site failover</button>
        <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('site_failback')}>Failback</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('run_drill')}>DR drill</button>
      </div>
      <div className="dc-drawer-label mt-2">Sites</div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {(d.sites || []).map((s) => (
          <span key={s.id} className="dc-topology-chip">{s.id}: {s.role}/{s.status}</span>
        ))}
      </div>
      <div className="dc-drawer-label mt-2">Runbook</div>
      {(d.runbook_steps || []).map((step) => {
        const done = (d.completed_steps || []).includes(step)
        return (
          <button key={step} type="button" disabled={busy}
            className={`dc-btn-xs ${done ? 'dc-btn-primary' : 'dc-btn-outline'}`}
            style={{ display: 'block', marginBottom: 4, textAlign: 'left', width: '100%' }}
            onClick={() => onOp?.('complete_step', { step })}>
            {done ? '✓ ' : ''}{step}
          </button>
        )
      })}
      {(d.events || []).slice(0, 3).map((e, i) => (
        <div key={i} className="dc-muted">{e.time} · {e.message}</div>
      ))}
    </div>
  )
}

/** Security gate / badges / SOC */
export function AccessControlPanel({ access, busy, onOp }) {
  const a = access || {}
  if (!a.gate) return <p className="dc-muted">No access control.</p>
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><ShieldCheck size={13} /> Access / Security</span>
        <span className={a.gate?.status === 'secured' ? 'dc-text-ok' : 'dc-text-bad'}>{a.gate?.status}</span>
      </div>
      <div className="dc-hw-meta">
        <div><span className="dc-hw-k">Gate</span> barrier {a.gate?.vehicle_barrier}{a.gate?.tailgate_alarm ? ' · TAILGATE' : ''}</div>
        <div><span className="dc-hw-k">Biometrics</span> {a.biometrics?.status} · {a.biometrics?.readers} readers · fails {a.biometrics?.failed_scans_24h}</div>
        <div><span className="dc-hw-k">Cameras</span> {a.cameras?.online}/{a.cameras?.total} · recording {a.cameras?.recording ? 'yes' : 'no'}</div>
        <div><span className="dc-hw-k">Mantrap</span> {a.mantrap?.status}{a.mantrap?.occupied ? ' · occupied' : ''}</div>
      </div>
      <div className="dc-action-row mt-1" style={{ flexWrap: 'wrap' }}>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('open_gate')}>Open gate</button>
        <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs" onClick={() => onOp?.('secure_gate')}>Secure gate</button>
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('tailgate_alarm')}>Tailgate</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('clear_alarms')}>Clear alarms</button>
        <button type="button" disabled={busy} className="dc-btn-danger dc-btn-xs" onClick={() => onOp?.('biometric_fail')}>Bio fail</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('biometric_ok')}>Bio OK</button>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={() => onOp?.('camera_offline')}>Cam offline</button>
      </div>
      <div className="dc-drawer-label mt-2">Badge-in</div>
      <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
        {(a.badges || []).map((b) => (
          <button key={b.id} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
            onClick={() => onOp?.('badge_in', { badge_id: b.id, zone: 'data-hall-a' })}
            title={(b.zones || []).join(', ')}>
            {b.holder} → hall
          </button>
        ))}
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
          onClick={() => onOp?.('badge_in', { badge_id: 'BADGE-3003', zone: 'data-hall-a' })}>
            Visitor → hall (expect deny)
        </button>
      </div>
      {(a.active_alarms || []).slice(0, 4).map((al, i) => (
        <div key={i} className="dc-alert-row">[{al.severity}] {al.message}</div>
      ))}
      <div className="dc-drawer-label mt-2">Events</div>
      {(a.events || []).slice(0, 5).map((e, i) => (
        <div key={i} className="dc-muted">{e.time} · {e.type} · {e.message}</div>
      ))}
    </div>
  )
}

/** Automation runbooks + ops report */
export function AutomationReportPanel({ automation, opsReport, busy, onRun, onReport }) {
  const auto = automation || {}
  const report = opsReport || {}
  const sum = report.summary || {}
  return (
    <div className="dc-twin-panel">
      <div className="dc-twin-toolbar">
        <span className="dc-twin-title"><Boxes size={13} /> Automation · {auto.engine || 'Runbooks'}</span>
        <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs" onClick={onReport}>Generate report</button>
      </div>
      <div className="dc-drawer-label">Catalog</div>
      {(auto.catalog || []).map((rb) => (
        <div key={rb.id} className="dc-vd-card">
          <div className="dc-vd-head">
            <strong>{rb.name}</strong>
            <button type="button" disabled={busy} className="dc-btn-primary dc-btn-xs"
              onClick={() => onRun?.(rb.id)}>Run</button>
          </div>
          <div className="dc-muted">{(rb.steps || []).join(' → ')}</div>
        </div>
      ))}
      <div className="dc-drawer-label mt-2">Recent jobs</div>
      {(auto.jobs || []).slice(0, 4).map((j) => (
        <div key={j.id} className="dc-muted">{j.id} · {j.name} · {j.status} · {j.finished}</div>
      ))}
      {report.generated_at && (
        <>
          <div className="dc-drawer-label mt-2">Ops report · {report.generated_at}</div>
          <div className="dc-facility-metrics">
            <div className="dc-facility-metric"><span>Servers</span><strong>{sum.healthy_servers}/{sum.servers}</strong></div>
            <div className="dc-facility-metric"><span>Tickets</span><strong>{sum.open_tickets}</strong></div>
            <div className="dc-facility-metric"><span>PUE</span><strong>{sum.pue ?? '—'}</strong></div>
            <div className="dc-facility-metric"><span>IT kW</span><strong>{sum.it_kw ?? '—'}</strong></div>
          </div>
          <div className="dc-drawer-label mt-1">Recommendations</div>
          {(report.recommendations || []).map((r, i) => (
            <div key={i} className="dc-muted">• {r}</div>
          ))}
        </>
      )}
    </div>
  )
}
