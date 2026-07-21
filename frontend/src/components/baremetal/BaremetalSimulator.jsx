import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { baremetalApi } from '../../api/baremetal'
import toast from 'react-hot-toast'
import {
  LogIn, Play, Square, Server, Box, Cpu,
  AlertTriangle, Network, RefreshCw, Power, ChevronLeft,
  HardDrive, Cable, Terminal, Rocket, Plus,
} from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { simPanelRoot } from '../../utils/simLayout'

const ACCENT = '#0d9488'

const TABS = [
  { key: 'maas', label: 'MAAS', icon: Server },
  { key: 'spaces', label: 'Spaces & Tags', icon: Cable },
  { key: 'lxd', label: 'LXD', icon: Box },
  { key: 'kvm', label: 'KVM', icon: Cpu },
  { key: 'ipmi', label: 'IPMI', icon: Network },
]

// Machine states that are still advancing on wall-clock — while any machine is
// in one of these, we keep polling so the UI reflects backend progress.
const TRANSIENT = new Set(['Commissioning', 'Deploying'])

const STATUS_STYLE = {
  New: 'bg-slate-100 text-slate-600 border-slate-200',
  Commissioning: 'bg-blue-50 text-blue-700 border-blue-200',
  Ready: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  Allocated: 'bg-teal-50 text-teal-700 border-teal-200',
  Deploying: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  Deployed: 'bg-green-50 text-green-700 border-green-200',
  Failed: 'bg-red-50 text-red-700 border-red-200',
}

