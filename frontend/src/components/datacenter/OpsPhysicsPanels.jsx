import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Boxes, ClipboardList, Cpu, Gauge, Ticket } from 'lucide-react'

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
export function RackPhysicsFruPanel({ rack, busy, onToggleCasters, onBlanking, onOutlet }) {
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
            <div><span className="dc-hw-k">QR</span> {fru.qr_code}</div>
            <div><span className="dc-hw-k">Warranty</span> {fru.warranty_sticker?.vendor} exp {fru.warranty_sticker?.expires}</div>
            <div><span className="dc-hw-k">Rails</span> {fru.rails?.front?.type} · {fru.rails?.screws} screws · {fru.cage_nuts_installed} cage nuts · {fru.washers} washers</div>
            <div><span className="dc-hw-k">Ground</span> {fru.grounding_strap?.status} @ {fru.grounding_strap?.torque_nm} N·m</div>
            <div><span className="dc-hw-k">Blanking</span> {(fru.blanking_panels || []).filter((p) => p.installed).length} panels · ties {fru.cable_ties} · velcro {fru.velcro_straps}</div>
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
