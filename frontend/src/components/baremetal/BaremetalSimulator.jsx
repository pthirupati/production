import { useCallback, useEffect, useState } from 'react'
import { baremetalApi } from '../../api/baremetal'
import toast from 'react-hot-toast'
import {
  LogIn, Play, Server, Box, Cpu,
  AlertTriangle, Network, RefreshCw,
} from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { simPanelRoot } from '../../utils/simLayout'

const ACCENT = '#0d9488'

const TABS = [
  { key: 'maas', label: 'MAAS', icon: Server },
  { key: 'lxd', label: 'LXD', icon: Box },
  { key: 'kvm', label: 'KVM', icon: Cpu },
  { key: 'ipmi', label: 'IPMI', icon: Network },
]

export default function BaremetalSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
}) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('maas')
  const [busy, setBusy] = useState(false)
  const slug = scenario?.slug || ''

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

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}

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
            <button key={key} onClick={() => setTab(key)}
              className={`bm-sidebar-item ${tab === key ? 'bm-sidebar-active' : ''}`}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </nav>
        <main className="flex-1 overflow-auto p-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {[
              ['Machines', (st.maas?.machines || []).length],
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
          {tab === 'maas' && (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <h2 className="text-lg font-semibold">MAAS Machines</h2>
                <button onClick={refresh} className="text-xs flex items-center gap-1 border px-2 py-1 rounded bg-white"><RefreshCw size={12} /> Refresh</button>
              </div>
              {(st.maas?.machines || []).map((m) => (
                <div key={m.id} className="bm-card p-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{m.hostname}</div>
                    <div className="text-xs text-slate-500">{m.status} · {m.ip || 'no IP'} · power {m.power}</div>
                  </div>
                  <div className="flex gap-2">
                    {m.status === 'Failed commissioning' && (
                      <button onClick={() => run(() => baremetalApi.commission(sessionId, m.id), 'Commissioned')}
                        className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Commission</button>
                    )}
                    {m.status === 'Ready' && (
                      <button onClick={() => run(() => baremetalApi.deploy(sessionId, m.id), 'Deployed')}
                        className="px-3 py-1.5 rounded border text-sm">Deploy</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {tab === 'lxd' && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">LXD Containers</h2>
              {(st.lxd?.containers || []).map((c) => (
                <div key={c.name} className="bm-card p-3 flex justify-between items-center">
                  <div><div className="font-medium">{c.name}</div><div className="text-xs text-slate-500">{c.image} · {c.ipv4 || '—'}</div></div>
                  {c.status !== 'Running' ? (
                    <button onClick={() => run(() => baremetalApi.startLxd(sessionId, c.name), 'Started')}
                      className="px-3 py-1.5 rounded text-white text-sm flex items-center gap-1" style={{ background: ACCENT }}>
                      <Play size={14} /> Start
                    </button>
                  ) : <span className="text-green-600 text-sm">{c.status}</span>}
                </div>
              ))}
            </div>
          )}
          {tab === 'kvm' && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">KVM Virtual Machines</h2>
              {(st.kvm?.vms || []).map((v) => (
                <div key={v.name} className="bm-card p-3 flex justify-between items-center">
                  <div><div className="font-medium">{v.name}</div><div className="text-xs text-slate-500">{v.vcpu} vCPU · {v.ram_gb} GB · {v.ip || '—'}</div></div>
                  {v.state !== 'running' ? (
                    <button onClick={() => run(() => baremetalApi.startKvm(sessionId, v.name), 'Started')}
                      className="px-3 py-1.5 rounded text-white text-sm flex items-center gap-1" style={{ background: ACCENT }}>
                      <Play size={14} /> Start
                    </button>
                  ) : <span className="text-green-600 text-sm">running</span>}
                </div>
              ))}
            </div>
          )}
          {tab === 'ipmi' && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">IPMI / BMC</h2>
              {(st.ipmi?.bmc_hosts || []).map((b) => (
                <div key={b.name} className="bm-card p-3 flex justify-between items-center gap-3">
                  <span>{b.name}</span>
                  <span className={b.reachable ? 'text-green-600' : 'text-red-600'}>{b.reachable ? 'reachable' : 'unreachable'}</span>
                </div>
              ))}
              {broken.bmc_unreachable && (
                <button onClick={() => run(() => baremetalApi.ipmiPowerOn(sessionId), 'BMC online')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>IPMI power on / restore BMC</button>
              )}
              {broken.pxe_vlan_wrong && (
                <button onClick={() => run(() => baremetalApi.fixPxeVlan(sessionId), 'PXE fixed')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Fix PXE VLAN</button>
              )}
              {broken.thermal_alert && (
                <button onClick={() => run(() => baremetalApi.clearThermal(sessionId), 'Thermal cleared')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Clear thermal alert</button>
              )}
              {broken.commission_stuck && (
                <button onClick={() => run(() => baremetalApi.resetCommission(sessionId, broken.commission_stuck), 'Commission reset')}
                  className="px-3 py-1.5 rounded text-white text-sm" style={{ background: ACCENT }}>Reset stuck commission</button>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