function StatusBadge({ status }) {
  const cls = STATUS_STYLE[status] || 'bg-slate-100 text-slate-600 border-slate-200'
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cls}`}>{status}</span>
  )
}

function ProgressBar({ pct, label }) {
  const v = Math.max(0, Math.min(100, Number(pct) || 0))
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-slate-500 mb-1">
        <span>{label}</span><span>{v}%</span>
      </div>
      <div className="h-2 rounded bg-slate-200 overflow-hidden">
        <div className="h-full rounded transition-all duration-500" style={{ width: `${v}%`, background: ACCENT }} />
      </div>
    </div>
  )
}

export default function BaremetalSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
}) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('maas')
  const [busy, setBusy] = useState(false)
  const [detailId, setDetailId] = useState(null)
  const slug = scenario?.slug || ''
  const pollRef = useRef(null)

  const refresh = useCallback(async () => {
    const data = await baremetalApi.getState(sessionId, slug)
    setState(data)
    setLoading(false)
  }, [sessionId, slug])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    const s = (slug || '').toLowerCase()
    if (s.includes('lxd') || s.includes('lxc')) setTab('lxd')
    else if (s.includes('kvm') || s.includes('virsh')) setTab('kvm')
    else if (s.includes('pxe') || s.includes('ipmi')) setTab('ipmi')
    else if (s.includes('maas')) setTab('maas')
  }, [slug])

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}
  const machines = useMemo(() => st.maas?.machines || [], [st.maas])
  const anyTransient = useMemo(
    () => machines.some((m) => TRANSIENT.has(m.status)),
    [machines],
  )

  // Poll while a machine is mid-commission/deploy so wall-clock progress shows.
  useEffect(() => {
    if (!loggedIn || !anyTransient) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      return undefined
    }
    if (pollRef.current) return undefined
    pollRef.current = setInterval(() => { refresh() }, 3000)
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }
  }, [loggedIn, anyTransient, refresh])

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const run = async (fn, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await fn()
      if (res?.ok === false) toast.error(res.error || 'Action failed')
      else if (okMsg) toast.success(res?.message || okMsg)
      if (res?.state) setState(res.state)
      else await refresh()
    } finally { setBusy(false) }
  }

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? undefined : onExit,
    hintsLabel, checkDisabled, extendDisabled,
  }

  if (!loading && state && !loggedIn) {
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0f172a]')}>
        <LabChromeBar title="Bare Metal Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold" style={{ background: ACCENT }}>Bare Metal Console</div>
            <div className="p-6 space-y-3">
              <p className="text-sm text-slate-600">MAAS · LXD · KVM training environment</p>
              <button onClick={() => run(() => baremetalApi.login(sessionId), 'Signed in')} disabled={busy}
                className="w-full py-2 rounded text-white font-medium flex items-center justify-center gap-2" style={{ background: ACCENT }}>
                <LogIn size={16} /> Sign In
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const detailMachine = detailId != null ? machines.find((m) => m.id === detailId) : null

  return (
    <div className={simPanelRoot(embedded, 'bm-shell sim-product')}>
      <LabChromeBar title="Bare Metal · MAAS / LXD / KVM" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />

      {goal.objective && (
        <div className="px-4 py-2 text-sm bg-amber-50 border-b border-amber-200 flex items-center gap-2">
          <AlertTriangle size={14} className="text-amber-600 shrink-0" />
          <span><strong>{goal.title}:</strong> {goal.objective}</span>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <nav className="bm-sidebar shrink-0 py-2">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => { setTab(key); setDetailId(null) }}
              className={`bm-sidebar-item ${tab === key ? 'bm-sidebar-active' : ''}`}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </nav>
        <main className="flex-1 overflow-auto p-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {[
              ['Machines', machines.length],
              ['Containers', (st.lxd?.containers || []).length],
              ['VMs', (st.kvm?.vms || []).length],
              ['BMC', (st.ipmi?.bmc_hosts || []).length],
            ].map(([label, val]) => (
              <div key={label} className="bm-kpi">
                <div className="text-xs text-slate-500 uppercase tracking-wide">{label}</div>
                <div className="bm-kpi-val text-teal-700">{val}</div>
              </div>
            ))}
          </div>

          {tab === 'maas' && detailMachine && (
            <NodeDetail
              machine={detailMachine}
              busy={busy}
              onBack={() => setDetailId(null)}
              onCommission={() => run(() => baremetalApi.action(sessionId, 'maas_commission', { machine_id: detailMachine.id }), 'Commissioning started')}
              onDeploy={() => run(() => baremetalApi.action(sessionId, 'maas_deploy', { machine_id: detailMachine.id }), 'Deploy started')}
              onPower={(power) => run(() => baremetalApi.action(sessionId, 'maas_power', { machine_id: detailMachine.id, power }), 'Power toggled')}
            />
          )}

          {tab === 'maas' && !detailMachine && (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <h2 className="text-lg font-semibold">MAAS Machines</h2>
                <div className="flex items-center gap-2">
                  <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'maas_enlist', {}), 'Machine enlisted via PXE')}
                    className="text-xs flex items-center gap-1 border px-2 py-1 rounded bg-white"><Rocket size={12} /> Enlist (PXE)</button>
                  <button onClick={refresh} className="text-xs flex items-center gap-1 border px-2 py-1 rounded bg-white"><RefreshCw size={12} /> Refresh</button>
                </div>
              </div>
              {machines.map((m) => (
                <div key={m.id} className="bm-card p-3">
                  <div className="flex items-center justify-between gap-3">
                    <button className="text-left" onClick={() => setDetailId(m.id)}>
                      <div className="font-medium flex items-center gap-2">
                        {m.hostname} <StatusBadge status={m.status} />
                      </div>
                      <div className="text-xs text-slate-500">{m.ip || 'no IP'} · power {m.power} · {m.arch || 'amd64'}{(m.tags || []).length ? ` · ${(m.tags || []).join(', ')}` : ''}</div>
                    </button>
                    <div className="flex gap-2 items-center">
                      {(m.status === 'Failed' || m.status === 'New') && (
                        <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'maas_commission', { machine_id: m.id }), 'Commissioning started')}
                          className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Commission</button>
                      )}
                      {(m.status === 'Ready' || m.status === 'Allocated') && (
                        <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'maas_deploy', { machine_id: m.id }), 'Deploy started')}
                          className="px-3 py-1.5 rounded border text-sm flex items-center gap-1"><Rocket size={13} /> Deploy</button>
                      )}
                      <button disabled={busy} onClick={() => run(() => baremetalApi.tagMachine(sessionId, m.hostname, 'lab'), 'Tagged')}
                        className="text-xs border px-2 py-1.5 rounded bg-white">+ Tag</button>
                      <button onClick={() => setDetailId(m.id)} className="text-xs border px-2 py-1.5 rounded bg-white">Details</button>
                    </div>
                  </div>
                  {TRANSIENT.has(m.status) && (
                    <ProgressBar pct={m.progress} label={m.status === 'Commissioning' ? 'Commissioning' : 'Deploying'} />
                  )}
                </div>
              ))}
            </div>
          )}

          {tab === 'spaces' && (
            <div className="space-y-5">
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <h2 className="text-lg font-semibold">Spaces</h2>
                  <button disabled={busy} onClick={() => run(() => baremetalApi.createSpace(sessionId, `space-${Date.now().toString(36).slice(-3)}`), 'Space created')}
                    className="text-xs flex items-center gap-1 border px-2 py-1 rounded bg-white"><Plus size={12} /> Create space</button>
                </div>
                {(st.maas?.spaces || []).map((s) => (
                  <div key={s.id || s.name} className="bm-card p-3 flex justify-between items-center gap-3">
                    <div>
                      <div className="font-medium">{s.name}</div>
                      <div className="text-xs text-slate-500">{(s.subnets || []).join(', ')}</div>
                    </div>
                    <button disabled={busy} onClick={() => run(() => baremetalApi.addSubnet(sessionId, s.name, `10.${40 + (s.subnets || []).length}.0.0/24`), 'Subnet added')}
                      className="text-xs border px-2 py-1 rounded bg-white">+ Subnet</button>
                  </div>
                ))}
              </div>
              <div className="space-y-3">
                <h2 className="text-lg font-semibold">Tags</h2>
                {(st.maas?.tags || []).map((t) => (
                  <div key={t.name} className="bm-card p-3">
                    <div className="font-medium">{t.name}</div>
                    <div className="text-xs text-slate-500">{(t.machines || []).join(', ') || 'No machines'}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <h2 className="text-lg font-semibold">Commissioning scripts</h2>
                  <button disabled={busy} onClick={() => run(() => baremetalApi.attachScript(sessionId, `fixitlab-check-${Date.now().toString(36).slice(-3)}`, ['*']), 'Script attached')}
                    className="text-xs flex items-center gap-1 border px-2 py-1 rounded bg-white"><Plus size={12} /> Attach script</button>
                </div>
                {(st.maas?.commissioning_scripts || []).map((s) => (
                  <div key={s.name} className="bm-card p-3">
                    <div className="font-medium font-mono text-sm">{s.name}</div>
                    <div className="text-xs text-slate-500">{s.type} · applied to {(s.applied_to || []).join(', ')}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'lxd' && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">LXD Containers</h2>
              {(st.lxd?.containers || []).map((c) => (
                <div key={c.name} className="bm-card p-3 flex justify-between items-center">
                  <div><div className="font-medium">{c.name}</div><div className="text-xs text-slate-500">{c.image} · {c.ipv4 || '—'} · {c.status}</div></div>
                  {c.status === 'Running' ? (
                    <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'lxd_stop', { name: c.name }), 'Stopped')}
                      className="px-3 py-1.5 rounded border text-sm flex items-center gap-1 text-red-600 border-red-200">
                      <Square size={13} /> Stop
                    </button>
                  ) : (
                    <button disabled={busy} onClick={() => run(() => baremetalApi.startLxd(sessionId, c.name), 'Started')}
                      className="px-3 py-1.5 rounded text-white text-sm flex items-center gap-1" style={{ background: ACCENT }}>
                      <Play size={14} /> Start
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {tab === 'kvm' && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">KVM Virtual Machines</h2>
              {(st.kvm?.vms || []).map((v) => (
                <div key={v.name} className="bm-card p-3 flex justify-between items-center">
                  <div><div className="font-medium">{v.name}</div><div className="text-xs text-slate-500">{v.vcpu} vCPU · {v.ram_gb} GB · {v.ip || '—'} · {v.state}</div></div>
                  {v.state === 'running' ? (
                    <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'kvm_stop', { name: v.name }), 'Stopped')}
                      className="px-3 py-1.5 rounded border text-sm flex items-center gap-1 text-red-600 border-red-200">
                      <Square size={13} /> Stop
                    </button>
                  ) : (
                    <button disabled={busy} onClick={() => run(() => baremetalApi.startKvm(sessionId, v.name), 'Started')}
                      className="px-3 py-1.5 rounded text-white text-sm flex items-center gap-1" style={{ background: ACCENT }}>
                      <Play size={14} /> Start
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {tab === 'ipmi' && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">IPMI / BMC</h2>
              {(st.ipmi?.bmc_hosts || []).map((b) => {
                const mach = machines.find((m) => m.hostname === b.name)
                const mid = mach?.id
                return (
                <div key={b.name} className="bm-card p-3 flex justify-between items-center gap-3 flex-wrap">
                  <span className="font-mono">{b.name}</span>
                  <span className={b.reachable ? 'text-green-600' : 'text-red-600'}>{b.reachable ? 'reachable' : 'unreachable'}</span>
                  <span className="text-xs text-slate-500">chassis power: {mach?.power ?? b.power ?? 'unknown'}</span>
                  {mid != null && b.reachable && (
                    <div className="flex gap-1.5 ml-auto">
                      <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'ipmi_power', { machine_id: mid, verb: 'on' }), 'Power on')}
                        className="px-2 py-1 rounded border text-xs flex items-center gap-1"><Power size={12} /> On</button>
                      <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'ipmi_power', { machine_id: mid, verb: 'off' }), 'Power off')}
                        className="px-2 py-1 rounded border text-xs flex items-center gap-1 text-red-600 border-red-200"><Power size={12} /> Off</button>
                      <button disabled={busy} onClick={() => run(() => baremetalApi.action(sessionId, 'ipmi_power', { machine_id: mid, verb: 'cycle' }), 'Power cycle')}
                        className="px-2 py-1 rounded border text-xs flex items-center gap-1"><RefreshCw size={12} /> Cycle</button>
                    </div>
                  )}
                </div>
              )})}
              {broken.bmc_unreachable && (
                <button disabled={busy} onClick={() => run(() => baremetalApi.ipmiPowerOn(sessionId), 'BMC online')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>IPMI power on / restore BMC</button>
              )}
              {broken.pxe_vlan_wrong && (
                <button disabled={busy} onClick={() => run(() => baremetalApi.fixPxeVlan(sessionId), 'PXE fixed')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Fix PXE VLAN</button>
              )}
              {broken.thermal_alert && (
                <button disabled={busy} onClick={() => run(() => baremetalApi.clearThermal(sessionId), 'Thermal cleared')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Clear thermal alert</button>
              )}
              {broken.commission_stuck && (
                <button disabled={busy} onClick={() => run(() => baremetalApi.resetCommission(sessionId, broken.commission_stuck), 'Commission reset')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Reset stuck commission</button>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

function NodeDetail({ machine, busy, onBack, onCommission, onDeploy, onPower }) {
  const m = machine
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="text-sm flex items-center gap-1 text-slate-600 hover:text-slate-900">
          <ChevronLeft size={16} /> Back to machines
        </button>
        <div className="flex gap-2">
          {(m.status === 'Failed' || m.status === 'New') && (
            <button disabled={busy} onClick={onCommission}
              className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Commission</button>
          )}
          {(m.status === 'Ready' || m.status === 'Allocated') && (
            <button disabled={busy} onClick={onDeploy}
              className="px-3 py-1.5 rounded border text-sm flex items-center gap-1"><Rocket size={13} /> Deploy</button>
          )}
          <button disabled={busy} onClick={() => onPower(m.power === 'on' ? 'off' : 'on')}
            className="px-3 py-1.5 rounded border text-sm flex items-center gap-1">
            <Power size={13} /> Power {m.power === 'on' ? 'off' : 'on'}
          </button>
        </div>
      </div>

      <div className="bm-card p-4">
        <div className="flex items-center gap-3">
          <Server size={22} className="text-teal-700" />
          <div>
            <div className="text-lg font-semibold flex items-center gap-2">{m.hostname} <StatusBadge status={m.status} /></div>
            <div className="text-xs text-slate-500">{m.arch || 'amd64/generic'} · {m.cpu_count || '—'} cores · {m.ram_gb || '—'} GB RAM · power {m.power}</div>
          </div>
        </div>
        {TRANSIENT.has(m.status) && (
          <ProgressBar pct={m.progress} label={m.status === 'Commissioning' ? 'Commissioning' : 'Deploying'} />
        )}
        {m.os && <div className="text-xs text-slate-500 mt-2">OS: {m.os} · IP {m.ip || '—'}</div>}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bm-card">
          <div className="bm-card-head flex items-center gap-2"><Cable size={14} /> Interfaces</div>
          <div className="p-3 space-y-2">
            {(m.interfaces || []).map((iface) => (
              <div key={iface.name} className="flex justify-between text-sm">
                <span className="font-mono">{iface.name}</span>
                <span className="text-slate-500 font-mono text-xs">{iface.mac}</span>
                <span className="text-xs">vlan {iface.vlan}</span>
                <span className={iface.link === 'up' ? 'text-green-600 text-xs' : 'text-slate-400 text-xs'}>{iface.link}</span>
              </div>
            ))}
            {(m.interfaces || []).length === 0 && <div className="text-xs text-slate-400">No interfaces discovered.</div>}
          </div>
        </div>

        <div className="bm-card">
          <div className="bm-card-head flex items-center gap-2"><HardDrive size={14} /> Storage</div>
          <div className="p-3 space-y-2">
            {(m.storage || []).map((d) => (
              <div key={d.name} className="flex justify-between text-sm">
                <span className="font-mono">{d.name}</span>
                <span className="text-xs">{d.size_gb} GB {d.type}</span>
                <span className="text-xs text-slate-500">{d.role}</span>
              </div>
            ))}
            {(m.storage || []).length === 0 && <div className="text-xs text-slate-400">No storage discovered.</div>}
          </div>
        </div>
      </div>

      <div className="bm-card">
        <div className="bm-card-head flex items-center gap-2"><Terminal size={14} /> Commissioning / boot log</div>
        <div className="p-3 bg-slate-900 text-slate-100 font-mono text-xs rounded-b max-h-64 overflow-auto">
          {(m.log || []).length === 0 && <div className="text-slate-500">No log output yet.</div>}
          {(m.log || []).map((e, i) => (
            <div key={`${e.time}-${i}`}><span className="text-slate-500">{e.time}</span> {e.message}</div>
          ))}
        </div>
      </div>
    </div>
  )
}
